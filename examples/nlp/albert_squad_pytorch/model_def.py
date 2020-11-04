from typing import Dict, Sequence, Union
import torch
import torch.nn as nn
import time

from determined.pytorch import DataLoader, PyTorchTrial, PyTorchTrialContext, LRScheduler
import data
import constants

from transformers import (
    AdamW,
    get_linear_schedule_with_warmup,
)
from transformers.data.processors.squad import SquadResult
from transformers.data.metrics.squad_metrics import (
    compute_predictions_logits,
    squad_evaluate,
)
from radam import RAdam, PlainRAdam

TorchData = Union[Dict[str, torch.Tensor], Sequence[torch.Tensor], torch.Tensor]

USE_BIND_DIR = True  # TODO: Make this dynamic


class AlbertSQuADPyTorch(PyTorchTrial):
    def __init__(self, context: PyTorchTrialContext):
        self.context = context
        self.download_directory = data.data_directory(USE_BIND_DIR, self.context.distributed.get_rank())
        self.config_class, self.tokenizer_class, self.model_class = constants.MODEL_CLASSES[
            self.context.get_hparam("model_type")
        ]
        self.tokenizer = self.tokenizer_class.from_pretrained(
            self.context.get_data_config().get("pretrained_model_name"),
            do_lower_case=self.context.get_hparam("do_lower_case"),
            cache_dir=None
        )

        cache_dir_per_rank = data.cache_dir(USE_BIND_DIR, self.context.distributed.get_rank())

        config = self.config_class.from_pretrained(
            self.context.get_data_config().get("pretrained_model_name"),
            cache_dir=cache_dir_per_rank,
        )
        self.model = self.context.wrap_model(self.model_class.from_pretrained(
            self.context.get_data_config().get("pretrained_model_name"),
            from_tf=bool(".ckpt" in self.context.get_data_config().get("pretrained_model_name")),
            config=config,
            cache_dir=cache_dir_per_rank,
        ))

        no_decay = ["bias", "LayerNorm.weight"]
        optimizer_grouped_parameters = [
            {
                "params": [
                    p for n, p in self.model.named_parameters() if not any(nd in n for nd in no_decay)
                ],
                "weight_decay": self.context.get_hparam("weight_decay"),
            },
            {
                "params": [
                    p for n, p in self.model.named_parameters() if any(nd in n for nd in no_decay)
                ],
                "weight_decay": 0.0,
            },
        ]

        if self.context.get_hparam("use_radam"):
            lr = self.context.get_hparam("learning_rate")
            eps = self.context.get_hparam("adam_epsilon")
            print(f"Using PlainRAdam with params: lr={lr}, ε={eps}")
            optimizer = PlainRAdam(
                optimizer_grouped_parameters,
                lr=lr,
                eps=eps
            )
        else:
            lr = self.context.get_hparam("learning_rate")
            eps = self.context.get_hparam("adam_epsilon")
            print(f"Using AdamW with params: lr={lr}, ε={eps}")
            optimizer = AdamW(
                optimizer_grouped_parameters,
                lr=lr,
                eps=eps,
            )

        self.optimizer = self.context.wrap_optimizer(optimizer)

        self.lr_scheduler = self.context.wrap_lr_scheduler(
            get_linear_schedule_with_warmup(
                self.optimizer,
                num_warmup_steps=self.context.get_hparam("num_warmup_steps"),
                num_training_steps=self.context.get_hparam("num_training_steps"),
            ),
            LRScheduler.StepMode.STEP_EVERY_BATCH
        )


    def build_training_data_loader(self):
        train_dataset, _, _ = data.load_and_cache_examples(
            data_dir=self.download_directory,
            tokenizer=self.tokenizer,
            task=self.context.get_data_config().get("task"),
            max_seq_length=self.context.get_hparam("max_seq_length"),
            doc_stride=self.context.get_hparam("doc_stride"),
            max_query_length=self.context.get_hparam("max_query_length"),
            evaluate=False,
        )
        return DataLoader(train_dataset, batch_size=self.context.get_per_slot_batch_size())

    def build_validation_data_loader(self):
        self.validation_dataset, self.validation_examples, self.validation_features = data.load_and_cache_examples(
            data_dir=self.download_directory,
            tokenizer=self.tokenizer,
            task=self.context.get_data_config().get("task"),
            max_seq_length=self.context.get_hparam("max_seq_length"),
            doc_stride=self.context.get_hparam("doc_stride"),
            max_query_length=self.context.get_hparam("max_query_length"),
            evaluate=True,
            # model_name=self.context.get_data_config().get("pretrained_model_name")
        )

        return DataLoader(
            self.validation_dataset,
            batch_size=self.context.get_per_slot_batch_size(),
        )

    def train_batch(self, batch: TorchData, epoch_idx: int, batch_idx: int):
        inputs = {
            "input_ids": batch[0],
            "attention_mask": batch[1],
            "token_type_ids": batch[2],
            "start_positions": batch[3],
            "end_positions": batch[4],
        }
        outputs = self.model(**inputs)
        loss = outputs[0]

        # if self.context.distributed.get_rank() == 0:
        #     print(f"LR (epoch={epoch_idx}, batch={batch_idx}): ", self.lr_scheduler.get_last_lr())

        self.context.backward(loss)
        self.context.step_optimizer(
            self.optimizer,
            clip_grads=lambda params: torch.nn.utils.clip_grad_norm_(
                params, self.context.get_hparam("max_grad_norm")
            )
        )

        return {"loss": loss, "lr": float(self.lr_scheduler.get_last_lr()[0])}
        # return {"loss": loss}


    def evaluate_full_dataset(self, data_loader: DataLoader):
        def eval_print(s):
            print("[EVALUATE_FULL_DATASET]", f"(rank={self.context.distributed.get_rank()})", s)

        eval_print(f"start={time.time()}")
        all_results = []

        batch_idx = 0
        for batch in data_loader:
            batch_idx += 1
            batch_start = time.time()
            inputs = {
                "input_ids": batch[0].cuda(),
                "attention_mask": batch[1].cuda(),
                "token_type_ids": batch[2].cuda(),
            }
            feature_indices = batch[3]
            outputs = self.model(**inputs)
            for i, feature_index in enumerate(feature_indices):
                eval_feature = self.validation_features[feature_index.item()]
                unique_id = int(eval_feature.unique_id)
                output = [output[i].detach().cpu().tolist() for output in outputs]
                start_logits, end_logits = output
                result = SquadResult(unique_id, start_logits, end_logits)
                all_results.append(result)
            batch_end = time.time()
            eval_print(f"Batch {batch_idx} took {batch_end-batch_start} seconds")

        eval_print(f"squad_results_available={time.time()}")
        output_prediction_file = None
        output_nbest_file = None
        output_null_log_odds_file = None

        task = self.context.get_data_config().get("task")
        if task == "SQuAD1.1":
            version_2_with_negative = False
        elif task == "SQuAD2.0":
            version_2_with_negative = True
        else:
            raise NameError(f"Incompatible dataset '{task}' detected")

        # TODO: Make verbose logging configurable
        verbose_logging = False
        predictions = compute_predictions_logits(
            self.validation_examples,
            self.validation_features,
            all_results,
            self.context.get_hparam("n_best_size"),
            self.context.get_hparam("max_answer_length"),
            self.context.get_hparam("do_lower_case"),
            output_prediction_file,
            output_nbest_file,
            output_null_log_odds_file,
            verbose_logging,
            version_2_with_negative,
            self.context.get_hparam("null_score_diff_threshold"),
            self.tokenizer,
        )
        eval_print(f"prediction_logits_available={time.time()}")
        results = squad_evaluate(self.validation_examples, predictions)
        eval_print(f"end={time.time()}")
        return results

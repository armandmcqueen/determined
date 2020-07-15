import importlib
import logging
import pathlib
from typing import Any, Dict, List, Optional, cast

import determined as det
from determined import constants
from determined._experiment_config import ExperimentConfig
from determined._rendezvous_info import RendezvousInfo
from determined_common import check


class _PolyHorovod:
    """
    Importing two different types of horovod in the same python process (horovod.tensorflow and
    horovod.pytorch, for instance) results in a segfault.

    _PolyHorovod is a wrapper around the horovod module to delay the actual importing of horovod
    until it is known which version is actually needed for the task. The result is that horovod
    importing across Determined becomes simple, easy, and robust.

    After require_horovod_type() is called once, horovod is imported, and _PolyHorovod passes all
    other calls to the real horovod module.
    """

    def __init__(self) -> None:
        self._poly_hvd_type = None  # type: Optional[str]
        self._poly_hvd_first_reason = "(horovod type has not been set)"
        self._poly_hvd_module = None  # type: Any
        self._poly_hvd_imported = False

    def require_horovod_type(self, horovod_type: str, reason: str) -> None:
        """
        Declare the required type of horovod and give a unique reason as to why it is required.

        The reason makes for clear error reporting if require_horovod_type() is called a second
        time but with a different type.
        """

        known_types = {"tensorflow", "tensorflow.keras", "torch"}
        check.is_in(horovod_type, known_types, "Unknown horovod type requested.")

        if self._poly_hvd_type is not None:
            check.eq(
                horovod_type,
                self._poly_hvd_type,
                f"require_horovod_type() called with with type {horovod_type} after a previous "
                f"call with type {self._poly_hvd_type} in the same process. The reason for the "
                f"first call was '{self._poly_hvd_first_reason}'; the reason for this call is "
                f"'{reason}'.",
            )
        else:
            self._poly_hvd_type = horovod_type
            self._poly_hvd_first_reason = reason
            # If horovod has not been imported yet, do it now.
            try:
                self._poly_hvd_module = importlib.import_module(f"horovod.{horovod_type}")
            except ImportError:
                pass

    def __getattr__(self, attr: str) -> Any:
        check.is_not_none(
            self._poly_hvd_type,
            "You must call det.horovod.hvd.require_horovod_type() before any other calls.",
        )
        check.is_not_none(self._poly_hvd_module, "Horovod could not be imported in this process.")
        return getattr(self._poly_hvd_module, attr)


hvd = _PolyHorovod()


def create_hostlist_arg(num_gpus_per_machine: int, ip_addresses: List[str]) -> str:
    trial_runner_hosts = ip_addresses.copy()
    # Horovodrun does not interpret "0.0.0.0" correctly.
    trial_runner_hosts[0] = "localhost"
    return ",".join([f"{host}:{num_gpus_per_machine}" for host in trial_runner_hosts])


def create_network_interface_arg_if_specified(env: det.EnvContext, num_machines: int) -> List[str]:
    if (
        env.det_trial_runner_network_interface
        != constants.AUTO_DETECT_TRIAL_RUNNER_NETWORK_INTERFACE
    ) and num_machines > 1:
        return [
            "--network-interface",
            str(env.det_trial_runner_network_interface),
        ]
    return []


def create_performance_args(env: det.EnvContext) -> List[str]:
    optimizations = env.experiment_config.get("optimizations", {})
    check.check_in("auto_tune_tensor_fusion", optimizations)
    check.check_in("tensor_fusion_threshold", optimizations)
    check.check_in("tensor_fusion_cycle_time", optimizations)

    if optimizations.get("auto_tune_tensor_fusion"):
        performance_args = [
            "--autotune",
            "--autotune-log-file",
            str(constants.HOROVOD_AUTOTUNE_LOG_FILEPATH),
        ]
    else:
        performance_args = [
            "--fusion-threshold-mb",
            str(optimizations.get("tensor_fusion_threshold")),
            "--cycle-time-ms",
            str(optimizations.get("tensor_fusion_cycle_time")),
        ]

    # Prevent horovod from auto-tuning these parameters.
    performance_args.extend(
        [
            "--cache-capacity",
            str(1024),
            "--no-hierarchical-allreduce",
            "--no-hierarchical-allgather",
        ]
    )
    return performance_args


def create_horovod_timeline_args(env: det.EnvContext) -> List[str]:
    optimizations = env.experiment_config.get("optimizations", {})
    check.check_in("horovod_timeline", optimizations)

    htimeline_path = optimizations.get("horovod_timeline")
    if htimeline_path is None:
        return []

    return [
        "--timeline-filename",
        htimeline_path,
        "--timeline-mark-cycles" # This is useful information, but it is strange that it is not
                                 # enabled by default in Horovod so it is possible that
                                 # it has performance implications we are unaware of.
    ]


def create_run_command(
    num_gpus_per_machine: int,
    ip_addresses: List[str],
    env: det.EnvContext,
    debug: bool,
    optional_args: List[str],
    worker_process_env_path: pathlib.Path,
) -> List[str]:
    num_machines = len(ip_addresses)
    num_gpus_total = num_gpus_per_machine * num_machines

    # Construct the horovodrun command.
    horovod_process_cmd = [
        "horovodrun",
        "-np",
        str(num_gpus_total),
        "-p",
        str(constants.HOROVOD_SSH_PORT),
        "-H",
        create_hostlist_arg(num_gpus_per_machine, ip_addresses),
        "--start-timeout",
        str(constants.HOROVOD_STARTUP_TIMEOUT_SECONDS),
        "--gloo-timeout-seconds",
        str(constants.HOROVOD_GLOO_TIMEOUT_SECONDS),
    ]
    horovod_process_cmd.extend(create_network_interface_arg_if_specified(env, num_machines))
    horovod_process_cmd.extend(create_performance_args(env))
    horovod_process_cmd.extend(create_horovod_timeline_args(env))
    if debug:
        horovod_process_cmd.append("--verbose")
    horovod_process_cmd.extend(optional_args)
    horovod_process_cmd += [
        "python",
        "-m",
        "determined.exec.worker_process",
        str(worker_process_env_path),
    ]

    logging.debug(f"Chief worker subprocess launch command: {horovod_process_cmd}.")
    return horovod_process_cmd


class HorovodContext:
    def __init__(
        self,
        use: bool,
        aggregation_frequency: int,
        fp16_compression: bool,
        grad_updates_size_file: str,
        average_aggregated_gradients: bool,
        average_training_metrics: bool,
        horovod_timeline: Optional[str]
    ) -> None:
        self.use = use
        self.aggregation_frequency = aggregation_frequency
        self.fp16_compression = fp16_compression
        self.grad_updates_size_file = grad_updates_size_file
        self.average_aggregated_gradients = average_aggregated_gradients
        self.average_training_metrics = average_training_metrics

        if horovod_timeline == "":
            horovod_timeline = None

        self.horovod_timeline = horovod_timeline

    @staticmethod
    def from_configs(
        experiment_config: ExperimentConfig,
        rendezvous_info: RendezvousInfo,
        hparams: Dict[str, Any],
    ) -> "HorovodContext":
        """
        Create the HorovodContext according to experiment config and rendezvous info for this trial.
        """

        # Horovod is always used for multi-machine distributed training. For
        # single-machine multi-GPU training, Horovod is used when native_parallel is
        # disabled.
        multi_machine_trial = rendezvous_info.get_size() > 1
        multi_slot_trial = experiment_config["resources"]["slots_per_trial"] > 1
        use_horovod = multi_machine_trial or (
            multi_slot_trial and not experiment_config.native_parallel_enabled()
        )

        check.is_in("optimizations", experiment_config)
        optimizations_config = cast(Dict[str, Any], experiment_config.get("optimizations"))

        check.is_in("aggregation_frequency", optimizations_config)
        check.is_in("gradient_compression", optimizations_config)
        check.is_in("average_training_metrics", optimizations_config)
        check.is_in("horovod_timeline", optimizations_config)

        # Help users migrate from the old locations for these settings, in hparams.
        def error_message_removed_from_hparams(removed_hparam: str) -> str:
            return (
                f"Please move `{removed_hparam}` in the experiment config to "
                f"`Optimizations` from `hyperparameters`."
            )

        check.not_in(
            "aggregation_frequency",
            hparams,
            error_message_removed_from_hparams("aggregation_frequency"),
        )
        check.not_in(
            "gradient_compression",
            hparams,
            error_message_removed_from_hparams("gradient_compression"),
        )
        check.not_in(
            "grad_updates_size_file",
            hparams,
            error_message_removed_from_hparams("grad_updates_size_file"),
        )

        hvd_config = HorovodContext(
            use=use_horovod,
            aggregation_frequency=cast(int, optimizations_config.get("aggregation_frequency")),
            fp16_compression=cast(bool, optimizations_config.get("gradient_compression")),
            grad_updates_size_file=optimizations_config.get("grad_updates_size_file", None),
            average_aggregated_gradients=cast(
                bool, optimizations_config.get("average_aggregated_gradients")
            ),
            average_training_metrics=cast(
                bool, optimizations_config.get("average_training_metrics")
            ),
            horovod_timeline=cast(
                Optional[str], optimizations_config.get("horovod_timeline")
            ),
        )

        if hvd_config.use and hvd_config.aggregation_frequency > 1:
            logging.info(
                f"Setting `aggregation_frequency` to {hvd_config.aggregation_frequency} "
                "to optimize training."
            )

        if hvd_config.use and hvd_config.fp16_compression:
            logging.info("Enabling `gradient_compression` to optimize training.")

        return hvd_config

import os
from io import BytesIO

import numpy as np
import torchvision.transforms.functional as transformfn
import boto3
from PIL import Image
from torch.utils.data import Dataset

from determined.util import download_gcs_blob_with_backoff


def load_image(path):
    # Helper function from https://pytorch.org/docs/stable/_modules/torchvision/datasets/folder.html#ImageFolder
    with open(path, "rb") as f:
        img = Image.open(f)
        return img.convert("RGB")


# def list_blobs(storage_client, bucket_name, prefix=None):
#     # Helper functions for GCP from https://cloud.google.com/storage/docs/listing-objects#code-samples
#     """Lists all the blobs in the bucket."""
#     blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
#     return blobs

def list_objects(s3_client, bucket, prefix=None):

    objects = []
    list_obj_params = dict(Bucket=bucket)

    if prefix:
        list_obj_params["Prefix"] = prefix

    paginator = s3_client.get_paginator('list_objects_v2')

    for response in paginator.paginate(**list_obj_params):
        objects += response.get('Contents', [])

    return objects





def create_file_dirs(target_path):
    destination_dir = target_path[0 : target_path.rfind("/")]
    if not os.path.exists(destination_dir):
        try:
            os.makedirs(destination_dir)
        except:
            assert os.path.exists(destination_dir)
            pass


class ImageNetDataset(Dataset):
    def __init__(
        self, split, bucket_name, streaming=True, data_download_dir=None, transform=None
    ):
        """
        Args:
            split: train or validation split to return the right dataset
            directory: root directory for imagenet where "train" and "validation" folders reside
        """
        assert split in [
            "train",
            "validation",
        ], "split {} not in (train, validation)".format(split)
        self._split = split

        # If bucket name is None, we will generate random data.
        self._bucket_name = bucket_name

        self._target_dir = data_download_dir
        self._source_dir = os.path.join("imagenet/imagenet", self._split)
        # self._source_dir = os.path.join("train2014")
        self._transform = transform

        # Streaming always downloads image from GCP regardless of whether it
        # has been downloaded before.
        # When streaming is false, we will save the downloaded image to disk and
        # check whether the image is available before sending a download request
        # to the GCP bucket.
        self._streaming = streaming

        if self._bucket_name is not None:
            self._storage_client = boto3.client('s3')

            # When the dataset is first initialized, we'll loop through to catalogue the classes (subdirectories)
            # This step might take a long time.
            self._imgs_paths = []
            self._labels = []
            self._subdir_to_class = {}
            class_count = 0

            # Get blobs from S3
            blobs = list_objects(
                self._storage_client, self._bucket_name, prefix=self._source_dir
            )

            for b in blobs:
                # print(b)
                path = b["Key"]
                self._imgs_paths.append(path)
                sub_dir = path.split("/")[-2]
                if sub_dir not in self._subdir_to_class:
                    self._subdir_to_class[sub_dir] = class_count
                    class_count += 1
                self._labels.append(self._subdir_to_class[sub_dir])
            self._imgs_paths.sort()
            print("There are {} records in dataset.".format(len(self._imgs_paths)))

    def __len__(self):
        # Return some length if using randomly generated data.
        if self._bucket_name is None:
            return 1024 * 100
        return len(self._imgs_paths)

    def __getitem__(self, idx):
        # print("entering __getitem__")
        # Generate random data if a bucket name is not provided.
        if self._bucket_name is None:
            array = np.random.rand(256, 256, 3)
            img = Image.fromarray(array, mode="RGB")
            return transformfn.to_tensor(img), np.random.choice(1000)

        img_path = self._imgs_paths[idx]
        # blob = self._bucket.blob(img_path)
        if self._streaming:
            # print("Streaming download")
            img_bytes = BytesIO()
            self._storage_client.download_fileobj(Bucket=self._bucket_name, Key=img_path, Fileobj=img_bytes)
        else:
            target_path = os.path.join(self._target_dir, img_path)
            if not os.path.exists(target_path):
                create_file_dirs(target_path)
                # print("downloading...")
                self._storage_client.download_file(Bucket=self._bucket_name, Key=img_path, Filename=target_path)
                # img_str = download_gcs_blob_with_backoff(blob)
                # with open(target_path, "wb") as f:
                #     f.write(img_str)

            with open(target_path, "rb") as f:
                img_str = f.read()
                img_bytes = BytesIO(img_str)
        img = Image.open(img_bytes)
        img = img.convert("RGB")

        if self._transform is not None:
            img = self._transform(img)

        return img, self._labels[idx]


if __name__ == '__main__':
    imagenet_ds = ImageNetDataset(split='train', bucket_name="determined-imagenet-dataset", streaming=False, data_download_dir="./data")
    item, label = imagenet_ds[0]
    print(item)

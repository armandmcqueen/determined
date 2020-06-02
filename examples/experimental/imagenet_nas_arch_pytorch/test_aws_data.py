import random
import time

from data_aws import ImageNetDataset as ImageNetDatasetAWS
from data import ImageNetDataset as ImageNetDatasetGCP

def humanize_float(num): return "{0:,.2f}".format(num)

if __name__ == '__main__':
    gcp_ds = ImageNetDatasetGCP(split='train', bucket_name="determined-ai-datasets", streaming=False, data_download_dir="./data_gcp")
    aws_ds = ImageNetDatasetAWS(split='train', bucket_name="determined-imagenet-dataset", streaming=False, data_download_dir="./data_aws")

    t0 = time.time()
    print("GCP Len", len(gcp_ds))
    t1 = time.time()
    print("GCP Dataset Init Duration", humanize_float(t1-t0), "secs")
    print("AWS Len", len(aws_ds))
    t2 = time.time()
    print("AWS Dataset Init Duration", humanize_float(t2-t1), "secs")


    num = 50
    for i in [random.randint(0,100_000) for i in range(num)]:
        print("-------")
        print("Index", i)

        gcp_item = gcp_ds[i]
        print(gcp_item)
        print(gcp_item[0].tobytes()[:10])

        aws_item = aws_ds[i]
        print(aws_item)
        print(aws_item[0].tobytes()[:10])


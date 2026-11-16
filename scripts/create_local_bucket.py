"""Creates the photo bucket on the local S3 server from compose.yaml (make docker-run). Local use only."""

import time

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

BUCKET = "yearly-photos"

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="yearly-access",
    aws_secret_access_key="yearly-secret-key",
    region_name="us-east-1",
)

for _attempt in range(30):  # the server needs a moment after starting
    try:
        s3.head_bucket(Bucket=BUCKET)
        print(f"bucket {BUCKET} is ready")
        break
    except ClientError:
        s3.create_bucket(Bucket=BUCKET)
        print(f"bucket {BUCKET} created")
        break
    except EndpointConnectionError:
        time.sleep(1)
else:
    raise SystemExit("the local S3 server did not start")

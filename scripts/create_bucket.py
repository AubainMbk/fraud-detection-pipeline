"""
Crée le bucket 'raw' dans MinIO s'il n'existe pas déjà.
Ce bucket va accueillir les données brutes, jamais modifiées après ingestion.
"""
import os

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
)

bucket_name = os.getenv("MINIO_BUCKET_RAW")

try:
    s3_client.head_bucket(Bucket=bucket_name)
    print(f"Le bucket '{bucket_name}' existe déjà.")
except ClientError:
    s3_client.create_bucket(Bucket=bucket_name)
    print(f"Bucket '{bucket_name}' créé avec succès.")

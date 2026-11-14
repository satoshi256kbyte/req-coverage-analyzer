"""E2E テストの共通部品。デプロイ済みのスタックに対して、実際の S3 と Step Functions を使う。

必要な環境変数:
- E2E_BUCKET: スタックの出力 `BucketName`
- E2E_REGION: 省略すると ap-northeast-1
"""

import os
import time
import uuid
from collections.abc import Iterator

import boto3
import pytest


@pytest.fixture(scope="session")
def bucket() -> str:
    name = os.environ.get("E2E_BUCKET")
    if not name:
        pytest.fail("E2E_BUCKET が未設定です。スタックの出力 BucketName を指定してください")
    return name


@pytest.fixture(scope="session")
def s3():
    return boto3.client("s3", region_name=os.environ.get("E2E_REGION", "ap-northeast-1"))


@pytest.fixture
def run_id(s3, bucket: str) -> Iterator[str]:
    """新しい実行フォルダの名前。テストのあと、フォルダの中身を消す。"""
    rid = f"e2e-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    yield rid
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"runs/{rid}/"):
        keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
        if keys:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": keys})

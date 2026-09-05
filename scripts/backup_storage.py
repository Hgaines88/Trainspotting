"""Upload encrypted backup artifacts to private S3-compatible object storage."""

from __future__ import annotations

import json
import os
from pathlib import Path

import boto3
from botocore.config import Config


def storage_client():
    required = {
        "endpoint_url": os.getenv("BACKUP_S3_ENDPOINT"),
        "aws_access_key_id": os.getenv("BACKUP_S3_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("BACKUP_S3_SECRET_ACCESS_KEY"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("Missing backup storage configuration: " + ", ".join(missing))
    return boto3.client(
        "s3",
        **required,
        region_name=os.getenv("BACKUP_S3_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def upload_backup(client, bucket: str, prefix: str, backup: Path) -> dict:
    manifest_path = backup.with_suffix(backup.suffix + ".json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    normalized_prefix = prefix.strip("/")
    object_key = "/".join(part for part in (normalized_prefix, backup.name) if part)
    manifest_key = f"{object_key}.json"
    metadata = {
        "encrypted-sha256": manifest["encrypted_sha256"],
        "format-version": str(manifest["format_version"]),
    }
    client.upload_file(
        str(backup),
        bucket,
        object_key,
        ExtraArgs={"ContentType": "application/octet-stream", "Metadata": metadata},
    )
    client.upload_file(
        str(manifest_path),
        bucket,
        manifest_key,
        ExtraArgs={"ContentType": "application/json"},
    )
    remote = client.head_object(Bucket=bucket, Key=object_key)
    if remote.get("ContentLength") != backup.stat().st_size:
        raise RuntimeError("Remote encrypted backup size verification failed")
    if remote.get("Metadata", {}).get("encrypted-sha256") != manifest["encrypted_sha256"]:
        raise RuntimeError("Remote encrypted backup checksum metadata verification failed")
    return {
        "bucket": bucket,
        "object_key": object_key,
        "manifest_key": manifest_key,
        "encrypted_bytes": remote["ContentLength"],
        "encrypted_sha256": manifest["encrypted_sha256"],
    }

"""MinIO storage adapter for the API service.

Thin wrapper around minio-py for document storage.
"""

import io
import logging
import os

logger = logging.getLogger(__name__)

MINIO_ENDPOINT = os.environ.get("DOCPILOT_MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("DOCPILOT_MINIO_ACCESS_KEY", "docpilot")
MINIO_SECRET_KEY = os.environ.get("DOCPILOT_MINIO_SECRET_KEY", "docpilot123")
MINIO_SECURE = os.environ.get("DOCPILOT_MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET_PREFIX = os.environ.get("DOCPILOT_MINIO_BUCKET_PREFIX", "docpilot-")


def _get_client():
    from minio import Minio

    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def _bucket_name(project_id: str) -> str:
    return f"{MINIO_BUCKET_PREFIX}{project_id[:36].lower()}".replace("_", "-")[:63]


def _ensure_bucket(client, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("Created bucket %s", bucket)


def upload_bytes(project_id: str, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to MinIO, return the storage key (bucket/object_name)."""
    client = _get_client()
    bucket = _bucket_name(project_id)
    _ensure_bucket(client, bucket)

    client.put_object(
        bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return f"{bucket}/{object_name}"


def download_bytes(project_id: str, object_name: str) -> bytes:
    """Download bytes from MinIO."""
    client = _get_client()
    bucket = _bucket_name(project_id)

    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()

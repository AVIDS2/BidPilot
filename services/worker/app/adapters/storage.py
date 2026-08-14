"""MinIO storage adapter for document upload/download.

Provides a thin wrapper around minio-py for storing and retrieving
source documents in a project-scoped bucket layout.
"""

import io
import logging
import os
from os import PathLike
logger = logging.getLogger(__name__)

MINIO_ENDPOINT = os.environ.get("DOCPILOT_MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("DOCPILOT_MINIO_ACCESS_KEY", "docpilot")
MINIO_SECRET_KEY = os.environ.get("DOCPILOT_MINIO_SECRET_KEY", "docpilot123")
MINIO_SECURE = os.environ.get("DOCPILOT_MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET_PREFIX = os.environ.get("DOCPILOT_MINIO_BUCKET_PREFIX", "docpilot-")


def _get_client():
    """Lazily create a MinIO client."""
    from minio import Minio

    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def _bucket_name(project_id: str) -> str:
    """Derive bucket name from project ID."""
    # MinIO bucket names must be 3-63 chars, lowercase
    return f"{MINIO_BUCKET_PREFIX}{project_id[:36].lower()}".replace("_", "-")[:63]


def _ensure_bucket(client, bucket: str) -> None:
    """Create the bucket if it does not exist."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("Created bucket %s", bucket)


def upload_document(project_id: str, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload a document to MinIO and return the object path.

    Returns: ``bucket/object_name`` path for later retrieval.
    """
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
    logger.info("Uploaded %s/%s (%d bytes)", bucket, object_name, len(data))
    return f"{bucket}/{object_name}"


def upload_bytes(project_id: str, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """API-compatible alias used by shared document commands."""
    return upload_document(project_id, object_name, data, content_type)


def upload_file(
    project_id: str,
    object_name: str,
    file_path: str | PathLike[str],
    content_type: str = "application/octet-stream",
) -> str:
    """Upload a local file without first materializing it as bytes."""
    client = _get_client()
    bucket = _bucket_name(project_id)
    _ensure_bucket(client, bucket)
    client.fput_object(bucket, object_name, str(file_path), content_type=content_type)
    logger.info("Uploaded %s/%s from %s", bucket, object_name, file_path)
    return f"{bucket}/{object_name}"


def download_document(project_id: str, object_name: str) -> bytes:
    """Download a document from MinIO and return its bytes."""
    client = _get_client()
    bucket = _bucket_name(project_id)

    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def download_storage_key(storage_key: str) -> bytes:
    """Download a document using the persisted ``bucket/object_name`` key.

    The API owns bucket naming when it uploads a source document.  Workers must
    therefore read the durable key directly instead of trying to derive a bucket
    from an unrelated identifier.
    """
    bucket, object_name = storage_key.split("/", 1)
    response = _get_client().get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def list_documents(project_id: str, prefix: str = "") -> list[str]:
    """List document object names in a project bucket."""
    client = _get_client()
    bucket = _bucket_name(project_id)

    if not client.bucket_exists(bucket):
        return []

    objects = client.list_objects(bucket, prefix=prefix, recursive=True)
    return [obj.object_name for obj in objects if obj.object_name]


def delete_document(project_id: str, object_name: str) -> None:
    """Delete a document from MinIO."""
    client = _get_client()
    bucket = _bucket_name(project_id)
    client.remove_object(bucket, object_name)
    logger.info("Deleted %s/%s", bucket, object_name)


def delete_storage_key(storage_key: str) -> None:
    """Delete an internal object addressed by its persisted bucket/key value."""
    bucket, object_name = storage_key.split("/", 1)
    _get_client().remove_object(bucket, object_name)

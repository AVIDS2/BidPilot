from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import (
    ContentLibraryEntryCreate,
    ContentLibraryEntryRead,
    ContentLibraryPublish,
    ContentLibraryUsageCreate,
    ContentLibraryUsageRead,
    ContentLibraryVersionCreate,
)
from .service import (
    apply_content_library_entry_command,
    archive_content_library_entry_command,
    create_content_library_entry_command,
    create_content_library_version_command,
    get_content_library_entry_query,
    list_content_library_query,
    publish_content_library_entry_command,
)


router = APIRouter(prefix="/content-library", tags=["content-library"])


@router.get("", response_model=list[ContentLibraryEntryRead])
def list_entries(
    lifecycle_status: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[ContentLibraryEntryRead]:
    return list_content_library_query(
        db,
        current_user=current_user,
        lifecycle_status=lifecycle_status,
        category=category,
    )


@router.post("", response_model=ContentLibraryEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: ContentLibraryEntryCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ContentLibraryEntryRead:
    return create_content_library_entry_command(db, payload=payload, current_user=current_user)


@router.get("/{entry_id}", response_model=ContentLibraryEntryRead)
def get_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ContentLibraryEntryRead:
    return get_content_library_entry_query(db, entry_id=entry_id, current_user=current_user)


@router.post("/{entry_id}/versions", response_model=ContentLibraryEntryRead)
def create_version(
    entry_id: str,
    payload: ContentLibraryVersionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ContentLibraryEntryRead:
    return create_content_library_version_command(db, entry_id=entry_id, payload=payload, current_user=current_user)


@router.post("/{entry_id}/publish", response_model=ContentLibraryEntryRead)
def publish_entry(
    entry_id: str,
    payload: ContentLibraryPublish,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ContentLibraryEntryRead:
    return publish_content_library_entry_command(db, entry_id=entry_id, payload=payload, current_user=current_user)


@router.post("/{entry_id}/archive", response_model=ContentLibraryEntryRead)
def archive_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ContentLibraryEntryRead:
    return archive_content_library_entry_command(db, entry_id=entry_id, current_user=current_user)


@router.post("/{entry_id}/usages", response_model=ContentLibraryUsageRead, status_code=status.HTTP_201_CREATED)
def apply_entry(
    entry_id: str,
    payload: ContentLibraryUsageCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ContentLibraryUsageRead:
    return apply_content_library_entry_command(db, entry_id=entry_id, payload=payload, current_user=current_user)

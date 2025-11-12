from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.schemas.auth import AuthenticatedUser

router = APIRouter(prefix="/attachments", tags=["attachments"])


def _resolve_storage_path(filename: str) -> Path:
    settings = get_settings()
    base_dir = Path(settings.attachments_storage_dir).expanduser()
    base_resolved = base_dir.resolve()
    clean_name = Path(filename).name
    if clean_name != filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid attachment name")
    target = (base_resolved / clean_name).resolve()
    if not str(target).startswith(str(base_resolved)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid attachment path")
    return target


@router.get("/{attachment_name}", response_class=FileResponse)
def download_attachment(
    attachment_name: str,
    _: AuthenticatedUser = Depends(get_current_user),
) -> FileResponse:
    file_path = _resolve_storage_path(attachment_name)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return FileResponse(file_path, filename=file_path.name)

"""Repository upload helpers for Streamlit deployments."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

SUPPORTED_REPOSITORY_MARKERS = {".feature", ".java", ".properties", ".json", ".xml"}


class RepositoryUploadError(ValueError):
    """Raised when an uploaded repository archive cannot be used."""


def extract_repository_zip(file_name: str, data: bytes) -> Path:
    """Extract a repository ZIP safely and return the repository root path."""

    if not file_name.lower().endswith(".zip"):
        raise RepositoryUploadError("Upload a .zip file containing the repository.")
    if not data:
        raise RepositoryUploadError("Uploaded ZIP file is empty.")

    digest = hashlib.sha256(data).hexdigest()[:16]
    archive_name = Path(file_name).stem or "repository"
    extraction_root = Path(tempfile.gettempdir()) / "are_uploaded_repositories" / f"{archive_name}-{digest}"

    if extraction_root.exists():
        shutil.rmtree(extraction_root)
    extraction_root.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            _validate_zip_members(archive)
            archive.extractall(extraction_root)
    except zipfile.BadZipFile as exc:
        raise RepositoryUploadError("Uploaded file is not a valid ZIP archive.") from exc

    repository_root = _select_repository_root(extraction_root)
    if not _contains_supported_files(repository_root):
        raise RepositoryUploadError(
            "The ZIP does not contain supported files: .feature, .java, .properties, .json, or .xml."
        )
    return repository_root


def _validate_zip_members(archive: zipfile.ZipFile) -> None:
    for member in archive.infolist():
        member_path = Path(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise RepositoryUploadError(f"Unsafe ZIP path detected: {member.filename}")


def _select_repository_root(extraction_root: Path) -> Path:
    children = [
        child
        for child in extraction_root.iterdir()
        if child.name not in {"__MACOSX", ".DS_Store"}
    ]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return extraction_root


def _contains_supported_files(path: Path) -> bool:
    return any(
        file_path.is_file() and file_path.suffix.lower() in SUPPORTED_REPOSITORY_MARKERS
        for file_path in path.rglob("*")
    )

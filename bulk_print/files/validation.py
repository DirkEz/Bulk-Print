from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".rtf",
    ".xls",
    ".xlsx",
    ".xlsm",
    ".csv",
    ".ppt",
    ".pptx",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
}


@dataclass(frozen=True)
class FileValidationResult:
    path: Path
    valid: bool
    error: str | None = None


def normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def is_supported_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def validate_file(path: str | Path) -> FileValidationResult:
    normalized = normalize_path(path)
    if not normalized.exists():
        return FileValidationResult(normalized, False, "Bestand bestaat niet")
    if not normalized.is_file():
        return FileValidationResult(normalized, False, "Pad is geen bestand")
    if not is_supported_file(normalized):
        return FileValidationResult(normalized, False, "Bestandstype wordt niet ondersteund")
    return FileValidationResult(normalized, True)

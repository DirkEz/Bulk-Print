from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PrintOrientation(str, Enum):
    AUTO = "auto"
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


@dataclass(frozen=True)
class PrintSettings:
    copies: int = 1
    orientation: PrintOrientation = PrintOrientation.AUTO

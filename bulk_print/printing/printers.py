from __future__ import annotations

import sys
import subprocess


def list_printers() -> list[str]:
    if sys.platform != "win32":
        return []
    import win32print

    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    printers = win32print.EnumPrinters(flags)
    names = sorted({printer[2] for printer in printers if printer[2]})
    return names


def open_printer_preferences(printer_name: str) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Printerinstellingen zijn alleen beschikbaar op Windows.")
    subprocess.Popen(
        ["rundll32.exe", "printui.dll,PrintUIEntry", "/e", "/n", printer_name],
        shell=False,
    )

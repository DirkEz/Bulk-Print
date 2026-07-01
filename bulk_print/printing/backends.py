from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageWin

from bulk_print.printing.settings import PrintOrientation, PrintSettings


WORD_EXTENSIONS = {".doc", ".docx", ".rtf"}
EXCEL_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".csv"}
POWERPOINT_EXTENSIONS = {".ppt", ".pptx"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


class PrintError(RuntimeError):
    pass


@contextmanager
def selected_default_printer(printer_name: str) -> Iterator[None]:
    import win32print

    previous = win32print.GetDefaultPrinter()
    try:
        if previous != printer_name:
            win32print.SetDefaultPrinter(printer_name)
        yield
    finally:
        if previous and previous != printer_name:
            win32print.SetDefaultPrinter(previous)


def print_file(path: Path, printer_name: str, settings: PrintSettings | None = None) -> None:
    active_settings = settings or PrintSettings()
    if sys.platform != "win32":
        raise PrintError("Printen wordt alleen op Windows ondersteund")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        print_pdf(path, printer_name, active_settings)
        return
    if suffix in WORD_EXTENSIONS:
        print_word(path, printer_name, active_settings)
        return
    if suffix in EXCEL_EXTENSIONS:
        print_excel(path, printer_name, active_settings)
        return
    if suffix in POWERPOINT_EXTENSIONS:
        print_powerpoint(path, printer_name, active_settings)
        return
    if suffix in IMAGE_EXTENSIONS:
        print_image(path, printer_name, active_settings)
        return
    raise PrintError(f"Bestandstype wordt niet ondersteund: {suffix}")


def print_pdf(path: Path, printer_name: str, settings: PrintSettings) -> None:
    import win32con
    import win32ui

    try:
        import fitz
    except ImportError as exc:
        raise PrintError("PyMuPDF is niet geinstalleerd. Voer pip install -r requirements.txt uit.") from exc

    dc = None
    document = None
    try:
        document = fitz.open(str(path))
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(printer_name)
        printable_width = dc.GetDeviceCaps(win32con.HORZRES)
        printable_height = dc.GetDeviceCaps(win32con.VERTRES)
        for copy_index in range(settings.copies):
            suffix = f" ({copy_index + 1})" if settings.copies > 1 else ""
            dc.StartDoc(f"{path.name}{suffix}")
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                dc.StartPage()
                draw_image_to_dc(dc, image, printable_width, printable_height, settings.orientation)
                dc.EndPage()
            dc.EndDoc()
    except Exception as exc:
        raise PrintError(f"PDF kon niet worden geprint: {exc}") from exc
    finally:
        if document is not None:
            try:
                document.close()
            except Exception:
                pass
        if dc is not None:
            try:
                dc.DeleteDC()
            except Exception:
                pass


def print_word(path: Path, printer_name: str, settings: PrintSettings) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    app = None
    document = None
    try:
        with selected_default_printer(printer_name):
            app = win32com.client.DispatchEx("Word.Application")
            app.Visible = False
            app.DisplayAlerts = 0
            app.ActivePrinter = printer_name
            document = app.Documents.Open(str(path), ReadOnly=True, AddToRecentFiles=False)
            document.PrintOut(Background=False, Copies=settings.copies)
    except Exception as exc:
        raise PrintError(f"Word-bestand kon niet worden geprint: {exc}") from exc
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def print_excel(path: Path, printer_name: str, settings: PrintSettings) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    app = None
    workbook = None
    try:
        with selected_default_printer(printer_name):
            app = win32com.client.DispatchEx("Excel.Application")
            app.Visible = False
            app.DisplayAlerts = False
            workbook = app.Workbooks.Open(str(path), ReadOnly=True)
            workbook.PrintOut(Copies=settings.copies)
    except Exception as exc:
        raise PrintError(f"Excel-bestand kon niet worden geprint: {exc}") from exc
    finally:
        if workbook is not None:
            try:
                workbook.Close(False)
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def print_powerpoint(path: Path, printer_name: str, settings: PrintSettings) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    app = None
    presentation = None
    try:
        with selected_default_printer(printer_name):
            app = win32com.client.DispatchEx("PowerPoint.Application")
            presentation = app.Presentations.Open(str(path), WithWindow=False, ReadOnly=True, Untitled=False)
            presentation.PrintOptions.ActivePrinter = printer_name
            presentation.PrintOut(Copies=settings.copies)
    except Exception as exc:
        raise PrintError(f"PowerPoint-bestand kon niet worden geprint: {exc}") from exc
    finally:
        if presentation is not None:
            try:
                presentation.Close()
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def print_image(path: Path, printer_name: str, settings: PrintSettings) -> None:
    import win32con
    import win32ui

    dc = None
    try:
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(printer_name)
        printable_width = dc.GetDeviceCaps(win32con.HORZRES)
        printable_height = dc.GetDeviceCaps(win32con.VERTRES)
        image = Image.open(path)
        for copy_index in range(settings.copies):
            suffix = f" ({copy_index + 1})" if settings.copies > 1 else ""
            dc.StartDoc(f"{path.name}{suffix}")
            dc.StartPage()
            draw_image_to_dc(dc, image, printable_width, printable_height, settings.orientation)
            dc.EndPage()
            dc.EndDoc()
    except Exception as exc:
        raise PrintError(f"Afbeelding kon niet worden geprint: {exc}") from exc
    finally:
        if dc is not None:
            try:
                dc.DeleteDC()
            except Exception:
                pass


def draw_image_to_dc(
    dc,
    image: Image.Image,
    printable_width: int,
    printable_height: int,
    orientation: PrintOrientation,
) -> None:
    normalized = normalize_image_for_print(image)
    normalized = apply_orientation(normalized, orientation)
    image_width, image_height = normalized.size
    scale = min(printable_width / image_width, printable_height / image_height)
    target_width = int(image_width * scale)
    target_height = int(image_height * scale)
    left = int((printable_width - target_width) / 2)
    top = int((printable_height - target_height) / 2)
    dib = ImageWin.Dib(normalized)
    dib.draw(dc.GetHandleOutput(), (left, top, left + target_width, top + target_height))


def normalize_image_for_print(image: Image.Image) -> Image.Image:
    if image.mode not in ("RGB", "RGBA"):
        return image.convert("RGB")
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.split()[3])
        return background
    return image


def apply_orientation(image: Image.Image, orientation: PrintOrientation) -> Image.Image:
    width, height = image.size
    if orientation == PrintOrientation.PORTRAIT and width > height:
        return image.rotate(90, expand=True)
    if orientation == PrintOrientation.LANDSCAPE and height > width:
        return image.rotate(90, expand=True)
    return image

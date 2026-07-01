from __future__ import annotations

import os

from bulk_print import __version__


APP_NAME = "Bulk Print"
APP_VERSION = __version__
APP_COMPANY = "Deyvo"
APP_AUTHOR = "Dirk Schaafstra"

UPDATE_REPO = os.environ.get("BULK_PRINT_UPDATE_REPO", "DirkEz/bulk-print")
UPDATE_API_URL = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
UPDATE_INSTALLER_PREFIX = os.environ.get("BULK_PRINT_UPDATE_INSTALLER_PREFIX", "BulkPrint-Setup-v")

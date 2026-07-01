from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import requests
from packaging.version import Version

from bulk_print.settings import APP_VERSION, UPDATE_API_URL, UPDATE_INSTALLER_PREFIX


class UpdateService:
    @staticmethod
    def get_current_version() -> Version:
        return Version(UpdateService.normalize_version(APP_VERSION))

    @staticmethod
    def normalize_version(value: str) -> str:
        version = str(value or "").strip().lower().replace("v", "")
        if version == "dev" or not version:
            return "0.0.0"
        return version

    @staticmethod
    def get_latest_release() -> dict[str, Any]:
        response = requests.get(
            UPDATE_API_URL,
            timeout=20,
            headers={"Accept": "application/vnd.github+json"},
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def find_installer_asset(release: dict[str, Any]) -> dict[str, Any] | None:
        assets = release.get("assets", [])
        installer_assets = []

        for asset in assets:
            name = asset.get("name", "")
            url = asset.get("browser_download_url", "")
            if url and name.startswith(UPDATE_INSTALLER_PREFIX) and name.lower().endswith(".exe"):
                installer_assets.append(asset)

        if not installer_assets:
            return None

        def version_from_name(asset: dict[str, Any]) -> Version:
            name = asset.get("name", "")
            match = re.search(r"v(\d+\.\d+\.\d+)", name)
            if not match:
                return Version("0.0.0")
            return Version(match.group(1))

        installer_assets.sort(key=version_from_name, reverse=True)
        return installer_assets[0]

    @staticmethod
    def check_for_update() -> dict[str, Any]:
        release = UpdateService.get_latest_release()
        latest_version = Version(UpdateService.normalize_version(release.get("tag_name", "")))
        current_version = UpdateService.get_current_version()
        asset = UpdateService.find_installer_asset(release)
        available = latest_version > current_version and asset is not None

        return {
            "available": available,
            "message": "Nieuwe update beschikbaar." if available else "Je gebruikt al de nieuwste versie.",
            "release": release,
            "asset": asset,
            "latest_version": str(latest_version),
            "current_version": str(current_version),
        }

    @staticmethod
    def download_update(asset: dict[str, Any]) -> Path:
        download_url = asset["browser_download_url"]
        filename = asset["name"]
        temp_dir = Path(tempfile.gettempdir()) / "bulk_print_update"
        temp_dir.mkdir(exist_ok=True)
        destination = temp_dir / filename

        with requests.get(download_url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with destination.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)

        return destination

    @staticmethod
    def is_frozen() -> bool:
        return bool(getattr(sys, "frozen", False))

    @staticmethod
    def current_exe_path() -> Path:
        return Path(sys.executable).resolve()

    @staticmethod
    def create_installer_runner(installer_path: Path, current_exe_path: Path) -> Path:
        temp_dir = Path(tempfile.gettempdir()) / "bulk_print_update"
        temp_dir.mkdir(exist_ok=True)
        script_path = temp_dir / "run_bulk_print_update.bat"
        script = f"""@echo off
timeout /t 2 /nobreak > nul
start "" /wait "{installer_path}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS
timeout /t 1 /nobreak > nul
start "" "{current_exe_path}"
del "%~f0"
"""
        script_path.write_text(script, encoding="utf-8")
        return script_path

    @staticmethod
    def install_update(installer_path: Path) -> None:
        if os.name != "nt":
            raise RuntimeError("Automatisch updaten wordt alleen ondersteund op Windows.")
        if not UpdateService.is_frozen():
            raise RuntimeError("Automatisch installeren werkt alleen vanuit de geinstalleerde .exe.")

        current_exe = UpdateService.current_exe_path()
        runner = UpdateService.create_installer_runner(installer_path, current_exe)
        subprocess.Popen(["cmd", "/c", str(runner)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(0.5)
        sys.exit(0)

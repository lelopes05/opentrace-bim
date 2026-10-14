# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only, asynchronous OpenTrace BIM release notices.

IngeTrazo manages all downloads and installation through its Extensions
manager. This module only reads the official catalog and displays a notice.
"""
from __future__ import annotations

import json
import logging
import re

from PySide6.QtCore import QObject, QSettings, Qt, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from . import __version__
from .i18n import t, language

CATALOG_URL = (
    "https://raw.githubusercontent.com/"
    "ingelibre/ingetrazo-extensions/main/catalog.json"
)
CATALOG_ID = "opentrace_bim"
SETTINGS_KEY = "opentrace_bim/check_updates_automatically"
IGNORED_VERSION_KEY = "opentrace_bim/ignored_update_version"
MAX_CATALOG_BYTES = 2 * 1024 * 1024

log = logging.getLogger(__name__)

_VERSION = re.compile(
    r"^v?(?P<release>\d+(?:\.\d+)*)"
    r"(?P<suffix>(?:(?:[-_.]?)(?:dev|alpha|a|beta|b|rc|pre|preview|post|rev|r)"
    r"(?:[-_.]?\d+)?)?)"
    r"(?:\+[0-9a-z.-]+)?$", re.IGNORECASE
)
_PRE = re.compile(
    r"^[-_.]?(dev|alpha|a|beta|b|rc|pre|preview|post|rev|r)"
    r"[-_.]?(\d*)$", re.IGNORECASE
)
_STAGE = {
    "dev": -4, "a": -3, "alpha": -3, "b": -2, "beta": -2,
    "rc": -1, "pre": -1, "preview": -1,
    "post": 1, "rev": 1, "r": 1,
}


def auto_check_enabled() -> bool:
    """New installations receive notices by default."""
    return QSettings().value(SETTINGS_KEY, True, type=bool)


def set_auto_check_enabled(enabled: bool) -> None:
    QSettings().setValue(SETTINGS_KEY, bool(enabled))


def ignored_version() -> str:
    return str(QSettings().value(IGNORED_VERSION_KEY, "") or "")


def ignore_version(version: str) -> None:
    QSettings().setValue(IGNORED_VERSION_KEY, str(version))


def _version_key(raw: str) -> tuple[tuple[int, ...], int, int]:
    """Compare numeric releases, then development/prerelease/final/post tags."""
    match = _VERSION.fullmatch(str(raw).strip())
    if match is None:
        raise ValueError(f"Invalid catalog version: {raw!r}")
    release = tuple(int(piece) for piece in match.group("release").split("."))
    suffix = match.group("suffix")
    if not suffix:
        return release, 0, 0
    parts = _PRE.fullmatch(suffix)
    if parts is None:
        raise ValueError(f"Invalid catalog version suffix: {raw!r}")
    return release, _STAGE[parts.group(1).lower()], int(parts.group(2) or 0)


def compare_versions(left: str, right: str) -> int:
    """Return -1, 0 or 1; prereleases are below their final release."""
    la, stage_a, serial_a = _version_key(left)
    lb, stage_b, serial_b = _version_key(right)
    length = max(len(la), len(lb))
    a = (la + (0,) * (length - len(la)), stage_a, serial_a)
    b = (lb + (0,) * (length - len(lb)), stage_b, serial_b)
    return (a > b) - (a < b)


def catalog_entry(payload: bytes | str | dict) -> dict:
    """Find the OpenTrace catalog entry; package URLs/checksums are not needed."""
    if isinstance(payload, bytes):
        payload = json.loads(payload.decode("utf-8"))
    elif isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict) or not isinstance(payload.get("extensions"), list):
        raise ValueError("Invalid IngeTrazo extension catalog")
    for entry in payload["extensions"]:
        if isinstance(entry, dict) and entry.get("id") == CATALOG_ID:
            if not isinstance(entry.get("version"), str) or not entry["version"].strip():
                raise ValueError("OpenTrace BIM catalog entry is missing its version")
            return entry
    raise ValueError("OpenTrace BIM is absent from the IngeTrazo catalog")


def _localized(value: object) -> str:
    """Catalog release notes may be plain text or language-keyed text."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        code = {"pt-BR": "pt", "es": "es", "en": "en"}[language()]
        for key in (code, "en", "pt", "es"):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


def catalog_whats_new(entry: dict) -> str:
    """Do not present the general catalog summary as a release changelog."""
    for key in ("whats_new", "changelog", "release_notes"):
        text = _localized(entry.get(key))
        if text:
            return text
    return ""


class UpdateNotice(QDialog):
    """Nonmodal, read-only notice; dismissal never downloads anything."""

    def __init__(self, parent, entry: dict):
        super().__init__(parent, Qt.Tool)
        self.version = entry["version"]
        self.setObjectName("opentrace_update_notice")
        self.setWindowTitle(t("Atualização do OpenTrace BIM"))
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)

        version = QLabel(t("OpenTrace BIM {version} está disponível.", version=self.version), self)
        version.setObjectName("opentrace_update_version")
        version.setWordWrap(True)
        version.setTextFormat(Qt.PlainText)
        layout.addWidget(version)

        notes = catalog_whats_new(entry)
        if notes:
            heading = QLabel(t("O que há de novo"), self)
            layout.addWidget(heading)
            details = QLabel(notes, self)
            details.setObjectName("opentrace_update_notes")
            details.setTextFormat(Qt.PlainText)
            details.setWordWrap(True)
            layout.addWidget(details)

        guide = QLabel(
            t("Para atualizar, abra Extensions ▸ Manage extensions no IngeTrazo."),
            self,
        )
        guide.setObjectName("opentrace_update_instruction")
        guide.setTextFormat(Qt.PlainText)
        guide.setWordWrap(True)
        layout.addWidget(guide)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        acknowledge = QPushButton(t("Entendi"), self)
        acknowledge.setObjectName("opentrace_update_acknowledge")
        acknowledge.clicked.connect(self.close)
        buttons.addWidget(acknowledge)
        ignore = QPushButton(t("Não avisar mais desta versão"), self)
        ignore.setObjectName("opentrace_update_ignore")
        ignore.clicked.connect(self._ignore)
        buttons.addWidget(ignore)
        layout.addLayout(buttons)

    def _ignore(self) -> None:
        ignore_version(self.version)
        self.close()


class UpdateManager(QObject):
    """One nonblocking catalog request per plugin start, if enabled."""

    def __init__(self, parent_widget, *, catalog_url: str = CATALOG_URL):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.catalog_url = catalog_url
        self._network = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None
        self.notice: UpdateNotice | None = None

    def set_enabled(self, enabled: bool) -> None:
        set_auto_check_enabled(enabled)
        if enabled:
            self.check()
        elif self._reply is not None:
            self._reply.abort()

    def check(self) -> bool:
        if not auto_check_enabled() or self._reply is not None:
            return False
        request = QNetworkRequest(QUrl(self.catalog_url))
        request.setTransferTimeout(12000)
        request.setRawHeader(b"User-Agent", f"OpenTrace-BIM/{__version__} notice".encode())
        self._reply = self._network.get(request)
        self._reply.finished.connect(self._finish_check)
        return True

    def _finish_check(self) -> None:
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NoError:
                log.info("OpenTrace catalog notice unavailable: %s", reply.errorString())
                return
            data = bytes(reply.readAll())
            if len(data) > MAX_CATALOG_BYTES:
                raise ValueError("IngeTrazo catalog exceeds the allowed size")
            entry = catalog_entry(data)
            available = entry["version"]
            if not auto_check_enabled() or available == ignored_version():
                return
            if compare_versions(available, __version__) <= 0:
                return
            if self.notice is not None and self.notice.isVisible():
                return
            self.notice = UpdateNotice(self.parent_widget, entry)
            self.notice.show()
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            log.info("OpenTrace catalog notice could not be processed: %s", exc)
        finally:
            reply.deleteLater()

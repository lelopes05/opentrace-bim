# SPDX-License-Identifier: GPL-3.0-or-later
"""Real IngeTrazo/Qt tests for catalog-only release notices.

All tests share one offscreen host window and destroy it with the same
DeferredDelete sequence as test_wall_openings_host.py.
"""
from __future__ import annotations

import gc
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QSettings, QUrl
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from views.main_window import MainWindow

from OpenTrace_BIM import __version__
from OpenTrace_BIM.i18n import t
from OpenTrace_BIM.updater import (
    IGNORED_VERSION_KEY, SETTINGS_KEY,
    UpdateManager, auto_check_enabled, ignored_version,
)

APP = QApplication.instance() or QApplication([])
_SHARED = {}


def shared_window():
    if not _SHARED:
        _SHARED["window"] = MainWindow(defer_extensions=True)
    return _SHARED["window"]


def tearDownModule():
    window = _SHARED.pop("window", None)
    _SHARED.clear()
    if window is not None:
        window.deleteLater()
        APP.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()
    gc.collect()


class UpdateNoticeHostTests(unittest.TestCase):
    def setUp(self):
        self.window = shared_window()
        self.settings = QSettings()
        self.saved = {
            key: (self.settings.contains(key), self.settings.value(key))
            for key in (SETTINGS_KEY, IGNORED_VERSION_KEY)
        }
        self.settings.setValue(SETTINGS_KEY, True)
        self.settings.remove(IGNORED_VERSION_KEY)
        self.directory = tempfile.TemporaryDirectory()
        self.managers = []

    def tearDown(self):
        for manager in self.managers:
            if manager.notice is not None:
                manager.notice.close()
                manager.notice.deleteLater()
            manager.deleteLater()
        APP.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()
        self.directory.cleanup()
        for key, (was_set, value) in self.saved.items():
            if was_set:
                self.settings.setValue(key, value)
            else:
                self.settings.remove(key)
        self.settings.sync()

    def manager(self, version, *, notes=None, exists=True):
        location = Path(self.directory.name) / "catalog.json"
        if exists:
            entry = {"id": "opentrace_bim", "version": version}
            if notes is not None:
                entry["whats_new"] = notes
            location.write_text(json.dumps({
                "format": 1,
                "extensions": [
                    {"id": "another_extension", "version": "999"},
                    entry,
                ],
            }), encoding="utf-8")
        manager = UpdateManager(
            self.window, catalog_url=QUrl.fromLocalFile(str(location)).toString()
        )
        self.managers.append(manager)
        return manager

    def complete_check(self, manager):
        self.assertTrue(manager.check())
        deadline = time.monotonic() + 5.0
        while manager._reply is not None and time.monotonic() < deadline:
            APP.processEvents(QEventLoop.AllEvents, 50)
        self.assertIsNone(manager._reply, "Qt file:// catalog request did not finish")
        APP.processEvents()

    def test_new_version_shows_nonmodal_notice(self):
        manager = self.manager("0.14.0", notes="New door workflow")
        self.complete_check(manager)
        notice = manager.notice
        self.assertIsNotNone(notice)
        self.assertTrue(notice.isVisible())
        self.assertFalse(notice.isModal())
        self.assertEqual(notice.version, "0.14.0")
        self.assertEqual(notice.findChild(
            QLabel, "opentrace_update_notes").text(), "New door workflow")
        self.assertEqual(notice.findChild(
            QLabel, "opentrace_update_instruction").text(),
            t("Para atualizar, abra Extensions ▸ Manage extensions no IngeTrazo."))
        self.assertIsNotNone(notice.findChild(
            QPushButton, "opentrace_update_acknowledge"))
        self.assertIsNotNone(notice.findChild(
            QPushButton, "opentrace_update_ignore"))
        notice.findChild(QPushButton, "opentrace_update_acknowledge").click()
        self.assertFalse(notice.isVisible())

    def test_equal_version_has_no_notice(self):
        manager = self.manager(__version__)
        self.complete_check(manager)
        self.assertIsNone(manager.notice)

    def test_ignored_version_has_no_notice(self):
        first = self.manager("0.14.0")
        self.complete_check(first)
        self.assertIsNotNone(first.notice)
        first.notice.findChild(QPushButton, "opentrace_update_ignore").click()
        self.assertEqual(ignored_version(), "0.14.0")
        self.assertFalse(first.notice.isVisible())
        second = self.manager("0.14.0")
        self.complete_check(second)
        self.assertIsNone(second.notice)

    def test_disabled_setting_does_not_request_catalog(self):
        self.settings.setValue(SETTINGS_KEY, False)
        manager = self.manager("0.14.0")
        self.assertFalse(auto_check_enabled())
        self.assertFalse(manager.check())
        self.assertIsNone(manager._reply)
        APP.processEvents()
        self.assertIsNone(manager.notice)

    def test_missing_local_catalog_is_silent(self):
        manager = self.manager("0.14.0", exists=False)
        self.complete_check(manager)
        self.assertIsNone(manager.notice)


if __name__ == "__main__":
    unittest.main()

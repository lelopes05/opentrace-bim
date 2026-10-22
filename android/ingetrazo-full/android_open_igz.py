"""Android .igz opener: imports SAF content URI into an app-owned file.

This action is added to the genuine IngeTrazo MainWindow. Qt's file dialog
may return content:// on Android; pathlib.Path cannot read that directly.
"""
from __future__ import annotations
import os
from pathlib import Path

from PySide6.QtCore import QFile, QIODevice, QStandardPaths, QUrl
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMessageBox


def _copy_document(url: QUrl) -> Path:
    target_dir = Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation)) / "imports"
    target_dir.mkdir(parents=True, exist_ok=True)
    # The local staged copy is deliberately fixed to avoid trust in untrusted
    # filename/path traversal data supplied by Android document providers.
    destination = target_dir / "imported.igz"
    if url.isLocalFile():
        source_path = Path(url.toLocalFile())
        if source_path.suffix.lower() != ".igz":
            raise ValueError("Only .igz projects are supported")
        import shutil
        shutil.copyfile(source_path, destination)
    else:
        if url.scheme() != "content":
            raise ValueError(f"Unsupported file scheme: {url.scheme()}")
        # QFile may be able to open Android content:// via the Qt platform
        # plugin; this specific path needs validation on a physical handset.
        src = QFile(url.toString())
        if not src.open(QIODevice.OpenModeFlag.ReadOnly):
            raise OSError(f"Android provider refused document: {src.errorString()}")
        try:
            with destination.open("wb") as out:
                while not src.atEnd():
                    data = src.read(1 << 20)
                    if not data and not src.atEnd():
                        raise OSError(f"Read failed: {src.errorString()}")
                    out.write(data.data() if hasattr(data, 'data') else bytes(data))
        finally:
            src.close()
    if not destination.is_file() or destination.stat().st_size == 0:
        raise ValueError("Document is empty")
    return destination


def install_android_open(window) -> None:
    menu = window.menuBar().addMenu("Android")
    action = QAction("Open saved IngeTrazo project (.igz)…", window)
    def open_saved() -> None:
        try:
            url, _ = QFileDialog.getOpenFileUrl(
                window, "Open IngeTrazo model", QUrl(),
                "IngeTrazo documents (*.igz);;All files (*)")
            if url.isEmpty():
                return
            path = _copy_document(url)
            ok = window.open_path(path)
            if ok is False:
                raise RuntimeError("IngeTrazo rejected the .igz model")
            if hasattr(window, "_on_zoom_extents"):
                window._on_zoom_extents()
        except Exception as exc:
            QMessageBox.critical(window, "Android .igz import failed",
                                 f"{type(exc).__name__}: {exc}")
    action.triggered.connect(open_saved)
    menu.addAction(action)
    window._android_file_action = action

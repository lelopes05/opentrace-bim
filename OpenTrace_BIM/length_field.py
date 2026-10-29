# SPDX-License-Identifier: GPL-3.0-or-later
"""Length fields in the document's units.

OpenTrace stores every length in metres, and that does not change here:
``value()`` and ``setValue()`` are always metres, so the code behind a
panel never converts anything. What changes is the TEXT: a
:class:`LengthField` shows and reads lengths the way IngeTrazo's own
readouts do (``core.units``, IngeTrazo 0.5.8+) -- ``2.70 m``, ``270 cm``,
``8' 10 1/4"`` -- following the document's units, and it re-renders when
those units change (Preferences, or opening another document).

Fields were written for metres (``setSuffix(" m")``, ``setDecimals(4)``,
``setSingleStep(0.05)``...). On a host with ``core.units`` those calls are
ignored, so swapping the constructor is the whole change at each site; on
an older host the field is exactly the metre field it replaces.
"""
from __future__ import annotations

import weakref

from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QToolTip

from .widgets import FlexibleDoubleSpinBox

try:  # IngeTrazo 0.5.8+: document units.
    from core import units as _units
    _HAS_UNITS = all(hasattr(_units, name) for name in (
        "parse", "format_length", "localized", "model_unit",
        "fine_precision", "display_step"))
except Exception:  # noqa: BLE001 - older host: plain metre fields
    _units = None
    _HAS_UNITS = False

# Every live field, so a change of document units can re-render them all.
_LIVE: "weakref.WeakSet[LengthField]" = weakref.WeakSet()


def has_document_units() -> bool:
    return _HAS_UNITS


class LengthField(FlexibleDoubleSpinBox):
    """A spin box whose value is metres and whose text is in the
    document's units. Typed text is read like IngeTrazo's value box:
    ``2,70``, ``270 cm``, ``8'10"``, ``8' 10 1/4"``, ``3/4"``; a bare number
    is in the document's unit. Text that is not a length is not taken and
    the reason shows next to the field."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._unit = None
        self._shown = None
        if _HAS_UNITS:
            # Qt rounds the stored value to decimals(): metres to the
            # micron keep every unit's shown precision exact.
            super().setDecimals(9)
            super().setSuffix("")
            self._apply_unit()
            _LIVE.add(self)

    # -- metre-era calls are harmless when units are live -------------------
    def setSuffix(self, suffix):  # noqa: N802 - Qt API
        if not _HAS_UNITS:
            super().setSuffix(suffix)

    def setDecimals(self, decimals):  # noqa: N802 - Qt API
        if not _HAS_UNITS:
            super().setDecimals(decimals)

    def setSingleStep(self, step):  # noqa: N802 - Qt API
        # The arrows add one step of the SHOWN precision (1 mm, 1/16"...),
        # not a metre-based step that means nothing in feet.
        if not _HAS_UNITS:
            super().setSingleStep(step)

    def setLocale(self, locale):  # noqa: N802 - Qt API
        # The document decides the decimal separator (core.units.localized).
        if not _HAS_UNITS:
            super().setLocale(locale)

    # -- units ---------------------------------------------------------------
    def _apply_unit(self) -> None:
        self._unit = _units.model_unit()
        self._shown = (self._unit, _units.fine_precision())
        super().setSingleStep(
            _units.display_step(self._unit, _units.fine_precision()))

    def refresh_units(self) -> None:
        """Re-render in the document's current units or precision, if they
        changed."""
        if not _HAS_UNITS or (_units.model_unit(),
                              _units.fine_precision()) == self._shown:
            return
        self._apply_unit()
        edit = self.lineEdit()
        blocked = edit.blockSignals(True)
        try:
            edit.setText(self.textFromValue(self.value()))
        finally:
            edit.blockSignals(blocked)

    # -- text <-> metres -------------------------------------------------------
    def textFromValue(self, value: float) -> str:  # noqa: N802 - Qt API
        if not _HAS_UNITS:
            return super().textFromValue(value)
        return _units.localized(_units.format_length(
            value, self._unit or _units.model_unit(), _units.fine_precision()))

    def _reading(self, text: str):
        r = _units.parse(text, "length", self._unit)
        if not r.ok:
            return None, r.message()
        if not self.minimum() - 1e-12 <= r.value <= self.maximum() + 1e-12:
            return None, "{} … {}".format(self.textFromValue(self.minimum()),
                                          self.textFromValue(self.maximum()))
        return r.value, ""

    def valueFromText(self, text: str) -> float:  # noqa: N802 - Qt API
        if not _HAS_UNITS:
            return super().valueFromText(text)
        value, _ = self._reading(text)
        return self.value() if value is None else value

    def validate(self, text: str, pos: int):
        if not _HAS_UNITS:
            return super().validate(text, pos)
        value, _ = self._reading(text)
        state = (QValidator.Acceptable if value is not None
                 else QValidator.Intermediate)
        return state, text, pos

    def fixup(self, text: str) -> str:
        if _HAS_UNITS:
            _, msg = self._reading(text)
            if msg:
                # Leaving the field puts the last good value back; say why.
                QToolTip.showText(
                    self.mapToGlobal(self.rect().bottomLeft()), msg, self)
        return text


def format_length(metres: float, signed: bool = False) -> str:
    """A length as text in the document's units (labels, totals, viewport
    readouts), at least to the millimetre; ``1.2345 m`` on a host without
    document units. ``signed`` puts a ``+`` before positive values."""
    metres = float(metres)
    if _HAS_UNITS:
        text = _units.localized(_units.format_length(
            metres, _units.model_unit(), _units.fine_precision()))
    else:
        text = f"{metres:.4f} m"
    if signed and metres >= 0 and not text.startswith(("+", "-")):
        text = "+" + text
    return text


def refresh_all() -> None:
    """Re-render every live length field (hooked to document changes)."""
    for field in list(_LIVE):
        try:
            field.refresh_units()
        except RuntimeError:  # the Qt object is already gone
            pass

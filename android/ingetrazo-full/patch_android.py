"""Android-only staging patch for the REAL IngeTrazo upstream application.

Runs on a disposable checkout before pyside6-android-deploy.
Does not edit ingelibre/ingetrazo or OpenTrace main.
"""
from __future__ import annotations
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
main = root / "main.py"
code = main.read_text(encoding="utf-8")
def subst(old: str, new: str) -> None:
    global code
    if code.count(old) != 1:
        raise RuntimeError(f"Upstream changed: expected exactly one occurrence of {old[:90]!r}, found {code.count(old)}")
    code = code.replace(old, new)

# Android supplies OpenGL ES, not GL 3.3 Core. This allows Qt's widgets to
# request a context, but does NOT magically translate desktop GLSL shaders.
subst(
    "    fmt.setVersion(3, 3)\n    fmt.setProfile(QSurfaceFormat.CoreProfile)",
    "    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGLES)\n"
    "    fmt.setVersion(3, 0)\n"
    "    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.NoProfile)",
)

# The upstream GL fallback probes for desktop GL 3.3 and restarts on xcb
# (not available on Android). Keep the original code everywhere else.
subst(
    "    gl_fallback = ensure_gl_context(app)",
    "    gl_fallback = 'android-opengles'",
)

# Real MainWindow and tools remain intact. Add native-document import action
# to the existing menu; unlike previous GPU lab this imports real .igz files.
subst(
    "    window = MainWindow(defer_extensions=True)",
    "    window = MainWindow(defer_extensions=True)\n"
    "    from android_open_igz import install_android_open\n"
    "    install_android_open(window)",
)

# Show the ACTUAL upstream example .igz model after MainWindow initializes.
# The sample file uses the same loader as a user project.
subst(
    "        window.load_extensions()\n        if arg:",
    "        window.load_extensions()\n"
    "        sample = Path(__file__).resolve().parent / 'examples' / 'banca-pergola-yanque.igz'\n"
    "        if sample.exists() and not arg:\n"
    "            _open_document_in(window, sample)\n"
    "        if arg:",
)
main.write_text(code, encoding="utf-8")
print(f"Patched Android startup for real IngeTrazo at {root}")

"""Pin the Qt-for-Python Android builder to a compatible CPython runtime.

PySide6 6.11.2 Android wheels have a cp311 target and require libpython3.11.so.
The python-for-android 'develop' branch moved to CPython 3.14, so using its
floating head can produce an unusable APK. This is only a build-host patch:
it does NOT change IngeTrazo, OpenTrace, or Android runtime files.

Reference compatibility investigation:
https://github.com/evadeflow/pyside-p4a-example
"""
from pathlib import Path
import importlib.util

P4A_COMMIT = "3762c88c56e3443efb8eba2a02a2604b680240fd"

spec = importlib.util.find_spec("PySide6")
if spec is None or not spec.submodule_search_locations:
    raise SystemExit("PySide6 is missing from builder")
source = Path(next(iter(spec.submodule_search_locations))) / "scripts/deploy_lib/android/buildozer.py"
code = source.read_text(encoding="utf-8")
old = '        self.set_value("app", "p4a.branch", "develop")'
new = old + '\n        self.set_value("app", "p4a.commit", "' + P4A_COMMIT + '")'
if new in code:
    print("Already pinned:", P4A_COMMIT)
elif code.count(old) == 1:
    source.write_text(code.replace(old, new), encoding="utf-8")
    print("Pinned p4a to", P4A_COMMIT)
else:
    raise RuntimeError("PySide6 deploy tool changed: cannot apply safe p4a pin")

# Buildozer's default file filter includes Python/images only. IngeTrazo
# needs its native saved model, GLSL source and bundled JSON asset libraries.
code = source.read_text(encoding="utf-8")
old = 'include_exts = f"{include_exts},qml,js"'
new = 'include_exts = f"{include_exts},qml,js,igz,json,vert,frag,svg,ttf,otf,qm,ini,toml,xml,woff,woff2,txt"'
if new in code:
    print("IngeTrazo data assets already allowed")
elif code.count(old) == 1:
    source.write_text(code.replace(old, new), encoding="utf-8")
    print("Allowed packaged IngeTrazo .igz, shaders, and resources")
else:
    raise RuntimeError("PySide6 deploy tool changed: cannot adjust packaged data file extensions")


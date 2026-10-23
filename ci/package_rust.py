# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the Windows installation ZIP from the checksum-verified 0.44.0 release."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "b03455f4c24b95592e4ce671bdb85eb60e06bff02a617bcc497d8697fa40a937"
OVERLAYS = [
    "OpenTrace_BIM/__init__.py",
    "OpenTrace_BIM/suite_panel.py",
    "OpenTrace_BIM/arrange_ui.py",
    "OpenTrace_BIM/model.py",
    "OpenTrace_BIM/slab_model.py",
    "OpenTrace_BIM/beam_model.py",
    "OpenTrace_BIM/complex_profile.py",
    "OpenTrace_BIM/door_grooves.py",
    "OpenTrace_BIM/door_window_geometry.py",
    "OpenTrace_BIM/wall_polygon.py",
    "OpenTrace_BIM/RUST_VERSION.md",
    "OpenTrace_BIM/rust_bridge.py",
    "OpenTrace_BIM/rust_dispatch.py",
    "OpenTrace_BIM/rust_core/Cargo.toml",
    "OpenTrace_BIM/rust_core/src/lib.rs",
    "OpenTrace_BIM/rust_core/verify_rust.py",
]
DLL = "OpenTrace_BIM/rust_core/target/release/opentrace_rust_core.dll"


def main():
    source = Path(sys.argv[1])
    if sha256(source.read_bytes()).hexdigest() != EXPECTED:
        raise RuntimeError("The source ZIP does not match the supplied 0.44.0 archive")
    binary = ROOT / DLL
    if not binary.is_file():
        raise RuntimeError(f"Windows Rust DLL not built: {binary}")
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        with zipfile.ZipFile(source) as original:
            for info in original.infolist():
                member = Path(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise RuntimeError("Unsafe path in source ZIP")
                original.extract(info, base)
        package = base / "OpenTrace_BIM"
        if not (package / "__init__.py").is_file():
            raise RuntimeError("Source archive is missing OpenTrace_BIM")
        for relative in OVERLAYS:
            src = ROOT / relative
            dest = base / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        target = base / DLL
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, target)
        manifest = package / "PACKAGE_MANIFEST.txt"
        lines = []
        for file in sorted(package.rglob("*")):
            if not file.is_file() or file == manifest or "__pycache__" in file.parts:
                continue
            lines.append(f"{sha256(file.read_bytes()).hexdigest()}  {file.relative_to(package).as_posix()}")
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        output = ROOT / "output" / "OpenTrace BIM 0.44.0 Rust.zip"
        output.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as result:
            for file in sorted(package.rglob("*")):
                if file.is_file() and "__pycache__" not in file.parts:
                    result.write(file, file.relative_to(base))
        with zipfile.ZipFile(output) as built:
            names = built.namelist()
            assert "OpenTrace_BIM/__init__.py" in names
            assert DLL in names
            assert "OpenTrace_BIM/PACKAGE_MANIFEST.txt" in names
        print(f"Windows package: {output}")


if __name__ == "__main__":
    main()

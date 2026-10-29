# SPDX-License-Identifier: GPL-3.0-or-later
"""US layer template following the National CAD Standard (NCS) naming.

Layer names follow the NCS pattern ``D-MMMM-mmmm``: a discipline designator
(``A`` architectural, ``S`` structural, ``M``/``P``/``E``/``F``/``T`` systems,
``C``/``L`` site, ``G`` general, ``I`` interiors), a major group and optional
minor groups. Construction status (new / existing / demolish) is NOT encoded
in layer names: OpenTrace keeps it in each element's IFC status, so the same
layers serve demolition and new-work drawings.

The structure is the same as the Brazilian templates in ``__init__.py``:
layers with a folder and a default intersection group, and named
combinations (visibility / lock states) organised like a US sheet set.
"""
from __future__ import annotations

#: name, folder path, default intersection group (0 = joins nothing).
#: Groups per discipline: architecture 1, structure 2, electrical 3,
#: plumbing 4, mechanical 5, fire protection 6, telecom 7.
LAYER_DEFS = (
    ("Layer 0", "G General / Auxiliary", 1),
    ("G-GRID", "G General / Grid & References", 0),
    ("G-REFR", "G General / Grid & References", 0),
    ("G-REFR-IMPT", "G General / Grid & References", 0),
    ("G-REFR-SCAN", "G General / Grid & References", 0),

    ("C-TOPO", "C Civil / Site", 0),
    ("C-PROP", "C Civil / Site", 0),
    ("C-PKNG", "C Civil / Site", 0),
    ("C-ROAD", "C Civil / Site", 0),
    ("L-PLNT", "L Landscape", 0),
    ("L-SITE", "L Landscape", 0),

    ("A-WALL-EXTR", "A Architectural / Walls", 1),
    ("A-WALL-INTR", "A Architectural / Walls", 1),
    ("A-WALL-PRHT", "A Architectural / Walls", 1),
    ("A-COLS", "A Architectural / Walls", 1),
    ("A-GLAZ", "A Architectural / Openings", 1),
    ("A-GLAZ-CWMG", "A Architectural / Openings", 1),
    ("A-DOOR", "A Architectural / Openings", 1),
    ("A-FLOR", "A Architectural / Floors & Circulation", 1),
    ("A-FLOR-STRS", "A Architectural / Floors & Circulation", 1),
    ("A-FLOR-HRAL", "A Architectural / Floors & Circulation", 0),
    ("A-FLOR-EVTR", "A Architectural / Floors & Circulation", 1),
    ("A-CLNG", "A Architectural / Ceilings & Roof", 0),
    ("A-CLNG-GRID", "A Architectural / Ceilings & Roof", 0),
    ("A-ROOF", "A Architectural / Ceilings & Roof", 1),
    ("A-FLOR-PFIX", "A Architectural / Equipment & Fixtures", 0),
    ("A-FLOR-CASE", "A Architectural / Equipment & Fixtures", 0),
    ("A-EQPM", "A Architectural / Equipment & Fixtures", 0),
    ("A-AREA-IDEN", "A Architectural / Annotation", 0),
    ("A-ANNO-DIMS", "A Architectural / Annotation", 0),
    ("A-ANNO-NOTE", "A Architectural / Annotation", 0),
    ("A-ANNO-SYMB", "A Architectural / Annotation", 0),
    ("A-ANNO-TTLB", "A Architectural / Annotation", 0),
    ("A-ANNO-REVS", "A Architectural / Annotation", 0),
    ("A-ANNO-NPLT", "A Architectural / Annotation", 0),

    ("I-FURN", "I Interiors", 0),
    ("I-CASE", "I Interiors", 0),
    ("I-EQPM", "I Interiors", 0),

    ("S-GRID", "S Structural", 0),
    ("S-FNDN", "S Structural", 2),
    ("S-COLS", "S Structural", 2),
    ("S-BEAM", "S Structural", 2),
    ("S-SLAB", "S Structural", 2),
    ("S-WALL", "S Structural", 2),
    ("S-JOIS", "S Structural", 2),
    ("S-FRAM", "S Structural", 2),

    ("M-HVAC-DUCT", "M Mechanical", 5),
    ("M-HVAC-EQPM", "M Mechanical", 0),
    ("M-HVAC-DIFF", "M Mechanical", 0),
    ("P-DOMW", "P Plumbing", 4),
    ("P-SANR", "P Plumbing", 4),
    ("P-STRM", "P Plumbing", 4),
    ("P-FIXT", "P Plumbing", 0),
    ("P-NGAS", "P Plumbing", 4),
    ("E-LITE", "E Electrical", 0),
    ("E-POWR", "E Electrical", 3),
    ("F-PROT-SPRN", "F Fire Protection", 6),
    ("F-ALRM", "F Fire Protection", 0),
    ("T-DATA", "T Telecommunications", 7),
    ("T-SECU", "T Telecommunications", 7),
)

#: Annotation and no-plot layers, hidden in model-only combinations.
ANNOTATION = ("A-AREA-IDEN", "A-ANNO-DIMS", "A-ANNO-NOTE", "A-ANNO-SYMB",
              "A-ANNO-TTLB", "A-ANNO-REVS", "A-ANNO-NPLT")
SYSTEMS = ("M", "P", "E", "F", "T")


def discipline(name: str) -> str:
    """The NCS discipline designator: ``A-WALL-EXTR`` -> ``A``."""
    return name.split("-", 1)[0] if "-" in name else name


def combinations(make_combo):
    """The sheet-set combinations, built with the template's ``make_combo``
    (show/lock by discipline designator, or by exact layer name)."""
    return [
        make_combo(
            "00 3D Model",
            ("G", "C", "L", "A", "I", "S") + SYSTEMS,
            hide_exact=ANNOTATION + ("G-REFR-IMPT", "G-REFR-SCAN"),
        ),
        make_combo(
            "A-101 Floor Plan",
            ("A", "I"),
            show_exact=("G-GRID",),
            hide_exact=("A-CLNG", "A-CLNG-GRID", "A-ROOF", "A-ANNO-NPLT"),
        ),
        make_combo(
            "A-121 Reflected Ceiling Plan",
            (),
            show_exact=("A-WALL-EXTR", "A-WALL-INTR", "A-COLS", "A-GLAZ",
                        "A-GLAZ-CWMG", "A-CLNG", "A-CLNG-GRID", "E-LITE",
                        "M-HVAC-DIFF", "F-PROT-SPRN", "A-AREA-IDEN",
                        "A-ANNO-DIMS", "A-ANNO-NOTE", "A-ANNO-SYMB"),
            lock_exact=("A-WALL-EXTR", "A-WALL-INTR", "A-COLS", "A-GLAZ",
                        "A-GLAZ-CWMG"),
        ),
        make_combo(
            "A-201 Elevations",
            ("A",),
            show_exact=("C-TOPO", "L-PLNT"),
            hide_exact=("A-CLNG", "A-CLNG-GRID", "A-AREA-IDEN", "A-ANNO-NPLT"),
        ),
        make_combo(
            "A-301 Sections",
            ("A", "S"),
            show_exact=("C-TOPO",),
            hide_exact=("A-AREA-IDEN", "A-ANNO-NPLT"),
        ),
        make_combo(
            "A-501 Details",
            ("A", "S"),
            hide_exact=("A-AREA-IDEN", "A-ANNO-NPLT"),
        ),
        make_combo(
            "AS-101 Site Plan",
            ("C", "L"),
            show_exact=("A-WALL-EXTR", "A-ROOF", "G-GRID", "A-ANNO-DIMS",
                        "A-ANNO-NOTE", "A-ANNO-SYMB"),
            lock_exact=("A-WALL-EXTR", "A-ROOF"),
        ),
        make_combo(
            # Status comes from each element's IFC status, not from layers.
            "D-101 Demolition Plan",
            ("A",),
            show_exact=("G-GRID",),
            hide_exact=("A-CLNG", "A-CLNG-GRID", "A-ROOF", "A-AREA-IDEN",
                        "A-ANNO-NPLT"),
        ),
        make_combo(
            "S-101 Foundation / Framing",
            ("S",),
            show_exact=("G-GRID", "A-WALL-EXTR", "A-ANNO-DIMS", "A-ANNO-NOTE",
                        "A-ANNO-SYMB"),
            lock_exact=("A-WALL-EXTR",),
        ),
        make_combo(
            "G-001 Life Safety Plan",
            ("F",),
            show_exact=("A-WALL-EXTR", "A-WALL-INTR", "A-WALL-PRHT", "A-COLS",
                        "A-GLAZ", "A-DOOR", "A-FLOR-STRS", "A-FLOR-HRAL",
                        "A-FLOR-EVTR", "A-AREA-IDEN", "A-ANNO-DIMS",
                        "A-ANNO-NOTE", "A-ANNO-SYMB"),
            lock_exact=("A-WALL-EXTR", "A-WALL-INTR", "A-WALL-PRHT", "A-COLS",
                        "A-GLAZ", "A-DOOR"),
        ),
        make_combo(
            "MEP Coordination",
            ("A", "S") + SYSTEMS,
            lock_prefixes=("A", "S"),
            hide_exact=ANNOTATION + ("A-CLNG-GRID",),
        ),
    ]


NAME = "US · National CAD Standard"
DESCRIPTION = (
    "US office template with NCS layer names (A-WALL-EXTR, S-FNDN, "
    "M-HVAC-DUCT…) and combinations organised like a US sheet set: floor "
    "plan, reflected ceiling plan, elevations, sections, details, site, "
    "demolition, structural, life safety and MEP coordination. Construction "
    "status is taken from each element's IFC status, not from layer names."
)
DEFAULT_COMBINATION = "00 3D Model"

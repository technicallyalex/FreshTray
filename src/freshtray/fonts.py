"""Private IBM Plex Sans registration; no registry or system font installation."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
from tkinter import font

_loaded = set()


def application_fonts(root):
    folder = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "assets/fonts"
    add = ctypes.WinDLL("gdi32").AddFontResourceExW
    add.argtypes, add.restype = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p], ctypes.c_int
    for path in folder.glob("IBMPlexSans-*.ttf"):
        if str(path) not in _loaded and add(str(path), 0x10, None):
            _loaded.add(str(path))
    available = set(font.families(root))
    body = "IBM Plex Sans" if "IBM Plex Sans" in available else "Arial"
    # Use an already installed Founders font if available, never redistribute it.
    heading = next((name for name in ("Founders Grotesk", "IBM Plex Sans SemiBold", body) if name in available), body)
    medium = "IBM Plex Sans Medium" if "IBM Plex Sans Medium" in available else body
    specs = {"AppBody": (body, 10, "normal"), "AppSmall": (body, 9, "normal"),
             "AppButton": (medium, 10, "normal"), "AppHeading": (heading, 10, "bold" if heading == body else "normal"),
             "AppTitle": (heading, 20, "bold" if heading == body else "normal"),
             "AppSection": (heading, 12, "bold" if heading == body else "normal"),
             "AppBrand": (heading, 14, "bold" if heading == body else "normal")}
    result = {}
    for name, (family, size, weight) in specs.items():
        result[name] = font.Font(root=root, name=name, family=family, size=size, weight=weight)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        font.nametofont(name, root=root).configure(family=body, size=10)
    return result

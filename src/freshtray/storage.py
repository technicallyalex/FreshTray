"""Atomic preferences and a Windows DPAPI CurrentUser encrypted vault."""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import threading


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class Blob(ctypes.Structure):
    _fields_ = [("size", w.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    if os.name != "nt":
        raise OSError("The encrypted vault requires Windows.")
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, target = Blob(len(data), buffer), Blob()
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, w.DWORD, ctypes.POINTER(Blob)]
    function.restype = w.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    # CRYPTPROTECT_UI_FORBIDDEN; never LOCAL_MACHINE.
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OSError("Windows could not unlock/save the encrypted vault. Use the same Windows account.")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


class Vault:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.data = json.loads(protect(self.path.read_bytes(), True)) if self.path.exists() else {}

    def get(self, key, default=None):
        with self.lock:
            return self.data.get(key, default)

    def update(self, **values):
        with self.lock:
            changed = dict(self.data, **values)
            atomic_write(self.path, protect(json.dumps(changed).encode("utf-8")))
            self.data = changed


DEFAULTS = {"reminders": True, "time": "17:00", "weekdays_only": True,
            "last_reminded": "", "business_id": None, "always_on_top": False, "docked_mode": False, "close_to_tray": True, "theme": "system", "window_size": None, "layout_revision": 0}


class Preferences:
    def __init__(self, path):
        self.path = Path(path)
        self.data = dict(DEFAULTS)
        if self.path.exists():
            self.data.update(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, **values):
        updated = dict(self.data, **values)
        atomic_write(self.path, json.dumps(updated, indent=2).encode("utf-8"))
        self.data = updated

"""Launch FreshTray. Source mode needs only Python with Tk (no pip packages)."""
import argparse
import ctypes
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox

from freshtray.api import FreshBooks
from freshtray.demo import Demo
from freshtray.storage import Vault, Preferences
from freshtray.ui import App
from freshtray.windows import SingleInstance


def main():
    parser = argparse.ArgumentParser(description="FreshTray personal Windows time logger")
    parser.add_argument("--demo", action="store_true", help="Offline UI preview; sends no network requests")
    parser.add_argument("--background", action="store_true", help="Start hidden in the system tray")
    parser.add_argument("--data-dir", type=Path, help="Override the per-user settings directory")
    args = parser.parse_args()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (OSError, AttributeError):
        pass
    instance = SingleInstance(args.demo)
    if instance.exists:
        ctypes.windll.user32.MessageBoxW(None, "FreshTray is already running. Click its clock in the system tray (check the hidden icons arrow).", "FreshTray", 0x40)
        instance.close()
        return
    root = tk.Tk()
    root.withdraw()
    try:
        folder = args.data_dir or Path(os.environ["LOCALAPPDATA"]) / ("FreshTray-Preview" if args.demo else "FreshTray")
        vault = Vault(folder / "vault.dpapi")
        preferences = Preferences(folder / "settings.json")
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        api = Demo() if args.demo else FreshBooks(vault)
        app = App(root, api, vault, preferences, base / "assets", Path(__file__), args.demo)
        if not args.background:
            app.show()
        root.mainloop()
    except Exception:
        # Do not persist exception text, stack traces, HTTP data or OAuth URLs.
        messagebox.showerror("FreshTray could not start", "Check that the app folder is intact and your Windows account can read its encrypted settings. If you moved computers/accounts, see the recovery section of the guide.", parent=root)
    finally:
        instance.close()


if __name__ == "__main__":
    main()

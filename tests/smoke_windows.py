"""Real Windows/Tk checks for the unified responsive UI; no network or real profile."""
from datetime import date, timedelta
from pathlib import Path
import argparse
import sys
import tempfile
import time
import tkinter as tk
from tkinter import ttk, font

import _paths  # Make src imports independent of the working directory.
from freshtray.demo import Demo
from freshtray.storage import Preferences, Vault
from freshtray.ui import App
from freshtray.appearance import PALETTES
from freshtray.scrollbars import SlimScrollbar
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scaling', type=float)
    args = parser.parse_args()
    root = tk.Tk()
    root.withdraw()
    if args.scaling:
        root.tk.call('tk', 'scaling', args.scaling)
    app = None
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        prefs = Preferences(folder / 'settings.json')
        prefs.save(reminders=False, theme='light')
        try:
            app = App(root, Demo(), Vault(folder / 'vault.dpapi'), prefs,
                      Path(__file__).resolve().parents[1] / 'src/assets', Path(__file__), True)
            def settled():
                deadline = time.monotonic() + 6
                while app.busy and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.02)
                root.update()
                assert not app.busy
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            app.show()
            settled()
            assert tuple(root.resizable()) == (1, 1)
            assert app.clients and app.tray.hwnd
            assert app.appearance.fonts['AppBody'].actual('family') == 'IBM Plex Sans', 'Bundled interface font did not load'
            assert not any(isinstance(w, ttk.Scrollbar) for w in descendants(root)), 'A heavy native scrollbar remains'
            # Hidden for short content; rounded, draggable and theme-aware for overflow.
            note_bar = next(w for w in app.note.master.winfo_children() if isinstance(w, SlimScrollbar))
            root.update()
            assert not note_bar.is_needed
            original_note = app.note.get('1.0', 'end-1c')
            app.note.insert('end', '\n' + ('Scrollable note line\n' * 80))
            root.update()
            assert note_bar.is_needed and note_bar.winfo_width() <= 12
            start, end, travel, fraction = note_bar.thumb_bounds()
            note_bar.press(SimpleNamespace(x=6, y=start+3))
            note_bar.drag(SimpleNamespace(x=6, y=note_bar.winfo_height()-3))
            note_bar.release()
            root.update()
            assert app.note.yview()[0] > .5, 'Scrollbar drag did not scroll the actual note'
            note_bar.move(0)
            root.update()
            assert app.note.yview()[0] < .01
            app.note.delete('1.0', 'end')
            app.note.insert('1.0', original_note)
            root.update()
            assert not note_bar.is_needed
            assert not any(isinstance(w, tk.Toplevel) for w in root.winfo_children())
            app.project_combo.current(1)
            app.filter_services()
            assert len(app.filtered_services) == 1
            app.save_button.invoke()
            settled()
            assert app.status.get() == 'Preview complete. No time was sent.'
            app.calendar_button.invoke()
            root.update()
            picker = app.calendar_window
            assert picker.winfo_exists() and tuple(picker.resizable()) == (1, 1)
            old = app.day.get()
            picker.select(date.today() + timedelta(days=1))
            assert app.day.get() == old
            picker.month = date(2024, 2, 1)
            picker.render()
            picker.day_buttons[date(2024, 2, 29)].invoke()
            assert app.day.get() == '2024-02-29'
            app.settings()
            root.update()
            settings = app.settings_window
            assert settings.winfo_toplevel() == root and app.active_page == 'settings'
            assert not any(isinstance(w, tk.Toplevel) for w in root.winfo_children())
            assert (app.reminder_time.clock.get(), app.reminder_time.period.get()) == ('5:00', 'PM')
            app.reminder_time.clock.set('12:00')
            app.reminder_time.period.set('AM')
            settings.always_on_top.set(True)
            settings.save_button.invoke()
            root.update()
            assert root.attributes('-topmost') and prefs.data['time'] == '00:00'
            assert Preferences(folder / 'settings.json').data['always_on_top']
            # Switching away and back retains unsaved connection fields without floating windows.
            settings.client_id.set('unsaved-local-preview-value')
            settings.secret.set('local-preview-secret')
            app.show_entry()
            app.settings()
            assert app.settings_window is settings and settings.client_id.get() == 'unsaved-local-preview-value'
            assert settings.secret.get() == 'local-preview-secret'
            for name in ('Dark', 'Light', 'Use Windows setting'):
                settings.theme_value.set(name)
                settings.change_theme()
                root.update()
                mode = {'Dark': 'dark', 'Light': 'light', 'Use Windows setting': 'system'}[name]
                assert Preferences(folder / 'settings.json').data['theme'] == mode
                assert app.note.cget('background') == PALETTES[app.appearance.current]['field']
                assert note_bar.cget('background') == PALETTES[app.appearance.current]['field']
            root.state('zoomed')
            root.update()
            app.settings()
            root.update()
            assert root.state() == 'zoomed', 'Changing pages unmaximized the app'
            app.hide()
            app.show()
            root.update()
            assert root.state() == 'zoomed', 'Tray restore lost maximized state'
            root.state('normal')
            root.update()
            # At minimum size, Settings can scroll to its last controls; footer stays visible.
            for width, height in ((640, 460), (900, 680), (1180, 900)):
                root.geometry(f'{width}x{height}')
                root.update()
                page = app.pages['settings']
                page.sync()
                page.canvas.yview_moveto(1)
                root.update()
                assert page.canvas.yview()[1] > .99
                assert not page.hscroll.is_needed, 'Wide scrollbar shown when the Settings page fits horizontally'
                app.show_entry()
                root.update()
                assert app.date_entry.winfo_width() >= 90
                assert app.calendar_button.winfo_width() >= app.calendar_button.winfo_reqwidth()
                app.settings()
                root.update()
            root.geometry('900x680')
            app.show_entry()
            root.update()
            app.hide()
            root.update()
            assert root.state() == 'withdrawn'
            from freshtray.windows import user
            user.PostMessageW(app.tray.hwnd, 0x8001, 0, 0x0202)
            deadline = time.monotonic() + 2
            while root.state() == 'withdrawn' and time.monotonic() < deadline:
                root.update()
                time.sleep(.02)
            deadline = time.monotonic() + .3
            while time.monotonic() < deadline:
                root.update()
                time.sleep(.02)
            assert root.attributes('-topmost')
            settings.always_on_top.set(False)
            settings.save_button.invoke()
            root.update()
            assert not root.attributes('-topmost')
            app.remember_size()
            assert Preferences(folder / 'settings.json').data['window_size'] == [root.winfo_width(), root.winfo_height()]
            print(f'PASS: IBM Plex Sans/private font loading, slim auto-hide/drag scrollbars, unified docked pages, resizable form, scrolling/footer bounds, themes, retained connection fields, AM/PM, pinning, calendar and tray restore (Tk scale {root.tk.call("tk", "scaling")}).')
        finally:
            if app:
                app.tray.close()
                app.executor.shutdown(wait=True)
            root.destroy()


if __name__ == '__main__':
    main()

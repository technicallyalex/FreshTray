"""Taskbar-adjacent tool-window mode with safe focus dismissal."""
import tkinter as tk
from .sizing import work_area, frame_size

class DockedMode:
    def __init__(self, app):
        self.app = app
        self.enabled = False
        app.root.bind('<FocusOut>', self.focus_out, add='+')

    def apply(self):
        root = self.app.root
        self.enabled = bool(self.app.prefs.data.get('docked_mode', False))
        root.wm_attributes('-toolwindow', self.enabled)
        if self.enabled and root.state() == 'zoomed':
            root.state('normal')
        self.app.was_maximized = False if self.enabled else self.app.was_maximized
        if root.state() == 'normal':
            self.app.launch_fit.pending = True
            self.app.launch_fit.schedule()
            root.after_idle(self.position)

    def position(self):
        root = self.app.root
        if not self.enabled or root.state() != 'normal':
            return
        left, top, right, bottom = work_area(root)
        # Work-area edges account for the taskbar and leave a small inset.
        frame_width, frame_height = frame_size(root)
        x = max(left, right-root.winfo_width()-frame_width-12)
        y = max(top, bottom-root.winfo_height()-frame_height-12)
        root.geometry(f'{x:+d}{y:+d}')

    def focus_out(self, event):
        if self.enabled:
            self.app.root.after(180, self.dismiss_if_inactive)

    def dismiss_if_inactive(self):
        root = self.app.root
        if not self.enabled or root.state() != 'normal' or self.app.busy:
            return
        try:
            # Pop-up lists, date pickers and modal dialogs must remain usable.
            if root.focus_displayof() is not None or root.grab_current() is not None:
                return
            self.app.hide()
        except tk.TclError:
            pass

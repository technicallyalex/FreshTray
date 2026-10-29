"""Fit the rendered pages once at launch, within the usable Windows desktop."""
import calendar
import ctypes
from ctypes import wintypes


def fitted_size(requested, available, chrome=(0, 0), margin=24):
    """Client size; leave room for title bar/borders and a small desktop margin."""
    return tuple(max(1, min(int(wanted), int(space) - frame - margin))
                 for wanted, space, frame in zip(requested, available, chrome))


def work_area(root):
    class MonitorInfo(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT), ('work', wintypes.RECT), ('flags', wintypes.DWORD)]
    user = ctypes.WinDLL('user32')
    user.GetAncestor.argtypes, user.GetAncestor.restype = [wintypes.HWND, wintypes.UINT], wintypes.HWND
    user.MonitorFromWindow.argtypes, user.MonitorFromWindow.restype = [wintypes.HWND, wintypes.DWORD], wintypes.HANDLE
    user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    info = MonitorInfo();info.size = ctypes.sizeof(info)
    monitor = user.MonitorFromWindow(user.GetAncestor(root.winfo_id(), 2), 2)
    if user.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return info.work.left, info.work.top, info.work.right, info.work.bottom
    area = wintypes.RECT()
    if not ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(area), 0):
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
    return area.left, area.top, area.right, area.bottom


def frame_size(root):
    user = ctypes.WinDLL('user32')
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetAncestor.restype = wintypes.HWND
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    rect = wintypes.RECT()
    if user.GetWindowRect(user.GetAncestor(root.winfo_id(), 2), ctypes.byref(rect)):
        return max(0, rect.right-rect.left-root.winfo_width()), max(0, rect.bottom-rect.top-root.winfo_height())
    return 16, 40


class LaunchFit:
    def __init__(self, app):
        self.app = app
        self.pending, self.is_ready, self.job = True, False, None

    def ready(self):
        self.is_ready = True
        self.schedule()

    def schedule(self):
        if self.pending and self.is_ready and self.job is None and self.app.root.state() == 'normal':
            self.job = self.app.root.after_idle(self.fit)

    def fit(self):
        self.job = None
        app, root = self.app, self.app.root
        if not self.pending or root.state() != 'normal':
            return
        self.pending = False
        # Build the history layout for measurement without fetching any time entries.
        if app.businesses and app.profile_data and app.history_window is None:
            from .history import MonthlyView
            app.history_window = MonthlyView(app, app.selected_business(), app.profile_data)
            app.history_window.pack(fill='both', expand=True)
            app.history_window.status.set('Open Monthly hours to load logged time.')
            app.appearance.repaint()
        selected, focus = app.active_page, root.focus_get()
        left, top, right, bottom = work_area(root)
        chrome = frame_size(root)
        available = right-left, bottom-top
        width = max(760, app.pages[selected].min_width + 16)
        if selected == 'history' and app.history_window is not None:
            tree = app.history_window.tree
            width = max(width, app.history_window.preferred_table_width + 64)
        width, _ = fitted_size((width, 760), available, chrome)
        root.geometry(f'{width}x{root.winfo_height()}')
        height = 0
        try:
            # Two passes settle wrapping and responsive columns at the final width.
            for _ in range(3):
                for name, page in [(selected, app.pages[selected])]:
                    app.page_host.select(page)
                    page.activate()
                    root.update_idletasks()
                    measured_width = max(width, page.min_width + 16)
                    measured_width, _ = fitted_size((measured_width, 760), available, chrome)
                    if measured_width != width:
                        width = measured_width
                        root.geometry(f'{width}x{root.winfo_height()}')
                        root.update_idletasks()
                    needed = page.body.winfo_reqheight()
                    if name == 'history' and app.history_window is not None:
                        history = app.history_window
                        weeks = len(calendar.Calendar(6).monthdayscalendar(history.month.year, history.month.month))
                        # Reserve six rows so changing months doesn't clip the details.
                        needed += (6-weeks) * (app.appearance.line_height*2+12)
                    height = max(height, needed)
            height += sum(band.winfo_reqheight() for band in app.shell_bands) + 12
            width, height = fitted_size((width, height), available, chrome)
            x = left + max(0, (right-left-width-chrome[0])//2)
            y = top + max(0, (bottom-top-height-chrome[1])//2)
            root.geometry(f'{width}x{height}{x:+d}{y:+d}')
            if app.prefs.data.get("docked_mode"):
                root.after_idle(app.docking.position)
        finally:
            app.page_host.select(app.pages[selected])
            app.refresh_pages()
            if focus is not None and focus.winfo_exists():
                focus.focus_set()

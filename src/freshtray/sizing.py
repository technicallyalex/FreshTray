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
        self.sizes = {}

    def ready(self):
        self.is_ready = True
        self.schedule()

    def schedule(self):
        if self.pending and self.is_ready and self.job is None and self.app.root.state() == 'normal':
            self.job = self.app.root.after_idle(self.fit)

    def fit(self):
        self.job = None
        app,root = self.app,self.app.root
        if not self.pending or root.state()!='normal':return
        self.pending=False
        selected=app.active_page
        if selected=="history" and app.history_window is None:return
        left,top,right,bottom=work_area(root)
        chrome=frame_size(root);available=(right-left,bottom-top)
        key=(selected,app.appearance.current,float(root.tk.call('tk','scaling')),bool(app.editing_entry),app.settings_window.connection_expanded,app.prefs.data.get("business_id"),available)
        def commit(width,height):
            width,height=fitted_size((width,height),available,chrome)
            x=max(left,min(root.winfo_x(),right-width-chrome[0]))
            y=max(top,min(root.winfo_y(),bottom-height-chrome[1]))
            if app.prefs.data.get('docked_mode'):
                x=max(left,right-width-chrome[0]-12);y=max(top,bottom-height-chrome[1]-12)
            self.sizes[key]=(width,height)
            app.pages[selected].viewport.measure_width = None
            app.transition.resize(width,height,x,y)
            app.pages[selected].activate()
        cached=self.sizes.get(key)
        if cached:
            commit(*cached);return
        width=max(760,app.pages[selected].min_width+16)
        if selected=='history' and app.history_window is not None:
            width=max(width,app.history_window.preferred_table_width+64)
        width,_=fitted_size((width,760),available,chrome)
        app.pages[selected].viewport.measure_width = width
        app.pages[selected].viewport.schedule()
        # Let Tk lay out naturally; never pump a nested idle/event loop during resize.
        def measure(attempt=0):
            if not root.winfo_exists():return
            if app.active_page!=selected:
                app.pages[selected].viewport.measure_width=None
                app.pages[selected].sync()
                return
            page=app.pages[selected]
            measured,_=fitted_size((max(width,page.min_width+16),760),available,chrome)
            if abs(page.body.winfo_width()-measured)>20 and attempt<2:
                page.viewport.measure_width=measured
                page.viewport.schedule()
                root.after(16,lambda:measure(attempt+1));return
            height=page.body.winfo_reqheight()+sum(b.winfo_reqheight() for b in app.shell_bands)+12
            if selected=='history' and app.history_window is not None:
                h=app.history_window
                weeks=len(calendar.Calendar(6).monthdayscalendar(h.month.year,h.month.month))
                height+=(6-weeks)*(app.appearance.line_height*2+12)
            commit(measured,height)
        root.after(16,measure)

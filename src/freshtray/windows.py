"""Small native Windows tray adapter. All callbacks are queued for Tk's thread."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import queue
import subprocess
import sys
import threading
import winreg

user = c.WinDLL("user32", use_last_error=True)
shell = c.WinDLL("shell32", use_last_error=True)
kernel = c.WinDLL("kernel32", use_last_error=True)
LRESULT = c.c_ssize_t
WNDPROC = c.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)


class WindowClass(c.Structure):
    _fields_ = [("style", w.UINT), ("proc", WNDPROC), ("clsExtra", c.c_int), ("wndExtra", c.c_int),
                ("instance", w.HINSTANCE), ("icon", w.HICON), ("cursor", w.HANDLE),
                ("background", w.HBRUSH), ("menuName", w.LPCWSTR), ("className", w.LPCWSTR)]


class NotifyData(c.Structure):
    _fields_ = [("size", w.DWORD), ("hwnd", w.HWND), ("id", w.UINT), ("flags", w.UINT),
                ("callback", w.UINT), ("icon", w.HICON), ("tip", w.WCHAR * 128),
                ("state", w.DWORD), ("stateMask", w.DWORD), ("info", w.WCHAR * 256),
                ("timeout", w.UINT), ("title", w.WCHAR * 64), ("infoFlags", w.DWORD),
                ("guid", c.c_byte * 16), ("balloonIcon", w.HICON)]


def signature(dll, name, args, result):
    function = getattr(dll, name)
    function.argtypes, function.restype = args, result
    return function


signature(kernel, "GetModuleHandleW", [w.LPCWSTR], w.HMODULE)
signature(kernel, "CreateMutexW", [c.c_void_p, w.BOOL, w.LPCWSTR], w.HANDLE)
signature(kernel, "CloseHandle", [w.HANDLE], w.BOOL)
signature(user, "RegisterClassW", [c.POINTER(WindowClass)], w.WORD)
signature(user, "CreateWindowExW", [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, c.c_int, c.c_int,
          c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p], w.HWND)
signature(user, "DefWindowProcW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM], LRESULT)
signature(user, "PostMessageW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL)
signature(user, "DestroyWindow", [w.HWND], w.BOOL)
signature(user, "LoadImageW", [w.HINSTANCE, w.LPCWSTR, w.UINT, c.c_int, c.c_int, w.UINT], w.HANDLE)
signature(user, "DestroyIcon", [w.HICON], w.BOOL)
signature(user, "CreatePopupMenu", [], w.HMENU)
signature(user, "AppendMenuW", [w.HMENU, w.UINT, c.c_size_t, w.LPCWSTR], w.BOOL)
signature(user, "TrackPopupMenu", [w.HMENU, w.UINT, c.c_int, c.c_int, c.c_int, w.HWND, c.c_void_p], w.UINT)
signature(user, "DestroyMenu", [w.HMENU], w.BOOL)
signature(user, "SetForegroundWindow", [w.HWND], w.BOOL)
signature(user, "GetCursorPos", [c.POINTER(w.POINT)], w.BOOL)
signature(user, "GetMessageW", [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT], w.BOOL)
signature(user, "TranslateMessage", [c.POINTER(w.MSG)], w.BOOL)
signature(user, "DispatchMessageW", [c.POINTER(w.MSG)], LRESULT)
signature(user, "RegisterWindowMessageW", [w.LPCWSTR], w.UINT)
signature(shell, "Shell_NotifyIconW", [w.DWORD, c.POINTER(NotifyData)], w.BOOL)


class SingleInstance:
    def __init__(self, demo=False):
        self.handle = kernel.CreateMutexW(None, False, "Local\\FreshTray.Personal." + ("Demo" if demo else "Live"))
        if not self.handle:
            raise OSError("Could not create the FreshTray instance lock.")
        self.exists = c.get_last_error() == 183

    def close(self):
        if self.handle:
            kernel.CloseHandle(self.handle)
            self.handle = None


class Tray:
    def __init__(self, events, icon_path):
        self.events = events
        self.icon_path = str(icon_path)
        self.hwnd = None
        self.ready = threading.Event()
        self.notifications = queue.Queue()
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        if not self.ready.wait(5) or self.error:
            raise OSError(self.error or "Windows tray did not initialize.")

    def _run(self):
        try:
            self._pump()
        except Exception:
            self.error = "Could not add the Windows tray icon. Restart the app."
            self.ready.set()
            self.events.put(("tray_error", self.error))

    def _pump(self):
        taskbar_created = user.RegisterWindowMessageW("TaskbarCreated")

        @WNDPROC
        def callback(hwnd, message, wp, lp):
            if message == 0x8001:
                if lp in (0x0202, 0x0203, 0x0405):  # click, double click, balloon click
                    self.events.put(("show", None))
                elif lp in (0x0205, 0x007B):
                    menu = user.CreatePopupMenu()
                    for ident, title in [(1, "Log time"), (5, "Monthly hours"), (2, "Settings"), (3, "Test notification"), (4, "Quit FreshTray")]:
                        user.AppendMenuW(menu, 0, ident, title)
                    point = w.POINT()
                    user.GetCursorPos(c.byref(point))
                    user.SetForegroundWindow(hwnd)
                    selection = user.TrackPopupMenu(menu, 0x100 | 0x2, point.x, point.y, 0, hwnd, None)
                    user.DestroyMenu(menu)
                    if selection:
                        self.events.put(({1: "show", 2: "settings", 3: "notify", 4: "quit", 5: "history"}[selection], None))
                    user.PostMessageW(hwnd, 0, 0, 0)
                return 0
            if message == 0x8002:
                while not self.notifications.empty():
                    title, text = self.notifications.get()
                    self.data.flags = 0x10
                    self.data.title, self.data.info, self.data.infoFlags = title[:63], text[:255], 1
                    shell.Shell_NotifyIconW(1, c.byref(self.data))
                return 0
            if message == taskbar_created:
                self._add()
                return 0
            if message == 0x0010:
                user.DestroyWindow(hwnd)
                return 0
            if message == 0x0002:
                shell.Shell_NotifyIconW(2, c.byref(self.data))
                user.PostQuitMessage(0)
                return 0
            return user.DefWindowProcW(hwnd, message, wp, lp)

        self.callback = callback
        instance = kernel.GetModuleHandleW(None)
        name = "FreshTray.MessageWindow"
        wc = WindowClass(proc=callback, instance=instance, className=name)
        if not user.RegisterClassW(c.byref(wc)):
            raise OSError()
        self.hwnd = user.CreateWindowExW(0, name, name, 0, 0, 0, 0, 0, None, None, instance, None)
        if not self.hwnd:
            raise OSError()
        self.icon = user.LoadImageW(None, self.icon_path, 1, 32, 32, 0x10)
        if not self.icon:
            raise OSError()
        self.data = NotifyData(size=c.sizeof(NotifyData), hwnd=self.hwnd, id=1, callback=0x8001, icon=self.icon)
        self._add()
        self.ready.set()
        message = w.MSG()
        while user.GetMessageW(c.byref(message), None, 0, 0) > 0:
            user.TranslateMessage(c.byref(message))
            user.DispatchMessageW(c.byref(message))
        user.DestroyIcon(self.icon)

    def _add(self):
        self.data.flags = 1 | 2 | 4
        self.data.tip = "FreshTray — click to log time"
        if not shell.Shell_NotifyIconW(0, c.byref(self.data)):
            raise OSError()

    def notify(self, title="Time to log your hours", text="Click here or the FreshTray clock to log today's work."):
        self.notifications.put((title, text))
        user.PostMessageW(self.hwnd, 0x8002, 0, 0)

    def close(self):
        if self.hwnd:
            user.PostMessageW(self.hwnd, 0x0010, 0, 0)
            self.thread.join(timeout=2)


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, "FreshTray")
            return True
    except FileNotFoundError:
        return False


def set_startup(enabled, launcher):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            if getattr(sys, "frozen", False):
                command = [sys.executable, "--background"]
            else:
                pythonw = Path(sys.executable).with_name("pythonw.exe")
                command = [str(pythonw), str(Path(launcher).resolve()), "--background"]
            winreg.SetValueEx(key, "FreshTray", 0, winreg.REG_SZ, subprocess.list2cmdline(command))
        else:
            try:
                winreg.DeleteValue(key, "FreshTray")
            except FileNotFoundError:
                pass

"""One shared light/dark palette and font-aware sizing for every app view."""
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, font
import winreg
from .fonts import application_fonts
from .refined_theme import apply_refinement

# Light colors are from FreshBooks' public mui app stylesheet (2026-10-28).
# Dark values are a contrast-preserving desktop adaptation of that palette.
PALETTES = {
    "light": {"bg": "#F7F9FC", "panel": "#FFFFFF", "field": "#FFFFFF", "ink": "#001B40",
              "muted": "#576981", "border": "#D6DCE5", "hover": "#EEF6FC", "accent": "#038A06",
              "accent_hover": "#027505", "accent_text": "#FFFFFF", "selection": "#E2F0FB", "disabled": "#7F8C9F",
              "subtle": "#F2F3F5", "warning": "#946400", "blue": "#0075DD", "header": "#FFFFFF",
              "header_text": "#001B40", "header_muted": "#576981", "scroll_thumb": "#B8C1CD", "scroll_hover": "#7F8C9F"},
    "dark": {"bg": "#101B2A", "panel": "#17273B", "field": "#122237", "ink": "#EEF6FC",
             "muted": "#AAB9CB", "border": "#3D5069", "hover": "#233C58", "accent": "#4CC66A",
             "accent_hover": "#70D789", "accent_text": "#001B40", "selection": "#153D60", "disabled": "#8293AB",
             "subtle": "#1C2E43", "warning": "#FFC414", "blue": "#64B5F6", "header": "#17273B",
             "header_text": "#EEF6FC", "header_muted": "#AAB9CB", "scroll_thumb": "#52647D", "scroll_hover": "#7F8C9F"},
}


def system_theme():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return "light" if winreg.QueryValueEx(key, "AppsUseLightTheme")[0] else "dark"
    except OSError:
        return "light"


def resolved_theme(mode):
    return system_theme() if mode == "system" else (mode if mode in PALETTES else "light")


class Appearance:
    def __init__(self, root, mode="system"):
        self.root, self.mode, self.current = root, mode, None
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.fonts = application_fonts(root)
        self.line_height = self.fonts["AppBody"].metrics("linespace")
        self.apply(mode)

    def apply(self, mode=None):
        if mode is not None:
            self.mode = mode
        target = resolved_theme(self.mode)
        if target == self.current and hasattr(self, "palette"):
            return
        self.current = target
        p, s = PALETTES[self.current], self.style
        self.palette = p
        s.configure(".", font="AppBody", background=p["bg"], foreground=p["ink"], bordercolor=p["border"],
                    lightcolor=p["border"], darkcolor=p["border"], troughcolor=p["subtle"], selectbackground=p["selection"], selectforeground=p["ink"])
        s.configure("TFrame", background=p["bg"])
        s.configure("Pages.TNotebook", background=p["bg"], borderwidth=0, padding=0)
        s.layout("Pages.TNotebook.Tab", [])
        s.configure("Card.TFrame", background=p["panel"], relief="solid", borderwidth=1)
        s.configure("CardBody.TFrame", background=p["panel"])
        s.configure("Header.TFrame", background=p["header"])
        s.configure("HeaderMuted.TLabel", background=p["header"], foreground=p["header_muted"], font="AppSmall")
        s.configure("TLabel", background=p["bg"], foreground=p["ink"])
        s.configure("Card.TLabel", background=p["panel"], foreground=p["ink"])
        s.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"], font="AppSmall")
        s.configure("CardMuted.TLabel", background=p["panel"], foreground=p["muted"], font="AppSmall")
        s.configure("Title.TLabel", font="AppTitle")
        s.configure("Section.TLabel", background=p["panel"], font="AppSection")
        s.configure("Brand.TLabel", background=p["header"], foreground=p["blue"], font="AppBrand")
        s.configure("Warning.TLabel", foreground=p["warning"])
        s.configure("TButton", background=p["panel"], foreground=p["ink"], padding=(10, 5), borderwidth=1, relief="flat",
                    focuscolor=p["blue"], font="AppButton", anchor="center")
        s.map("TButton", background=[("disabled", p["subtle"]), ("pressed", p["selection"]), ("active", p["hover"])],
              foreground=[("disabled", p["disabled"])], bordercolor=[("focus", p["blue"])])
        s.configure("Accent.TButton", background=p["accent"], foreground=p["accent_text"], font="AppHeading")
        s.map("Accent.TButton", background=[("disabled", p["subtle"]), ("active", p["accent_hover"])],
              foreground=[("disabled", p["disabled"]), ("!disabled", p["accent_text"])])
        s.configure("Caption.TButton", background=p["header"], foreground=p["header_text"], padding=(6, 3), borderwidth=0)
        s.map("Caption.TButton", background=[("active", "#164B91")], foreground=[("!disabled", "#FFFFFF")])
        s.configure("Nav.TButton", background=p["bg"], borderwidth=0, padding=(14, 6))
        s.configure("NavActive.TButton", background=p["selection"], foreground=p["blue"], borderwidth=0,
                    font="AppHeading", padding=(14, 6))
        s.map("NavActive.TButton", background=[("active", p["selection"])])
        for name in ("TEntry", "TCombobox", "TSpinbox"):
            s.configure(name, fieldbackground=p["field"], background=p["subtle"], foreground=p["ink"],
                        insertcolor=p["ink"], padding=5, arrowcolor=p["ink"], bordercolor=p["border"], selectbackground=p["selection"], selectforeground=p["ink"])
            s.map(name, fieldbackground=[("disabled", p["subtle"]), ("readonly", p["field"])],
                  foreground=[("disabled", p["disabled"]), ("readonly", p["ink"])], bordercolor=[("focus", p["blue"])])
        s.configure("TCheckbutton", background=p["panel"], foreground=p["ink"], padding=(0, 3),
                    indicatorbackground=p["field"], indicatorforeground=p["accent"], indicatormargin=(0, 0, 8, 0))
        s.map("TCheckbutton", background=[("active", p["panel"])], foreground=[("disabled", p["disabled"])])
        s.configure("Treeview", background=p["panel"], fieldbackground=p["panel"], foreground=p["ink"],
                    rowheight=self.line_height + 10, borderwidth=0, font="AppBody")
        s.map("Treeview", background=[("selected", p["selection"])], foreground=[("selected", p["ink"])])
        s.configure("Treeview.Heading", background=p["subtle"], foreground=p["muted"], padding=(7, 5),
                    font="AppHeading", relief="flat")
        s.map("Treeview.Heading", background=[("active", p["hover"])])
        s.configure("CalendarLegend.TLabel", background=p["panel"], foreground=p["blue"], font="AppSmall")
        s.configure("MonthDay.TButton", borderwidth=0, background=p["panel"], anchor="nw", padding=(7, 5), font="AppBody")
        s.configure("SelectedMonthDay.TButton", borderwidth=0, background=p["selection"], anchor="nw", padding=(7, 5),
                    foreground=p["ink"], font="AppHeading")
        s.map("SelectedMonthDay.TButton", background=[("active", p["selection"]), ("disabled", p["subtle"])],
              foreground=[("disabled", p["disabled"]), ("!disabled", p["ink"])])
        s.configure("WeekTotal.TLabel", background=p["subtle"], foreground=p["ink"], padding=(5, 5), font="AppHeading")
        s.configure("OutsideMonth.TLabel", background=p["subtle"])
        s.configure("Calendar.TButton", width=3, padding=(5, 4))
        s.configure("SelectedDay.TButton", width=3, padding=(5, 4), background=p["blue"], foreground="#FFFFFF")
        s.map("SelectedDay.TButton", background=[("active", p["blue"])], foreground=[("!disabled", "#FFFFFF")])
        self.root.option_add("*TCombobox*Listbox.background", p["field"])
        self.root.option_add("*TCombobox*Listbox.foreground", p["ink"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", p["selection"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", p["ink"])
        # Native dropdown scrollbars use the same quiet, arrowless treatment.
        for orientation in ("Vertical", "Horizontal"):
            name = orientation + ".TScrollbar"
            prefix = orientation + ".Scrollbar."
            s.layout(name, [(prefix + "trough", {"sticky": "nswe", "children": [
                (prefix + "thumb", {"expand": "1", "sticky": "nswe"})]})])
            s.configure(name, background=p["scroll_thumb"], troughcolor=p["panel"],
                        bordercolor=p["panel"], lightcolor=p["scroll_thumb"], darkcolor=p["scroll_thumb"],
                        borderwidth=0, relief="flat", width=9, arrowsize=0)
            s.map(name, background=[("active", p["scroll_hover"])])
        apply_refinement(self)
        self.repaint()
        self.root.event_generate("<<AppearanceChanged>>", when="tail")

    def repaint(self):
        p = self.palette
        def walk(widget):
            if isinstance(widget, (tk.Tk, tk.Toplevel)):
                widget.configure(background=p["bg"])
                self.caption(widget)
            elif hasattr(widget, "apply_palette"):
                widget.apply_palette(p)
            elif isinstance(widget, tk.Canvas):
                widget.configure(background=p["bg"], highlightthickness=0)
            elif isinstance(widget, tk.Text):
                widget.configure(background=p["field"], foreground=p["ink"], insertbackground=p["ink"],
                                 selectbackground=p["selection"], selectforeground=p["ink"],
                                 highlightbackground=p["border"], highlightcolor=p["blue"])
            for child in widget.winfo_children():
                walk(child)
        walk(self.root)

    def caption(self, window):
        try:
            user = ctypes.WinDLL("user32")
            user.GetAncestor.argtypes, user.GetAncestor.restype = [wintypes.HWND, wintypes.UINT], wintypes.HWND
            hwnd = user.GetAncestor(window.winfo_id(), 2)
            dark = wintypes.BOOL(self.current == "dark")
            function = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
            function.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            function(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        except (OSError, AttributeError, tk.TclError):
            pass

    def refresh_system(self):
        if resolved_theme(self.mode) != self.current:
            self.apply()

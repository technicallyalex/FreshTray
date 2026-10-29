"""Responsive layout primitives shared by form, settings and monthly history."""
import tkinter as tk
from tkinter import ttk
from .scrollbars import SlimScrollbar
from .viewport import Viewport


class CalendarGrid(tk.Frame):
    """Palette-aware one-pixel lines between every calendar cell."""
    def __init__(self, parent):
        super().__init__(parent, borderwidth=0, highlightthickness=0, padx=1, pady=1)

    def apply_palette(self, palette):
        self.configure(background=palette["border"])


class ScrollPage(ttk.Frame):
    def __init__(self, parent, min_width=500):
        super().__init__(parent)
        self.min_width = min_width
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.viewport = Viewport(self, min_width)
        # Keep the view API name used by mouse-wheel handling and existing checks.
        self.canvas = self.viewport
        self.viewport.grid(row=0, column=0, sticky="nsew")
        self.vscroll = SlimScrollbar(self, orient="vertical", command=self.viewport.yview)
        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.hscroll = SlimScrollbar(self, orient="horizontal", command=self.viewport.xview)
        self.hscroll.grid(row=1, column=0, sticky="ew")
        self.viewport.yscrollcommand = self.vscroll.set
        self.viewport.xscrollcommand = self.hscroll.set
        self.body = ttk.Frame(self.viewport, padding=(14, 10, 14, 12))
        self.viewport.set_content(self.body)
        self.bind("<Map>", lambda event: self.activate(), add="+")

    def sync(self, event=None):
        self.viewport.min_width = self.min_width
        self.viewport.schedule()

    def activate(self):
        self.viewport.min_width = self.min_width
        self.viewport.activate()

    def top(self):
        self.viewport.yview_moveto(0)

    def reveal(self, widget):
        """Bring an embedded editor into view without switching pages."""
        def scroll():
            if not widget.winfo_exists():
                return
            self.update_idletasks()
            self.viewport.refresh()
            start = widget.winfo_rooty() - self.body.winfo_rooty() - 10
            end = start + widget.winfo_height() + 20
            height = self.viewport.winfo_height()
            current = self.viewport.offset_y
            target = start if start < current or end-start > height else max(current, end-height)
            self.viewport.yview_moveto(max(0, target) / max(1, self.viewport.content_height))
        self.after_idle(scroll)


class WrapLabel(ttk.Label):
    def __init__(self, parent, **options):
        super().__init__(parent, **options)
        self.bind("<Configure>", self.wrap, add="+")

    def wrap(self, event):
        width = max(120, event.width - 6)
        if int(self.cget("wraplength") or 0) != width:
            self.configure(wraplength=width)


def card(parent, title=None, subtitle=None):
    outer = ttk.Frame(parent, style="Card.TFrame", padding=10)
    outer.pack(fill="x", pady=(0, 8))
    if title:
        ttk.Label(outer, text=title, style="Section.TLabel").pack(anchor="w", pady=(0, 4))
    if subtitle:
        WrapLabel(outer, text=subtitle, style="CardMuted.TLabel").pack(fill="x", pady=(0, 7))
    return outer


class FieldPair(ttk.Frame):
    """Stack at small widths instead of truncating the second field."""
    def __init__(self, parent, threshold=490):
        super().__init__(parent, style="CardBody.TFrame")
        self.left = ttk.Frame(self, style="CardBody.TFrame")
        self.right = ttk.Frame(self, style="CardBody.TFrame")
        self.threshold, self.stacked = threshold, None
        self.pack(fill="x", pady=(0, 7))
        self.bind("<Configure>", self.layout)

    def layout(self, event):
        stack = event.width < self.threshold
        if stack == self.stacked:
            return
        self.stacked = stack
        self.left.grid_forget()
        self.right.grid_forget()
        self.columnconfigure(0, weight=1, uniform="" if stack else "pair")
        self.columnconfigure(1, weight=0 if stack else 1, uniform="" if stack else "pair", minsize=0)
        self.left.grid(row=0, column=0, sticky="ew", padx=(0, 0 if stack else 8))
        self.right.grid(row=1 if stack else 0, column=0 if stack else 1, sticky="ew",
                        padx=(0 if stack else 8, 0), pady=(8 if stack else 0, 0))


def field_label(parent, text):
    ttk.Label(parent, text=text, style="CardMuted.TLabel").pack(anchor="w", pady=(0, 3))


def note_field(parent, height=4, readonly=False):
    frame = ttk.Frame(parent, style="CardBody.TFrame")
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    text = tk.Text(frame, height=height, width=20, wrap="word", font="AppBody",
                   relief="flat", borderwidth=0, highlightthickness=1, padx=8, pady=6,
                   undo=not readonly, state="disabled" if readonly else "normal")
    text.grid(row=0, column=0, sticky="nsew")
    bar = SlimScrollbar(frame, orient="vertical", command=text.yview, surface="field")
    bar.grid(row=0, column=1, sticky="ns")
    text.configure(yscrollcommand=bar.set)
    return text


class CalendarIcon(tk.Canvas):
    """Theme-aware calendar outline with keyboard activation."""
    def __init__(self,parent,command):
        super().__init__(parent,width=34,height=28,borderwidth=0,highlightthickness=0,takefocus=True,cursor='hand2')
        self.command,self.hover,self.enabled=command,False,True
        self.tooltip=Tooltip(self, "Choose entry date (Alt+Down)")
        self.palette={'panel':'#FFFFFF','hover':'#EEF6FC','ink':'#001B40','blue':'#0075DD','disabled':'#7F8C9F'}
        self.bind('<Enter>',lambda _:self.highlight(True))
        self.bind('<Leave>',lambda _:self.highlight(False))
        self.bind('<FocusIn>',lambda _:self.highlight(True))
        self.bind('<FocusOut>',lambda _:self.highlight(False))
        self.bind('<ButtonRelease-1>',lambda e:self.invoke() if 0<=e.x<34 and 0<=e.y<28 else None)
        self.bind('<Return>',lambda _:self.invoke())
        self.bind('<space>',lambda _:self.invoke())
        self.paint()

    def configure(self,cnf=None,**options):
        if 'state' in options:
            self.enabled=options['state']!='disabled'
        result=super().configure(cnf,**options)
        if hasattr(self,'palette'):self.paint()
        return result
    config=configure

    def highlight(self,value):
        self.hover=value
        self.paint()

    def apply_palette(self,palette):
        self.palette=palette
        self.paint()

    def paint(self):
        p=self.palette
        # Call the base method to avoid recursion through configure.
        tk.Canvas.configure(self,background=p['hover'] if self.hover and self.enabled else p['panel'])
        self.delete('all')
        ink=p['blue'] if self.enabled else p['disabled']
        self.create_rectangle(9,7,25,22,outline=ink,width=1.5)
        self.create_line(9,12,25,12,fill=ink,width=1.5)
        for x in (13,21):self.create_line(x,5,x,9,fill=ink,width=2)
        for x in (13,17,21):
            for y in (16,19):self.create_rectangle(x,y,x+1,y+1,fill=ink,outline=ink)

    def invoke(self):
        if self.enabled:self.command()


class Tooltip:
    """Short keyboard/mouse help for icon-only controls."""
    def __init__(self, widget, text):
        self.widget,self.text,self.job,self.tip=widget,text,None,None
        widget.bind('<Enter>',self.schedule,add='+')
        widget.bind('<FocusIn>',self.schedule,add='+')
        for event in ('<Leave>','<FocusOut>','<ButtonPress>','<Destroy>'):
            widget.bind(event,self.hide,add='+')
    def schedule(self,event=None):
        self.hide()
        self.job=self.widget.after(600,self.show)
    def show(self):
        self.job=None
        if not self.widget.winfo_exists() or not self.widget.winfo_ismapped():return
        self.tip=tk.Toplevel(self.widget);self.tip.overrideredirect(True)
        ttk.Label(self.tip,text=self.text,padding=(8,4)).pack()
        self.tip.geometry(f'{self.widget.winfo_rootx():+d}{self.widget.winfo_rooty()+self.widget.winfo_height()+3:+d}')
    def hide(self,event=None):
        if self.job is not None:
            self.widget.after_cancel(self.job);self.job=None
        if self.tip is not None:
            self.tip.destroy();self.tip=None

"""Transient in-panel feedback and cancellable window-size transitions."""
import time
import ctypes
from ctypes import wintypes
from tkinter import ttk

class Feedback:
    def __init__(self,app):self.app=app;self.widget=None;self.timer=None
    def show(self,text):
        self.clear()
        self.widget=ttk.Frame(self.app.root,style='Card.TFrame',padding=12)
        ttk.Label(self.widget,text=text,style='Card.TLabel',wraplength=340).pack()
        self.widget.place(relx=1,x=-18,y=self.app.page_host.winfo_y()+14,anchor='ne')
        self.widget.lift()
        self.timer=self.app.root.after(3500,self.clear)
    def clear(self):
        if self.timer is not None:self.app.root.after_cancel(self.timer);self.timer=None
        if self.widget is not None:self.widget.destroy();self.widget=None

class PanelTransition:
    def __init__(self,app):self.app=app;self.job=None;self.active=False
    def cancel(self):
        if self.job is not None:self.app.root.after_cancel(self.job);self.job=None
        self.active=False
    def resize(self,width,height,x,y):
        self.cancel();root=self.app.root
        start=(root.winfo_width(),root.winfo_height(),root.winfo_x(),root.winfo_y())
        end=(width,height,x,y)
        reduced=wintypes.BOOL(True)
        try:ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(reduced),0)
        except (OSError,AttributeError):pass
        if not reduced.value or root.state()!='normal' or start==end:
            root.geometry(f'{width}x{height}{x:+d}{y:+d}');self.app.chrome.thaw();return
        self.active=True;began=time.monotonic()
        def frame():
            if root.state()!='normal':self.cancel();self.app.chrome.thaw();return
            t=min(1,(time.monotonic()-began)/.18)
            progress=t*t*(3-2*t)
            w,h,left,top=(round(a+(b-a)*progress) for a,b in zip(start,end))
            root.geometry(f'{w}x{h}{left:+d}{top:+d}')
            if t<1:self.job=root.after(16,frame)
            else:
                self.job=None;self.active=False
                self.app.pages[self.app.active_page].activate();self.app.chrome.thaw()
        frame()

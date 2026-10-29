"""Slim app title bar while retaining Windows resize and minimize behavior."""
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk
from .components import Tooltip

class WindowChrome:
    def __init__(self, app, header):
        self.app, self.root = app, app.root
        self.user = ctypes.WinDLL('user32')
        self.user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user.GetAncestor.restype = wintypes.HWND
        self.user.SendMessageW.argtypes = [wintypes.HWND,wintypes.UINT,ctypes.c_size_t,ctypes.c_ssize_t]
        self.user.SetWindowPos.argtypes = [wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        self.user.GetWindowLongW.argtypes = [wintypes.HWND,ctypes.c_int]
        self.user.SetWindowLongW.argtypes = [wintypes.HWND,ctypes.c_int,ctypes.c_long]
        self.user.RedrawWindow.argtypes = [wintypes.HWND,ctypes.c_void_p,ctypes.c_void_p,wintypes.UINT]
        self.frozen = False
        controls = ttk.Frame(header,style='Header.TFrame')
        controls.grid(row=0,column=2,padx=(12,0))
        self.icons=[]
        for kind, command in [('minimize',self.minimize), ('maximize',self.maximize), ('close',app.close_window)]:
            icon=CaptionIcon(controls,kind,command)
            icon.pack(side='left',padx=3)
            self.icons.append(icon)
        for widget in [header]+[c for c in header.winfo_children() if c is not controls]:
            widget.bind('<ButtonPress-1>',self.drag_start)
            widget.bind('<B1-Motion>',self.drag)
            widget.bind('<ButtonRelease-1>',self.drag_end)
            widget.bind('<Double-Button-1>',lambda _:self.maximize())
        self.root.bind('<Map>',lambda e:self.root.after_idle(self.apply) if e.widget is self.root else None,add='+')
        self.root.after_idle(self.apply)

    def hwnd(self):
        return self.user.GetAncestor(self.root.winfo_id(),2)

    def apply(self):
        if not self.root.winfo_exists():return
        hwnd=self.hwnd()
        style=self.user.GetWindowLongW(hwnd,-16)
        if not style & 0x00C00000:return
        self.user.SetWindowLongW(hwnd,-16,style & ~0x00C00000)
        self.user.SetWindowPos(hwnd,None,0,0,0,0,0x37)

    def drag_start(self,event):
        self.drag_end()
        rect=wintypes.RECT()
        self.user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        self.user.GetWindowRect(self.hwnd(),ctypes.byref(rect))
        self.drag_origin=(event.x_root,event.y_root,rect.left,rect.top)
        self.drag_target=None
        self.drag_job=None

    def drag(self,event):
        if self.app.prefs.data.get('docked_mode') or self.root.state()!='normal':return
        if not hasattr(self,'drag_origin'):return
        x,y,left,top=self.drag_origin
        self.drag_target=(left+event.x_root-x,top+event.y_root-y)
        if self.drag_job is None:
            self.drag_job=self.root.after(16,self.move_frame)

    def move_frame(self):
        self.drag_job=None
        target=getattr(self,'drag_target',None)
        if target is not None and self.root.winfo_exists() and self.root.state()=='normal':
            # Move the native wrapper without asking Tk to recompute client geometry.
            self.user.SetWindowPos(self.hwnd(),None,target[0],target[1],0,0,0x15)
            self.drag_target=None

    def drag_end(self,event=None):
        job=getattr(self,'drag_job',None)
        if job is not None:
            self.root.after_cancel(job)
            self.drag_job=None
        self.move_frame()
        if hasattr(self,'drag_origin'):
            del self.drag_origin
            self.user.RedrawWindow(self.hwnd(),None,None,0x185)
            self.app.pages[self.app.active_page].activate()

    def minimize(self):
        self.root.iconify()

    def maximize(self):
        if not self.app.prefs.data.get('docked_mode'):
            self.root.state('normal' if self.root.state()=='zoomed' else 'zoomed')

    def freeze(self):
        if not self.frozen:
            self.frozen=True
            self.cover=ttk.Frame(self.app.page_host)
            self.cover.place(x=0,y=0,relwidth=1,relheight=1)
            self.cover.lift()

    def thaw(self):
        if self.frozen:
            self.cover.destroy()
            self.frozen=False


class CaptionIcon(tk.Canvas):
    """Crisp line controls, keyboard focus and quiet branded hover surfaces."""
    def __init__(self,parent,kind,command):
        super().__init__(parent,width=32,height=28,highlightthickness=0,borderwidth=0,takefocus=True,cursor='hand2')
        self.kind,self.command,self.hover=kind,command,False
        self.tooltip=Tooltip(self, {"close":"Close", "minimize":"Minimize", "maximize":"Maximize / Restore"}[kind])
        self.palette={'header':'#002D79','header_text':'#FFFFFF'}
        self.bind('<Enter>',lambda _:self.set_hover(True))
        self.bind('<Leave>',lambda _:self.set_hover(False))
        self.bind('<ButtonRelease-1>',lambda e:command() if 0<=e.x<32 and 0<=e.y<28 else None)
        self.bind('<Return>',lambda _:command())
        self.bind('<space>',lambda _:command())
        self.bind('<FocusIn>',lambda _:self.set_hover(True))
        self.bind('<FocusOut>',lambda _:self.set_hover(False))
        self.paint()

    def set_hover(self,value):
        self.hover=value
        self.paint()

    def apply_palette(self,palette):
        self.palette=palette
        self.paint()

    def paint(self):
        bg=('#B62D42' if self.kind=='close' else '#164B91') if self.hover else self.palette['header']
        self.configure(background=bg)
        self.delete('all')
        ink=self.palette['header_text']
        if self.kind=='minimize':self.create_line(11,17,21,17,fill=ink,width=1.5)
        elif self.kind=='maximize':self.create_rectangle(11,9,21,19,outline=ink,width=1.5)
        else:
            self.create_line(12,10,20,18,fill=ink,width=1.5)
            self.create_line(20,10,12,18,fill=ink,width=1.5)

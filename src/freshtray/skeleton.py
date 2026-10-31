"""Static, theme-aware placeholders shown only for actual slow API work."""
import tkinter as tk

class LoadingSkeleton:
    def __init__(self,app):self.app=app;self.job=None;self.cover=None
    def start(self,future):
        self.stop();page=self.app.pages[self.app.active_page]
        def show():
            self.job=None
            if future.done() or not page.winfo_ismapped():return
            p=self.app.appearance.palette
            self.cover=tk.Canvas(page,background=p['bg'],highlightthickness=0)
            self.cover.place(x=0,y=0,relwidth=1,relheight=1);self.cover.tk.call("raise", self.cover._w)
            width=max(300,page.winfo_width()-40)
            self.cover.create_text(20,25,text='Loading from FreshBooks…',anchor='w',fill=p['muted'],font='AppBody')
            if page is self.app.pages['history']:
                for row in range(5):
                    for column in range(7):
                        x=20+column*width/7;y=65+row*42
                        self.cover.create_rectangle(x,y,x+width/7-4,y+36,fill=p['subtle'],outline='')
                return
            for y,w in ((60,.4),(95,1),(140,.7),(185,1),(230,.8),(275,1)):
                self.cover.create_rectangle(20,y,20+width*w,y+18,fill=p['subtle'],outline='')
        self.job=self.app.root.after(120,show)
    def stop(self):
        if self.job is not None:self.app.root.after_cancel(self.job);self.job=None
        if self.cover is not None:self.cover.destroy();self.cover=None

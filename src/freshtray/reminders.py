"""Visible, non-modal reminder independent of Windows notification delivery."""
from datetime import date
import tkinter as tk
from tkinter import ttk
from .sizing import work_area

class ReminderPopup(tk.Toplevel):
    def __init__(self,app):
        super().__init__(app.root)
        self.app=app
        self.withdraw()
        self.title('FreshTray - Log your hours')
        self.wm_attributes('-toolwindow',True)
        self.attributes('-topmost',True)
        self.resizable(False,False)
        self.protocol('WM_DELETE_WINDOW',self.dismiss)
        self.bind('<Escape>',lambda _:self.dismiss())
        body=ttk.Frame(self,padding=20);body.pack(fill='both',expand=True)
        ttk.Label(body,text='Time to log your hours',style='Title.TLabel').pack(anchor='w')
        ttk.Label(body,text=date.today().strftime('%A, %B %d'),style='Muted.TLabel').pack(anchor='w',pady=(5,10))
        ttk.Label(body,text='Take a moment to record what you worked on today.',wraplength=340).pack(anchor='w')
        row=ttk.Frame(body);row.pack(fill='x',pady=(18,0))
        ttk.Button(row,text='Dismiss',command=self.dismiss).pack(side='left')
        self.log_button=ttk.Button(row,text='Log hours',style='Accent.TButton',command=self.open_entry)
        self.log_button.pack(side='right')
        self.update_idletasks()
        left,top,right,bottom=work_area(app.root)
        x=left+max(0,(right-left-self.winfo_reqwidth())//2)
        y=top+max(0,(bottom-top-self.winfo_reqheight())//2)
        self.geometry(f'{x:+d}{y:+d}')
        app.appearance.repaint()
        self.deiconify();self.lift()
        self.log_button.focus_set()

    def open_entry(self):
        self.dismiss()
        self.app.show_entry()

    def dismiss(self):
        self.app.reminder_popup=None
        self.destroy()

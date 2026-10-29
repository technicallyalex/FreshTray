"""Date and reminder controls using only the standard Tk library."""
import calendar
import ctypes
from ctypes import wintypes
from datetime import date
import tkinter as tk
from tkinter import ttk

from .model import display_reminder_time, parse_reminder_time


class ReminderTime(ttk.Frame):
    """Display 12-hour time; preserve the scheduler's existing 24-hour format."""

    def __init__(self, parent, stored_value):
        super().__init__(parent, style="CardBody.TFrame")
        try:
            clock, period = display_reminder_time(stored_value)
        except ValueError:
            clock, period = "5:00", "PM"
        self.clock = tk.StringVar(value=clock)
        self.period = tk.StringVar(value=period)
        self.entry = ttk.Entry(self, textvariable=self.clock, width=7)
        self.entry.pack(side="left")
        self.selector = ttk.Combobox(self, textvariable=self.period, values=("AM", "PM"),
                                     state="readonly", width=4)
        self.selector.pack(side="left", padx=(6, 0))

    def value(self):
        return parse_reminder_time(self.clock.get(), self.period.get())


class CalendarPicker(tk.Toplevel):
    """A compact month view with navigation, Today, Cancel and Escape."""

    def __init__(self, anchor, selected, on_select):
        super().__init__(anchor.winfo_toplevel())
        self.withdraw()
        self.anchor, self.selected, self.on_select = anchor, selected, on_select
        self.month = selected.replace(day=1)
        self.title("Choose entry date")
        self.resizable(True, True)
        self.transient(anchor.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda event: self.close())
        self.bind("<Prior>", lambda event: self.shift_month(-1))
        self.bind("<Next>", lambda event: self.shift_month(1))
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        header = ttk.Frame(body)
        header.pack(fill="x", pady=(0, 10))
        self.previous_button = ttk.Button(header, text="‹", width=3,
                                         command=lambda: self.shift_month(-1))
        self.previous_button.pack(side="left")
        self.month_title = tk.StringVar()
        ttk.Label(header, textvariable=self.month_title, anchor="center",
                  font="AppHeading", width=21).pack(side="left", expand=True, fill="x")
        self.next_button = ttk.Button(header, text="›", width=3,
                                     command=lambda: self.shift_month(1))
        self.next_button.pack(side="right")
        self.grid_frame = ttk.Frame(body)
        self.grid_frame.pack(fill="both", expand=True)
        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(9, 0))
        ttk.Button(footer, text="Today", command=lambda: self.select(date.today())).pack(side="left")
        ttk.Button(footer, text="Cancel", command=self.close).pack(side="right")
        self.render()
        self.update_idletasks()
        self.minsize(self.winfo_reqwidth(), self.winfo_reqheight())
        work_area = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(work_area), 0)
        x = max(work_area.left, min(anchor.winfo_rootx(), work_area.right - self.winfo_reqwidth() - 8))
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        if y + self.winfo_reqheight() > work_area.bottom - 8:
            y = anchor.winfo_rooty() - self.winfo_reqheight() - 4
        self.geometry(f"+{x}+{max(work_area.top, y)}")
        self.deiconify()
        self.grab_set()
        focus = self.day_buttons.get(selected)
        (focus or self.previous_button).focus_set()

    def render(self):
        for child in self.grid_frame.winfo_children():
            child.destroy()
        today = date.today()
        self.month_title.set(f"{calendar.month_name[self.month.month]} {self.month.year}")
        self.previous_button.configure(state="disabled" if self.month == date.min else "normal")
        self.next_button.configure(state="disabled" if self.month >= today.replace(day=1) else "normal")
        self.day_buttons = {}
        for row in range(1, 7):
            self.grid_frame.rowconfigure(row, weight=1)
        for column, label in enumerate(("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")):
            ttk.Label(self.grid_frame, text=label, anchor="center", style="Muted.TLabel").grid(
                row=0, column=column, sticky="ew", pady=(0, 5))
            self.grid_frame.columnconfigure(column, weight=1, uniform="day")
        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(self.month.year, self.month.month)
        weeks += [[0] * 7 for _ in range(6 - len(weeks))]
        for row, week in enumerate(weeks, 1):
            for column, day in enumerate(week):
                if not day:
                    ttk.Label(self.grid_frame, text="", width=3, padding=(4, 5)).grid(
                        row=row, column=column, sticky="nsew", padx=1, pady=1)
                    continue
                value = self.month.replace(day=day)
                button = ttk.Button(self.grid_frame, text=str(day),
                                    style="SelectedDay.TButton" if value == self.selected else "Calendar.TButton",
                                    command=lambda chosen=value: self.select(chosen),
                                    state="disabled" if value > today else "normal")
                button.grid(row=row, column=column, sticky="nsew", padx=1, pady=1)
                self.day_buttons[value] = button

    def shift_month(self, offset):
        year, month = divmod(self.month.year * 12 + self.month.month - 1 + offset, 12)
        if not 1 <= year <= 9999:
            return
        candidate = date(year, month + 1, 1)
        if candidate > date.today().replace(day=1):
            return
        self.month = candidate
        self.render()

    def select(self, selected):
        if selected > date.today():
            return
        self.on_select(selected.isoformat())
        self.close()

    def close(self):
        if self.grab_current() == self:
            self.grab_release()
        self.destroy()
        if self.anchor.winfo_exists():
            self.anchor.focus_set()

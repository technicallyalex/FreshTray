"""Scrollable normal child windows, without an embedded Canvas window item."""
import tkinter as tk


class Viewport(tk.Frame):
    def __init__(self, parent, min_width=500):
        super().__init__(parent, width=1, height=1, borderwidth=0, highlightthickness=0)
        self.min_width = min_width
        self.content = None
        self.offset_x = self.offset_y = 0
        self.content_width = self.content_height = 1
        self.xscrollcommand = self.yscrollcommand = None
        self._job = None
        self._geometry = None
        self.bind("<Configure>", self.schedule, add="+")
        self.bind("<Map>", self.schedule, add="+")
        self.bind("<Destroy>", self.cleanup, add="+")

    def set_content(self, widget):
        self.content = widget
        widget.bind("<Configure>", self.schedule, add="+")
        self.schedule()

    def apply_palette(self, palette):
        self.configure(background=palette["bg"])
        self.schedule()

    def schedule(self, event=None):
        if self._job is None:
            self._job = self.after_idle(self.refresh)

    def cleanup(self, event):
        if event.widget == self and self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def refresh(self):
        self._job = None
        if self.content is None or not self.content.winfo_exists():
            return
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        self.content_width = max(self.min_width, width)
        self.content_height = max(1, self.content.winfo_reqheight())
        self.offset_x = min(max(0, self.offset_x), max(0, self.content_width - width))
        self.offset_y = min(max(0, self.offset_y), max(0, self.content_height - height))
        geometry = (-self.offset_x, -self.offset_y, self.content_width, self.content_height)
        if geometry != self._geometry or not self.content.winfo_manager():
            # Keep natural requested height so newly expanded/wrapped content
            # generates Configure events instead of being clipped at an old height.
            self.content.place(x=geometry[0], y=geometry[1], width=geometry[2], height="")
            self._geometry = geometry
        if self.xscrollcommand:
            self.xscrollcommand(*self.xview())
        if self.yscrollcommand:
            self.yscrollcommand(*self.yview())

    def activate(self):
        self._geometry = None
        self.schedule()

    def _view(self, axis, arguments):
        total = self.content_width if axis == "x" else self.content_height
        visible = max(1, self.winfo_width() if axis == "x" else self.winfo_height())
        offset = self.offset_x if axis == "x" else self.offset_y
        if not arguments:
            if total <= visible:
                return 0.0, 1.0
            return offset / total, min(1.0, (offset + visible) / total)
        if arguments[0] == "moveto":
            offset = int(float(arguments[1]) * total)
        elif arguments[0] == "scroll":
            step = max(20, int(visible * .9)) if arguments[2] == "pages" else 28
            offset += int(arguments[1]) * step
        else:
            raise ValueError("Unknown scroll command")
        if axis == "x":
            self.offset_x = offset
        else:
            self.offset_y = offset
        self.refresh()

    def xview(self, *arguments):
        return self._view("x", arguments)

    def yview(self, *arguments):
        return self._view("y", arguments)

    def xview_moveto(self, fraction):
        self.xview("moveto", fraction)

    def yview_moveto(self, fraction):
        self.yview("moveto", fraction)

    def xview_scroll(self, count, units):
        self.xview("scroll", count, units)

    def yview_scroll(self, count, units):
        self.yview("scroll", count, units)

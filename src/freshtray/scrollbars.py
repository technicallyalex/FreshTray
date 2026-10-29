"""Slim, rounded, auto-hiding scrollbars with dragging and keyboard support."""
import tkinter as tk


class SlimScrollbar(tk.Canvas):
    def __init__(self, parent, orient="vertical", command=None, surface="bg", **options):
        self.orient, self.command, self.surface = orient, command, surface
        # A scrollbar must never dictate the content's size along its long axis.
        # Canvas defaults to ~276px high; that can cause auto-hide reflow loops.
        size = {"width": 12, "height": 1} if orient == "vertical" else {"width": 1, "height": 12}
        super().__init__(parent, borderwidth=0, highlightthickness=0, takefocus=0,
                         background="#FFFEFD", **size, **options)
        self.first, self.last, self.is_needed = 0.0, 1.0, False
        self.hover, self.drag_offset = False, None
        self._shown = None
        self.palette = {"bg": "#FFFEFD", "panel": "#FFFFFF", "field": "#FFFFFF",
                        "scroll_thumb": "#B8C1CD", "scroll_hover": "#7F8C9F"}
        self.bind("<Configure>", lambda event: self.draw())
        self.bind("<Enter>", lambda event: self.set_hover(True))
        self.bind("<Leave>", lambda event: self.set_hover(False))
        self.bind("<Button-1>", self.press)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<Up>", lambda event: self.scroll(-1))
        self.bind("<Down>", lambda event: self.scroll(1))
        self.bind("<Left>", lambda event: self.scroll(-1))
        self.bind("<Right>", lambda event: self.scroll(1))
        self.bind("<Prior>", lambda event: self.scroll(-1, "pages"))
        self.bind("<Next>", lambda event: self.scroll(1, "pages"))
        self.bind("<Home>", lambda event: self.move(0))
        self.bind("<End>", lambda event: self.move(1))
        self._visibility_job = self.after_idle(self.initial_visibility)
        self.bind("<Destroy>", self.cleanup, add="+")

    def cleanup(self, event):
        if event.widget == self and self._visibility_job:
            self.after_cancel(self._visibility_job)
            self._visibility_job = None

    def apply_palette(self, palette):
        self.palette = palette
        self.configure(background=palette[self.surface])
        self.draw()

    def set(self, first, last):
        self.first, self.last = max(0.0, float(first)), min(1.0, float(last))
        self.is_needed = self.last - self.first < 0.999999
        self.visibility()
        self.draw()

    def initial_visibility(self):
        self._visibility_job = None
        self.visibility()

    def visibility(self):
        if self._shown == self.is_needed:
            return
        self._shown = self.is_needed
        if self.is_needed:
            self.grid()
        else:
            self.grid_remove()

    def set_hover(self, value):
        self.hover = value
        self.draw()

    def thumb_bounds(self):
        length = max(1, (self.winfo_height() if self.orient == "vertical" else self.winfo_width()) - 4)
        fraction = max(0.0, min(1.0, self.last - self.first))
        thumb = min(length, max(24, length * fraction))
        travel = max(0, length - thumb)
        start = 2 + (self.first / max(1e-9, 1 - fraction)) * travel
        return start, start + thumb, travel, fraction

    def draw(self):
        self.delete("all")
        if not self.is_needed:
            return
        start, end, travel, fraction = self.thumb_bounds()
        thickness = 8 if self.hover or self.drag_offset is not None else 6
        if self.orient == "vertical":
            center = self.winfo_width() / 2
            x1, x2, y1, y2 = center - thickness / 2, center + thickness / 2, start, end
        else:
            center = self.winfo_height() / 2
            x1, x2, y1, y2 = start, end, center - thickness / 2, center + thickness / 2
        radius = min(4, (x2 - x1) / 2, (y2 - y1) / 2)
        points = (x1+radius,y1,x2-radius,y1,x2,y1,x2,y1+radius,x2,y2-radius,x2,y2,
                  x2-radius,y2,x1+radius,y2,x1,y2,x1,y2-radius,x1,y1+radius,x1,y1)
        color = self.palette["scroll_hover"] if self.hover or self.drag_offset is not None else self.palette["scroll_thumb"]
        self.create_polygon(points, smooth=True, splinesteps=24, fill=color, outline="")

    def coordinate(self, event):
        return event.y if self.orient == "vertical" else event.x

    def press(self, event):
        start, end, _, _ = self.thumb_bounds()
        position = self.coordinate(event)
        if start <= position <= end:
            self.drag_offset = position - start
        else:
            self.scroll(-1 if position < start else 1, "pages")
        self.draw()

    def drag(self, event):
        if self.drag_offset is None:
            return
        _, _, travel, fraction = self.thumb_bounds()
        relative = (self.coordinate(event) - self.drag_offset - 2) / max(1, travel)
        self.move(relative * (1 - fraction))

    def release(self, event=None):
        self.drag_offset = None
        self.draw()

    def move(self, fraction):
        if self.command:
            self.command("moveto", max(0.0, min(1.0, fraction)))

    def scroll(self, amount, units="units"):
        if self.command:
            self.command("scroll", amount, units)

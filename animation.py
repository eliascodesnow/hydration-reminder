"""A small always-on-top popup with a pouring-water animation."""
import tkinter as tk


class WaterPopup(tk.Toplevel):
    def __init__(self, master, duration_sec=20, message="Time to drink water!", on_close=None):
        super().__init__(master)
        self.on_close = on_close

        self.overrideredirect(True)      # no title bar
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.97)
        except Exception:
            pass

        w, h = 360, 280
        sw = self.winfo_screenwidth()
        x = (sw - w) // 2
        y = 60
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.configure(bg="#0b1f33")

        self.canvas = tk.Canvas(self, width=w, height=180, bg="#0b1f33", highlightthickness=0)
        self.canvas.pack(pady=(10, 0))

        # glass outline
        gx0, gy0, gx1, gy1 = 130, 30, 230, 150
        self.canvas.create_rectangle(gx0, gy0, gx1, gy1, outline="#9fd3ff", width=3)
        self.glass_bounds = (gx0, gy0, gx1, gy1)

        self.water_level = gy1  # starts empty
        self.water_rect = self.canvas.create_rectangle(
            gx0 + 2, self.water_level, gx1 - 2, gy1, fill="#3aa0ff", outline=""
        )
        self.stream = self.canvas.create_line(180, 0, 180, gy0, fill="#3aa0ff", width=4)

        label = tk.Label(
            self, text=f"\U0001F4A7 {message} \U0001F4A7", fg="white", bg="#0b1f33",
            font=("Segoe UI", 13, "bold"), wraplength=320, justify="center",
        )
        label.pack(pady=10)

        btn = tk.Button(
            self, text="Got it, drinking now!", command=self.close,
            bg="#3aa0ff", fg="white", relief="flat", padx=10, pady=4, cursor="hand2",
        )
        btn.pack()

        self._animate_pour()
        self._close_job = self.after(duration_sec * 1000, self.close)

    def _animate_pour(self):
        gx0, gy0, gx1, gy1 = self.glass_bounds
        target = gy0 + 15
        if self.water_level > target:
            self.water_level -= 4
            self.canvas.coords(self.water_rect, gx0 + 2, self.water_level, gx1 - 2, gy1)
            self.after(40, self._animate_pour)
        else:
            self.canvas.itemconfig(self.stream, state="hidden")

    def close(self):
        try:
            self.after_cancel(self._close_job)
        except Exception:
            pass
        if self.on_close:
            self.on_close()
        self.destroy()

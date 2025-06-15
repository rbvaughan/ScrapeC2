import ctypes
import tkinter as tk
import threading
import pytesseract
import time
from PIL import ImageGrab
import cv2
import numpy as np

try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

HANDLE_SIZE = 8

class CaptureWindow(tk.Toplevel):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.3)
        self.config(bg="red")

        self.geometry("400x150+300+300")

        self.canvas = tk.Canvas(self, bg="gray", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)

        self.resize_handles = {}
        cursor_map = {
            "nw": "top_left_corner",
            "ne": "top_right_corner",
            "sw": "bottom_left_corner",
            "se": "bottom_right_corner",
            "n": "top_side",
            "s": "bottom_side",
            "e": "right_side",
            "w": "left_side"
        }

        for direction in cursor_map:
            handle = tk.Frame(self.canvas, bg="red", cursor=cursor_map[direction])
            handle.place(width=HANDLE_SIZE, height=HANDLE_SIZE)
            handle.bind("<ButtonPress-1>", self.start_resize)
            handle.bind("<B1-Motion>", self.do_resize)
            self.resize_handles[direction] = handle

        self.bind("<Configure>", self.position_handles)

        self._offset_x = 0
        self._offset_y = 0
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._start_width = 0
        self._start_height = 0
        self._resize_dir = None

    def start_move(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def do_move(self, event):
        x = self.winfo_pointerx() - self._offset_x
        y = self.winfo_pointery() - self._offset_y
        self.geometry(f"+{x}+{y}")

    def start_resize(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._start_width = self.winfo_width()
        self._start_height = self.winfo_height()
        self._start_x = self.winfo_x()
        self._start_y = self.winfo_y()
        self._resize_dir = event.widget.cget("cursor")

    def do_resize(self, event):
        dx = event.x_root - self._resize_start_x
        dy = event.y_root - self._resize_start_y
        x, y = self._start_x, self._start_y
        w, h = self._start_width, self._start_height

        if "right" in self._resize_dir:
            w = max(100, self._start_width + dx)
        if "bottom" in self._resize_dir:
            h = max(50, self._start_height + dy)
        if "left" in self._resize_dir:
            x = self._start_x + dx
            w = max(100, self._start_width - dx)
        if "top" in self._resize_dir:
            y = self._start_y + dy
            h = max(50, self._start_height - dy)

        self.geometry(f"{w}x{h}+{x}+{y}")

    def position_handles(self, event=None):
        w, h = self.winfo_width(), self.winfo_height()
        s = HANDLE_SIZE // 2

        positions = {
            "nw": (0, 0),
            "ne": (w - HANDLE_SIZE, 0),
            "sw": (0, h - HANDLE_SIZE),
            "se": (w - HANDLE_SIZE, h - HANDLE_SIZE),
            "n": (w // 2 - s, 0),
            "s": (w // 2 - s, h - HANDLE_SIZE),
            "e": (w - HANDLE_SIZE, h // 2 - s),
            "w": (0, h // 2 - s),
        }

        for dir, (x, y) in positions.items():
            self.resize_handles[dir].place(x=x, y=y)

    def get_bbox(self):
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        return (x, y, x + w, y + h)

class OutputWindow(tk.Toplevel):
    def __init__(self):
        super().__init__()
        self.title("OCR Output")
        self.geometry("400x200+750+300")
        self.attributes("-topmost", True)

        self.text_box = tk.Text(self, font=("Consolas", 12), bg="white", wrap="word")
        self.text_box.pack(expand=True, fill="both", padx=10, pady=10)
        self.text_box.insert("1.0", "Waiting for OCR...")
        self.text_box.config(state="disabled")

        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)
        self._offset_x = 0
        self._offset_y = 0

    def start_move(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def do_move(self, event):
        x = self.winfo_pointerx() - self._offset_x
        y = self.winfo_pointery() - self._offset_y
        self.geometry(f"+{x}+{y}")

    def update_text(self, new_text):
        self.text_box.config(state="normal")
        self.text_box.delete("1.0", tk.END)
        self.text_box.insert("1.0", new_text)
        self.text_box.config(state="disabled")

def run_ocr_loop(capture_win, output_win):
    previous_text = ""
    time.sleep(0.5)
    while True:
        start_time = time.time()
        bbox = capture_win.get_bbox()
        img = ImageGrab.grab(bbox=bbox)
        img_np = np.array(img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Default Tesseract config
        custom_config = r'--psm 6'

        text = pytesseract.image_to_string(binary, config=custom_config).strip()

        if text and text != previous_text:
            output_win.update_text(text)
            previous_text = text

        elapsed = time.time() - start_time
        print(f"[OCR] Frame time: {elapsed:.3f} sec")
        time.sleep(max(0, 0.2 - elapsed))  # ~5 Hz update rate

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    capture_win = CaptureWindow()
    output_win = OutputWindow()
    threading.Thread(target=run_ocr_loop, args=(capture_win, output_win), daemon=True).start()
    root.mainloop()

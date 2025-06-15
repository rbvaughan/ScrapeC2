# -*- coding: utf-8 -*-
"""
ScrapeC2 GUI  ─  live OCR ➜ parse ➜ (optional) Lattice publish
"""
import ctypes, sys, threading, time, json, tkinter as tk
from typing import Optional, Tuple

# ── OCR deps ─────────────────────────────────────────────────────────────
import pytesseract        # pip install pytesseract
from PIL import ImageGrab # pillow
import cv2, numpy as np
# ── Lattice SDK & HTTP fallback ──────────────────────────────────────────
try:
    from anduril_lattice_sdk import Lattice
    SDK_AVAILABLE = True
except ImportError:
    import requests
    SDK_AVAILABLE = False
# ── Coordinate parser ───────────────────────────────────────────────────
from position_parser import parse_position

# DPI-aware on Windows
try: ctypes.windll.user32.SetProcessDPIAware()
except Exception: pass
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
HANDLE_SIZE = 8


# ╔══════════════════════════════════════════════════════════════════════╗
# ║                               GUI                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝
class CaptureWindow(tk.Toplevel):
    """Translucent rectangle to pick OCR area."""
    def __init__(self, on_close):
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", on_close)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.30)
        self.config(bg="red")
        self.geometry("600x260+300+300")

        self.canvas = tk.Canvas(self, bg="gray", highlightthickness=0)
        self.canvas.pack(expand=True, fill="both")
        self.canvas.bind("<ButtonPress-1>", self._start_move)
        self.canvas.bind("<B1-Motion>", self._do_move)

        self._dx = self._dy = 0
        self._start_geom = None
        self._resize_dir = None
        self._make_handles()

    def _start_move(self, e): self._dx, self._dy = e.x, e.y
    def _do_move(self, e): self.geometry(f"+{self.winfo_pointerx()-self._dx}+{self.winfo_pointery()-self._dy}")

    # ----- resize handles -------------------------------------------------
    def _start_resize(self, e):
        self._start_geom = (self.winfo_x(), self.winfo_y(), self.winfo_width(), self.winfo_height())
        self._sx, self._sy, self._resize_dir = e.x_root, e.y_root, e.widget.cget("cursor")
    def _do_resize(self, e):
        x0,y0,w0,h0 = self._start_geom
        dx,dy = e.x_root-self._sx, e.y_root-self._sy
        x,y,w,h = x0,y0,w0,h0
        if "right" in self._resize_dir:  w = max(120, w0+dx)
        if "bottom" in self._resize_dir: h = max(60,  h0+dy)
        if "left"  in self._resize_dir:  x,w = x0+dx, max(120, w0-dx)
        if "top"   in self._resize_dir:  y,h = y0+dy, max(60,  h0-dy)
        self.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
    def _make_handles(self):
        curs = {"nw":"top_left_corner","n":"top_side","ne":"top_right_corner",
                "w":"left_side","e":"right_side",
                "sw":"bottom_left_corner","s":"bottom_side","se":"bottom_right_corner"}
        self._handles={}
        for d,c in curs.items():
            f=tk.Frame(self.canvas,bg="red",cursor=c,width=HANDLE_SIZE,height=HANDLE_SIZE)
            f.bind("<ButtonPress-1>", self._start_resize); f.bind("<B1-Motion>",self._do_resize)
            self._handles[d]=f
        self.bind("<Configure>", self._place_handles)
    def _place_handles(self,*_):
        w,h,s=self.winfo_width(),self.winfo_height(),HANDLE_SIZE
        pos={"nw":(0,0),"n":(w//2-s//2,0),"ne":(w-s,0),
             "w":(0,h//2-s//2),"e":(w-s,h//2-s//2),
             "sw":(0,h-s),"s":(w//2-s//2,h-s),"se":(w-s,h-s)}
        for d,(x,y) in pos.items(): self._handles[d].place(x=x,y=y)
    def get_bbox(self): self.update_idletasks(); x,y=self.winfo_rootx(),self.winfo_rooty(); return (x,y,x+self.winfo_width(),y+self.winfo_height())


class OutputWindow(tk.Toplevel):
    """Shows OCR / parsed / publisher controls."""
    def __init__(self, on_close):
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", on_close)
        self.title("ScrapeC2 – OCR ➜ Parsed ➜ Lattice")
        self.geometry("780x560+930+260")
        self.attributes("-topmost", True)

        # ── grid ──────────────────────────────────────────────────────────
        self.rowconfigure(1,weight=1); self.rowconfigure(3,weight=1)
        self.columnconfigure(0,weight=1)

        # OCR raw
        tk.Label(self,text="OCR text").grid(row=0,column=0,sticky="w",padx=8,pady=(8,0))
        self.txt_raw=tk.Text(self,height=12,font=("Consolas",10),bg="#f2f2f2",wrap="word")
        self.txt_raw.grid(row=1,column=0,sticky="nsew",padx=8)

        # Parsed JSON
        tk.Label(self,text="Parsed (LLA JSON)").grid(row=2,column=0,sticky="w",padx=8,pady=(8,0))
        self.txt_parsed=tk.Text(self,height=10,font=("Consolas",12,"bold"),wrap="word")
        self.txt_parsed.grid(row=3,column=0,sticky="nsew",padx=8)

        # Publisher controls
        frm = tk.Frame(self,relief="groove",bd=1); frm.grid(row=4,column=0,sticky="ew",padx=6,pady=6)
        frm.columnconfigure(1,weight=1)
        tk.Label(frm,text="API Base").grid(row=0,column=0,sticky="e",padx=4,pady=2)
        tk.Label(frm,text="Entity ID").grid(row=1,column=0,sticky="e",padx=4,pady=2)
        tk.Label(frm,text="Token").grid(row=2,column=0,sticky="e",padx=4,pady=2)

        self.var_url  = tk.StringVar(value="https://sandbox.api.anduril.com")
        self.var_eid  = tk.StringVar()
        self.var_tok  = tk.StringVar()
        self.var_live = tk.BooleanVar(value=False)

        tk.Entry(frm,textvariable=self.var_url).grid(row=0,column=1,sticky="ew",padx=4)
        tk.Entry(frm,textvariable=self.var_eid).grid(row=1,column=1,sticky="ew",padx=4)
        tk.Entry(frm,textvariable=self.var_tok,show="•").grid(row=2,column=1,sticky="ew",padx=4)

        tk.Checkbutton(frm,text="Send every update",variable=self.var_live).grid(row=0,column=2,rowspan=2,padx=6)
        self.lbl_status=tk.Label(frm,text="●",fg="gray"); self.lbl_status.grid(row=2,column=2,padx=6)

        # drag window
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<B1-Motion>", self._do_move); self._dx=self._dy=0

    def _start_move(self,e): self._dx,self._dy=e.x,e.y
    def _do_move(self,e): self.geometry(f"+{self.winfo_pointerx()-self._dx}+{self.winfo_pointery()-self._dy}")

    # UI helpers
    def _set(self,widget,text): widget.config(state="normal"); widget.delete("1.0",tk.END); widget.insert("1.0",text); widget.config(state="disabled")
    def show_raw(self,t):     self._set(self.txt_raw,t)
    def show_parsed(self,p):  self.txt_parsed.config(bg="#ccffcc" if p else "#ffcccc"); self._set(self.txt_parsed,p or "— no valid coordinates —")
    def update_status(self,ok:bool): self.lbl_status.config(fg=("green" if ok else "red"))

    # Expose publisher settings
    def lattice_cfg(self): return dict(
        url=self.var_url.get().rstrip("/"),
        entity=self.var_eid.get().strip(),
        token=self.var_tok.get().strip(),
        enabled=self.var_live.get()
    )


# ╔══════════════════════════════════════════════════════════════════════╗
# ║                   OCR ➜ parse ➜ publish thread                       ║
# ╚══════════════════════════════════════════════════════════════════════╝
def publisher_send(cfg:dict, lat:float, lon:float, alt:Optional[float]) -> bool:
    if not (cfg["url"] and cfg["entity"] and cfg["token"]):
        return False
    try:
        if SDK_AVAILABLE:
            client = Lattice(base_url=cfg["url"], bearer_token=cfg["token"])
            client.entities.update_pose(cfg["entity"], lat, lon, alt or 0.0)
        else:  # simple HTTP fallback
            url=f'{cfg["url"]}/entities/{cfg["entity"]}/components/pose'
            headers={"Authorization":f'Bearer {cfg["token"]}',
                     "Content-Type":"application/json"}
            body={"lat":lat,"lon":lon,"alt":(alt if alt is not None else 0)}
            r=requests.post(url,json=body,headers=headers,timeout=4)
            r.raise_for_status()
        return True
    except Exception as exc:
        print("[Publish] FAIL:", exc)
        return False


def run_loop(cap:CaptureWindow, ui:OutputWindow, stop_evt:threading.Event):
    prev_txt=""; prev_sent=None
    while not stop_evt.is_set():
        t0=time.time()
        img=ImageGrab.grab(bbox=cap.get_bbox())
        gray=cv2.cvtColor(np.array(img),cv2.COLOR_BGR2GRAY)
        _,thr=cv2.threshold(cv2.GaussianBlur(gray,(3,3),0),0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        text=pytesseract.image_to_string(thr,config="--psm 6").strip()
        if text!=prev_txt:
            ui.show_raw(text)
            parsed=parse_position(text)
            if parsed:
                lat,lon,alt=parsed
                payload=json.dumps({"lat":lat,"lon":lon,**({"alt":alt} if alt is not None else {})},indent=2)
                ui.show_parsed(payload)
                cfg=ui.lattice_cfg()
                if cfg["enabled"] and parsed!=prev_sent:
                    ok=publisher_send(cfg,lat,lon,alt)
                    ui.update_status(ok); prev_sent=parsed
            else:
                ui.show_parsed(None); ui.update_status(False)
            prev_txt=text
        time.sleep(max(0,0.2-(time.time()-t0)))


# ╔══════════════════════════════════════════════════════════════════════╗
# ║                              main                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝
if __name__=="__main__":
    root=tk.Tk(); root.withdraw()
    stop=threading.Event()
    def close_all(): stop.set(); root.destroy(); sys.exit(0)

    cap=CaptureWindow(close_all)
    ui =OutputWindow(close_all)
    threading.Thread(target=run_loop,args=(cap,ui,stop),daemon=True).start()
    root.mainloop()

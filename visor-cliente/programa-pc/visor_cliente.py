"""Visor de cliente: refleja en la pantalla del cliente SOLO una zona de la pantalla del
mostrador (por ejemplo, el «Resumen» de Western Union), y nada más.

Funciona con cualquier programa o web: no lee su contenido, solo copia los píxeles de la zona
elegida unas 10 veces por segundo. No guarda ni envía nada; solo recuerda el rectángulo elegido.

Uso:  py herramientas/visor_cliente.py
"""
import ctypes
import json
import io
import os
import random
import socket
import sys
import threading
import time
import tkinter as tk
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from ctypes import wintypes
from tkinter import messagebox

from PIL import Image, ImageGrab, ImageTk

try:                                         # coordenadas en píxeles reales, no escaladas
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

CARPETA = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False) else __file__))
RUTA_CONFIG = os.path.join(CARPETA, "config_visor_cliente.json")
INTERVALO_MS = 100


def monitores():
    """Lista de (x, y, ancho, alto, es_principal) de cada pantalla conectada."""
    res = []

    class RECT(ctypes.Structure):
        _fields_ = [("l", wintypes.LONG), ("t", wintypes.LONG), ("r", wintypes.LONG), ("b", wintypes.LONG)]

    class INFO(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("mon", RECT), ("work", RECT), ("flags", wintypes.DWORD)]

    def cb(hmon, hdc, rect, data):
        info = INFO(); info.cb = ctypes.sizeof(INFO)
        ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info))
        m = info.mon
        res.append((m.l, m.t, m.r - m.l, m.b - m.t, bool(info.flags & 1)))
        return True

    proc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
                              ctypes.POINTER(RECT), wintypes.LPARAM)(cb)
    ctypes.windll.user32.EnumDisplayMonitors(0, 0, proc, 0)
    res.sort(key=lambda m: (not m[4], m[0], m[1]))          # la principal, primero
    return res


def cargar_zona():
    try:
        z = json.load(open(RUTA_CONFIG, encoding="utf-8")).get("zona")
        if z and len(z) == 4 and z[2] > 10 and z[3] > 10:
            return tuple(int(v) for v in z)
    except Exception:
        pass
    return None


def guardar_zona(z):
    try:
        json.dump({"zona": list(z)}, open(RUTA_CONFIG, "w", encoding="utf-8"))
    except Exception:
        pass


# ── la extensión del navegador: le dice dónde está el «Resumen» en la pantalla ───────────
PUERTO_EXTENSION = 8760
CADUCA_EXTENSION_S = 3.0          # si la extensión calla más de esto, se vuelve a la zona a mano


def zona_desde_navegador(d, mons):
    """De lo que mide la extensión (en píxeles CSS del navegador) saca el rectángulo en píxeles
    reales de la pantalla, o None si el recuadro no se ve. Devuelve (x, y, ancho, alto)."""
    if not d.get("visible") or d.get("w", 0) < 5 or d.get("h", 0) < 5 or not d.get("sw"):
        return None
    sw, dpr = float(d["sw"]), float(d["dpr"])
    # escala del sistema (125 % → 1,25): píxeles reales de la pantalla / píxeles lógicos del navegador
    esc = None
    for (mx, my, mw, mh, _) in mons:
        e = mw / sw
        cx, cy = (d["sx"] + d["ow"] / 2) * e, (d["sy"] + d["oh"] / 2) * e
        if mx <= cx < mx + mw and my <= cy < my + mh:
            esc = e; break
    if esc is None:
        esc = mons[0][2] / sw
    zoom = dpr / esc                                  # zoom de la página (110 % → 1,1)
    borde = max(0.0, (d["ow"] - d["iw"] * zoom) / 2)  # marco lateral e inferior de la ventana
    arriba = d["oh"] - d["ih"] * zoom - borde         # barra de pestañas, direcciones…
    x = (d["sx"] + borde + d["l"] * zoom) * esc
    y = (d["sy"] + arriba + d["t"] * zoom) * esc
    return (int(round(x)), int(round(y)), int(round(d["w"] * zoom * esc)), int(round(d["h"] * zoom * esc)))


class ReceptorExtension:
    """Recibe en 127.0.0.1 (solo este PC) lo que manda la extensión. Una web cualquiera no puede
    usarlo: exige una cabecera propia, que obliga al navegador a pedir permiso antes y aquí nunca se da."""

    def __init__(self):
        self.zona, self.hora, yo = None, 0.0, self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                try:
                    if self.client_address[0] != "127.0.0.1" or self.headers.get("X-Visor-Cliente") != "1"                             or self.path != "/zona":
                        self.send_response(403); self.end_headers(); return
                    n = min(int(self.headers.get("Content-Length", "0")), 4096)
                    d = json.loads(self.rfile.read(n).decode("utf-8"))
                    yo.zona, yo.hora = zona_desde_navegador(d, monitores()), time.time()
                    self.send_response(204); self.end_headers()
                except Exception:
                    self.send_response(400); self.end_headers()

        try:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", PUERTO_EXTENSION), H)
            threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        except OSError:
            self.httpd = None                         # puerto ocupado: la extensión no funcionará

    def viva(self):
        return self.httpd is not None and time.time() - self.hora < CADUCA_EXTENSION_S

    def parar(self):
        if self.httpd:
            try: self.httpd.shutdown(); self.httpd.server_close()
            except Exception: pass


PAGINA_TABLET = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pantalla del cliente</title>
<style>html,body{margin:0;height:100%;background:#000;overflow:hidden}
#i{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}
#s{position:absolute;inset:0;display:none;align-items:center;justify-content:center;
background:#000;color:#fff;font:600 7vmin sans-serif;text-align:center}</style></head>
<body><img id="i" alt=""><div id="s">Sin se&ntilde;al&hellip;</div>
<script>
var c=location.search, i=document.getElementById("i"), s=document.getElementById("s"), ok=0;
function pedir(){ i.src="/frame.jpg"+c+(c?"&":"?")+"t="+Date.now(); }
i.onload=function(){ ok=Date.now(); s.style.display="none"; setTimeout(pedir,120); };
i.onerror=function(){ s.style.display="flex"; setTimeout(pedir,1000); };
setInterval(function(){ if(Date.now()-ok>3000) s.style.display="flex"; },500);
document.body.onclick=function(){ var e=document.documentElement; (e.requestFullscreen||e.webkitRequestFullscreen||function(){}).call(e); };
pedir();
</script></body></html>"""


def ip_local():
    """La dirección del PC en la red local (la que se teclea en la tablet)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1)); ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class ServidorTablet:
    """Sirve la zona elegida como una imagen que la tablet pide una y otra vez. Solo mientras
    está encendido y solo con el código de esta activación."""

    def __init__(self, zona_actual):
        self.zona_actual, self.codigo, self.jpeg, self.activo = zona_actual, f"{random.randint(0, 9999):04d}", b"", True
        yo = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                u = urlparse(self.path)
                if parse_qs(u.query).get("c", [""])[0] != yo.codigo:
                    self.send_response(403); self.end_headers(); self.wfile.write(b"Codigo incorrecto"); return
                if u.path == "/frame.jpg":
                    cuerpo, tipo = yo.jpeg, "image/jpeg"
                    if not cuerpo: self.send_response(503); self.end_headers(); return
                else:
                    cuerpo, tipo = PAGINA_TABLET.encode("utf-8"), "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", tipo); self.send_header("Content-Length", str(len(cuerpo)))
                self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(cuerpo)

        self.puerto = 8765
        for p in range(8765, 8775):
            try:
                self.httpd = ThreadingHTTPServer(("0.0.0.0", p), H); self.puerto = p; break
            except OSError:
                continue
        else:
            raise OSError("No hay ningún puerto libre (8765-8774).")
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        threading.Thread(target=self._capturar, daemon=True).start()

    @property
    def url(self):
        return f"http://{ip_local()}:{self.puerto}/?c={self.codigo}"

    def _capturar(self):
        while self.activo:
            try:
                z = self.zona_actual()
                if z is None:
                    self.jpeg = b""; time.sleep(0.12); continue     # recuadro oculto: «Sin señal»
                x, y, w, h = z
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).convert("RGB")
                if img.width > 1600: img = img.resize((1600, max(1, int(img.height * 1600 / img.width))), Image.BILINEAR)
                b = io.BytesIO(); img.save(b, "JPEG", quality=80); self.jpeg = b.getvalue()
            except Exception:
                pass
            time.sleep(0.12)

    def parar(self):
        self.activo = False
        try: self.httpd.shutdown(); self.httpd.server_close()
        except Exception: pass


class Visor:
    def __init__(self, raiz):
        self.raiz, self.zona, self.cliente, self.foto = raiz, cargar_zona(), None, None
        self.ext = ReceptorExtension()
        raiz.title("Visor de cliente")
        raiz.resizable(False, False)
        raiz.attributes("-topmost", True)
        f = tk.Frame(raiz, padx=18, pady=14); f.pack()
        tk.Label(f, text="Enseña al cliente solo una parte de tu pantalla.",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.lbl = tk.Label(f, text="", justify="left", font=("Segoe UI", 10), fg="#555")
        self.lbl.pack(anchor="w", pady=(6, 10))
        tk.Button(f, text="1.  Elegir la zona que verá el cliente", command=self.elegir_zona,
                  font=("Segoe UI", 11), pady=6).pack(fill="x", pady=2)
        self.btn = tk.Button(f, text="2.  Mostrar al cliente", command=self.alternar,
                             font=("Segoe UI", 11, "bold"), pady=6)
        self.btn.pack(fill="x", pady=2)
        self.btn_tablet = tk.Button(f, text="3.  Mostrar en tablet (navegador)", command=self.alternar_tablet,
                                    font=("Segoe UI", 11), pady=6)
        self.btn_tablet.pack(fill="x", pady=2)
        self.lbl_tablet = tk.Entry(f, font=("Segoe UI", 10), state="readonly", justify="center")
        self.tablet = None
        raiz.bind("<F8>", lambda e: self.alternar())
        raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.pintar_estado(); self.vigilar_extension()

    def vigilar_extension(self):
        """Refresca el texto cuando la extensión se conecta o se desconecta."""
        v = self.ext.viva()
        if v != getattr(self, '_ext_viva', None):
            self._ext_viva = v; self.pintar_estado()
        self.raiz.after(1000, self.vigilar_extension)

    def zona_efectiva(self):
        """La que manda la extensión si está conectada (None = el recuadro no se ve); si no, la elegida a mano."""
        return self.ext.zona if self.ext.viva() else self.zona

    def pintar_estado(self):
        ms = monitores()
        z = f"{self.zona[2]} × {self.zona[3]} px" if self.zona else "sin elegir"
        if self.ext.viva(): z = "la marca la extensión del navegador"
        pantalla = "pantalla del cliente detectada" if len(ms) > 1 else "solo hay UNA pantalla: se verá en una ventana"
        self.lbl.config(text=f"Zona: {z}\n{pantalla}.   (F8: mostrar / quitar)")
        self.btn.config(text="Quitar la pantalla del cliente" if self.cliente else "2.  Mostrar al cliente")

    # ── elegir la zona: se congela la pantalla principal y se arrastra un rectángulo ──────
    def elegir_zona(self):
        if self.cliente: self.alternar()
        ox, oy, w, h, _ = monitores()[0]
        self.raiz.withdraw(); self.raiz.update(); self.raiz.after(250)
        foto = ImageGrab.grab(bbox=(ox, oy, ox + w, oy + h), all_screens=True)
        self.raiz.deiconify()
        v = tk.Toplevel(self.raiz)
        v.overrideredirect(True); v.geometry(f"{w}x{h}+{ox}+{oy}"); v.attributes("-topmost", True)
        c = tk.Canvas(v, width=w, height=h, highlightthickness=0, cursor="crosshair"); c.pack()
        fondo = ImageTk.PhotoImage(Image.eval(foto, lambda p: int(p * 0.55)))
        c.create_image(0, 0, image=fondo, anchor="nw"); c.image = fondo
        c.create_text(w // 2, 40, fill="#ffeb3b", font=("Segoe UI", 20, "bold"),
                      text="Arrastra para marcar la zona que verá el cliente   ·   Esc: cancelar")
        est = {"x": 0, "y": 0, "r": None}

        def bajar(e): est["x"], est["y"] = e.x, e.y
        def mover(e):
            if est["r"]: c.delete(est["r"])
            est["r"] = c.create_rectangle(est["x"], est["y"], e.x, e.y, outline="#ffeb3b", width=3)
        def soltar(e):
            x0, x1 = sorted((est["x"], e.x)); y0, y1 = sorted((est["y"], e.y))
            v.destroy()
            if x1 - x0 > 20 and y1 - y0 > 20:
                self.zona = (ox + x0, oy + y0, x1 - x0, y1 - y0)
                guardar_zona(self.zona)
            self.pintar_estado()
        c.bind("<ButtonPress-1>", bajar); c.bind("<B1-Motion>", mover); c.bind("<ButtonRelease-1>", soltar)
        v.bind("<Escape>", lambda e: (v.destroy(), self.pintar_estado()))
        v.focus_force()

    # ── la tablet: el mismo recuadro, por la wifi y en un navegador ──────────────────
    def alternar_tablet(self):
        if self.tablet:
            self.tablet.parar(); self.tablet = None
            self.lbl_tablet.pack_forget(); self.btn_tablet.config(text="3.  Mostrar en tablet (navegador)"); return
        if not self.zona and not self.ext.viva():
            messagebox.showinfo("Visor de cliente", "Primero elige la zona (botón 1)."); return
        try:
            self.tablet = ServidorTablet(self.zona_efectiva)
        except Exception as e:
            messagebox.showerror("Visor de cliente", f"No se pudo encender el visor para la tablet:\n{e}"); return
        self.lbl_tablet.config(state="normal"); self.lbl_tablet.delete(0, "end")
        self.lbl_tablet.insert(0, self.tablet.url); self.lbl_tablet.config(state="readonly")
        self.lbl_tablet.pack(fill="x", pady=(6, 0))
        self.btn_tablet.config(text="Quitar la tablet")

    # ── la pantalla del cliente ───────────────────────────────────────────────────────
    def alternar(self):
        if self.cliente:
            self.cliente.destroy(); self.cliente = None; self.pintar_estado(); return
        if not self.zona and not self.ext.viva():
            messagebox.showinfo("Visor de cliente", "Primero elige la zona (botón 1)."); return
        ms = monitores()
        t = tk.Toplevel(self.raiz); t.configure(bg="black")
        if len(ms) > 1:
            x, y, w, h, _ = ms[1]
            t.overrideredirect(True); t.geometry(f"{w}x{h}+{x}+{y}")
        else:
            t.title("Pantalla del cliente"); t.geometry("720x405+80+80")
        self.etq = tk.Label(t, bg="black", bd=0); self.etq.pack(expand=True, fill="both")
        t.bind("<Escape>", lambda e: self.alternar())
        t.protocol("WM_DELETE_WINDOW", self.alternar)
        self.cliente = t
        self.pintar_estado(); self.refrescar()

    def refrescar(self):
        if not self.cliente: return
        try:
            z = self.zona_efectiva()
            if z is None:
                self.etq.config(image=""); self.foto = None
                self.raiz.after(INTERVALO_MS, self.refrescar); return
            x, y, w, h = z
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
            cw, ch = max(self.etq.winfo_width(), 50), max(self.etq.winfo_height(), 50)
            k = min(cw / img.width, ch / img.height)
            img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.BILINEAR)
            self.foto = ImageTk.PhotoImage(img); self.etq.config(image=self.foto)
        except Exception:
            pass
        self.raiz.after(INTERVALO_MS, self.refrescar)

    def cerrar(self):
        if self.cliente: self.cliente.destroy()
        if self.tablet: self.tablet.parar()
        self.ext.parar()
        self.raiz.destroy()


if __name__ == "__main__":
    raiz = tk.Tk()
    Visor(raiz)
    raiz.mainloop()

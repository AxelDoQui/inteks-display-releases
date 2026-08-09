"""
Genera el icono de InTeks Display: assets/icon.ico, icon.svg y los PNG sueltos.

Sin dependencias externas, que es la regla del proyecto: el PNG se escribe a
mano con zlib (firma + IHDR + IDAT + IEND) y el ICO es su cabecera mas los PNG
embebidos, que Windows admite desde Vista.

El dibujo: cuadrado redondeado azul marino con tres barras naranjas de anchura
decreciente. Representa las filas de un tablero de tasas, se distingue de un
vistazo y sigue leyendose a 16 px, que es donde mueren los iconos con detalle.

Ejecutar:  python tools/gen_iconos.py
"""
import os, struct, zlib

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(RAIZ, "assets")

FONDO = (7, 24, 43)        # #07182b
BARRA = (255, 127, 0)      # #FF7F00
SS = 4                     # supermuestreo: sin esto los bordes salen dentados


def _dentro_redondeado(x, y, lado, radio):
    if x < radio and y < radio:
        return (x - radio) ** 2 + (y - radio) ** 2 <= radio ** 2
    if x > lado - radio and y < radio:
        return (x - (lado - radio)) ** 2 + (y - radio) ** 2 <= radio ** 2
    if x < radio and y > lado - radio:
        return (x - radio) ** 2 + (y - (lado - radio)) ** 2 <= radio ** 2
    if x > lado - radio and y > lado - radio:
        return (x - (lado - radio)) ** 2 + (y - (lado - radio)) ** 2 <= radio ** 2
    return True


def dibujar(n):
    """Devuelve los pixeles RGBA del icono de n x n."""
    g = n * SS
    radio = g * 0.22
    # Tres barras: margen izquierdo comun, anchuras decrecientes
    x0 = g * 0.22
    anchos = [0.56, 0.44, 0.30]
    alto = g * 0.105
    hueco = g * 0.075
    total = 3 * alto + 2 * hueco
    y0 = (g - total) / 2

    filas = []
    for y in range(g):
        fila = []
        for x in range(g):
            if not _dentro_redondeado(x, y, g, radio):
                fila.append((0, 0, 0, 0))
                continue
            color = FONDO
            for i, w in enumerate(anchos):
                by = y0 + i * (alto + hueco)
                if by <= y < by + alto and x0 <= x < x0 + g * w:
                    color = BARRA
                    break
            fila.append(color + (255,))
        filas.append(fila)

    # Reducir por promedio: el supermuestreo se convierte en suavizado
    out = bytearray()
    for y in range(n):
        for x in range(n):
            r = g_ = b = a = 0
            for dy in range(SS):
                for dx in range(SS):
                    p = filas[y * SS + dy][x * SS + dx]
                    r += p[0]; g_ += p[1]; b += p[2]; a += p[3]
            k = SS * SS
            out += bytes((r // k, g_ // k, b // k, a // k))
    return bytes(out)


def png(n, pixeles):
    def trozo(tipo, datos):
        c = tipo + datos
        return struct.pack(">I", len(datos)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    crudo = b"".join(b"\x00" + pixeles[y * n * 4:(y + 1) * n * 4] for y in range(n))
    return (b"\x89PNG\r\n\x1a\n"
            + trozo(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0))
            + trozo(b"IDAT", zlib.compress(crudo, 9))
            + trozo(b"IEND", b""))


def ico(imagenes):
    """imagenes: lista de (lado, bytes_png). 0 en la cabecera significa 256."""
    n = len(imagenes)
    cabecera = struct.pack("<HHH", 0, 1, n)
    entradas, cuerpo = b"", b""
    desplazamiento = 6 + 16 * n
    for lado, datos in imagenes:
        entradas += struct.pack("<BBBBHHII", lado if lado < 256 else 0,
                                lado if lado < 256 else 0, 0, 0, 1, 32,
                                len(datos), desplazamiento + len(cuerpo))
        cuerpo += datos
    return cabecera + entradas + cuerpo


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" rx="22" fill="#07182b"/>
  <rect x="22" y="30.75" width="56" height="10.5" rx="2" fill="#FF7F00"/>
  <rect x="22" y="48.75" width="44" height="10.5" rx="2" fill="#FF7F00"/>
  <rect x="22" y="66.75" width="30" height="10.5" rx="2" fill="#FF7F00"/>
</svg>
'''


def main():
    os.makedirs(ASSETS, exist_ok=True)
    tamanos = [16, 24, 32, 48, 64, 128, 256]
    imagenes = []
    for n in tamanos:
        datos = png(n, dibujar(n))
        imagenes.append((n, datos))
        if n in (32, 192 if 192 in tamanos else 256):
            pass
    with open(os.path.join(ASSETS, "icon.ico"), "wb") as f:
        f.write(ico(imagenes))
    # PNG sueltos: favicon de respaldo y usos varios
    for n in (32, 256):
        with open(os.path.join(ASSETS, f"icon-{n}.png"), "wb") as f:
            f.write(dict(imagenes)[n] if False else png(n, dibujar(n)))
    with open(os.path.join(ASSETS, "tray.png"), "wb") as f:
        f.write(png(32, dibujar(32)))
    with open(os.path.join(ASSETS, "icon.svg"), "w", encoding="utf-8", newline="") as f:
        f.write(SVG)

    for nombre in ("icon.ico", "icon.svg", "icon-32.png", "icon-256.png", "tray.png"):
        r = os.path.join(ASSETS, nombre)
        print(f"  {nombre:<16} {os.path.getsize(r):>7} bytes")


main()

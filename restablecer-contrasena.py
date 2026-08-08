"""
InTeks Display — restablecer la contraseña del panel de administración.

Se ejecuta EN EL ORDENADOR donde está instalado el servidor. No existe ningún
"he olvidado la contraseña" accesible por la red, y es a propósito: eso no
sería recuperación, sería una puerta trasera que cualquiera en el wifi de la
tienda podría usar. La prueba de identidad es estar delante del equipo.

Lo que hace: borra SOLO la contraseña (`salt` y `pwd_hash`) de admin.json y
deja intactos el secreto de sesión y el token de la extensión. Si se borrara el
archivo entero, la extensión de Chrome dejaría de poder enviar tasas y habría
que reconfigurarla.

Uso:
    python restablecer-contrasena.py
"""
import json
import os
import shutil
import sys
import time

NOMBRES_DATOS = ("InTeks Display", "SignalOS Pro", "SignalOS")


def carpetas_candidatas():
    """Dónde puede vivir admin.json.

    Si SIGNALOS_DATA está puesta, manda ELLA Y NADA MÁS. Una variable que dice
    explícitamente dónde están los datos no puede caer en silencio hacia otra
    carpeta: esta herramienta borra credenciales, y equivocarse de instalación
    significa dejar sin contraseña a un equipo que nadie estaba tocando. Pasó
    de verdad, en las pruebas de esta misma herramienta.

    Tampoco se busca junto al programa: en una instalación real los datos viven
    en %PROGRAMDATA%, nunca en Archivos de programa, así que ese camino solo
    sirve para encontrar el admin.json equivocado de una copia del código.
    """
    entorno = os.environ.get("SIGNALOS_DATA")
    if entorno:
        return [entorno]
    programdata = os.environ.get("PROGRAMDATA")
    if not programdata:
        return []
    return [os.path.join(programdata, nombre) for nombre in NOMBRES_DATOS]


def localizar_admin():
    """Todas las instalaciones encontradas. Nunca se elige por su cuenta."""
    rutas = []
    for carpeta in carpetas_candidatas():
        ruta = os.path.join(carpeta, "admin.json")
        if os.path.exists(ruta):
            rutas.append(ruta)
    return rutas


def restablecer(ruta):
    """Quita la contraseña conservando el resto. Devuelve (ok, mensaje)."""
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except Exception as e:
        return False, f"No se pudo leer {ruta}: {e}"

    if not datos.get("pwd_hash"):
        return True, "Ese equipo ya no tenía contraseña puesta."

    copia = ruta + time.strftime(".bak-%Y%m%d-%H%M%S")
    try:
        shutil.copy2(ruta, copia)
    except Exception as e:
        return False, f"No se pudo hacer la copia de seguridad: {e}"

    conservados = [k for k in ("secret", "api_token") if datos.get(k)]
    datos.pop("pwd_hash", None)
    datos.pop("salt", None)

    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2)
    except Exception as e:
        return False, f"No se pudo escribir {ruta}: {e}"

    return True, (f"Contraseña borrada.\n"
                  f"  Copia previa: {copia}\n"
                  f"  Se conservan: {', '.join(conservados) or 'nada más'}")


def main():
    print()
    print("  InTeks Display - restablecer la contrasena del panel")
    print("  " + "-" * 52)
    print()

    rutas = localizar_admin()
    if not rutas:
        print("  No se encuentra admin.json. Se ha buscado en:")
        for c in carpetas_candidatas():
            print(f"    {os.path.join(c, 'admin.json')}")
        print()
        print("  Si el servidor esta instalado en otro sitio, ejecuta esto")
        print("  indicando la carpeta de datos:")
        print("    set SIGNALOS_DATA=C:\\ruta\\a\\los\\datos")
        print("    python restablecer-contrasena.py")
        return 1

    if len(rutas) == 1:
        ruta = rutas[0]
    else:
        # Varias instalaciones a la vez (una antigua que quedo ahi, por
        # ejemplo). Elegir por su cuenta seria dejar sin contrasena a un equipo
        # que nadie estaba tocando, asi que se pregunta.
        print("  Hay varias instalaciones. Elige cual:")
        for i, r in enumerate(rutas, 1):
            print(f"    {i}. {r}")
        print()
        elegida = input("  Numero: ").strip()
        if not elegida.isdigit() or not (1 <= int(elegida) <= len(rutas)):
            print("\n  Eleccion no valida. No se ha tocado nada.\n")
            return 1
        ruta = rutas[int(elegida) - 1]
        print()

    print(f"  Archivo encontrado: {ruta}")
    print()
    print("  Se va a BORRAR la contrasena del panel. El token de la extension")
    print("  de Chrome y las sesiones abiertas NO se tocan.")
    print()
    respuesta = input("  Escribe SI para continuar: ").strip().upper()
    if respuesta not in ("SI", "SÍ"):
        print("\n  Cancelado. No se ha tocado nada.\n")
        return 1

    ok, mensaje = restablecer(ruta)
    print()
    print(f"  {mensaje}")
    print()
    if not ok:
        return 1

    print("  AHORA, SIN PERDER TIEMPO:")
    print("    1. Abre el panel (acceso directo 'InTeks Display').")
    print("    2. Te pedira crear una contrasena nueva. Creala YA.")
    print()
    print("  Mientras no haya contrasena, cualquiera que llegue al servidor")
    print("  desde la red puede crear una y quedarse con el panel.")
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Cancelado.\n")
        sys.exit(1)

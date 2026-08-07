#!/usr/bin/env python3
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

os.chdir("c:/Users/axeld/Documents/Digital Signage")
PORT = 9000

print(f"Iniciando servidor en puerto {PORT}...")

server = HTTPServer(('0.0.0.0', PORT), SimpleHTTPRequestHandler)
print(f"Servidor activo en http://localhost:{PORT}/")
print("Presiona Ctrl+C para detener\n")

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nServidor detenido")

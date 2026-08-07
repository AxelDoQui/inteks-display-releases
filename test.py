#!/usr/bin/env python3
import sys
print("Python OK")
print(f"Version: {sys.version}")
print(f"Path: {sys.executable}")

try:
    import json
    print("JSON OK")
except Exception as e:
    print(f"JSON ERROR: {e}")

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    print("HTTP Server OK")
except Exception as e:
    print(f"HTTP Server ERROR: {e}")

print("Todas las importaciones OK")

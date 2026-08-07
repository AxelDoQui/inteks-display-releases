#!/usr/bin/env python3
import sys
import os

sys.stdout.flush()
sys.stderr.flush()

try:
    print("Iniciando server.py...", flush=True)
    sys.stdout.flush()

    # Importar y ejecutar server.py
    exec(open('server.py').read())

except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()

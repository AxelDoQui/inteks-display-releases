# SignalOS Pro — Construcción del Instalador

## Requisitos

1. **Inno Setup 6** (descárgalo de https://jrsoftware.org/isdl.php)
2. **Python 3.10+** (ya tienes Python instalado en el sistema)

## Pasos para construir el instalador

### 1. Instala Inno Setup

- Descarga desde: https://jrsoftware.org/isdl.php
- Ejecuta el instalador (acepta configuración por defecto)
- Se instalará en: `C:\Program Files (x86)\Inno Setup 6\`

### 2. Asegúrate de que todos los archivos están presentes

```
Digital Signage/
├── server.py
├── admin.html
├── player.html
├── pair.html
├── config.json
├── start_signalos.bat
├── build_installer.ps1
├── assets/
│   ├── icon.ico
│   └── (otros assets)
└── installer/
    └── setup.iss
```

### 3. Ejecuta el script de compilación

```powershell
cd "c:\Users\axeld\Documents\Digital Signage"
.\build_installer.ps1
```

O manualmente con Inno Setup:
- Abre `installer/setup.iss` con Inno Setup
- Haz clic en "Compile"

### 4. El instalador se generará en

```
Digital Signage/dist/installer/SignalOS_Pro_Setup_v1.0.0.exe
```

## Qué hace el instalador

✓ Instala SignalOS Pro en `C:\Program Files\SignalOS Pro\`
✓ Crea acceso directo en escritorio
✓ Crea entrada en menú inicio
✓ Al ejecutar, inicia automáticamente server.py y abre http://localhost:9000
✓ Permite desinstalar desde "Programas y características"

## Distribución

- Comparte `SignalOS_Pro_Setup_v1.0.0.exe` con usuarios finales
- No requiere Python instalado (está embebido en la instalación)
- No requiere Node.js u otras dependencias
- Compatible con Windows 10 y Windows 11 (64-bit)

## Troubleshooting

### "Inno Setup no encontrado"
- Verifica que está instalado en: `C:\Program Files (x86)\Inno Setup 6\`
- Si está en otra ubicación, edita `build_installer.ps1`

### El servidor no inicia
- Verifica que Python esté en el PATH: `python --version`
- Si no está, edita `start_signalos.bat` y reemplaza `python.exe` con la ruta completa

### Puerto ocupado
- El script usa puerto 9000 (configurable en config.json)
- Si está ocupado, prueba puertos alternativos (9001, 9002, etc.)

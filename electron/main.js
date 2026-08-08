const { app, BrowserWindow, Menu, Tray, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const net = require('net');

let mainWindow;
let tray;
let serverProcess;
let isQuitting = false;
let currentPort = 80;

function loadConfig() {
  const defaults = {
    port: 80,
    port_fallback: 9000,
    installation_name: "InTeks Display",
    mdns_name: "signage",
    autostart: false,
    kiosk: false,             // si true: esta PC también es pantalla (player a pantalla completa)
    kiosk_screen: "pantalla1",
    first_run: true
  };
  try {
    const configPath = path.join(__dirname, '..', 'config.json');
    if (fs.existsSync(configPath)) {
      return { ...defaults, ...JSON.parse(fs.readFileSync(configPath, 'utf8')) };
    }
  } catch (e) {
    console.error('Error reading config:', e);
  }
  return defaults;
}

function saveConfig(config) {
  try {
    fs.writeFileSync(path.join(__dirname, '..', 'config.json'), JSON.stringify(config, null, 2));
  } catch (e) {
    console.error('Error saving config:', e);
  }
}

function isPortAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => { server.close(); resolve(true); });
    server.listen(port);
  });
}

async function findAvailablePort(preferred, fallback) {
  if (await isPortAvailable(preferred)) return preferred;
  if (await isPortAvailable(fallback)) return fallback;
  for (let i = 9002; i <= 9010; i++) {
    if (await isPortAvailable(i)) return i;
  }
  return null;
}

// Lanza el proceso del servidor y lo VIGILA: si muere inesperadamente, lo relanza (watchdog)
function spawnServer(port) {
  const serverScript = path.join(__dirname, '..', 'server.py');
  serverProcess = spawn('python', [serverScript, '--port', String(port)], {
    cwd: path.join(__dirname, '..'),
    windowsHide: true,
    env: { ...process.env, SIGNALOS_MANAGED: '1' }  // el server sabe que Electron lo gestiona
  });
  serverProcess.on('error', (e) => console.error('Server error:', e));
  serverProcess.on('exit', (code) => {
    if (isQuitting) return;
    console.error(`[watchdog] el servidor terminó (code ${code}); relanzando en 1.5s...`);
    setTimeout(() => spawnServer(port), 1500);  // <-- watchdog: revive el servidor
  });
}

// Arranque inicial: lanza el server y espera a que acepte conexiones
function startServer(port) {
  return new Promise((resolve, reject) => {
    spawnServer(port);
    let attempts = 0;
    const checkServer = setInterval(() => {
      attempts++;
      const client = net.createConnection(port, 'localhost', () => {
        clearInterval(checkServer); client.destroy(); resolve(port);
      });
      client.on('error', () => {
        if (attempts >= 30) { clearInterval(checkServer); reject(new Error('Server startup timeout')); }
      });
    }, 500);
  });
}

function createWindow(port) {
  const config = loadConfig();
  const kiosk = !!config.kiosk;
  mainWindow = new BrowserWindow({
    width: 1280, height: 800, minWidth: 800, minHeight: 600,
    fullscreen: kiosk,
    kiosk: kiosk,
    frame: !kiosk,            // sin bordes en modo kiosco
    autoHideMenuBar: true,
    backgroundColor: '#000000',
    webPreferences: { nodeIntegration: false },
    icon: path.join(__dirname, '..', 'assets', 'icon.ico')
  });

  // En kiosco la ventana ES la pantalla (player); si no, es el panel de administración
  const screen = encodeURIComponent(config.kiosk_screen || 'pantalla1');
  const urlPath = kiosk ? `/player.html?screen=${screen}` : '/';
  mainWindow.loadURL(`http://localhost:${port}${urlPath}`);

  if (kiosk) {
    // Ocultar el cursor y bloquear atajos que cierren/recarguen la app
    mainWindow.webContents.on('did-finish-load', () => {
      mainWindow.webContents.insertCSS('*{cursor:none !important}');
    });
    mainWindow.webContents.on('before-input-event', (event, input) => {
      const k = (input.key || '').toLowerCase();
      if ((input.alt && k === 'f4') || (input.control && (k === 'w' || k === 'r')) || k === 'f11' || k === 'f5') {
        event.preventDefault();
      }
    });
    // Watchdog del renderer: si el player se cuelga o crashea, recargar
    mainWindow.on('unresponsive', () => { if (!isQuitting) mainWindow.webContents.reload(); });
    mainWindow.webContents.on('render-process-gone', () => { if (!isQuitting) mainWindow.reload(); });
  } else {
    mainWindow.on('minimize', (e) => { e.preventDefault(); mainWindow.hide(); });
  }

  // Bloquear el cierre (Alt+F4) salvo salida intencional desde la bandeja
  mainWindow.on('close', (event) => {
    if (!isQuitting) { event.preventDefault(); if (!kiosk) mainWindow.hide(); }
  });

  if (process.argv.includes('--dev')) mainWindow.webContents.openDevTools();
}

function createTray(port) {
  tray = new Tray(path.join(__dirname, '..', 'assets', 'icon.ico'));
  const contextMenu = Menu.buildFromTemplate([
    { label: 'InTeks Display', enabled: false },
    { type: 'separator' },
    { label: 'Abrir Admin', click: () => shell.openExternal(`http://localhost:${port}/`) },
    { label: 'Recargar pantalla', click: () => { if (mainWindow) mainWindow.reload(); } },
    { type: 'separator' },
    { label: 'Salir', click: () => { isQuitting = true; app.quit(); } }
  ]);
  tray.setContextMenu(contextMenu);
  tray.setToolTip('InTeks Display');
  tray.on('click', () => { if (mainWindow) (mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show()); });
}

// Instancia única: evita dos copias compitiendo por el puerto
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('ready', async () => {
    try {
      const config = loadConfig();
      // Arranque automático con Windows
      try { app.setLoginItemSettings({ openAtLogin: !!config.autostart, path: process.execPath }); } catch (e) {}

      const port = await findAvailablePort(config.port, config.port_fallback);
      if (!port) { dialog.showErrorBox('Error', 'No hay puertos disponibles'); app.quit(); return; }
      currentPort = port;

      await startServer(port);
      createWindow(port);
      createTray(port);

      config.port = port;
      saveConfig(config);
    } catch (err) {
      dialog.showErrorBox('Error', `No se pudo iniciar: ${err.message}`);
      app.quit();
    }
  });
}

app.on('before-quit', () => {
  isQuitting = true;
  if (serverProcess) { try { serverProcess.kill(); } catch (e) {} }
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });

app.on('activate', () => { if (!mainWindow) createWindow(currentPort); else mainWindow.show(); });

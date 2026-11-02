# Acceso remoto con cuenta y PIN — diseño

Fecha: 2026-11-02 · Estado: pendiente de revisión

## Objetivo

Que cualquier PC con InTeks Display sea accesible desde internet en su propia
dirección (`tienda1.inteksdisplay.com`) **sin que el usuario escriba comandos ni
toque Cloudflare**: saca un PIN en su cuenta, lo mete en el panel del PC y ya.

Hoy (2026-11-02) esto se hizo a mano en un PC de pruebas: dominio en Cloudflare,
túnel «InTeks Display» y servicio `cloudflared`. Este diseño automatiza ese camino
y lo hace repetible para varios PCs.

## Decisiones tomadas con Axel

- **Para quién:** solo sus locales, una única cuenta. Sin registro público ni
  verificación de correo. Los clientes se añadirán en otra versión.
- **Dirección de cada PC:** se elige al sacar el PIN (`tienda1`), no sale del
  nombre de la instalación.
- **Entrada a la cuenta:** Cloudflare Access con código por correo. No hay
  contraseñas propias (no se escribe código de login).
- **Un túnel por PC.** Nunca dos PCs en el mismo túnel: Cloudflare repartiría las
  visitas entre servidores con contenido distinto.

## Piezas

### 1. Worker «InTeks Cuenta» (`cuenta/`, nuevo)

Cloudflare Worker en `cuenta.inteksdisplay.com`, con un KV (`PCS`) y dos secretos:
`CF_API_TOKEN` y `CF_ACCOUNT_ID` (más el ID de zona de `inteksdisplay.com`).

- **La web de la cuenta** (`GET /`, `/api/pcs`, `POST /api/pcs`, `DELETE /api/pcs/:nombre`)
  va detrás de **Cloudflare Access** (política: solo el correo de Axel). El Worker
  comprueba además la cabecera `Cf-Access-Jwt-Assertion` por si Access se
  desconfigura; sin ella responde 403.
  - Lista de PCs: nombre, dirección, creado y estado (en línea / sin conexión).
  - «Añadir PC»: valida el nombre, crea el registro `pendiente` con un PIN de 6
    cifras (aleatorio criptográfico) válido 10 minutos y de un solo uso.
  - «Quitar PC»: borra el túnel y el registro DNS en Cloudflare y la entrada del KV.
- **Endpoint público** `POST /api/enlazar` `{pin}` (fuera de Access, es el que
  llama el servidor del PC):
  1. Limita intentos: 5 fallos por IP en 10 minutos y 30 fallos globales por hora
     (tras eso responde 429 y exige esperar).
  2. Busca el PIN en el KV (comparación de tiempo constante). Si no existe,
     caducó o ya se usó: mismo mensaje genérico para los tres casos.
  3. Crea el túnel (`POST /accounts/{id}/cfd_tunnel`, `config_src: cloudflare`),
     su configuración (`ingress`: `hostname → http://localhost:80`, y `http_status:404`
     por defecto) y el CNAME proxied `nombre.inteksdisplay.com → {id}.cfargotunnel.com`.
  4. Marca el PIN como usado y devuelve `{token, hostname}`, donde `token` es el
     del túnel (`GET /cfd_tunnel/{id}/token`).
  5. Si cualquier paso falla, deshace lo creado (túnel y DNS) y deja el PIN sin
     gastar para poder reintentar.
- **Nombres:** `^[a-z0-9]([a-z0-9-]{0,28}[a-z0-9])?$`, únicos, y una lista
  reservada (`cuenta`, `www`, `mail`, `api`, `admin`, `ftp`, `smtp`, `imap`, `pop`,
  `autodiscover`, `_dmarc`, `_domainconnect`, `ns1`, `ns2`).
- **Permisos de la llave de API (mínimos):** Account · Cloudflare Tunnel · Edit,
  y Zone · DNS · Edit solo sobre `inteksdisplay.com`.
- **Estado de cada PC:** no hay latido propio. Al abrir la lista, el Worker pregunta
  a Cloudflare el estado de cada túnel (`healthy`, `degraded`, `down`, `inactive`) y
  lo enseña como «en línea» / «sin conexión».

### 2. Servidor del PC (`server.py`)

- Estado en `<DATA_DIR>\acceso-remoto.json`: `{hostname, tunel_id?, activado_en}`.
  Nunca guarda el token (lo guarda el servicio de Windows).
- `GET /api/acceso-remoto` (admin): `{disponible, activo, hostname, servicio}`.
- `POST /api/acceso-remoto/activar` `{pin}` (admin):
  - **Rechaza si el panel no tiene contraseña de administrador** (quedaría abierto
    a internet).
  - Valida el PIN (6 cifras) y llama a `https://cuenta.inteksdisplay.com/api/enlazar`.
  - Instala `cloudflared` (`cloudflared.exe service install <token>`) con el
    `cloudflared.exe` incluido en el instalador. Corre como SYSTEM, así que puede.
  - El token **no** viaja en argumentos visibles en el registro: se redacta en
    cualquier salida, como la passphrase del LG.
  - Un único trabajo a la vez, en un hilo, con estado consultable (patrón de
    `/api/lg-instalar`).
- `POST /api/acceso-remoto/desactivar` (admin): desinstala el servicio y borra
  `acceso-remoto.json`. La dirección se quita del todo desde la cuenta.
- Si ya había un servicio `cloudflared` (de otro túnel), lo desinstala antes y se
  lo dice al usuario en el aviso previo.
- Prueba y desarrollo: variable `SIGNALOS_CUENTA_URL` para apuntar a un Worker falso
  y `SIGNALOS_CLOUDFLARED` para un ejecutable falso.

### 3. Panel (`admin.html`)

Tarjeta «Acceso remoto» en Ajustes → Seguridad y acceso:

- Sin activar: campo de PIN (6 cifras) y botón «Activar acceso remoto», con el
  texto «Saca el PIN en cuenta.inteksdisplay.com → Añadir PC».
- Activando: progreso en pasos (comprobando PIN, creando túnel, instalando
  servicio, comprobando conexión).
- Activo: «Conectado: https://tienda1.inteksdisplay.com» con botón de copiar y
  «Desconectar».
- Si no hay contraseña de administrador: la tarjeta lo explica y enlaza a
  crearla; el botón está desactivado.

### 4. Instalador

- Incluye `cloudflared.exe` (versión fija, SHA-256 comprobado al construir).
- La actualización automática lo conserva; no hay casilla nueva.

## Seguridad

- La llave de API vive solo como secreto del Worker. No está en el repo, ni en el
  instalador, ni en ningún PC.
- El PIN: 6 cifras, 10 minutos, un uso, comparación de tiempo constante, límite de
  intentos por IP y global. Con 10⁶ combinaciones y 30 intentos/hora el ataque de
  fuerza bruta es inviable dentro de la ventana de 10 minutos.
- El panel de cada PC sigue protegido por su contraseña de administrador; el
  acceso remoto no la sustituye.
- Los datos de cada PC (pantallas, contenido) siguen en el PC. Cloudflare solo
  transporta el tráfico.

## Pruebas

- **Worker (Node, `node --test`):** API de Cloudflare simulada. Casos: PIN válido,
  caducado, ya usado, inexistente; límite de intentos; nombre inválido, repetido,
  reservado; rollback si falla el DNS; «Quitar PC»; rechazo sin cabecera de Access.
- **Servidor (Python, `tests/test_acceso_remoto.py`):** Worker falso y
  `cloudflared` falso. Casos: activar con éxito, PIN malo, sin contraseña de admin,
  segundo trabajo mientras hay uno, desactivar, redacción del token.
- **De punta a punta:** en este PC, con el Worker real, un PIN real y la dirección
  comprobada desde internet.

## Fuera de esta versión

Registro de clientes, varias cuentas, facturación, estado en tiempo real
(la lista solo lo consulta al abrirse) y gestión de pantallas desde la nube.

## Pasos que hace Axel (una vez)

1. Iniciar sesión en Cloudflare cuando `wrangler` lo pida.
2. Crear la política de Access (su correo) para `cuenta.inteksdisplay.com`.
3. Aprobar la llave de API con permisos mínimos (la crea Claude desde el
   navegador; no se enseña).

# Guía: Acceso remoto a InTeks Display con Cloudflare Tunnel

> Objetivo: que tus pantallas (Smart TV, tablet, mini-PC) y tú podáis acceder al
> servidor InTeks Display **desde cualquier lugar** a través de una URL `https://`,
> sin abrir puertos en el router y sin VPN en los dispositivos.
>
> Escenario: dominio comprado en **Hostinger**, servidor InTeks Display en una **PC con
> Windows** (puerto 80), una pantalla **Smart TV en otra oficina**.

---

> **Nota (1.0.67):** esta guía es el método manual. Desde la 1.0.67 el panel trae
> **Ajustes → Acceso remoto**, que enlaza cada PC con un PIN de tu cuenta sin tocar Cloudflare.
> Esta guía sigue valiendo para entenderlo o para montarlo a mano.

## 0. Resumen de cómo queda

```
   https://signage.tudominio.com
            │
     ☁ Cloudflare (HTTPS automático)
            │  (conexión SALIENTE desde el servidor; sin abrir puertos)
            ▼
   PC servidor (Windows)  ──  cloudflared (servicio)  ──►  InTeks Display en localhost:80
            │
   (otros sistemas con credenciales: INTACTOS, no se tocan)

   Smart TV oficina 2  ─────►  abre https://signage.tudominio.com  (sin instalar nada)
```

- **Una sola URL** = puerta de entrada a todo. Cada pantalla se distingue por su
  identidad (se enlaza una vez con el PIN y la recuerda).
- El admin entra en `https://signage.tudominio.com/admin.html` (pide contraseña).
- Todo es **gratis** salvo el dominio (~10 USD/año en Hostinger).

---

## 1. Antes de empezar (requisitos)

- [ ] Dominio comprado en Hostinger (ej. `tudominio.com`).
- [ ] La PC servidor enciende y ejecuta InTeks Display (`python server.py`, puerto 80).
- [ ] **Contraseña del admin ya creada** (la pusiste en la primera pantalla de login).
- [ ] **Token de API** copiado desde el admin → *Ajustes → Seguridad y acceso*
      (lo necesitarás solo si usarás la extensión de Chrome a distancia).

> ⚠️ Importante: NO expongas el servidor a internet sin la contraseña del admin.
> Eso ya está hecho en InTeks Display, pero verifica que al abrir `/admin.html` te pide login.

---

## 2. Crear cuenta en Cloudflare y añadir tu dominio

1. Entra en https://dash.cloudflare.com y crea una cuenta **gratuita**.
2. Pulsa **"Add a site" / "Añadir un sitio"** e introduce `tudominio.com`
   (sin `www`, sin `https`).
3. Elige el plan **Free** (0 USD).
4. Cloudflare escaneará los registros DNS existentes. Pulsa **Continuar**.
5. Cloudflare te mostrará **2 nameservers**, algo como:
   ```
   xxxx.ns.cloudflare.com
   yyyy.ns.cloudflare.com
   ```
   👉 **Cópialos**, los necesitas en el paso siguiente.

---

## 3. Apuntar el dominio de Hostinger a Cloudflare (cambiar nameservers)

1. Entra en tu panel de **Hostinger** → **Dominios** → selecciona `tudominio.com`.
2. Busca **"DNS / Nameservers"** (o "Servidores de nombres").
3. Elige **"Cambiar nameservers" / "Usar nameservers personalizados"**.
4. Borra los de Hostinger y pega los **2 de Cloudflare** del paso anterior.
5. Guarda.

⏳ La activación tarda de **15 minutos a 24 horas** (normalmente <1 h).
Cloudflare te enviará un email "tu dominio está activo" cuando termine.
En el panel de Cloudflare el sitio pasará de *"Pending"* a *"Active"*.

> No sigas al paso 4 hasta que Cloudflare diga **Active**.

---

## 4. Crear el túnel (método panel — el más fácil)

Usaremos el panel **Zero Trust**, que instala `cloudflared` como **servicio de
Windows** (arranca solo con la PC, ideal para señalización).

1. En el panel de Cloudflare, menú izquierdo → **Zero Trust**
   (la primera vez te pedirá un nombre de equipo y elegir plan **Free**).
2. Dentro de Zero Trust: **Networks → Tunnels → Create a tunnel**.
3. Tipo de conector: **Cloudflared** → **Next**.
4. Nombre del túnel: `signalos` → **Save tunnel**.
5. Te mostrará la instalación para distintos sistemas → elige **Windows (64-bit)**.
   Verás algo así:
   - Un botón para **descargar `cloudflared`** (un `.exe`).
   - Un comando con un **token largo**, parecido a:
     ```
     cloudflared.exe service install eyJhIjoiXXXX....token-muy-largo....
     ```
6. En la PC servidor:
   - Descarga `cloudflared.exe` y guárdalo, por ejemplo, en
     `C:\cloudflared\cloudflared.exe`.
   - Abre **PowerShell como Administrador** y ejecuta el comando que te dio
     Cloudflare (pega el token tal cual):
     ```powershell
     cd C:\cloudflared
     .\cloudflared.exe service install eyJhIjoiXXXX....token....
     ```
   - Esto instala y arranca el servicio. Vuelve al panel: el túnel debe aparecer
     como **"Healthy" / "Connected"** (puede tardar ~30 s). Pulsa **Next**.

> 💡 Alternativa por línea de comandos (sin panel): ver Anexo A al final.

---

## 5. Conectar el subdominio con InTeks Display

Seguimos en el asistente del túnel, pestaña **Public Hostname** (o
*Route traffic → Public hostnames → Add a public hostname*):

1. **Subdomain**: `signage`
2. **Domain**: elige `tudominio.com` en el desplegable
   *(aparece porque ya está activo en Cloudflare — paso 3).*
3. **Path**: déjalo vacío.
4. **Service**:
   - Type: **HTTP**
   - URL: `localhost:80`
5. **Save hostname**.

✅ ¡Listo! En 1–2 minutos, `https://signage.tudominio.com` apunta a tu InTeks Display.

### Añadir más subdominios (opcional)
Puedes repetir el paso 5 con otros subdominios al **mismo** `localhost:80`,
por ejemplo `admin.tudominio.com` o `pantallas.tudominio.com`. No es necesario:
con un solo subdominio te basta para todo.

---

## 6. Probar que funciona

Desde **cualquier** dispositivo (tu móvil con datos, otra oficina, etc.):

| Abre en el navegador | Debe pasar |
|---|---|
| `https://signage.tudominio.com` | Pantalla "Iniciando…" → te lleva a emparejar (si el aparato no está enlazado) |
| `https://signage.tudominio.com/admin.html` | Pide **contraseña** del admin |
| `https://signage.tudominio.com/pair` | Pantalla de emparejamiento (PIN) |

Si ves el candado 🔒 (HTTPS) y carga, **funciona**.

---

## 7. Enlazar la pantalla de la otra oficina (Smart TV)

1. En el navegador del TV, abre: `https://signage.tudominio.com`
2. Mostrará "Pantalla sin enlazar — pidiendo código".
3. En tu admin, ve a la sección de emparejamiento y genera/lee el **PIN**.
4. En el TV, introduce el **PIN** y un **nombre** (ej. `tv-oficina2`).
5. El TV queda enlazado y **lo recuerda**: si se apaga y enciende, reanuda solo
   abriendo la misma URL (gracias a la memoria por dispositivo).

> Configura el navegador del TV para que abra esa URL al arrancar (modo kiosco),
> y ya no tendrás que tocar nada más.

---

## 8. Usar la extensión de Chrome a distancia (opcional)

Si actualizas tipos de cambio desde otra PC con la extensión:

1. Abre el panel lateral de la extensión.
2. Campo **Servidor**: `https://signage.tudominio.com`
3. Campo **Token**: pega el **Token de API** (admin → *Ajustes → Seguridad*).
4. Guarda (✓). Ya puede enviar divisas de forma segura por internet.

---

## 9. Ventajas que ganas con esto (bonus)

- 🔒 **HTTPS real y gratis** (certificado automático de Cloudflare).
- 📴 **Caché offline (Service Worker) ahora SÍ funciona**: los Service Workers solo
  operan en `localhost` o `https://`. Al servir por HTTPS, las pantallas cachean
  el contenido y aguantan cortes de internet mucho mejor.
- 🚪 **Cero puertos abiertos** en el router (la conexión sale del servidor).
- 🛡️ Tus otros sistemas con credenciales **no se ven afectados** (cloudflared solo
  expone el puerto 80 de InTeks Display, nada más).

---

## 10. Mantenimiento y notas

- **Reinicios de la PC**: `cloudflared` está como servicio → arranca solo. Asegúrate
  también de que InTeks Display arranque solo (admin → *Ajustes → Iniciar con Windows*).
- **El servidor debe estar encendido**: si la PC se apaga, las pantallas pierden
  conexión (igual que en local). El túnel no sustituye a tener el servidor activo.
- **Vídeo pesado**: el plan gratis de Cloudflare desaconseja usarlo como CDN de
  vídeo HD masivo (ToS, sección 2.8). Para unas pocas pantallas con imágenes y
  vídeos cortos, sin problema. Si crecieras mucho, lo revisamos.
- **Cambiar el PIN o la contraseña**: se hace desde el admin como siempre; el túnel
  no cambia nada de eso.

---

## 11. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| El dominio sigue "Pending" en Cloudflare | Nameservers no propagados | Espera; verifica en Hostinger que pusiste **exactamente** los 2 NS de Cloudflare |
| `signage.tudominio.com` da error 1033 / "tunnel not found" | El servicio cloudflared no corre | En la PC: `Get-Service cloudflared` → debe estar *Running*. Reinícialo: `Restart-Service cloudflared` |
| Carga pero da **502 Bad Gateway** | InTeks Display no está activo en localhost:80 | Arranca `python server.py`; comprueba `http://localhost` en la propia PC |
| El subdominio no aparece en el desplegable | El dominio no está *Active* en Cloudflare | Termina el paso 3 antes del 5 |
| La extensión da 401 a distancia | Falta el token o URL incorrecta | Pon `https://signage.tudominio.com` + el token en la extensión |
| Quiero ver logs del túnel | — | `cloudflared.exe tunnel info signalos` o revisa el panel Zero Trust → Tunnels |

---

## Anexo A — Método por línea de comandos (alternativa avanzada)

Si prefieres no usar el panel Zero Trust:

```powershell
# 1. Autenticar (abre el navegador para elegir el dominio)
.\cloudflared.exe tunnel login

# 2. Crear el túnel
.\cloudflared.exe tunnel create signalos
#   -> genera un archivo de credenciales <UUID>.json y un Tunnel ID

# 3. Crear el registro DNS del subdominio
.\cloudflared.exe tunnel route dns signalos signage.tudominio.com

# 4. Crear el archivo de configuración  C:\Users\TU_USUARIO\.cloudflared\config.yml
#    (sustituye el UUID y la ruta del .json):
```
```yaml
tunnel: <UUID-del-tunel>
credentials-file: C:\Users\TU_USUARIO\.cloudflared\<UUID>.json

ingress:
  - hostname: signage.tudominio.com
    service: http://localhost:80
  - service: http_status:404
```
```powershell
# 5. Instalar como servicio (arranca con Windows)
.\cloudflared.exe service install

# 6. Probar manualmente (opcional, antes del servicio)
.\cloudflared.exe tunnel run signalos
```

---

## Checklist rápida

- [ ] Dominio comprado en Hostinger
- [ ] Sitio añadido a Cloudflare (plan Free)
- [ ] Nameservers de Cloudflare puestos en Hostinger → estado **Active**
- [ ] Túnel `signalos` creado y **Healthy**
- [ ] `cloudflared` instalado como **servicio** en la PC servidor
- [ ] Public hostname `signage.tudominio.com` → `HTTP localhost:80`
- [ ] Probado `https://signage.tudominio.com` desde fuera
- [ ] Contraseña del admin verificada
- [ ] (Opcional) Extensión configurada con URL https + token
- [ ] InTeks Display y cloudflared configurados para **arrancar con Windows**

---

*Documento generado para InTeks Display. Cuando tengas el dominio, sígueme los pasos
1→6 y avísame si algo no cuadra; lo afinamos juntos.*

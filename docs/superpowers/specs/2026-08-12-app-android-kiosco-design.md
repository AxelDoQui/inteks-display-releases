# App propia de kiosco para Android — diseño

> Estado: **diseñado, sin implementar** (2026-08-12). Sustituye a Fully Kiosk
> Browser (~7 € por pantalla) en las cajas Android que reproducen el player.
> Todo lo de «Lo medido» está comprobado por ADB contra el aparato real, no
> supuesto.

## El problema

Hoy una pantalla de tienda se monta con una caja Android + **Fully Kiosk
Browser**, y a Fully se le pega a mano el enlace directo de la pantalla. Eso
funciona —lleva meses funcionando en la tienda del LG— pero arrastra tres cosas:

1. **7 € por pantalla**, y una dependencia de un tercero sobre el que no
   tenemos ningún control.
2. **La dirección se escribe a mano** en un aparato sin pantalla táctil, letra
   a letra con la cruceta del mando. El propio `MANUAL.md` dice que teclear con
   el mando de un televisor «es lento y se equivoca uno» — y es justo por eso
   que el nombre de la pantalla se pone desde el ordenador.
3. **Si el PC cambia de IP** (DHCP tras reiniciar el router), todas las
   pantallas con la URL pegada se quedan muertas y hay que ir una por una.

## Lo medido en el aparato real

Caja **MXQ PRO 4K 5G**, la más básica del mercado, medida por ADB el
2026-08-12. Si funciona aquí, funciona en cualquier sitio.

| | Real | Consecuencia de diseño |
|---|---|---|
| Android | **7.1.2 · API 25** | `minSdk` bajo. Los ajustes del aparato dicen «Android 10»: **mienten** |
| SoC / ABI | Amlogic **S905W** · `armeabi-v7a` | 32 bits, sin arm64. No hay librerías nativas, así que da igual, pero conviene saberlo |
| RAM | **990 MB** (640 libres) | El proceso de render puede morir. Ver «El vigilante» |
| WebView | **119.0.6045.193** | Chrome 119: `clamp()`, IndexedDB, SSE y `-webkit-line-clamp` funcionan. **Congelado ahí para siempre**: Chrome 120 exige Android 8 |
| Pantalla | **1280×720**, densidad 160 | El «4K» del nombre es marketing. El player renderiza a 720 px CSS |
| Tipo | `leanback` **y** `leanback_only` | Dispositivo solo-TV, **sin táctil**. Obliga a `CATEGORY_LEANBACK_LAUNCHER` |
| Play Store | Presente, con GMS | Por eso el WebView llegó a la 119 |
| ROM | `test-keys`, `userdebug`, 2024-07-04 | Sin certificar por Google. Sideload sin problema |
| Red | HTTP al servidor ✅, ICMP bloqueado | El `ping` falla y **no significa nada**: lo bloquea el cortafuegos de Windows |

Verificado además que **la aplicación web entera renderiza bien** en esa caja:
se cargó `http://192.168.0.63/` en su Chrome y salió la página de emparejar
correcta, con su código de cuatro cifras. La barra del navegador se comía 90 px
de los 720 — un 12 % de la pantalla que una app de kiosco recupera.

## Decidido con el usuario

| Decisión | Elegido | Por qué |
|---|---|---|
| Alcance | **Equivalente a Fully**, sin tocar `server.py` | Lo que se quiere es quitar la dependencia y el coste, no rehacer el emparejamiento |
| Cómo encuentra el servidor | **Barrido de la subred**, y escribir a mano si falla | `/api/info` es público y sin token. No hace falta mDNS ni cambiar el servidor |
| Fuerza del kiosco | **Arranca sola y se pone delante**, sin reemplazar el lanzador | Reversible. Con el botón de inicio del mando se sale, así que no puede dejar la caja inservible |
| Dónde vive el código | **`android/` en este mismo repo** | La app y el servidor se versionan juntos. Nada de lo que existe hoy pasa a necesitar compilarse |

### Por qué no las otras vías de descubrimiento

**mDNS / DNS-SD con `NsdManager`.** Sería lo canónico, pero el responder mDNS
de `server.py` (`_mdns_response()`) **solo emite registros A** —nombre → IP—,
no publica PTR/SRV/TXT, que es lo que consume `NsdManager`. Habría que
escribir DNS-SD en el servidor. Es la razón por la que hoy Android necesita la
IP y no puede usar `signage.local`. Queda como mejora futura, no como
requisito.

**Escribir la dirección a mano y ya está**, como Fully. Es lo más simple, pero
en un aparato `leanback_only` significa teclado en pantalla y cruceta, y no
resuelve el cambio de IP. Se conserva **como respaldo**, no como camino
principal.

## Forma de la solución

La app es deliberadamente pequeña porque **la inteligencia de producto ya está
en la web**: identidad de pantalla, emparejamiento por PIN, caché offline en
IndexedDB, SSE y recarga por versión viven en `index.html` y `player.html`. La
app solo aporta lo que un navegador no puede.

```
android/app/src/main/java/com/inteks/display/
│
├── ServerFinder.kt      Encuentra el servidor en la red local
├── SettingsStore.kt     Recuerda la URL y el nombre de pantalla
├── KioskActivity.kt     El WebView a pantalla completa
├── SetupActivity.kt     Escribir la dirección a mano, con cruceta
└── BootReceiver.kt      BOOT_COMPLETED → lanza KioskActivity
```

**Flujo:**

```
Arranque (encender la caja o abrir la app)
    │
    ├─ ¿hay URL guardada? ──sí──► KioskActivity la carga
    │                                    │
    │                                    └─ falla repetidamente ──┐
    │                                                             │
    └─ no ──► ServerFinder.buscar() ◄────────── rebarrido ────────┘
                    │
                    ├─ encontrado ──► guardar + cargar
                    └─ nada        ──► SetupActivity (a mano)
```

`ServerFinder` es la única pieza con lógica real y está aislada a propósito: no
toca Android salvo para preguntar su propia IP y máscara. Prueba
`/api/info` en toda la subred, en los puertos **80 y 9000** (los dos que usa
`config.json`), y **valida que la respuesta es InTeks** —JSON con `mdns_name`—
y no cualquier otro servidor web de la red.

Cifras concretas: **1,5 s de timeout por dirección**, **32 sondas en paralelo**
y **8 s de tope** para el barrido entero; pasado ese tope se va a
`SetupActivity`. Con una subred /24 son 508 sondas (254 × 2 puertos), que a 32
a la vez caben de sobra en el presupuesto. Si la máscara **no es /24** —una /16
serían 65.534 direcciones— no se barre: se va directo a escribir a mano, porque
un barrido así tardaría minutos y molestaría a la red de la tienda.

Los reintentos de carga usan **espera creciente de 2 s a 60 s** (2, 4, 8, 16,
32, 60, 60…), sin rendirse nunca: una pantalla de tienda tiene todo el tiempo
del mundo y lo que no puede es quedarse muerta esperando a que alguien la
toque.

## Lo que decide si funciona o no

Cuatro ajustes del WebView. Los tres primeros, si faltan, dan fallos que no
parecen lo que son:

| Ajuste | Si falta |
|---|---|
| `android:usesCleartextTraffic="true"` | **No carga nada.** El servidor es HTTP plano y Android lo bloquea por defecto con `targetSdk` 28+ |
| `domStorageEnabled = true` | La pantalla **pierde su identidad en cada reinicio** y vuelve a pedir código. El bloque de identidad usa `localStorage` |
| `mediaPlaybackRequiresUserGesture = false` | **Los vídeos no arrancan solos**: se quedan en el primer fotograma esperando un clic que nadie dará |
| `javaScriptEnabled = true` | Nada funciona |

Del manifiesto, dos cosas que salen de lo medido:

- **`CATEGORY_LEANBACK_LAUNCHER` + banner 320×180**, además de
  `CATEGORY_LAUNCHER`. La caja declara `leanback_only`: con solo `LAUNCHER` la
  app **no aparecería en el lanzador**; con solo `LEANBACK` no saldría en cajas
  normales.
- **`minSdk 21`, `targetSdk 28`, `compileSdk 36`.** El `targetSdk` se queda en
  28 a propósito: desde el 29, Android restringe **lanzar una actividad desde
  segundo plano**, que es exactamente lo que hacen `BootReceiver` y el latido.
  Como la distribución es por sideload y no por Play Store, no hay ningún
  mínimo que cumplir. `compileSdk 36` porque es la plataforma que ya está
  instalada (`android-36.1`).

**Orientación: la app no fuerza ninguna.** El player ya rota por CSS con
`config.rotation`; imponer `landscape` pelearía contra una función que existe.

### El vigilante

Con 990 MB de RAM el proceso de render del WebView puede morir. En API 25 **no
existe `onRenderProcessGone`** (llegó en API 26), así que cuando eso pasa cae
la app entera y nadie la levanta: escaparate en negro — el mismo síntoma que
dio el LG.

Un servicio en segundo plano no sirve: moriría con el proceso. La solución es
un **latido de `AlarmManager`**, que vive en el sistema y sobrevive a la caída
de la app. Cada **2 minutos** (`setInexactRepeating`, que el sistema agrupa con
otras alarmas y no gasta batería ni CPU) comprueba si `KioskActivity` está
delante y, si no, la lanza. Se registra al arrancar la app y en
`BOOT_COMPLETED`, porque las alarmas no sobreviven a un reinicio.

Cubre los tres casos que dejan un escaparate muerto: el render sin memoria, la
app cerrada por el sistema, y alguien que salió al lanzador con el mando y se
dejó ahí.

## La identidad y el cambio de IP

`localStorage` y las cookies están atados al **origen**.
`http://192.168.0.63` y `http://192.168.0.70` son orígenes distintos, así que
un cambio de IP por DHCP dejaría a la pantalla sin identidad: el rebarrido
encontraría el servidor y la pantalla pediría código otra vez. El
auto-reparado se comería a sí mismo.

**La salida no toca la web.** `index.html:68` redirige a
`/player.html?screen=NOMBRE`, así que la app **observa la URL** y, cuando el
navegador llega ahí, se guarda ese nombre en sus preferencias —fuera del
WebView, fuera del origen—. Si la IP cambia, carga
`<nuevabase>/player.html?screen=<nombre>` y la pantalla sigue siendo quien era.

Esto hace la app **estrictamente mejor que Fully** en el caso del DHCP, que es
el fallo de campo más probable después del corte de luz.

## Errores y fallos

| Situación | Respuesta |
|---|---|
| Arranque: la wifi aún no ha subido | Reintento con espera creciente, sin pantalla de error. Al encender, la red tarda más que Android |
| El servidor cae **con el player ya cargado** | **No hacer nada.** El player sigue con su caché. Tapar eso con un «sin conexión» empeoraría el producto |
| El servidor cae **antes de cargar nada** | Pantalla propia de «buscando…» y reintento |
| `/api/info` falla varias veces seguidas | Rebarrido. Si aparece en otra IP, recargar conservando el nombre de pantalla |
| El render se queda sin memoria | El latido de `AlarmManager` levanta la app |

La regla que gobierna todo esto: **la app no debe estorbar a la resiliencia que
el player ya tiene.** Nuestra pantalla solo cuando el WebView no tiene nada que
enseñar.

## Pruebas

`ServerFinder` no depende de Android, así que su lógica —enumerar la subred,
validar que la respuesta es InTeks, timeouts, red caída, máscara distinta de
/24— va en **tests de JVM que corren sin aparato** (`gradlew test`).

El resto no se puede fingir y se verifica en la MXQ por ADB:

```
instalar          adb install -r app-release.apk
arranque real     adb reboot                 → ¿sale sola?
caída del render  adb shell am force-stop …  → ¿la levanta el latido?
sin red           desenchufar el cable       → ¿sigue reproduciendo de caché?
cambio de IP      mover el servidor          → ¿rebarre y conserva el nombre?
```

Es la aplicación directa de la lección de julio: **comprobar el efecto, no la
ausencia de errores.**

## Versionado y ubicación

La app entra en la disciplina que ya existe: `tools/subir-version.ps1` pasa a
tocar también `android/app/build.gradle.kts`, y `tests/version-sync.test.js` a
vigilar que coincida con `server.py`, `setup.iss` y `package.json`. Así no
puede salir un APK «1.0.0» como pasó con los cinco instaladores del 2026-08-09.

`.gitignore` excluye `android/build/`, `android/.gradle/` y
`android/app/build/`, igual que ya excluye `vendor/python/`.

**La regla «sin paso de build» se mantiene** para todo lo que existe hoy: el
servidor y las páginas se siguen editando y sirviendo tal cual. El paso de
compilación queda acotado a `android/`, que es código nativo y no puede ser de
otra manera.

## Lo que no se puede verificar aquí

Y hay que decirlo claro, como siempre:

- Que aguante **días encendida** sin degradarse.
- Que vuelva bien tras un **corte de luz de verdad**, que no es lo mismo que un
  `adb reboot` ordenado.
- Que el WebView 119 no se deteriore tras semanas sin reiniciar.

Ese bucle va al ritmo de quien tenga la caja delante, no al de quien escribe el
código.

## Fuera de alcance, a propósito

- **DNS-SD en el servidor** para descubrimiento canónico con `NsdManager`.
  Anotado arriba; hoy no hace falta porque el barrido resuelve el caso.
- **Reemplazar el lanzador** del sistema. Se descartó por reversibilidad.
- **Distribuir el APK** (servirlo desde el propio InTeks Display, firmarlo para
  actualizaciones). Para la primera versión se instala con `adb install`.
- **Android TV certificado / Play Store.** Se instala por sideload.

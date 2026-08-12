# App de kiosco Android — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Una app Android que sustituya a Fully Kiosk Browser: encuentra el servidor InTeks sola en la red, muestra el player a pantalla completa, arranca al encender la caja y se levanta sola si se cae.

**Architecture:** Un `WebView` a pantalla completa apuntado a `<base>/`, que deja que la web ya existente (`index.html` → `pair` o `player`) haga todo el trabajo de producto. La app solo aporta lo que un navegador no puede: descubrir el servidor barriendo la subred contra `/api/info`, arrancar en `BOOT_COMPLETED`, y un latido de `AlarmManager` que la relanza si muere. No se toca `server.py` ni ninguna página web.

**Tech Stack:** Kotlin, Gradle 9.4.1, Android Gradle Plugin 9.2.1, JDK 21 (el de Android Studio), JUnit 4.13.2. Sin dependencias de terceros: `HttpURLConnection` de la stdlib, sin OkHttp, sin Compose.

## Global Constraints

Todo esto está **verificado en esta máquina y en la caja real** el 2026-08-12. No son valores de catálogo.

- **`JAVA_HOME` debe apuntar a** `C:\Program Files\Android\Android Studio\jbr` (JDK 21.0.10). No hay `java` en el PATH: un `where java` da falso negativo.
- **AGP 9.2.1 + Gradle 9.4.1.** Ambos ya están en la caché de `~/.gradle`, así que no hay descarga de la distribución.
- **NO aplicar `org.jetbrains.kotlin.android`.** AGP 9 trae Kotlin incorporado y registra su propia extensión `kotlin`; aplicar el plugin aparte falla con *«Cannot add extension with name 'kotlin'»*. Basta `com.android.application`.
- **`compileSdk`** usa la sintaxis de bloque de AGP 9: `compileSdk { version = release(36) { minorApiLevel = 1 } }`. La plataforma instalada es `android-36.1`.
- **`minSdk = 21`, `targetSdk = 28`.** Verificado: compila, instala y arranca en la caja de API 25. El `targetSdk` se queda en 28 porque desde el 29 Android restringe lanzar actividades desde segundo plano, que es lo que hacen el `BootReceiver` y el latido.
- **`local.properties` es un `.properties` de Java: las barras van DOBLES.** `sdk.dir=C\:\\Users\\axeld\\AppData\\Local\\Android\\Sdk`. Con barras simples, Java se las come (`\U` y `\a` no son escapes válidos), `sdk.dir` queda como `C:UsersaxeldAppDataLocalAndroidSdk` y el build muere con un críptico `java.io.IOException: Invalid file path` en `compileDebugJavaWithJavac`. **Va en `.gitignore`**: es una ruta de esta máquina.
- **Manifiesto obligatorio:** `android:usesCleartextTraffic="true"` (el servidor es HTTP plano), `uses-feature android.software.leanback required="false"` y `uses-feature android.hardware.touchscreen required="false"`, y las categorías `LAUNCHER` **y** `LEANBACK_LAUNCHER`. La caja declara `leanback_only`.
- **Ajustes del WebView obligatorios:** `javaScriptEnabled = true`, `domStorageEnabled = true` (sin esto la pantalla pierde su identidad en cada reinicio), `mediaPlaybackRequiresUserGesture = false` (sin esto los vídeos no arrancan solos).
- **`android:banner`** en `<application>`: el lanzador de TV lo necesita. 320×180 px.
- **Aparato de pruebas:** `adb connect 192.168.0.64:5555`. `adb` está en `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`, tampoco en el PATH.
- **Estilo de los mensajes de commit del proyecto: sin tildes en el asunto.** Cuerpo explicando el porqué.
- **Nunca compilar dentro de una tubería con `Select-Object -First N`**: corta la tubería aguas arriba y mata al compilador a media faena.

---

## File Structure

```
android/
├── settings.gradle.kts              repositorios y módulos
├── build.gradle.kts                 declara AGP, apply false
├── gradle.properties                jvmargs y configuration-cache
├── local.properties                 sdk.dir — NO se versiona
├── gradlew / gradlew.bat            copiados de LauncherMayores
├── gradle/wrapper/
│   ├── gradle-wrapper.jar           copiado de LauncherMayores
│   └── gradle-wrapper.properties    apunta a gradle-9.4.1-bin
└── app/
    ├── build.gradle.kts             sdk, versión, dependencias
    └── src/
        ├── main/
        │   ├── AndroidManifest.xml
        │   ├── res/
        │   │   ├── drawable/banner.xml        banner 320x180 del lanzador TV
        │   │   ├── mipmap-mdpi/ic_launcher.png
        │   │   ├── layout/activity_setup.xml  entrada manual de la URL
        │   │   └── values/strings.xml
        │   └── java/com/inteks/display/
        │       ├── Red.kt            interfaces Sondeador y RedLocal (para poder probar sin Android)
        │       ├── ServerFinder.kt   subred, validación, barrido en paralelo
        │       ├── Urls.kt           extraerNombrePantalla(), construirUrl()
        │       ├── Reintentos.kt     secuencia de espera creciente
        │       ├── SettingsStore.kt  SharedPreferences
        │       ├── KioskActivity.kt  el WebView
        │       ├── SetupActivity.kt  escribir la dirección a mano
        │       ├── BootReceiver.kt   BOOT_COMPLETED
        │       └── LatidoReceiver.kt alarma que relanza la app
        └── test/java/com/inteks/display/
            ├── ServerFinderTest.kt
            ├── UrlsTest.kt
            └── ReintentosTest.kt
```

**Por qué esta división:** `ServerFinder`, `Urls` y `Reintentos` no tocan Android —reciben interfaces— así que sus tests corren en la JVM con `gradlew test`, sin aparato ni emulador. El resto (`KioskActivity`, receptores) es pegamento sin decisiones dentro, y se verifica en la caja real por ADB.

---

### Task 1: Esqueleto que compila, instala y arranca en la caja

Todo el andamiaje va en una sola tarea porque por separado no produce nada verificable.

**Files:**
- Create: `android/settings.gradle.kts`, `android/build.gradle.kts`, `android/gradle.properties`, `android/local.properties`, `android/app/build.gradle.kts`
- Create: `android/app/src/main/AndroidManifest.xml`, `android/app/src/main/java/com/inteks/display/KioskActivity.kt`
- Create: `android/app/src/main/res/values/strings.xml`, `android/app/src/main/res/drawable/banner.xml`
- Copy: `android/gradlew`, `android/gradlew.bat`, `android/gradle/wrapper/gradle-wrapper.jar`, `android/gradle/wrapper/gradle-wrapper.properties`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nada.
- Produces: un módulo `:app` compilable con `applicationId = "com.inteks.display"` y una `KioskActivity` lanzable.

- [ ] **Step 1: Copiar el wrapper de Gradle desde el proyecto que ya funciona**

```powershell
$dest = "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
$orig = "C:\Users\axeld\AndroidStudioProjects\LauncherMayores"
New-Item -ItemType Directory -Force "$dest\gradle\wrapper" | Out-Null
New-Item -ItemType Directory -Force "$dest\app\src\main\java\com\inteks\display" | Out-Null
New-Item -ItemType Directory -Force "$dest\app\src\main\res\values" | Out-Null
New-Item -ItemType Directory -Force "$dest\app\src\main\res\drawable" | Out-Null
New-Item -ItemType Directory -Force "$dest\app\src\test\java\com\inteks\display" | Out-Null
Copy-Item "$orig\gradlew","$orig\gradlew.bat" $dest
Copy-Item "$orig\gradle\wrapper\gradle-wrapper.jar","$orig\gradle\wrapper\gradle-wrapper.properties" "$dest\gradle\wrapper"
```

Esperado: sin errores. `gradle-wrapper.jar` pesa 45.457 bytes.

- [ ] **Step 2: Escribir los archivos de build**

`android/settings.gradle.kts`:

```kotlin
pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "InTeksPlayer"
include(":app")
```

`android/build.gradle.kts`:

```kotlin
// AGP 9 trae Kotlin incorporado: NO se aplica org.jetbrains.kotlin.android,
// que fallaria con "Cannot add extension with name 'kotlin'".
plugins {
    id("com.android.application") version "9.2.1" apply false
}
```

`android/gradle.properties`:

```properties
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.configuration-cache=true
kotlin.code.style=official
```

`android/app/build.gradle.kts`:

```kotlin
plugins {
    id("com.android.application")
}

android {
    namespace = "com.inteks.display"
    compileSdk { version = release(36) { minorApiLevel = 1 } }

    defaultConfig {
        applicationId = "com.inteks.display"
        minSdk = 21
        targetSdk = 28
        versionCode = 1
        versionName = "1.0.25"
    }

    buildTypes {
        release { optimization { enable = false } }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
```

- [ ] **Step 3: Escribir `local.properties` con las barras DOBLES**

```powershell
$linea = 'sdk.dir=C\:\\Users\\axeld\\AppData\\Local\\Android\\Sdk'
Set-Content -Path "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android\local.properties" -Value $linea -Encoding ascii
Get-Content "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android\local.properties"
```

Esperado exactamente: `sdk.dir=C\:\\Users\\axeld\\AppData\\Local\\Android\\Sdk`

Si salen barras simples, el build morirá con `java.io.IOException: Invalid file path`.

- [ ] **Step 4: Escribir el manifiesto, el banner, los strings y la actividad mínima**

`android/app/src/main/AndroidManifest.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />

    <uses-feature android:name="android.software.leanback" android:required="false" />
    <uses-feature android:name="android.hardware.touchscreen" android:required="false" />

    <application
        android:label="@string/app_name"
        android:banner="@drawable/banner"
        android:usesCleartextTraffic="true"
        android:allowBackup="false">

        <activity
            android:name=".KioskActivity"
            android:exported="true"
            android:launchMode="singleTask"
            android:configChanges="orientation|screenSize|keyboardHidden|screenLayout">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
                <category android:name="android.intent.category.LEANBACK_LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

`android/app/src/main/res/values/strings.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">InTeks Display</string>
    <string name="buscando">Buscando InTeks Display en la red…</string>
    <string name="no_encontrado">No se ha encontrado el servidor</string>
    <string name="escribe_direccion">Escribe la dirección del servidor</string>
    <string name="conectar">Conectar</string>
</resources>
```

`android/app/src/main/res/drawable/banner.xml` (banner vectorial, evita meter un PNG binario):

```xml
<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="320dp"
    android:height="180dp"
    android:viewportWidth="320"
    android:viewportHeight="180">
    <path android:fillColor="#07182b" android:pathData="M0,0h320v180h-320z" />
    <path android:fillColor="#FF7F00" android:pathData="M24,80h60v20h-60z" />
    <path android:fillColor="#eaf1f9" android:pathData="M24,110h180v8h-180z" />
</vector>
```

`android/app/src/main/java/com/inteks/display/KioskActivity.kt`:

```kotlin
package com.inteks.display

import android.app.Activity
import android.os.Bundle
import android.view.WindowManager

class KioskActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }
}
```

- [ ] **Step 5: Compilar**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat assembleDebug --no-daemon --console=plain
Pop-Location
```

Esperado: `BUILD SUCCESSFUL`. El APK aparece en `android/app/build/outputs/apk/debug/app-debug.apk`, alrededor de 900 KB.

- [ ] **Step 6: Instalar y arrancar en la caja**

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb connect 192.168.0.64:5555
& $adb -s 192.168.0.64:5555 install -r "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android\app\build\outputs\apk\debug\app-debug.apk"
& $adb -s 192.168.0.64:5555 shell "am start -n com.inteks.display/.KioskActivity"
& $adb -s 192.168.0.64:5555 shell "dumpsys activity activities | grep -m1 mResumedActivity"
```

Esperado: `Success`, y `mResumedActivity: ActivityRecord{… com.inteks.display/.KioskActivity …}`.

- [ ] **Step 7: Comprobar que el APK declara el lanzador de TV**

```powershell
$bt = "$env:LOCALAPPDATA\Android\Sdk\build-tools\37.0.0"
& "$bt\aapt2.exe" dump badging "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android\app\build\outputs\apk\debug\app-debug.apk" | Select-String -Pattern "launchable|leanback|uses-feature"
```

Esperado: aparecen **las dos** líneas, `launchable-activity:` y `leanback-launchable-activity:`, y en la línea `application:` un **`banner='res/drawable/banner.xml'`**.

Ojo con dónde se mira el banner: en la línea de `leanback-launchable-activity` sale `banner=''` y **está bien así**. Ese es el override por actividad; el que usa Android TV por defecto es el de `<application>`.

- [ ] **Step 8: Excluir del repo lo que no se versiona**

Añadir al final de `.gitignore`:

```
# App Android: artefactos de compilacion y ruta local del SDK
android/build/
android/.gradle/
android/app/build/
android/local.properties
```

Verificar (el `.gitignore` **no admite comentarios en línea**, por eso van en su propia línea):

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
git check-ignore -v android/local.properties android/app/build android/.gradle
Pop-Location
```

Esperado: las tres rutas salen listadas con la línea del `.gitignore` que las ignora.

- [ ] **Step 9: Commit**

```bash
git add .gitignore android/
git commit -m "App Android: esqueleto que compila e instala en la caja de la tienda

Modulo :app con AGP 9.2.1 y Gradle 9.4.1, los dos ya en cache. Kotlin NO
lleva plugin aparte: AGP 9 lo trae dentro y aplicar org.jetbrains.kotlin.android
falla con 'Cannot add extension with name kotlin'.

minSdk 21 y targetSdk 28, verificado instalando en la MXQ real, que es API 25.
El targetSdk se queda en 28 porque desde el 29 Android restringe lanzar
actividades desde segundo plano, que es justo lo que hara el arranque.

local.properties va con barras DOBLES y fuera del repo: es un .properties de
Java, y con barras simples se las come y el build muere con un
'java.io.IOException: Invalid file path' que no dice nada de la causa."
```

---

### Task 2: Enumerar la subred

**Files:**
- Create: `android/app/src/main/java/com/inteks/display/Red.kt`
- Create: `android/app/src/main/java/com/inteks/display/ServerFinder.kt`
- Test: `android/app/src/test/java/com/inteks/display/ServerFinderTest.kt`

**Interfaces:**
- Consumes: nada del Task 1 salvo el módulo.
- Produces: `data class RedLocal(val ip: String, val prefijo: Int)` y `fun direccionesDeLaSubred(red: RedLocal): List<String>`.

- [ ] **Step 1: Escribir el test que falla**

`android/app/src/test/java/com/inteks/display/ServerFinderTest.kt`:

```kotlin
package com.inteks.display

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ServerFinderTest {

    @Test
    fun `una 24 da 254 direcciones sin la de red ni la de difusion`() {
        val d = direccionesDeLaSubred(RedLocal("192.168.0.64", 24))
        assertEquals(254, d.size)
        assertEquals("192.168.0.1", d.first())
        assertEquals("192.168.0.254", d.last())
        assertTrue(!d.contains("192.168.0.0"))
        assertTrue(!d.contains("192.168.0.255"))
    }

    @Test
    fun `la propia direccion se incluye, que el servidor podria ser este aparato`() {
        val d = direccionesDeLaSubred(RedLocal("192.168.0.64", 24))
        assertTrue(d.contains("192.168.0.64"))
    }

    @Test
    fun `una red mas grande que 24 no se barre`() {
        assertEquals(0, direccionesDeLaSubred(RedLocal("10.0.0.5", 16)).size)
        assertEquals(0, direccionesDeLaSubred(RedLocal("10.0.0.5", 8)).size)
    }

    @Test
    fun `una 25 se barre entera, que es mas pequena que una 24`() {
        val d = direccionesDeLaSubred(RedLocal("192.168.0.130", 25))
        assertEquals(126, d.size)
        assertEquals("192.168.0.129", d.first())
        assertEquals("192.168.0.254", d.last())
    }

    @Test
    fun `una ip que no es ipv4 no revienta, devuelve vacio`() {
        assertEquals(0, direccionesDeLaSubred(RedLocal("no-es-una-ip", 24)).size)
        assertEquals(0, direccionesDeLaSubred(RedLocal("", 24)).size)
    }
}
```

- [ ] **Step 2: Ejecutar el test y ver que falla**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat testDebugUnitTest --no-daemon --console=plain
Pop-Location
```

Esperado: FALLA con error de compilación, `Unresolved reference: direccionesDeLaSubred`.

- [ ] **Step 3: Escribir la implementación mínima**

`android/app/src/main/java/com/inteks/display/Red.kt`:

```kotlin
package com.inteks.display

/** La red en la que está el aparato: su IP y el prefijo de la máscara. */
data class RedLocal(val ip: String, val prefijo: Int)

/** Quien sabe pedir una URL. Se sustituye en los tests. */
interface Sondeador {
    fun pedir(url: String, timeoutMs: Int): String?
}
```

`android/app/src/main/java/com/inteks/display/ServerFinder.kt`:

```kotlin
package com.inteks.display

/**
 * Direcciones a sondear dentro de la subred del aparato.
 *
 * Solo se barren redes de /24 o más pequeñas. Una /16 son 65.534 direcciones:
 * tardaría minutos y molestaría a la red de la tienda, así que se prefiere
 * pedirle la dirección al usuario.
 */
fun direccionesDeLaSubred(red: RedLocal): List<String> {
    if (red.prefijo < 24 || red.prefijo > 30) return emptyList()

    val partes = red.ip.split(".")
    if (partes.size != 4) return emptyList()
    val octetos = partes.map { it.toIntOrNull() ?: return emptyList() }
    if (octetos.any { it < 0 || it > 255 }) return emptyList()

    val ipNum = (octetos[0].toLong() shl 24) or (octetos[1].toLong() shl 16) or
                (octetos[2].toLong() shl 8) or octetos[3].toLong()
    val mascara = (0xFFFFFFFFL shl (32 - red.prefijo)) and 0xFFFFFFFFL
    val base = ipNum and mascara
    val difusion = base or (mascara.inv() and 0xFFFFFFFFL)

    return ((base + 1) until difusion).map { n ->
        "${(n shr 24) and 0xFF}.${(n shr 16) and 0xFF}.${(n shr 8) and 0xFF}.${n and 0xFF}"
    }
}
```

- [ ] **Step 4: Ejecutar el test y ver que pasa**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat testDebugUnitTest --no-daemon --console=plain
Pop-Location
```

Esperado: `BUILD SUCCESSFUL`, 5 tests pasando.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/inteks/display/Red.kt android/app/src/main/java/com/inteks/display/ServerFinder.kt android/app/src/test/java/com/inteks/display/ServerFinderTest.kt
git commit -m "App Android: enumerar las direcciones de la subred

Solo se barren redes de /24 o mas pequenas. Una /16 son 65.534 direcciones:
tardaria minutos y molestaria a la red de la tienda, asi que en ese caso se
prefiere pedirle la direccion al usuario. La propia IP entra en la lista
porque el servidor podria ser este mismo aparato."
```

---

### Task 3: Reconocer que la respuesta es de InTeks

**Files:**
- Modify: `android/app/src/main/java/com/inteks/display/ServerFinder.kt`
- Test: `android/app/src/test/java/com/inteks/display/ServerFinderTest.kt`

**Interfaces:**
- Consumes: `direccionesDeLaSubred()` del Task 2.
- Produces: `fun esRespuestaDeInTeks(cuerpo: String?): Boolean`.

- [ ] **Step 1: Escribir el test que falla**

Añadir a `ServerFinderTest.kt`:

```kotlin
    @Test
    fun `una respuesta real de api info se reconoce`() {
        val real = """{"version": "1.0.25", "port": 80, "ip": "192.168.0.63",
            "mdns_host": "signage.local", "mdns_name": "signage",
            "player_url": "http://192.168.0.63/player.html"}"""
        assertTrue(esRespuestaDeInTeks(real))
    }

    @Test
    fun `otro servidor web de la red no cuela`() {
        assertTrue(!esRespuestaDeInTeks("<html><body>Router</body></html>"))
        assertTrue(!esRespuestaDeInTeks("""{"status":"ok"}"""))
        assertTrue(!esRespuestaDeInTeks("""{"version":"1.0.0"}"""))
    }

    @Test
    fun `una respuesta vacia o rota no revienta`() {
        assertTrue(!esRespuestaDeInTeks(null))
        assertTrue(!esRespuestaDeInTeks(""))
        assertTrue(!esRespuestaDeInTeks("{"))
    }
```

- [ ] **Step 2: Ejecutar el test y ver que falla**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat testDebugUnitTest --no-daemon --console=plain
Pop-Location
```

Esperado: FALLA con `Unresolved reference: esRespuestaDeInTeks`.

- [ ] **Step 3: Escribir la implementación mínima**

Añadir a `ServerFinder.kt`:

```kotlin
/**
 * ¿Esta respuesta viene de un InTeks Display?
 *
 * Se exigen DOS campos, no uno: `mdns_name` y `player_url`. Con solo mirar
 * `version` colaría cualquier API de la red que devuelva un número de versión,
 * y en una tienda hay routers, impresoras y cámaras contestando en el 80.
 */
fun esRespuestaDeInTeks(cuerpo: String?): Boolean {
    if (cuerpo.isNullOrBlank()) return false
    return cuerpo.contains("\"mdns_name\"") && cuerpo.contains("\"player_url\"")
}
```

- [ ] **Step 4: Ejecutar el test y ver que pasa**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat testDebugUnitTest --no-daemon --console=plain
Pop-Location
```

Esperado: `BUILD SUCCESSFUL`, 8 tests pasando.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/inteks/display/ServerFinder.kt android/app/src/test/java/com/inteks/display/ServerFinderTest.kt
git commit -m "App Android: distinguir un InTeks de cualquier otro cacharro de la red

Se exigen DOS campos de /api/info, mdns_name y player_url, no solo la version.
En una tienda hay routers, impresoras y camaras contestando en el puerto 80, y
mirar solo 'version' haria que la pantalla se enganchara al primero que pase."
```

---

### Task 4: Barrer en paralelo con presupuesto de tiempo

**Files:**
- Modify: `android/app/src/main/java/com/inteks/display/ServerFinder.kt`
- Test: `android/app/src/test/java/com/inteks/display/ServerFinderTest.kt`

**Interfaces:**
- Consumes: `direccionesDeLaSubred()`, `esRespuestaDeInTeks()`, `Sondeador`.
- Produces: `fun buscarServidor(red: RedLocal, sondeador: Sondeador, puertos: List<Int> = listOf(80, 9000)): String?` que devuelve la URL base (`http://192.168.0.63` o `http://192.168.0.63:9000`) o `null`.

- [ ] **Step 1: Escribir el test que falla**

Añadir a `ServerFinderTest.kt`:

```kotlin
    private val respuestaBuena = """{"mdns_name":"signage","player_url":"http://x/player.html"}"""

    @Test
    fun `encuentra el servidor y devuelve su url base`() {
        val sondeador = object : Sondeador {
            override fun pedir(url: String, timeoutMs: Int): String? =
                if (url == "http://192.168.0.63/api/info") respuestaBuena else null
        }
        assertEquals("http://192.168.0.63", buscarServidor(RedLocal("192.168.0.64", 24), sondeador))
    }

    @Test
    fun `si esta en el 9000 la url base lleva el puerto`() {
        val sondeador = object : Sondeador {
            override fun pedir(url: String, timeoutMs: Int): String? =
                if (url == "http://192.168.0.70:9000/api/info") respuestaBuena else null
        }
        assertEquals("http://192.168.0.70:9000", buscarServidor(RedLocal("192.168.0.64", 24), sondeador))
    }

    @Test
    fun `si no contesta nadie devuelve null`() {
        val sondeador = object : Sondeador {
            override fun pedir(url: String, timeoutMs: Int): String? = null
        }
        assertEquals(null, buscarServidor(RedLocal("192.168.0.64", 24), sondeador))
    }

    @Test
    fun `un impostor que contesta pero no es InTeks no se elige`() {
        val sondeador = object : Sondeador {
            override fun pedir(url: String, timeoutMs: Int): String? = "<html>router</html>"
        }
        assertEquals(null, buscarServidor(RedLocal("192.168.0.64", 24), sondeador))
    }

    @Test
    fun `en una red que no se puede barrer no se sondea nada`() {
        var llamadas = 0
        val sondeador = object : Sondeador {
            override fun pedir(url: String, timeoutMs: Int): String? { llamadas++; return null }
        }
        assertEquals(null, buscarServidor(RedLocal("10.0.0.5", 16), sondeador))
        assertEquals(0, llamadas)
    }
```

- [ ] **Step 2: Ejecutar el test y ver que falla**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat testDebugUnitTest --no-daemon --console=plain
Pop-Location
```

Esperado: FALLA con `Unresolved reference: buscarServidor`.

- [ ] **Step 3: Escribir la implementación mínima**

Añadir a `ServerFinder.kt` (y su `import` arriba del archivo):

```kotlin
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

const val TIMEOUT_SONDA_MS = 1500
const val SONDAS_EN_PARALELO = 32
const val TOPE_BARRIDO_SEGUNDOS = 8L

/**
 * Busca un InTeks Display en la subred. Devuelve la URL base, o null.
 *
 * Se sondea con un pool acotado en vez de una a una: 254 direcciones por dos
 * puertos son 508 peticiones, y en serie a 1,5 s cada una serían 12 minutos.
 */
fun buscarServidor(
    red: RedLocal,
    sondeador: Sondeador,
    puertos: List<Int> = listOf(80, 9000)
): String? {
    val direcciones = direccionesDeLaSubred(red)
    if (direcciones.isEmpty()) return null

    val encontrada = AtomicReference<String?>(null)
    val pool = Executors.newFixedThreadPool(SONDAS_EN_PARALELO)
    try {
        for (ip in direcciones) {
            for (puerto in puertos) {
                pool.submit {
                    if (encontrada.get() != null) return@submit
                    val base = if (puerto == 80) "http://$ip" else "http://$ip:$puerto"
                    val cuerpo = sondeador.pedir("$base/api/info", TIMEOUT_SONDA_MS)
                    if (esRespuestaDeInTeks(cuerpo)) encontrada.compareAndSet(null, base)
                }
            }
        }
        pool.shutdown()
        pool.awaitTermination(TOPE_BARRIDO_SEGUNDOS, TimeUnit.SECONDS)
    } finally {
        pool.shutdownNow()
    }
    return encontrada.get()
}
```

- [ ] **Step 4: Ejecutar el test y ver que pasa**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat testDebugUnitTest --no-daemon --console=plain
Pop-Location
```

Esperado: `BUILD SUCCESSFUL`, 13 tests pasando.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/inteks/display/ServerFinder.kt android/app/src/test/java/com/inteks/display/ServerFinderTest.kt
git commit -m "App Android: barrido de la subred en paralelo, con tope de tiempo

254 direcciones por dos puertos son 508 peticiones. En serie, a 1,5 s cada una,
serian doce minutos; con 32 sondas a la vez y 8 s de tope cabe de sobra. En
cuanto una acierta, las demas se cortan.

El Sondeador es una interfaz para que todo esto se pruebe en la JVM, sin red y
sin aparato: los tests montan servidores de mentira, incluido un impostor que
contesta pero no es InTeks."
```

---

### Task 5: Recordar el nombre de la pantalla para sobrevivir a un cambio de IP

**Files:**
- Create: `android/app/src/main/java/com/inteks/display/Urls.kt`
- Test: `android/app/src/test/java/com/inteks/display/UrlsTest.kt`

**Interfaces:**
- Consumes: nada.
- Produces: `fun extraerNombrePantalla(url: String): String?` y `fun urlDeArranque(base: String, nombrePantalla: String?): String`.

- [ ] **Step 1: Escribir el test que falla**

`android/app/src/test/java/com/inteks/display/UrlsTest.kt`:

```kotlin
package com.inteks.display

import org.junit.Assert.assertEquals
import org.junit.Test

class UrlsTest {

    @Test
    fun `saca el nombre de la url del player`() {
        assertEquals("Escaparate",
            extraerNombrePantalla("http://192.168.0.63/player.html?screen=Escaparate"))
    }

    @Test
    fun `deshace el escapado del nombre con espacios y acentos`() {
        assertEquals("Pantalla Exterior (LG)",
            extraerNombrePantalla("http://192.168.0.63/player.html?screen=Pantalla%20Exterior%20(LG)"))
        assertEquals("Caja Nº2",
            extraerNombrePantalla("http://192.168.0.63/player.html?screen=Caja%20N%C2%BA2"))
    }

    @Test
    fun `las paginas que no son el player no dan nombre`() {
        assertEquals(null, extraerNombrePantalla("http://192.168.0.63/pair"))
        assertEquals(null, extraerNombrePantalla("http://192.168.0.63/"))
        assertEquals(null, extraerNombrePantalla("http://192.168.0.63/player.html?preview=1"))
        assertEquals(null, extraerNombrePantalla("http://192.168.0.63/player.html?screen="))
    }

    @Test
    fun `una url rota no revienta`() {
        assertEquals(null, extraerNombrePantalla(""))
        assertEquals(null, extraerNombrePantalla("no-es-una-url"))
    }

    @Test
    fun `sin nombre guardado se arranca por la raiz y decide la web`() {
        assertEquals("http://192.168.0.63/", urlDeArranque("http://192.168.0.63", null))
    }

    @Test
    fun `con nombre guardado se va directo al player, aunque la ip sea otra`() {
        assertEquals("http://192.168.0.70/player.html?screen=Escaparate",
            urlDeArranque("http://192.168.0.70", "Escaparate"))
    }

    @Test
    fun `el nombre se vuelve a escapar al construir la url`() {
        assertEquals("http://192.168.0.70/player.html?screen=Pantalla+Exterior",
            urlDeArranque("http://192.168.0.70", "Pantalla Exterior"))
    }
}
```

- [ ] **Step 2: Ejecutar el test y ver que falla**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat testDebugUnitTest --no-daemon --console=plain
Pop-Location
```

Esperado: FALLA con `Unresolved reference: extraerNombrePantalla`.

- [ ] **Step 3: Escribir la implementación mínima**

`android/app/src/main/java/com/inteks/display/Urls.kt`:

```kotlin
package com.inteks.display

import java.net.URLDecoder
import java.net.URLEncoder

/**
 * El nombre de pantalla que lleva dentro una URL del player, o null.
 *
 * Existe porque `localStorage` y las cookies van por ORIGEN: si el PC cambia de
 * IP, `http://192.168.0.63` y `http://192.168.0.70` son sitios distintos para
 * el navegador y la pantalla perdería su identidad. Guardando el nombre fuera
 * del WebView, un cambio de IP deja de importar.
 */
fun extraerNombrePantalla(url: String): String? {
    val i = url.indexOf("/player.html?")
    if (i < 0) return null
    val consulta = url.substring(i + "/player.html?".length)
    for (par in consulta.split("&")) {
        val trozos = par.split("=", limit = 2)
        if (trozos.size == 2 && trozos[0] == "screen" && trozos[1].isNotEmpty()) {
            return try { URLDecoder.decode(trozos[1], "UTF-8") } catch (e: Exception) { null }
        }
    }
    return null
}

/**
 * Por dónde empezar a cargar. Sin nombre guardado se entra por la raíz y decide
 * `index.html`, que ya sabe enrutar a emparejar o a reproducir.
 */
fun urlDeArranque(base: String, nombrePantalla: String?): String {
    if (nombrePantalla.isNullOrEmpty()) return "$base/"
    val escapado = URLEncoder.encode(nombrePantalla, "UTF-8")
    return "$base/player.html?screen=$escapado"
}
```

- [ ] **Step 4: Ejecutar el test y ver que pasa**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat testDebugUnitTest --no-daemon --console=plain
Pop-Location
```

Esperado: `BUILD SUCCESSFUL`, 20 tests pasando.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/inteks/display/Urls.kt android/app/src/test/java/com/inteks/display/UrlsTest.kt
git commit -m "App Android: recordar el nombre de pantalla fuera del WebView

localStorage y las cookies van por ORIGEN. Si el PC cambia de IP por DHCP,
http://192.168.0.63 y http://192.168.0.70 son sitios distintos para el
navegador, asi que el rebarrido encontraria el servidor pero la pantalla habria
perdido su identidad y volveria a pedir codigo: el auto-reparado comiendose a
si mismo.

La app observa la URL y, cuando la web llega a /player.html?screen=X, se guarda
esa X en sus preferencias. Con la IP nueva carga directamente el player de esa
pantalla. No hace falta tocar ni una linea de la web."
```

---

### Task 6: La espera creciente de los reintentos

**Files:**
- Create: `android/app/src/main/java/com/inteks/display/Reintentos.kt`
- Test: `android/app/src/test/java/com/inteks/display/ReintentosTest.kt`

**Interfaces:**
- Consumes: nada.
- Produces: `fun esperaMs(intento: Int): Long`.

- [ ] **Step 1: Escribir el test que falla**

`android/app/src/test/java/com/inteks/display/ReintentosTest.kt`:

```kotlin
package com.inteks.display

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ReintentosTest {

    @Test
    fun `dobla desde dos segundos`() {
        assertEquals(2_000L, esperaMs(0))
        assertEquals(4_000L, esperaMs(1))
        assertEquals(8_000L, esperaMs(2))
        assertEquals(16_000L, esperaMs(3))
        assertEquals(32_000L, esperaMs(4))
    }

    @Test
    fun `se queda en un minuto y no sigue creciendo`() {
        assertEquals(60_000L, esperaMs(5))
        assertEquals(60_000L, esperaMs(6))
        assertEquals(60_000L, esperaMs(50))
    }

    @Test
    fun `nunca se rinde ni devuelve una espera absurda`() {
        assertEquals(60_000L, esperaMs(100_000))
        assertTrue(esperaMs(Int.MAX_VALUE) == 60_000L)
    }

    @Test
    fun `un intento negativo se trata como el primero`() {
        assertEquals(2_000L, esperaMs(-1))
    }
}
```

- [ ] **Step 2: Ejecutar el test y ver que falla**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat testDebugUnitTest --no-daemon --console=plain
Pop-Location
```

Esperado: FALLA con `Unresolved reference: esperaMs`.

- [ ] **Step 3: Escribir la implementación mínima**

`android/app/src/main/java/com/inteks/display/Reintentos.kt`:

```kotlin
package com.inteks.display

const val ESPERA_MINIMA_MS = 2_000L
const val ESPERA_MAXIMA_MS = 60_000L

/**
 * Cuánto esperar antes del siguiente intento: 2, 4, 8, 16, 32, 60, 60…
 *
 * No se rinde nunca. Una pantalla de escaparate tiene todo el tiempo del mundo;
 * lo que no puede es quedarse muerta esperando a que alguien la toque, porque
 * no hay nadie que la toque.
 */
fun esperaMs(intento: Int): Long {
    if (intento <= 0) return ESPERA_MINIMA_MS
    if (intento >= 5) return ESPERA_MAXIMA_MS
    return ESPERA_MINIMA_MS shl intento
}
```

- [ ] **Step 4: Ejecutar el test y ver que pasa**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat testDebugUnitTest --no-daemon --console=plain
Pop-Location
```

Esperado: `BUILD SUCCESSFUL`, 24 tests pasando.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/inteks/display/Reintentos.kt android/app/src/test/java/com/inteks/display/ReintentosTest.kt
git commit -m "App Android: espera creciente que no se rinde nunca

2, 4, 8, 16, 32, 60, 60 segundos. Se queda en el minuto y sigue intentandolo
indefinidamente: una pantalla de escaparate tiene todo el tiempo del mundo, y
lo que no puede es quedarse muerta esperando a que alguien la toque, porque no
hay nadie que la vaya a tocar."
```

---

### Task 7: El sondeador real y dónde guardar los ajustes

**Files:**
- Create: `android/app/src/main/java/com/inteks/display/SettingsStore.kt`
- Modify: `android/app/src/main/java/com/inteks/display/Red.kt`

**Interfaces:**
- Consumes: `Sondeador`, `RedLocal`.
- Produces: `class SondeadorHttp : Sondeador`, `fun redLocalDe(context: Context): RedLocal?`, `class SettingsStore(context: Context)` con `var base: String?`, `var nombrePantalla: String?`.

- [ ] **Step 1: Escribir el sondeador HTTP**

Añadir a `android/app/src/main/java/com/inteks/display/Red.kt`:

```kotlin
import android.content.Context
import android.net.ConnectivityManager
import java.net.HttpURLConnection
import java.net.URL

/** Sondeador de verdad, con HttpURLConnection. Sin dependencias externas. */
class SondeadorHttp : Sondeador {
    override fun pedir(url: String, timeoutMs: Int): String? {
        var con: HttpURLConnection? = null
        return try {
            con = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = timeoutMs
                readTimeout = timeoutMs
                requestMethod = "GET"
                instanceFollowRedirects = false
            }
            if (con.responseCode != 200) {
                null
            } else {
                // Se leen como mucho 4 KB: /api/info son ~300 bytes, y en la red
                // puede haber un servidor sirviendo un video en el mismo puerto.
                val buf = CharArray(4096)
                con.inputStream.bufferedReader().use { r ->
                    val n = r.read(buf)
                    if (n <= 0) "" else String(buf, 0, n)
                }
            }
        } catch (e: Exception) {
            null
        } finally {
            con?.disconnect()
        }
    }
}

/** La IP y el prefijo de máscara del aparato, o null si no hay red. */
fun redLocalDe(context: Context): RedLocal? {
    val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    for (red in cm.allNetworks) {
        val props = cm.getLinkProperties(red) ?: continue
        for (dir in props.linkAddresses) {
            val ip = dir.address.hostAddress ?: continue
            if (ip.contains(":")) continue          // IPv6, no se barre
            if (ip.startsWith("127.")) continue     // loopback
            return RedLocal(ip, dir.prefixLength)
        }
    }
    return null
}
```

- [ ] **Step 2: Escribir el almacén de ajustes**

`android/app/src/main/java/com/inteks/display/SettingsStore.kt`:

```kotlin
package com.inteks.display

import android.content.Context

/**
 * Lo que la app recuerda entre arranques. Vive FUERA del WebView a propósito:
 * ver el comentario de `extraerNombrePantalla`.
 */
class SettingsStore(context: Context) {
    private val prefs = context.getSharedPreferences("inteks", Context.MODE_PRIVATE)

    var base: String?
        get() = prefs.getString("base", null)
        set(v) { prefs.edit().putString("base", v).apply() }

    var nombrePantalla: String?
        get() = prefs.getString("pantalla", null)
        set(v) { prefs.edit().putString("pantalla", v).apply() }
}
```

- [ ] **Step 3: Compilar**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat assembleDebug --no-daemon --console=plain
Pop-Location
```

Esperado: `BUILD SUCCESSFUL`.

- [ ] **Step 4: Comprobar el sondeador contra el servidor de verdad**

Instalar y, desde un `adb shell`, no se puede llamar a Kotlin directamente: se comprueba en el Task 8, cuando la actividad ya usa el sondeador. Aquí basta con que compile.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/inteks/display/Red.kt android/app/src/main/java/com/inteks/display/SettingsStore.kt
git commit -m "App Android: sondeador HTTP real y almacen de ajustes

HttpURLConnection de la libreria estandar, sin OkHttp: el proyecto no mete
dependencias que no necesita. Se leen como mucho 4 KB de la respuesta porque
/api/info son unos 300 bytes y en la red puede haber un servidor sirviendo un
video en el mismo puerto.

Los ajustes viven en SharedPreferences, fuera del WebView, que es lo que
permite sobrevivir a un cambio de IP."
```

---

### Task 8: El WebView a pantalla completa

**Files:**
- Modify: `android/app/src/main/java/com/inteks/display/KioskActivity.kt`

**Interfaces:**
- Consumes: `SettingsStore`, `buscarServidor()`, `redLocalDe()`, `SondeadorHttp`, `urlDeArranque()`, `extraerNombrePantalla()`, `esperaMs()`.
- Produces: una actividad que carga el player a pantalla completa.

- [ ] **Step 1: Escribir la actividad**

`android/app/src/main/java/com/inteks/display/KioskActivity.kt` (reemplaza el contenido del Task 1):

```kotlin
package com.inteks.display

import android.app.Activity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.WindowManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView

class KioskActivity : Activity() {

    private lateinit var web: WebView
    private lateinit var aviso: TextView
    private lateinit var ajustes: SettingsStore
    private val hilo = Handler(Looper.getMainLooper())
    private var intentos = 0
    private var algoPintado = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        ajustes = SettingsStore(this)

        aviso = TextView(this).apply {
            text = getString(R.string.buscando)
            setBackgroundColor(0xFF07182B.toInt())
            setTextColor(0xFF7A8CA3.toInt())
            textSize = 18f
            gravity = android.view.Gravity.CENTER
        }
        web = WebView(this)
        configurarWebView()
        setContentView(aviso)

        arrancar()
    }

    private fun configurarWebView() {
        web.settings.apply {
            javaScriptEnabled = true
            // Sin esto la pantalla pierde su identidad en cada reinicio:
            // el bloque de identidad de index.html usa localStorage.
            domStorageEnabled = true
            // Sin esto los videos se quedan en el primer fotograma esperando
            // un clic que nadie va a dar.
            mediaPlaybackRequiresUserGesture = false
        }
        web.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                algoPintado = true
                intentos = 0
                if (web.parent == null) setContentView(web)
                aplicarPantallaCompleta()
                url?.let { u ->
                    extraerNombrePantalla(u)?.let { ajustes.nombrePantalla = it }
                }
            }

            override fun onReceivedError(
                view: WebView?, req: WebResourceRequest?, err: WebResourceError?
            ) {
                // Si YA hay algo pintado no se toca nada: el player sigue
                // reproduciendo de su cache y taparlo empeoraria el producto.
                if (algoPintado) return
                reintentar()
            }
        }
    }

    private fun aplicarPantallaCompleta() {
        web.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_FULLSCREEN
                or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            )
    }

    private fun arrancar() {
        val base = ajustes.base
        if (base != null) { cargar(base); return }
        buscarYCargar()
    }

    private fun buscarYCargar() {
        Thread {
            val red = redLocalDe(this)
            val encontrada = if (red == null) null else buscarServidor(red, SondeadorHttp())
            hilo.post {
                if (encontrada != null) {
                    ajustes.base = encontrada
                    cargar(encontrada)
                } else {
                    startActivity(android.content.Intent(this, SetupActivity::class.java))
                    finish()
                }
            }
        }.start()
    }

    private fun cargar(base: String) {
        web.loadUrl(urlDeArranque(base, ajustes.nombrePantalla))
    }

    private fun reintentar() {
        val espera = esperaMs(intentos)
        intentos++
        // Cada 5 fallos seguidos se vuelve a barrer: puede que el PC haya
        // cambiado de IP.
        if (intentos % 5 == 0) { ajustes.base = null; buscarYCargar(); return }
        hilo.postDelayed({ ajustes.base?.let { cargar(it) } ?: buscarYCargar() }, espera)
    }

    override fun onResume() {
        super.onResume()
        aplicarPantallaCompleta()
    }

    override fun onDestroy() {
        hilo.removeCallbacksAndMessages(null)
        super.onDestroy()
    }
}
```

- [ ] **Step 2: Añadir el vigilante que detecta un cambio de IP**

Sin esto queda un agujero: si el servidor se muda **mientras el player va bien desde su caché**, no hay ningún error de carga, así que nada dispararía el rebarrido y la pantalla se quedaría con contenido viejo indefinidamente. Justo el caso para el que existe guardar el nombre de pantalla.

Añadir a `KioskActivity`, dentro de la clase:

```kotlin
    private var fallosSeguidos = 0

    private val vigilante = object : Runnable {
        override fun run() {
            val base = ajustes.base
            if (base == null) { hilo.postDelayed(this, VIGILANCIA_MS); return }
            Thread {
                val vivo = esRespuestaDeInTeks(
                    SondeadorHttp().pedir("$base/api/info", TIMEOUT_SONDA_MS))
                hilo.post {
                    if (vivo) {
                        fallosSeguidos = 0
                    } else if (++fallosSeguidos >= FALLOS_ANTES_DE_REBARRER) {
                        // El servidor no esta donde estaba. Puede haber cambiado
                        // de IP por DHCP: se busca otra vez y se vuelve con la
                        // misma pantalla, que su nombre esta guardado aparte.
                        fallosSeguidos = 0
                        ajustes.base = null
                        buscarYCargar()
                    }
                    hilo.postDelayed(this, VIGILANCIA_MS)
                }
            }.start()
        }
    }
```

Y en el fichero, junto a las demás constantes (arriba, fuera de la clase):

```kotlin
const val VIGILANCIA_MS = 60_000L
const val FALLOS_ANTES_DE_REBARRER = 3
```

Arrancarlo al final de `onCreate`:

```kotlin
        hilo.postDelayed(vigilante, VIGILANCIA_MS)
```

`onDestroy` ya hace `hilo.removeCallbacksAndMessages(null)`, así que también lo para.

- [ ] **Step 3: Compilar**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat assembleDebug --no-daemon --console=plain
Pop-Location
```

Esperado: `BUILD SUCCESSFUL`. (Fallará hasta que exista `SetupActivity`: si es así, crear primero el Task 9 y volver.)

- [ ] **Step 4: Instalar y comprobar EN LA CAJA que encuentra el servidor solo**

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$d = "192.168.0.64:5555"
& $adb -s $d shell "pm clear com.inteks.display"
& $adb -s $d install -r "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android\app\build\outputs\apk\debug\app-debug.apk"
& $adb -s $d shell "am start -n com.inteks.display/.KioskActivity"
Start-Sleep -Seconds 15
& $adb -s $d shell "screencap -p /sdcard/k.png"
& $adb -s $d pull /sdcard/k.png "$env:TEMP\k.png"
```

Esperado: la captura muestra **la página de emparejar de InTeks a pantalla completa**, sin barra de navegación y sin barra de estado, con su código de cuatro cifras. El `pm clear` es imprescindible: borra los ajustes para probar el barrido desde cero.

- [ ] **Step 5: Comprobar que guardó la base encontrada**

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s 192.168.0.64:5555 shell "run-as com.inteks.display cat /data/data/com.inteks.display/shared_prefs/inteks.xml"
```

Esperado: un XML con `<string name="base">http://192.168.0.63</string>`.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/inteks/display/KioskActivity.kt
git commit -m "App Android: el WebView a pantalla completa que encuentra el servidor solo

Los tres ajustes que, si faltan, dan fallos que no parecen lo que son:
domStorageEnabled (sin el, la pantalla pierde su identidad en cada reinicio),
mediaPlaybackRequiresUserGesture a false (sin el, los videos se quedan en el
primer fotograma) y javaScriptEnabled.

La regla de los errores: si YA hay algo pintado, no se toca nada. El player
guarda su contenido en IndexedDB y sigue reproduciendo sin servidor; taparlo
con un 'sin conexion' empeoraria el producto. Nuestra pantalla solo cuando el
WebView no tiene nada que ensenar.

Dos caminos llevan a rebarrer, y hacen falta los dos. Si la carga falla cinco
veces seguidas, se busca otra vez. Y un vigilante pregunta por /api/info cada
minuto, porque si el servidor se muda MIENTRAS el player va bien desde su
cache no hay ningun error de carga: sin el vigilante, la pantalla se quedaria
con contenido viejo indefinidamente."
```

---

### Task 9: Escribir la dirección a mano, con el mando

**Files:**
- Create: `android/app/src/main/java/com/inteks/display/SetupActivity.kt`
- Create: `android/app/src/main/res/layout/activity_setup.xml`
- Modify: `android/app/src/main/AndroidManifest.xml`

**Interfaces:**
- Consumes: `SettingsStore`.
- Produces: `SetupActivity`, que guarda la base y vuelve a `KioskActivity`.

- [ ] **Step 1: Escribir el layout**

`android/app/src/main/res/layout/activity_setup.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:gravity="center"
    android:padding="48dp"
    android:background="#07182b">

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="@string/no_encontrado"
        android:textColor="#FF7F00"
        android:textSize="20sp"
        android:layout_marginBottom="8dp" />

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="@string/escribe_direccion"
        android:textColor="#7a8ca3"
        android:textSize="15sp"
        android:layout_marginBottom="24dp" />

    <EditText
        android:id="@+id/direccion"
        android:layout_width="420dp"
        android:layout_height="wrap_content"
        android:text="http://192.168.0."
        android:inputType="textUri"
        android:textColor="#eaf1f9"
        android:textSize="18sp"
        android:focusable="true"
        android:focusableInTouchMode="true" />

    <Button
        android:id="@+id/conectar"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="@string/conectar"
        android:layout_marginTop="24dp"
        android:focusable="true" />
</LinearLayout>
```

- [ ] **Step 2: Escribir la actividad**

`android/app/src/main/java/com/inteks/display/SetupActivity.kt`:

```kotlin
package com.inteks.display

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText

class SetupActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_setup)

        val campo = findViewById<EditText>(R.id.direccion)
        findViewById<Button>(R.id.conectar).setOnClickListener {
            val escrito = campo.text.toString().trim().trimEnd('/')
            if (escrito.length > "http://".length) {
                SettingsStore(this).base = escrito
                startActivity(Intent(this, KioskActivity::class.java))
                finish()
            }
        }
        campo.requestFocus()
    }
}
```

- [ ] **Step 3: Declararla en el manifiesto**

Añadir dentro de `<application>`, después de `KioskActivity`:

```xml
        <activity
            android:name=".SetupActivity"
            android:exported="false"
            android:configChanges="orientation|screenSize|keyboardHidden|screenLayout" />
```

- [ ] **Step 4: Compilar e instalar, y comprobar que sale cuando no hay servidor**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat assembleDebug --no-daemon --console=plain
Pop-Location
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s 192.168.0.64:5555 install -r "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android\app\build\outputs\apk\debug\app-debug.apk"
```

Para forzar el caso «no hay servidor», **parar el servidor del PC** y luego:

```powershell
& $adb -s 192.168.0.64:5555 shell "pm clear com.inteks.display"
& $adb -s 192.168.0.64:5555 shell "am start -n com.inteks.display/.KioskActivity"
Start-Sleep -Seconds 15
& $adb -s 192.168.0.64:5555 shell "screencap -p /sdcard/s.png"
& $adb -s 192.168.0.64:5555 pull /sdcard/s.png "$env:TEMP\s.png"
```

Esperado: la captura muestra la pantalla de escribir la dirección. **Volver a arrancar el servidor después.**

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/inteks/display/SetupActivity.kt android/app/src/main/res/layout/activity_setup.xml android/app/src/main/AndroidManifest.xml
git commit -m "App Android: escribir la direccion a mano cuando el barrido no encuentra nada

Es el respaldo, no el camino principal: la caja es leanback_only, sin tactil,
asi que esto es cruceta y teclado en pantalla, letra a letra. El campo viene
relleno con http://192.168.0. para que queden tres cifras por teclear en el
caso normal."
```

---

### Task 10: Arrancar al encender y levantarse si se cae

**Files:**
- Create: `android/app/src/main/java/com/inteks/display/BootReceiver.kt`
- Create: `android/app/src/main/java/com/inteks/display/LatidoReceiver.kt`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Modify: `android/app/src/main/java/com/inteks/display/KioskActivity.kt`

**Interfaces:**
- Consumes: `KioskActivity`.
- Produces: `BootReceiver`, `LatidoReceiver`, `fun programarLatido(context: Context)`.

- [ ] **Step 1: Escribir los dos receptores**

`android/app/src/main/java/com/inteks/display/LatidoReceiver.kt`:

```kotlin
package com.inteks.display

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.SystemClock

const val LATIDO_MS = 2 * 60 * 1000L

/**
 * Relanza el reproductor si no está delante.
 *
 * Vive en AlarmManager, que es del sistema, no de la app: con 990 MB de RAM el
 * proceso de render del WebView puede morir, y en API 25 no existe
 * `onRenderProcessGone` (llegó en la 26), así que se cae la app entera y no
 * queda nadie dentro para levantarla. Un servicio en segundo plano moriría con
 * ella; la alarma no.
 */
class LatidoReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        context.startActivity(Intent(context, KioskActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            // singleTask + esta bandera: si ya está delante, no hace nada
            // visible; si no está, la trae.
            addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        })
        programarLatido(context)
    }
}

fun programarLatido(context: Context) {
    val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
    val pi = PendingIntent.getBroadcast(
        context, 0, Intent(context, LatidoReceiver::class.java),
        PendingIntent.FLAG_UPDATE_CURRENT
    )
    am.setInexactRepeating(
        AlarmManager.ELAPSED_REALTIME,
        SystemClock.elapsedRealtime() + LATIDO_MS,
        LATIDO_MS,
        pi
    )
}
```

`android/app/src/main/java/com/inteks/display/BootReceiver.kt`:

```kotlin
package com.inteks.display

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Al encender la caja: lanzar el reproductor y volver a poner la alarma, que
 *  las alarmas no sobreviven a un reinicio. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != Intent.ACTION_BOOT_COMPLETED) return
        context.startActivity(Intent(context, KioskActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        })
        programarLatido(context)
    }
}
```

- [ ] **Step 2: Declararlos en el manifiesto**

Añadir dentro de `<application>`:

```xml
        <receiver
            android:name=".BootReceiver"
            android:enabled="true"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
            </intent-filter>
        </receiver>

        <receiver
            android:name=".LatidoReceiver"
            android:enabled="true"
            android:exported="false" />
```

- [ ] **Step 3: Programar el latido también al abrir la app**

En `KioskActivity.onCreate`, justo después de `ajustes = SettingsStore(this)`:

```kotlin
        programarLatido(this)
```

- [ ] **Step 4: Compilar, instalar y comprobar el arranque real**

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat assembleDebug --no-daemon --console=plain
Pop-Location
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$d = "192.168.0.64:5555"
& $adb -s $d install -r "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android\app\build\outputs\apk\debug\app-debug.apk"
& $adb -s $d shell "am start -n com.inteks.display/.KioskActivity"
Start-Sleep -Seconds 10
& $adb -s $d reboot
Start-Sleep -Seconds 75
& $adb connect 192.168.0.64:5555
& $adb -s $d shell "dumpsys activity activities | grep -m1 mResumedActivity"
```

Esperado tras el reinicio, **sin tocar el mando**: `mResumedActivity: … com.inteks.display/.KioskActivity …`

- [ ] **Step 5: Comprobar que el latido la resucita**

**`am force-stop` NO sirve para esta prueba.** Deja la app en estado `stopped` y
**cancela sus alarmas**, así que simula que el usuario la detiene desde Ajustes,
no una muerte por falta de memoria — que es justo para lo que existe el latido.
Con `force-stop` el latido no la levanta, y eso es correcto, no un fallo. Hay
que matar el proceso:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$d = "192.168.0.64:5555"
& $adb -s $d root ; Start-Sleep -Seconds 4 ; & $adb connect $d   # la ROM es userdebug
$pid1 = ((& $adb -s $d shell "pidof com.inteks.display") -join "").Trim()
& $adb -s $d shell "kill -9 $pid1"
Start-Sleep -Seconds 4
& $adb -s $d shell "dumpsys package com.inteks.display | grep -m1 'stopped='"
& $adb -s $d shell "dumpsys alarm | grep -c -i inteks"
"--- esperando el latido (hasta 2 minutos) ---"
Start-Sleep -Seconds 140
& $adb -s $d shell "pidof com.inteks.display"
& $adb -s $d shell "dumpsys window windows | grep -m1 mCurrentFocus"
```

Esperado: tras el `kill` sale `stopped=false` y **3** alarmas vivas; a los ~2
minutos hay un **pid distinto** del de antes y `mCurrentFocus` vuelve a ser
`com.inteks.display/.KioskActivity`.

- [ ] **Step 6: Comprobar que enciende la pantalla si estaba dormida**

Esta es la prueba que destapó el fallo de producto más gordo del proyecto, así
que no se salta:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$d = "192.168.0.64:5555"
& $adb -s $d shell "am force-stop com.inteks.display"
& $adb -s $d shell "input keyevent KEYCODE_SLEEP"
Start-Sleep -Seconds 3
& $adb -s $d shell "dumpsys power | grep -m1 mWakefulness"     # Asleep
& $adb -s $d shell "am start -n com.inteks.display/.KioskActivity"
Start-Sleep -Seconds 12
& $adb -s $d shell "dumpsys power | grep -m1 mWakefulness"     # Awake
& $adb -s $d shell "dumpsys display | grep -m1 mScreenState"   # ON
```

**Y al mirar una captura en negro, comprobar SIEMPRE `dumpsys power` antes de
culpar al WebView.** `screencap` devuelve negro puro cuando el display está
apagado, y el síntoma es idéntico al de una página que no pinta.

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main/java/com/inteks/display/BootReceiver.kt android/app/src/main/java/com/inteks/display/LatidoReceiver.kt android/app/src/main/java/com/inteks/display/KioskActivity.kt android/app/src/main/AndroidManifest.xml
git commit -m "App Android: arrancar al encender y levantarse sola si se cae

El latido vive en AlarmManager, que es del sistema y no de la app. Con 990 MB
de RAM el proceso de render del WebView puede morir, y en API 25 no existe
onRenderProcessGone -llego en la 26-, asi que se cae la app entera y no queda
nadie dentro para levantarla. Un servicio en segundo plano moriria con ella.

Cubre los tres casos que dejan un escaparate muerto: el render sin memoria, la
app cerrada por el sistema, y alguien que salio al lanzador con el mando y se
dejo ahi.

Las alarmas no sobreviven a un reinicio, por eso BOOT_COMPLETED la vuelve a
poner ademas de lanzar el reproductor."
```

---

### Task 11: Meter la app en la disciplina de versiones

**Files:**
- Modify: `tools/subir-version.ps1`
- Modify: `tests/version-sync.test.js`

**Interfaces:**
- Consumes: `android/app/build.gradle.kts` del Task 1.
- Produces: nada nuevo; cierra el círculo del versionado.

- [ ] **Step 1: Escribir el test que falla**

El archivo ya tiene un ayudante `unico(archivo, patron, que)` y un `enServer()` que lee `APP_VERSION`. Añadir junto a los otros lectores, después de la línea de `enPackage`:

```javascript
const enAndroid = () =>
  unico("android/app/build.gradle.kts", /versionName\s*=\s*"([^"]+)"/, "versionName");
```

Y el test, después de `test("package.json va al mismo paso", …)`:

```javascript
test("la app Android va al mismo paso", () => {
  // Sin esto el APK saldria con la version que le tocara y no habria forma de
  // saber que codigo tiene instalado una tienda en su caja de TV.
  assert.strictEqual(enAndroid(), enServer(),
    "android/app/build.gradle.kts versionName no coincide con APP_VERSION");
});
```

- [ ] **Step 2: Ejecutar y ver que falla**

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
npm test
Pop-Location
```

Esperado: FALLA — `android/app/build.gradle.kts` dice `1.0.25` y `server.py` dirá lo que diga en ese momento; si coinciden, cambiar a mano el gradle a `0.0.1` para ver el test en rojo y luego devolverlo.

- [ ] **Step 3: Hacer que `subir-version.ps1` toque también el gradle**

El script ya tiene una función `Reemplazar $ruta $patron $nuevo $que` que aborta si no encuentra el patrón. Añadir una quinta llamada justo después de la de `package.json` (línea 57):

```powershell
Reemplazar "android\app\build.gradle.kts" '(?m)^(\s*versionName\s*=\s*)"[^"]+"' "`$1`"$Version`"" "versionName"
```

Y actualizar la cabecera del comentario, que dice «los tres sitios» y ahora son cuatro archivos:

```powershell
#  Sube el numero de version en los cuatro sitios donde vive.
```

- [ ] **Step 4: Probar el script de verdad y ver los tests en verde**

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
powershell -ExecutionPolicy Bypass -File tools\subir-version.ps1 1.0.26
npm test
Pop-Location
```

Esperado: el script anuncia los cinco archivos, incluido el gradle, y `npm test` pasa entero.

- [ ] **Step 5: Commit**

```bash
git add tools/subir-version.ps1 tests/version-sync.test.js android/app/build.gradle.kts server.py installer/setup.iss package.json CHANGELOG.md
git commit -m "1.0.26: la app Android entra en la disciplina de versiones

subir-version.ps1 toca ahora tambien android/app/build.gradle.kts, y
version-sync.test.js vigila que coincida con server.py, setup.iss y
package.json. Sin esto, el APK saldria con la version que le tocara y no habria
forma de saber que tiene instalada una tienda: exactamente el problema de los
cinco instaladores llamados 1.0.0 del 2026-08-09.

Anotado el cambio en CHANGELOG.md, que es lo unico que el script no puede
hacer solo."
```

---

## Verificación final

Antes de dar el trabajo por terminado, con el servidor arrancado y la caja encendida:

```powershell
# 1. Todos los tests, los de la app y los del proyecto
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\android"
.\gradlew.bat test --no-daemon --console=plain
Pop-Location
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
npm test
Get-ChildItem tests\test_*.py | ForEach-Object { python $_.FullName }
git status --short     # tiene que salir vacio
Pop-Location
```

Y en la caja, las cinco que no se pueden fingir:

| Prueba | Cómo | Qué tiene que pasar |
|---|---|---|
| Encuentra el servidor sola | `pm clear` + arrancar | Sale el player o la página de emparejar, sin escribir nada |
| Arranca al encender | `adb reboot`, esperar 75 s | La app está delante sin tocar el mando |
| Se levanta si se cae | `am force-stop`, esperar 2 min | Vuelve sola |
| Sobrevive sin servidor | Parar el servidor con el player ya cargado | **Sigue reproduciendo**, sin pantalla de error |
| Sobrevive a un cambio de IP | Cambiar el puerto del servidor a 9000 y reiniciarlo | Rebarre y vuelve **con la misma pantalla**, sin pedir código |

**Lo que sigue sin poder verificarse aquí, y hay que decirlo al entregar:** que aguante días encendida, que vuelva bien tras un corte de luz de verdad (que no es un `adb reboot`), y que el WebView 119 no se degrade tras semanas sin reiniciar.

# Interruptor «Este PC reproduce en su pantalla» — diseño

Fecha: 2026-10-30. Axel: «se me abre a cada rato la pantalla para anclar… esto de
activarlo y desactivarlo no lo podemos poner en la app».

## Problema
El instalador de Windows tiene la opción «mini PC del televisor». Al marcarla crea
la tarea programada **InTeks Display Pantalla** (`installer/registrar-pantalla.ps1`),
que lanza `InTeksDisplay.exe --pantalla` al iniciar sesión **y cada 5 minutos**. En un
PC de trabajo (el de Axel) eso reabre el reproductor a pantalla completa una y otra
vez. Hoy solo se evita borrando la tarea a mano en el Programador de tareas, y el
servidor (corre como SYSTEM) no puede tocarla desde el panel (Acceso denegado).

## Diseño
La tarea no se toca. Se le da un interruptor que ella misma respeta.

- **Ajuste** `pantalla_pc` (booleano) en `config.json`. Ausente = `true`, para que un
  mini PC de televisor ya instalado siga igual.
- **Panel → Ajustes → Opciones avanzadas**: casilla «Este PC reproduce en su propia
  pantalla (mini PC del televisor)», con aviso de que al desmarcarla la pantalla de
  este PC se cierra y un televisor conectado se quedaría sin contenido. Se guarda con
  el «Guardar cambios» de siempre; `/api/config` ya fusiona, no hace falta ruta nueva.
- **Lanzador** `escritorio/InTeksDisplay.cs`, solo con `--pantalla`:
  - al arrancar lee `config.json` (el mismo que ya lee `Puertos()`: el de
    `%ProgramData%\InTeks Display` y, si no existe, el de junto al .exe); si dice
    `"pantalla_pc": false`, **sale sin abrir ventana**;
  - con la ventana abierta, un temporizador mira el ajuste cada 5 s y, si pasa a
    `false`, **cierra la ventana**;
  - cualquier fallo de lectura o un valor distinto de `false` cuenta como activo: un
    error nunca debe dejar un televisor en negro.
- El panel (`InTeksDisplay.exe` sin `--pantalla`) no cambia.

## Límites
- Al volver a activarla, la pantalla reaparece cuando la tarea la relance (≤5 min) o
  al abrir el acceso directo: el servidor no tiene sesión de escritorio para abrirla.
- Para que el lanzador respete el ajuste hay que **instalar la versión nueva** en ese
  PC. Hasta entonces la tarea sigue abriendo la pantalla.
- No cambia el instalador, la tarea programada ni los reproductores Android.

## Fuera de alcance
Crear o borrar la tarea desde el panel; abrir la pantalla al instante al activar.

## Pruebas
- `tests/test_pantalla_pc.py`: guardar `pantalla_pc:false` por `/api/config` se
  conserva al fusionar otros ajustes y `GET /api/config` lo devuelve.
- Lógica del lanzador separada en una función pura (`LeerPantallaPc(texto)`) y
  comprobada compilando con `escritorio/compilar.ps1` y un arnés mínimo de `csc`.
- Visual/real: lo comprueba Axel en su PC tras instalar.

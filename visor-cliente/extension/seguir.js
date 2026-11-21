// Mide DÓNDE está el recuadro activo dentro de la pestaña (solo números, ~8 veces por segundo) y
// pinta el botón flotante para cambiar de recuadro u ocultar. Nunca lee ni envía el contenido de la página.
(function () {
  let zona = null;                        // { lista: [{nombre, selector}], activa }
  let compartiendo = false, mostrando = true, tabletOk = false;
  let barra = null, firma = "";

  const leer = () => chrome.storage.local.get(["zonas", "compartiendo", "mostrando", "tabletOk"]).then((e) => {
    zona = (e.zonas || {})[location.origin] || null;
    compartiendo = !!e.compartiendo; mostrando = e.mostrando !== false; tabletOk = !!e.tabletOk;
    pintar();
  });
  leer();
  chrome.storage.onChanged.addListener(leer);

  const activo = () => (zona && zona.lista[zona.activa]) || null;

  // Cada pulsación se refleja AL INSTANTE en la barra (sin esperar a la extensión) y, si algo
  // falla, el motivo se escribe en la propia barra en vez de quedarse mudo.
  function avisarError(e) {
    firma = ""; if (barra) { const t = barra.querySelector("[data-est]"); if (t) { t.textContent = "⚠ " + (e && e.message || e); t.style.color = "#f28b82"; } }
  }
  function elegirZona(i) {
    try {
      zona.activa = i; mostrando = true; pintar();
      chrome.storage.local.get("zonas").then(({ zonas = {} }) => {
        zonas[location.origin] = zona;
        return chrome.storage.local.set({ zonas });
      }).catch(avisarError);
      chrome.storage.local.set({ mostrando: true }).catch(avisarError);   // el fondo se lo pasa al emisor
    } catch (e) { avisarError(e); }
  }
  function ocultar() {
    try {
      mostrando = false; pintar();
      chrome.storage.local.set({ mostrando: false }).catch(avisarError);
    } catch (e) { avisarError(e); }
  }

  // ── barra flotante: un botón por recuadro + «Ocultar». Se arrastra por el asa (⠿).
  function pintar() {
    const ver = compartiendo && zona && zona.lista.length && window === window.top;
    if (!ver) { if (barra) { barra.remove(); barra = null; firma = ""; } return; }
    const nueva = JSON.stringify([zona.lista.map((z) => z.nombre), zona.activa, mostrando, tabletOk]);
    if (barra && nueva === firma) return;
    firma = nueva;
    const pos = barra ? { l: barra.style.left, t: barra.style.top } : null;
    if (barra) barra.remove();
    barra = document.createElement("div");
    barra.style.cssText = "position:fixed;right:18px;bottom:18px;z-index:2147483647;display:flex;gap:6px;align-items:center;" +
      "font:600 13px 'Segoe UI',sans-serif;padding:6px;border-radius:24px;background:rgba(32,33,36,.92);box-shadow:0 2px 10px rgba(0,0,0,.4)";
    if (pos && pos.l) { barra.style.left = pos.l; barra.style.top = pos.t; barra.style.right = "auto"; barra.style.bottom = "auto"; }
    const boton = (texto, color, fn) => {
      const b = document.createElement("div");
      b.textContent = texto;
      b.style.cssText = "padding:8px 14px;border-radius:18px;color:#fff;cursor:pointer;user-select:none;background:" + color;
      b.addEventListener("pointerup", (e) => { e.stopPropagation(); fn(); });
      b.addEventListener("click", (e) => e.stopPropagation());
      barra.appendChild(b);
    };
    const asa = document.createElement("div");
    asa.textContent = "⠿"; asa.style.cssText = "color:#aaa;cursor:move;padding:0 6px;font-size:16px;user-select:none";
    let mov = null;
    asa.addEventListener("pointerdown", (e) => { mov = true; asa.setPointerCapture(e.pointerId); });
    asa.addEventListener("pointermove", (e) => {
      if (!mov) return;
      barra.style.left = Math.max(0, e.clientX - 20) + "px"; barra.style.top = Math.max(0, e.clientY - 18) + "px";
      barra.style.right = "auto"; barra.style.bottom = "auto";
    });
    asa.addEventListener("pointerup", () => { mov = null; });
    barra.appendChild(asa);
    // Qué se ve ahora mismo en la tablet, sin tener que adivinarlo por los colores.
    const est = document.createElement("div");
    est.textContent = (tabletOk ? "📺 Pantalla conectada" : "📺 Pantalla sin conectar") + " · " +
      (mostrando ? "viendo: " + zona.lista[zona.activa].nombre : "publicidad");
    est.setAttribute("data-est", "1");
    est.style.cssText = "color:" + (tabletOk ? "#81c995" : "#fdd663") + ";padding:0 8px;white-space:nowrap";
    barra.appendChild(est);
    zona.lista.forEach((z, i) => boton((mostrando && i === zona.activa ? "● " : "") + z.nombre,
      mostrando && i === zona.activa ? "#1e8e3e" : "#3c4043", () => elegirZona(i)));
    boton(mostrando ? "⏸ Ocultar" : "⏸ Oculto", mostrando ? "#c5221f" : "#80868b", ocultar);
    document.documentElement.appendChild(barra);
  }

  setInterval(() => {
    const z = activo();
    if (!z || document.hidden) return;
    let el = null;
    try { el = document.querySelector(z.selector); } catch (e) {}
    const r = el ? el.getBoundingClientRect() : null;
    const visible = !!r && r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 &&
                    r.top < innerHeight && r.left < innerWidth;
    chrome.runtime.sendMessage({
      tipo: "rect", visible,
      l: r ? r.left : 0, t: r ? r.top : 0, w: r ? r.width : 0, h: r ? r.height : 0,
      iw: innerWidth, ih: innerHeight,
    }).catch(() => {});
  }, 125);
})();

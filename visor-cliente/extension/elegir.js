// Selector: pasa el ratón para ver el recuadro, pulsa para elegirlo. Esc cancela.
(function () {
  if (window.__visorElegir) return;
  window.__visorElegir = true;
  const marco = document.createElement("div");
  marco.style.cssText = "position:fixed;z-index:2147483647;pointer-events:none;border:3px solid #ffeb3b;background:rgba(255,235,59,.18);display:none";
  const aviso = document.createElement("div");
  aviso.textContent = "Pulsa el recuadro que verá el cliente  ·  Esc: cancelar";
  aviso.style.cssText = "position:fixed;z-index:2147483647;top:10px;left:50%;transform:translateX(-50%);background:#222;color:#ffeb3b;font:600 16px sans-serif;padding:8px 16px;border-radius:6px;pointer-events:none";
  document.documentElement.append(marco, aviso);
  let actual = null;

  function selectorDe(el) {
    const partes = [];
    while (el && el.nodeType === 1 && el !== document.body) {
      if (el.id && document.querySelectorAll("#" + CSS.escape(el.id)).length === 1) {
        partes.unshift("#" + CSS.escape(el.id)); break;
      }
      const hermanos = Array.from(el.parentNode.children).filter((h) => h.tagName === el.tagName);
      let p = el.tagName.toLowerCase();
      if (hermanos.length > 1) p += ":nth-of-type(" + (hermanos.indexOf(el) + 1) + ")";
      partes.unshift(p);
      el = el.parentNode;
    }
    return partes.join(" > ");
  }
  function mover(e) {
    actual = e.target;
    const r = actual.getBoundingClientRect();
    Object.assign(marco.style, { display: "block", left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px" });
  }
  function acabar() {
    document.removeEventListener("mousemove", mover, true);
    document.removeEventListener("click", pulsar, true);
    document.removeEventListener("keydown", tecla, true);
    marco.remove(); aviso.remove(); window.__visorElegir = false;
  }
  function pulsar(e) {
    e.preventDefault(); e.stopPropagation();
    const sel = selectorDe(actual);
    acabar();
    chrome.storage.local.get("zonas").then(({ zonas = {} }) => {
      const z = zonas[location.origin] || { lista: [], activa: 0 };
      const nombre = (prompt("Nombre del recuadro (por ejemplo: Resumen, Datos de la cuenta)",
        "Recuadro " + (z.lista.length + 1)) || "").trim() || "Recuadro " + (z.lista.length + 1);
      z.lista.push({ nombre, selector: sel });
      z.activa = z.lista.length - 1;
      zonas[location.origin] = z;
      chrome.storage.local.set({ zonas });
    });
  }
  function tecla(e) { if (e.key === "Escape") acabar(); }
  document.addEventListener("mousemove", mover, true);
  document.addEventListener("click", pulsar, true);
  document.addEventListener("keydown", tecla, true);
})();

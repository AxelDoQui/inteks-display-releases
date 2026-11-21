/**
 * Visor de cliente — buzón y página de la tablet.
 *
 * Hace dos cosas, y NINGUNA guarda imágenes ni datos del negocio:
 *  1) Sirve la página que abre la tablet (Tablet.html).
 *  2) Hace de buzón del «saludo» inicial entre el PC y la tablet (unos 2 KB de texto técnico, que
 *     caducan solos a la media hora). La imagen va directa del PC a la tablet por la wifi.
 *
 * Este script es APARTE de los de la caja: crea uno nuevo en script.google.com.
 */
var CADUCA_S = 1800;

function codigoValido_(c) {
  return /^[a-z0-9]{8,16}$/.test(String(c || ''));
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  var p = (e && e.parameter) || {};
  if (!p.fn) {
    var t = HtmlService.createTemplateFromFile('Tablet');
    t.codigo = codigoValido_(p.cod) ? p.cod : '';
    t.urlScript = ScriptApp.getService().getUrl();
    return t.evaluate()
      .setTitle('Pantalla del cliente')
      .addMetaTag('viewport', 'width=device-width,initial-scale=1')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  }
  if (!codigoValido_(p.cod)) return json_({ ok: false, error: 'codigo' });
  var cache = CacheService.getScriptCache();
  var clave = p.fn === 'oferta' ? 'o' + p.cod : p.fn === 'respuesta' ? 'a' + p.cod : null;
  if (!clave) return json_({ ok: false, error: 'fn' });
  var sdp = cache.get(clave);
  if (!sdp) return json_({ ok: false });
  cache.remove(clave);                       // de un solo uso: quien lo lee se lo lleva
  return json_({ ok: true, sdp: sdp });
}

function doPost(e) {
  var d;
  try { d = JSON.parse(e.postData.contents); } catch (x) { return json_({ ok: false, error: 'json' }); }
  if (!codigoValido_(d.c) || typeof d.sdp !== 'string' || d.sdp.length > 20000) return json_({ ok: false, error: 'datos' });
  var cache = CacheService.getScriptCache();
  if (d.fn === 'oferta') {
    cache.remove('a' + d.c);                 // una oferta nueva anula cualquier respuesta vieja
    cache.put('o' + d.c, d.sdp, CADUCA_S);
  } else if (d.fn === 'respuesta') {
    cache.put('a' + d.c, d.sdp, CADUCA_S);
  } else {
    return json_({ ok: false, error: 'fn' });
  }
  return json_({ ok: true });
}

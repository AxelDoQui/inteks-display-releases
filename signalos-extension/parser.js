// SignalOS Pro — detección de divisas (compartido por content.js y sidebar.js)
// No usa ES modules: expone window.SignalosParser para content scripts.
window.SignalosParser = (function () {
  // Misma base que admin.html (flags como emoji; el player las convierte a imagen)
  const CURRENCY_DB = [
    {code:"USD",country:"Estados Unidos",currency:"Dólar estadounidense",flag:"🇺🇸",aliases:["dollar","dolar","dólares","dolares","estados unidos","eeuu","usa","us dollar"]},
    {code:"EUR",country:"Zona Euro",currency:"Euro",flag:"🇪🇺",aliases:["euro","euros"]},
    {code:"GBP",country:"Reino Unido",currency:"Libra esterlina",flag:"🇬🇧",aliases:["pound","libra","sterling","reino unido","britain"]},
    {code:"JPY",country:"Japón",currency:"Yen japonés",flag:"🇯🇵",aliases:["yen","japon","japón","japan"]},
    {code:"CHF",country:"Suiza",currency:"Franco suizo",flag:"🇨🇭",aliases:["franco suizo","suiza","switzerland","swiss franc"]},
    {code:"CAD",country:"Canadá",currency:"Dólar canadiense",flag:"🇨🇦",aliases:["canadian","canada","canadá"]},
    {code:"AUD",country:"Australia",currency:"Dólar australiano",flag:"🇦🇺",aliases:["australian","australia"]},
    {code:"CNY",country:"China",currency:"Yuan chino",flag:"🇨🇳",aliases:["yuan","rmb","china","renminbi"]},
    {code:"MXN",country:"México",currency:"Peso mexicano",flag:"🇲🇽",aliases:["peso mexicano","mexico","méxico"]},
    {code:"BRL",country:"Brasil",currency:"Real brasileño",flag:"🇧🇷",aliases:["real","brasil","brazil"]},
    {code:"COP",country:"Colombia",currency:"Peso colombiano",flag:"🇨🇴",aliases:["peso colombiano","colombia"]},
    {code:"ARS",country:"Argentina",currency:"Peso argentino",flag:"🇦🇷",aliases:["peso argentino","argentina"]},
    {code:"CLP",country:"Chile",currency:"Peso chileno",flag:"🇨🇱",aliases:["peso chileno","chile"]},
    {code:"PEN",country:"Perú",currency:"Sol peruano",flag:"🇵🇪",aliases:["soles","sol peruano","peru","perú"]},
    {code:"UYU",country:"Uruguay",currency:"Peso uruguayo",flag:"🇺🇾",aliases:["peso uruguayo","uruguay"]},
    {code:"PYG",country:"Paraguay",currency:"Guaraní paraguayo",flag:"🇵🇾",aliases:["guarani","guaraní","paraguay"]},
    {code:"BOB",country:"Bolivia",currency:"Boliviano",flag:"🇧🇴",aliases:["boliviano","bolivia"]},
    {code:"VEF",country:"Venezuela",currency:"Bolívar venezolano",flag:"🇻🇪",aliases:["bolivar","bolívar","venezuela","ves"]},
    {code:"GTQ",country:"Guatemala",currency:"Quetzal guatemalteco",flag:"🇬🇹",aliases:["quetzal","guatemala"]},
    {code:"DZD",country:"Argelia",currency:"Dinar argelino",flag:"🇩🇿",aliases:["dinar","argelia","algeria"]},
    {code:"DKK",country:"Dinamarca",currency:"Corona danesa",flag:"🇩🇰",aliases:["corona danesa","dinamarca","denmark"]},
    {code:"SEK",country:"Suecia",currency:"Corona sueca",flag:"🇸🇪",aliases:["corona sueca","suecia","sweden"]},
    {code:"NOK",country:"Noruega",currency:"Corona noruega",flag:"🇳🇴",aliases:["corona noruega","noruega","norway"]},
    {code:"RUB",country:"Rusia",currency:"Rublo ruso",flag:"🇷🇺",aliases:["ruble","rublo","rusia","russia"]},
    {code:"TRY",country:"Turquía",currency:"Lira turca",flag:"🇹🇷",aliases:["lira","turquia","turquía","turkey"]},
    {code:"INR",country:"India",currency:"Rupia india",flag:"🇮🇳",aliases:["rupee","rupia","india"]},
    {code:"KRW",country:"Corea del Sur",currency:"Won surcoreano",flag:"🇰🇷",aliases:["won","korea","corea"]},
    {code:"SGD",country:"Singapur",currency:"Dólar de Singapur",flag:"🇸🇬",aliases:["singapore","singapur"]},
    {code:"HKD",country:"Hong Kong",currency:"Dólar de Hong Kong",flag:"🇭🇰",aliases:["hong kong"]},
    {code:"NZD",country:"Nueva Zelanda",currency:"Dólar neozelandés",flag:"🇳🇿",aliases:["new zealand","nueva zelanda"]},
    {code:"ZAR",country:"Sudáfrica",currency:"Rand sudafricano",flag:"🇿🇦",aliases:["rand","sudafrica","south africa"]},
    {code:"MAD",country:"Marruecos",currency:"Dírham marroquí",flag:"🇲🇦",aliases:["dirham","marruecos","morocco"]},
    {code:"DOP",country:"Rep. Dominicana",currency:"Peso dominicano",flag:"🇩🇴",aliases:["peso dominicano","dominicana","dominican"]},
    {code:"CUC",country:"Cuba",currency:"Peso cubano conv.",flag:"🇨🇺",aliases:["peso cubano","cuba"]},
    {code:"CRC",country:"Costa Rica",currency:"Colón costarricense",flag:"🇨🇷",aliases:["colon","colón","costa rica"]}
  ];

  const CODE_MAP = {};
  CURRENCY_DB.forEach(c => { CODE_MAP[c.code.toUpperCase()] = c; });

  // ¿Qué moneda aparece en este texto? Primero por código ISO (fiable), luego por alias.
  function matchCurrency(text) {
    const codes = (text.toUpperCase().match(/\b[A-Z]{3}\b/g) || []);
    for (const code of codes) { if (CODE_MAP[code]) return CODE_MAP[code]; }
    const low = text.toLowerCase();
    for (const c of CURRENCY_DB) {
      for (const a of c.aliases) {
        if (a.length < 4) continue;                 // evita falsos positivos cortos
        if (low.includes(a)) return c;
      }
    }
    return null;
  }

  // Extrae la tasa (primer número decimal plausible). Normaliza coma->punto.
  function extractRate(text, cur) {
    const t = text.replace(new RegExp('\\b' + cur.code + '\\b', 'gi'), ' ');
    const nums = t.match(/\d{1,3}(?:[.,]\d{1,6})|\d+[.,]\d+|\d{1,6}/g);
    if (!nums) return null;
    for (const raw of nums) {
      const v = parseFloat(raw.replace(',', '.'));
      if (isNaN(v) || v <= 0 || v > 100000) continue;     // descarta 0, negativos y enteros enormes (años, IDs)
      if (/^\d{4}$/.test(raw) && v > 1900 && v < 2100) continue; // descarta años
      return raw.replace(',', '.');
    }
    return null;
  }

  // Recorre líneas de texto buscando moneda + tasa
  function detectInText(text) {
    const out = [], seen = new Set();
    (text || '').split('\n').forEach(ln => {
      const t = ln.replace(/\s+/g, ' ').trim();
      if (!t || t.length > 160) return;
      const cur = matchCurrency(t);
      if (!cur || seen.has(cur.code)) return;
      const rate = extractRate(t, cur);
      if (rate === null) return;
      seen.add(cur.code);
      out.push({ flag: cur.flag, country: cur.country, currency: cur.currency, code: cur.code, rate });
    });
    return out;
  }

  // Escanea la página: filas de tablas/listas/clases típicas y, si hace falta, todo el texto
  function scanPage() {
    const results = [], seen = new Set();
    const sel = 'tr, li, [class*="rate" i], [class*="currency" i], [class*="moneda" i], [class*="divisa" i], [class*="exchange" i], [class*="cambio" i], [class*="cotiz" i]';
    let els = [];
    try { els = Array.prototype.slice.call(document.querySelectorAll(sel)); }
    catch (e) { els = Array.prototype.slice.call(document.querySelectorAll('tr, li')); }
    for (const el of els) {
      const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      if (!text || text.length > 160) continue;
      const cur = matchCurrency(text);
      if (!cur || seen.has(cur.code)) continue;
      const rate = extractRate(text, cur);
      if (rate === null) continue;
      seen.add(cur.code);
      results.push({ flag: cur.flag, country: cur.country, currency: cur.currency, code: cur.code, rate });
    }
    // Fallback por líneas si encontramos poco
    if (results.length < 2 && document.body) {
      detectInText(document.body.innerText).forEach(r => {
        if (!seen.has(r.code)) { seen.add(r.code); results.push(r); }
      });
    }
    return results;
  }

  return { CURRENCY_DB, CODE_MAP, matchCurrency, extractRate, detectInText, scanPage };
})();

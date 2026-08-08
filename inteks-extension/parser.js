// InTeks Display — detección de divisas (compartido por content.js y sidebar.js)
// No usa ES modules: expone window.SignalosParser para content scripts.
window.SignalosParser = (function () {
  // Base de monedas — COPIA EXACTA de la de admin.html.
  // La extensión no puede importar del admin, así que se duplica; hay un test
  // (tests/currency-db-sync.test.js) que falla si las dos dejan de coincidir.
  const CURRENCY_DB = [
    {code:"ARS",country:"Argentina",currency:"Peso argentino",flag:"🇦🇷",aliases:["peso argentino","argentina","ars$"]},
    {code:"AUD",country:"Australia",currency:"Dólar australiano",flag:"🇦🇺",aliases:["australian","australia","aud$"]},
    {code:"BOB",country:"Bolivia",currency:"Boliviano",flag:"🇧🇴",aliases:["boliviano","bolivia","bob"]},
    {code:"BRL",country:"Brasil",currency:"Real brasileño",flag:"🇧🇷",aliases:["real","brasil","brazil","r$","&r"]},
    {code:"BZD",country:"Belice",currency:"Dólar beliceño",flag:"🇧🇿",aliases:["belice","belize","dolar beliceño"]},
    {code:"CAD",country:"Canadá",currency:"Dólar canadiense",flag:"🇨🇦",aliases:["canadian","canada","canadá","cad$"]},
    {code:"CHF",country:"Suiza",currency:"Franco suizo",flag:"🇨🇭",aliases:["franc","franco suizo","suiza","switzerland","swiss franc"]},
    {code:"CLP",country:"Chile",currency:"Peso chileno",flag:"🇨🇱",aliases:["peso chileno","chile","clp$"]},
    {code:"CNY",country:"China",currency:"Yuan chino",flag:"🇨🇳",aliases:["yuan","rmb","china","renminbi"]},
    {code:"COP",country:"Colombia",currency:"Peso colombiano",flag:"🇨🇴",aliases:["peso colombiano","colombia"]},
    {code:"CRC",country:"Costa Rica",currency:"Colón costarricense",flag:"🇨🇷",aliases:["colon","colón","costa rica"]},
    {code:"DKK",country:"Dinamarca",currency:"Corona danesa",flag:"🇩🇰",aliases:["corona danesa","dinamarca","denmark"]},
    {code:"DOP",country:"Rep. Dominicana",currency:"Peso dominicano",flag:"🇩🇴",aliases:["peso dominicano","dominicana","dominican","rd$"]},
    {code:"DZD",country:"Argelia",currency:"Dinar argelino",flag:"🇩🇿",aliases:["dinar","argelia","algeria","dzd"]},
    {code:"EUR",country:"Zona Euro",currency:"Euro",flag:"🇪🇺",aliases:["euro","euros","€"]},
    {code:"GBP",country:"Reino Unido",currency:"Libra esterlina",flag:"🇬🇧",aliases:["pound","libra","sterling","reino unido","uk","britain","gbp£","£"]},
    {code:"GTQ",country:"Guatemala",currency:"Quetzal guatemalteco",flag:"🇬🇹",aliases:["quetzal","guatemala","gtq"]},
    {code:"HNL",country:"Honduras",currency:"Lempira hondureño",flag:"🇭🇳",aliases:["lempira","lempiras","honduras"]},
    {code:"INR",country:"India",currency:"Rupia india",flag:"🇮🇳",aliases:["rupee","rupia","india"]},
    {code:"JMD",country:"Jamaica",currency:"Dólar jamaicano",flag:"🇯🇲",aliases:["jamaica","dolar jamaicano"]},
    {code:"JPY",country:"Japón",currency:"Yen japonés",flag:"🇯🇵",aliases:["yen","japon","japón","japan","¥"]},
    {code:"KRW",country:"Corea del Sur",currency:"Won surcoreano",flag:"🇰🇷",aliases:["won","korea","corea"]},
    {code:"MAD",country:"Marruecos",currency:"Dírham marroquí",flag:"🇲🇦",aliases:["dirham","marruecos","morocco"]},
    {code:"MXN",country:"México",currency:"Peso mexicano",flag:"🇲🇽",aliases:["peso mexicano","mexico","méxico","mxn$"]},
    {code:"NIO",country:"Nicaragua",currency:"Córdoba nicaragüense",flag:"🇳🇮",aliases:["cordoba","córdoba","nicaragua"]},
    {code:"NOK",country:"Noruega",currency:"Corona noruega",flag:"🇳🇴",aliases:["corona noruega","noruega","norway"]},
    {code:"NZD",country:"Nueva Zelanda",currency:"Dólar neozelandés",flag:"🇳🇿",aliases:["new zealand","nueva zelanda","nzd$"]},
    {code:"PAB",country:"Panamá",currency:"Balboa panameño",flag:"🇵🇦",aliases:["balboa","balboas","panama","panamá"]},
    {code:"PEN",country:"Perú",currency:"Sol peruano",flag:"🇵🇪",aliases:["soles","sol peruano","peru","perú","s/.","s/"]},
    {code:"PYG",country:"Paraguay",currency:"Guaraní paraguayo",flag:"🇵🇾",aliases:["guarani","guaraní","paraguay","pyg"]},
    {code:"RUB",country:"Rusia",currency:"Rublo ruso",flag:"🇷🇺",aliases:["ruble","rublo","rusia","russia"]},
    {code:"SEK",country:"Suecia",currency:"Corona sueca",flag:"🇸🇪",aliases:["corona sueca","suecia","sweden"]},
    {code:"TRY",country:"Turquía",currency:"Lira turca",flag:"🇹🇷",aliases:["lira","turquia","turquía","turkey"]},
    {code:"USD",country:"Estados Unidos",currency:"Dólar estadounidense",flag:"🇺🇸",aliases:["dollar","dolar","dólares","dolares","estados unidos","eeuu","usa","us dollar","$usd","usd$"]},
    {code:"UYU",country:"Uruguay",currency:"Peso uruguayo",flag:"🇺🇾",aliases:["peso uruguayo","uruguay","uyu$"]},
    {code:"XAF",country:"África Central",currency:"Franco CFA",flag:"🌍",aliases:["fcfa","cfa","franco cfa","xaf","africa central"]},
    {code:"ZAR",country:"Sudáfrica",currency:"Rand sudafricano",flag:"🇿🇦",aliases:["rand","sudafrica","south africa"]},
    {code:"AED",country:"Emiratos Árabes Unidos",currency:"Dírham emiratí",flag:"🇦🇪",aliases:["dirham emirati","dírham emiratí","emiratos arabes unidos","emiratos árabes unidos"]},
    {code:"ALL",country:"Albania",currency:"Lek albanés",flag:"🇦🇱",aliases:["albania","lek albanes","lek albanés"]},
    {code:"AMD",country:"Armenia",currency:"Dram armenio",flag:"🇦🇲",aliases:["armenia","dram armenio"]},
    {code:"AOA",country:"Angola",currency:"Kwanza angoleño",flag:"🇦🇴",aliases:["angola","kwanza angoleno","kwanza angoleño"]},
    {code:"AZN",country:"Azerbaiyán",currency:"Manat azerbaiyano",flag:"🇦🇿",aliases:["azerbaiyan","azerbaiyán","manat azerbaiyano"]},
    {code:"BAM",country:"Bosnia y Herzegovina",currency:"Marco convertible",flag:"🇧🇦",aliases:["bosnia y herzegovina","marco convertible"]},
    {code:"BBD",country:"Barbados",currency:"Dólar de Barbados",flag:"🇧🇧",aliases:["barbados","dolar de barbados","dólar de barbados"]},
    {code:"BDT",country:"Bangladesh",currency:"Taka bangladesí",flag:"🇧🇩",aliases:["bangladesh","taka bangladesi","taka bangladesí"]},
    {code:"BSD",country:"Bahamas",currency:"Dólar bahameño",flag:"🇧🇸",aliases:["bahamas","dolar bahameno","dólar bahameño"]},
    {code:"BYN",country:"Bielorrusia",currency:"Rublo bielorruso",flag:"🇧🇾",aliases:["bielorrusia","rublo bielorruso"]},
    {code:"CDF",country:"Congo (Rep. Dem.)",currency:"Franco congoleño",flag:"🇨🇩",aliases:["congo (rep. dem.)","franco congoleno","franco congoleño"]},
    {code:"CUP",country:"Cuba",currency:"Peso cubano",flag:"🇨🇺",aliases:["cuba","peso cubano"]},
    {code:"CZK",country:"Chequia",currency:"Corona checa",flag:"🇨🇿",aliases:["chequia","corona checa"]},
    {code:"EGP",country:"Egipto",currency:"Libra egipcia",flag:"🇪🇬",aliases:["egipto","libra egipcia"]},
    {code:"ETB",country:"Etiopía",currency:"Birr etíope",flag:"🇪🇹",aliases:["birr etiope","birr etíope","etiopia","etiopía"]},
    {code:"GEL",country:"Georgia",currency:"Lari georgiano",flag:"🇬🇪",aliases:["georgia","lari georgiano"]},
    {code:"GHS",country:"Ghana",currency:"Cedi ghanés",flag:"🇬🇭",aliases:["cedi ghanes","cedi ghanés","ghana"]},
    {code:"GMD",country:"Gambia",currency:"Dalasi gambiano",flag:"🇬🇲",aliases:["dalasi gambiano","gambia"]},
    {code:"GNF",country:"Guinea",currency:"Franco guineano",flag:"🇬🇳",aliases:["franco guineano","guinea"]},
    {code:"GYD",country:"Guyana",currency:"Dólar guyanés",flag:"🇬🇾",aliases:["dolar guyanes","dólar guyanés","guyana"]},
    {code:"HTG",country:"Haití",currency:"Gourde haitiano",flag:"🇭🇹",aliases:["gourde haitiano","haiti","haití"]},
    {code:"HUF",country:"Hungría",currency:"Forinto húngaro",flag:"🇭🇺",aliases:["forinto hungaro","forinto húngaro","hungria","hungría"]},
    {code:"IDR",country:"Indonesia",currency:"Rupia indonesia",flag:"🇮🇩",aliases:["indonesia","rupia indonesia"]},
    {code:"ILS",country:"Israel",currency:"Séquel israelí",flag:"🇮🇱",aliases:["israel","sequel israeli","séquel israelí"]},
    {code:"JOD",country:"Jordania",currency:"Dinar jordano",flag:"🇯🇴",aliases:["dinar jordano","jordania"]},
    {code:"KES",country:"Kenia",currency:"Chelín keniano",flag:"🇰🇪",aliases:["chelin keniano","chelín keniano","kenia"]},
    {code:"KGS",country:"Kirguizistán",currency:"Som kirguís",flag:"🇰🇬",aliases:["kirguizistan","kirguizistán","som kirguis","som kirguís"]},
    {code:"KHR",country:"Camboya",currency:"Riel camboyano",flag:"🇰🇭",aliases:["camboya","riel camboyano"]},
    {code:"KZT",country:"Kazajistán",currency:"Tenge kazajo",flag:"🇰🇿",aliases:["kazajistan","kazajistán","tenge kazajo"]},
    {code:"LBP",country:"Líbano",currency:"Libra libanesa",flag:"🇱🇧",aliases:["libano","libra libanesa","líbano"]},
    {code:"LKR",country:"Sri Lanka",currency:"Rupia esrilanquesa",flag:"🇱🇰",aliases:["rupia esrilanquesa","sri lanka"]},
    {code:"MDL",country:"Moldavia",currency:"Leu moldavo",flag:"🇲🇩",aliases:["leu moldavo","moldavia"]},
    {code:"MKD",country:"Macedonia del Norte",currency:"Denar macedonio",flag:"🇲🇰",aliases:["denar macedonio","macedonia del norte"]},
    {code:"MMK",country:"Myanmar",currency:"Kyat birmano",flag:"🇲🇲",aliases:["kyat birmano","myanmar"]},
    {code:"MYR",country:"Malasia",currency:"Ringgit malayo",flag:"🇲🇾",aliases:["malasia","ringgit malayo"]},
    {code:"MZN",country:"Mozambique",currency:"Metical mozambiqueño",flag:"🇲🇿",aliases:["metical mozambiqueno","metical mozambiqueño","mozambique"]},
    {code:"NGN",country:"Nigeria",currency:"Naira nigeriana",flag:"🇳🇬",aliases:["naira nigeriana","nigeria"]},
    {code:"NPR",country:"Nepal",currency:"Rupia nepalí",flag:"🇳🇵",aliases:["nepal","rupia nepali","rupia nepalí"]},
    {code:"PHP",country:"Filipinas",currency:"Peso filipino",flag:"🇵🇭",aliases:["filipinas","peso filipino"]},
    {code:"PKR",country:"Pakistán",currency:"Rupia pakistaní",flag:"🇵🇰",aliases:["pakistan","pakistán","rupia pakistani","rupia pakistaní"]},
    {code:"PLN",country:"Polonia",currency:"Esloti polaco",flag:"🇵🇱",aliases:["esloti polaco","polonia"]},
    {code:"RON",country:"Rumania",currency:"Leu rumano",flag:"🇷🇴",aliases:["leu rumano","rumania"]},
    {code:"RSD",country:"Serbia",currency:"Dinar serbio",flag:"🇷🇸",aliases:["dinar serbio","serbia"]},
    {code:"SAR",country:"Arabia Saudí",currency:"Riyal saudí",flag:"🇸🇦",aliases:["arabia saudi","arabia saudí","riyal saudi","riyal saudí"]},
    {code:"SRD",country:"Surinam",currency:"Dólar surinamés",flag:"🇸🇷",aliases:["dolar surinames","dólar surinamés","surinam"]},
    {code:"THB",country:"Tailandia",currency:"Baht tailandés",flag:"🇹🇭",aliases:["baht tailandes","baht tailandés","tailandia"]},
    {code:"TJS",country:"Tayikistán",currency:"Somoni tayiko",flag:"🇹🇯",aliases:["somoni tayiko","tayikistan","tayikistán"]},
    {code:"TND",country:"Túnez",currency:"Dinar tunecino",flag:"🇹🇳",aliases:["dinar tunecino","tunez","túnez"]},
    {code:"TTD",country:"Trinidad y Tobago",currency:"Dólar trinitense",flag:"🇹🇹",aliases:["dolar trinitense","dólar trinitense","trinidad y tobago"]},
    {code:"TZS",country:"Tanzania",currency:"Chelín tanzano",flag:"🇹🇿",aliases:["chelin tanzano","chelín tanzano","tanzania"]},
    {code:"UAH",country:"Ucrania",currency:"Grivna ucraniana",flag:"🇺🇦",aliases:["grivna ucraniana","ucrania"]},
    {code:"UGX",country:"Uganda",currency:"Chelín ugandés",flag:"🇺🇬",aliases:["chelin ugandes","chelín ugandés","uganda"]},
    {code:"UZS",country:"Uzbekistán",currency:"Sum uzbeko",flag:"🇺🇿",aliases:["sum uzbeko","uzbekistan","uzbekistán"]},
    {code:"VES",country:"Venezuela",currency:"Bolívar venezolano",flag:"🇻🇪",aliases:["bolivar venezolano","bolívar venezolano","venezuela"]},
    {code:"VND",country:"Vietnam",currency:"Dong vietnamita",flag:"🇻🇳",aliases:["dong vietnamita","vietnam"]},
    {code:"XCD",country:"Caribe Oriental",currency:"Dólar del Caribe Oriental",flag:"",aliases:["caribe oriental","dolar del caribe oriental","dólar del caribe oriental"]},
    {code:"XOF",country:"África Occidental",currency:"Franco CFA de África Occidental",flag:"",aliases:["africa occidental","franco cfa de africa occidental","franco cfa de áfrica occidental","áfrica occidental"]},
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

  // Convierte un número escrito en una web al formato que se publica en pantalla:
  // COMA para decimales, sin separador de millares, máximo 2 decimales.
  //
  // Antes esto hacía raw.replace(',', '.') y devolvía eso, así que "1.716,50"
  // se publicaba como "1.716": mil setecientos dieciséis pasaba a uno coma siete.
  //
  // Reglas para decidir qué separador es el decimal:
  //  - Si aparecen los dos, manda el último ("1.716,54" español, "1,716.54" inglés).
  //  - Si solo hay coma, es decimal.
  //  - Si solo hay punto, es de millares cuando le siguen exactamente 3 cifras
  //    ("1.716"), y decimal en otro caso ("1.08"). Es ambiguo por naturaleza:
  //    "1.085" se lee como mil ochenta y cinco. Se asume que una cotización con
  //    tres decimales es menos frecuente que un millar.
  function normalizeRate(raw) {
    const s = String(raw == null ? '' : raw).trim();
    if (!/^\d[\d.,]*$/.test(s)) return null;          // solo dígitos y separadores
    const ultimaComa = s.lastIndexOf(',');
    const ultimoPunto = s.lastIndexOf('.');
    let dec = -1;
    if (ultimaComa >= 0 && ultimoPunto >= 0) dec = Math.max(ultimaComa, ultimoPunto);
    else if (ultimaComa >= 0) dec = ultimaComa;
    else if (ultimoPunto >= 0 && s.length - ultimoPunto - 1 !== 3) dec = ultimoPunto;

    const entero = (dec >= 0 ? s.slice(0, dec) : s).replace(/[.,]/g, '');
    const decimales = dec >= 0 ? s.slice(dec + 1).replace(/[.,]/g, '') : '';
    const v = parseFloat(entero + (decimales ? '.' + decimales : ''));
    if (isNaN(v) || v <= 0) return null;

    const red = Math.round(v * 100) / 100;
    return Number.isInteger(red)
      ? String(red)
      : red.toFixed(2).replace('.', ',');
  }

  // Extrae la tasa: el primer número plausible de la línea, ya normalizado.
  function extractRate(text, cur) {
    const t = text.replace(new RegExp('\\b' + cur.code + '\\b', 'gi'), ' ');
    // Se captura el número COMPLETO con sus separadores. La regex anterior
    // cortaba "1.716,50" en "1.716" y ahí nacía el error.
    const nums = t.match(/\d[\d.,]*\d|\d/g);
    if (!nums) return null;
    for (const raw of nums) {
      const val = normalizeRate(raw);
      if (val === null) continue;
      const v = parseFloat(val.replace(',', '.'));
      if (v > 100000) continue;                                  // enteros enormes: IDs
      if (/^\d{4}$/.test(raw) && v > 1900 && v < 2100) continue; // descarta años
      return val;
    }
    return null;
  }

  // ── Elección de agente en Ria ────────────────────────────────────────────
  // Ria ofrece VARIOS agentes de pago por país, cada uno con su tasa. El
  // criterio del negocio NO es "la más alta": en Colombia se recomienda
  // Davivienda (3.613,36) aunque 4-72 pague 3.645, porque 4-72 es el servicio
  // postal; y Ria Colombia se descarta por ser un servicio nuevo. Nada de eso
  // se deduce de los números, así que manda una lista de preferencias del
  // usuario y la tasa solo decide cuando esa lista no resuelve.

  function normalizeAgent(s) {
    return String(s == null ? '' : s)
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .toLowerCase().replace(/\s+/g, ' ').trim();
  }

  // Ria trunca las etiquetas ("Almacenes Ex", "Davivienda H"), así que hay que
  // emparejar en los dos sentidos: la pantalla puede quedarse corta respecto a
  // lo que escribió el usuario, o al revés.
  function agentMatches(enPantalla, preferido) {
    const a = normalizeAgent(enPantalla), b = normalizeAgent(preferido);
    if (!a || b.length < 3) return false;      // evita que "Ba" case con todo
    return a.startsWith(b) || b.startsWith(a);
  }

  function rateToNumber(r) {
    // Las tasas ya vienen normalizadas: coma decimal y sin separador de millares
    const n = parseFloat(String(r == null ? '' : r).replace(',', '.'));
    return isNaN(n) ? null : n;
  }

  /**
   * Decide qué agente ofrecer para un país.
   * @param candidatos  [{agent, rate, currency}] tal y como salen en la página
   * @param preferencias  nombres de agente en orden de preferencia
   * @param monedaLocal  código ISO de la moneda del país (COP, HNL, PYG...)
   */
  function elegirAgente(candidatos, preferencias, monedaLocal) {
    const lista = Array.isArray(candidatos) ? candidatos : [];
    const prefs = Array.isArray(preferencias) ? preferencias : [];
    const descartados = [];

    // 1. Solo la moneda local. Comparar 6.900 PYG con 1,1015 USD no significa
    //    nada: no es que uno sea mejor, es que miden cosas distintas.
    const validos = [];
    lista.forEach(c => {
      if (monedaLocal && String(c.currency).toUpperCase() !== String(monedaLocal).toUpperCase()) {
        descartados.push({ agent: c.agent, rate: c.rate, currency: c.currency, motivo: 'otra-moneda' });
      } else if (rateToNumber(c.rate) === null) {
        descartados.push({ agent: c.agent, rate: c.rate, currency: c.currency, motivo: 'tasa-ilegible' });
      } else {
        validos.push(c);
      }
    });

    if (!validos.length) return { elegido: null, motivo: 'ninguno', descartados, mejorAlternativa: null };

    // 2. El primero de la lista de preferencias que aparezca en la página.
    let elegido = null, motivo = 'sin-preferencia';
    for (const p of prefs) {
      const hit = validos.find(c => agentMatches(c.agent, p));
      if (hit) { elegido = hit; motivo = 'preferencia'; break; }
    }
    // 3. Si la lista no resuelve, entonces sí manda la tasa. Se marca como
    //    'sin-preferencia' para poder distinguir una elección del usuario de
    //    una por defecto.
    if (!elegido) {
      elegido = validos.reduce((a, b) => (rateToNumber(b.rate) > rateToNumber(a.rate) ? b : a));
    }

    // 4. Aviso informativo: ¿hay alguien que pague notablemente más?
    //    No cambia la elección; solo evita perder dinero sin enterarse.
    const mejor = validos.reduce((a, b) => (rateToNumber(b.rate) > rateToNumber(a.rate) ? b : a));
    let mejorAlternativa = null;
    if (mejor !== elegido) {
      const base = rateToNumber(elegido.rate);
      const diffPct = base > 0 ? ((rateToNumber(mejor.rate) - base) / base) * 100 : 0;
      if (diffPct > 0.5) {
        mejorAlternativa = { agent: mejor.agent, rate: mejor.rate, diffPct: Math.round(diffPct * 100) / 100 };
      }
    }

    validos.forEach(c => {
      if (c !== elegido) descartados.push({ agent: c.agent, rate: c.rate, currency: c.currency, motivo: 'no-elegido' });
    });
    return { elegido, motivo, descartados, mejorAlternativa };
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

  return { CURRENCY_DB, CODE_MAP, matchCurrency, extractRate, detectInText, scanPage,
           normalizeRate, normalizeAgent, agentMatches, elegirAgente };
})();

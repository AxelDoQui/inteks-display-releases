// SignalOS Pro — detección de divisas (compartido por content.js y sidebar.js)
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

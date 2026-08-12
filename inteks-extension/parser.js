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

  // ── Selector de país/moneda — COPIA EXACTA de FX_COUNTRIES en admin.html.
  // Igual que CURRENCY_DB arriba: la extensión no puede importar del admin,
  // así que se duplica. tests/fx-countries-sync.test.js falla si se separan.
  // Una entrada por país (y moneda): varios países comparten moneda y algunos
  // tienen dos (ej. Ecuador solo USD; Panamá PAB y también USD), por eso va en
  // su propia tabla y no mezclada con CURRENCY_DB.
  const FX_COUNTRIES = [
    {country:"Albania",flag:"al",code:"ALL"},
    {country:"Alemania",flag:"de",code:"EUR"},
    {country:"Angola",flag:"ao",code:"AOA"},
    {country:"Antigua y Barbuda",flag:"ag",code:"XCD"},
    {country:"Arabia Saudí",flag:"sa",code:"SAR"},
    {country:"Argelia",flag:"dz",code:"DZD"},
    {country:"Argentina",flag:"ar",code:"ARS"},
    {country:"Argentina",flag:"ar",code:"USD",extra:1},
    {country:"Armenia",flag:"am",code:"AMD"},
    {country:"Australia",flag:"au",code:"AUD"},
    {country:"Austria",flag:"at",code:"EUR"},
    {country:"Azerbaiyán",flag:"az",code:"AZN"},
    {country:"Bahamas",flag:"bs",code:"BSD"},
    {country:"Bangladesh",flag:"bd",code:"BDT"},
    {country:"Barbados",flag:"bb",code:"BBD"},
    {country:"Belice",flag:"bz",code:"BZD"},
    {country:"Bielorrusia",flag:"by",code:"BYN"},
    {country:"Bolivia",flag:"bo",code:"BOB"},
    {country:"Bolivia",flag:"bo",code:"USD",extra:1},
    {country:"Bosnia y Herzegovina",flag:"ba",code:"BAM"},
    {country:"Brasil",flag:"br",code:"BRL"},
    {country:"Bulgaria",flag:"bg",code:"EUR"},
    {country:"Burkina Faso",flag:"bf",code:"XOF"},
    {country:"Bélgica",flag:"be",code:"EUR"},
    {country:"Camboya",flag:"kh",code:"KHR"},
    {country:"Camerún",flag:"cm",code:"XAF"},
    {country:"Canadá",flag:"ca",code:"CAD"},
    {country:"Chequia",flag:"cz",code:"CZK"},
    {country:"Chile",flag:"cl",code:"CLP"},
    {country:"China",flag:"cn",code:"CNY"},
    {country:"Colombia",flag:"co",code:"COP"},
    {country:"Congo (Rep. Dem.)",flag:"cd",code:"CDF"},
    {country:"Corea del Sur",flag:"kr",code:"KRW"},
    {country:"Costa Rica",flag:"cr",code:"CRC"},
    {country:"Costa de Marfil",flag:"ci",code:"XOF"},
    {country:"Cuba",flag:"cu",code:"CUP"},
    {country:"Cuba",flag:"cu",code:"USD",extra:1},
    {country:"Dinamarca",flag:"dk",code:"DKK"},
    {country:"Dominica",flag:"dm",code:"XCD"},
    {country:"Ecuador",flag:"ec",code:"USD"},
    {country:"Egipto",flag:"eg",code:"EGP"},
    {country:"El Salvador",flag:"sv",code:"USD"},
    {country:"Emiratos Árabes Unidos",flag:"ae",code:"AED"},
    {country:"España",flag:"es",code:"EUR"},
    {country:"Estados Unidos",flag:"us",code:"USD"},
    {country:"Etiopía",flag:"et",code:"ETB"},
    {country:"Filipinas",flag:"ph",code:"PHP"},
    {country:"Francia",flag:"fr",code:"EUR"},
    {country:"Gambia",flag:"gm",code:"GMD"},
    {country:"Georgia",flag:"ge",code:"GEL"},
    {country:"Ghana",flag:"gh",code:"GHS"},
    {country:"Grecia",flag:"gr",code:"EUR"},
    {country:"Grenada",flag:"gd",code:"XCD"},
    {country:"Guatemala",flag:"gt",code:"GTQ"},
    {country:"Guinea",flag:"gn",code:"GNF"},
    {country:"Guyana",flag:"gy",code:"GYD"},
    {country:"Haití",flag:"ht",code:"HTG"},
    {country:"Honduras",flag:"hn",code:"HNL"},
    {country:"Hungría",flag:"hu",code:"HUF"},
    {country:"India",flag:"in",code:"INR"},
    {country:"Indonesia",flag:"id",code:"IDR"},
    {country:"Irlanda",flag:"ie",code:"EUR"},
    {country:"Israel",flag:"il",code:"ILS"},
    {country:"Italia",flag:"it",code:"EUR"},
    {country:"Jamaica",flag:"jm",code:"JMD"},
    {country:"Japón",flag:"jp",code:"JPY"},
    {country:"Jordania",flag:"jo",code:"JOD"},
    {country:"Kazajistán",flag:"kz",code:"KZT"},
    {country:"Kenia",flag:"ke",code:"KES"},
    {country:"Kirguizistán",flag:"kg",code:"KGS"},
    {country:"Líbano",flag:"lb",code:"LBP"},
    {country:"Macedonia del Norte",flag:"mk",code:"MKD"},
    {country:"Malasia",flag:"my",code:"MYR"},
    {country:"Mali",flag:"ml",code:"XOF"},
    {country:"Marruecos",flag:"ma",code:"MAD"},
    {country:"Moldavia",flag:"md",code:"MDL"},
    {country:"Mozambique",flag:"mz",code:"MZN"},
    {country:"Myanmar",flag:"mm",code:"MMK"},
    {country:"México",flag:"mx",code:"MXN"},
    {country:"Nepal",flag:"np",code:"NPR"},
    {country:"Nicaragua",flag:"ni",code:"NIO"},
    {country:"Nigeria",flag:"ng",code:"NGN"},
    {country:"Noruega",flag:"no",code:"NOK"},
    {country:"Nueva Zelanda",flag:"nz",code:"NZD"},
    {country:"Níger",flag:"ne",code:"XOF"},
    {country:"Pakistán",flag:"pk",code:"PKR"},
    {country:"Panamá",flag:"pa",code:"PAB"},
    {country:"Panamá",flag:"pa",code:"USD",extra:1},
    {country:"Paraguay",flag:"py",code:"PYG"},
    {country:"Paraguay",flag:"py",code:"USD",extra:1},
    {country:"Países Bajos",flag:"nl",code:"EUR"},
    {country:"Perú",flag:"pe",code:"PEN"},
    {country:"Perú",flag:"pe",code:"USD",extra:1},
    {country:"Polonia",flag:"pl",code:"PLN"},
    {country:"Portugal",flag:"pt",code:"EUR"},
    {country:"Reino Unido",flag:"gb",code:"GBP"},
    {country:"República Dominicana",flag:"do",code:"DOP"},
    {country:"Rumania",flag:"ro",code:"RON"},
    {country:"Rusia",flag:"ru",code:"RUB"},
    {country:"San Cristóbal y Nieves",flag:"kn",code:"XCD"},
    {country:"San Vicente y Granadinas",flag:"vc",code:"XCD"},
    {country:"Santa Lucía",flag:"lc",code:"XCD"},
    {country:"Senegal",flag:"sn",code:"XOF"},
    {country:"Serbia",flag:"rs",code:"RSD"},
    {country:"Sri Lanka",flag:"lk",code:"LKR"},
    {country:"Sudáfrica",flag:"za",code:"ZAR"},
    {country:"Suecia",flag:"se",code:"SEK"},
    {country:"Suiza",flag:"ch",code:"CHF"},
    {country:"Surinam",flag:"sr",code:"SRD"},
    {country:"Tailandia",flag:"th",code:"THB"},
    {country:"Tanzania",flag:"tz",code:"TZS"},
    {country:"Tayikistán",flag:"tj",code:"TJS"},
    {country:"Trinidad y Tobago",flag:"tt",code:"TTD"},
    {country:"Turquía",flag:"tr",code:"TRY"},
    {country:"Túnez",flag:"tn",code:"TND"},
    {country:"Ucrania",flag:"ua",code:"UAH"},
    {country:"Uganda",flag:"ug",code:"UGX"},
    {country:"Uruguay",flag:"uy",code:"UYU"},
    {country:"Uzbekistán",flag:"uz",code:"UZS"},
    {country:"Venezuela",flag:"ve",code:"VES"},
    {country:"Venezuela",flag:"ve",code:"USD",extra:1},
    {country:"Vietnam",flag:"vn",code:"VND"},
    {country:"Zimbabue",flag:"zw",code:"USD"},
  ];

  // El flag de FX_COUNTRIES es un código ISO de 2 letras (como en admin.html,
  // que lo usa para cargar /vendor/flags/{code}.svg). La extensión no empaqueta
  // esos SVG, así que aquí se convierte a su emoji equivalente -los emoji de
  // bandera son, letra a letra, "regional indicator symbols" que corresponden
  // 1 a 1 con el código ISO- en vez de mantener una segunda tabla de emojis
  // que se pueda desincronizar de FX_COUNTRIES.
  function isoToEmoji(iso) {
    iso = String(iso || "").trim().toUpperCase();
    if (iso.length !== 2 || !/^[A-Z]{2}$/.test(iso)) return "🏳";
    return String.fromCodePoint(...[...iso].map(ch => 0x1F1E6 + ch.charCodeAt(0) - 65));
  }

  // Quita acentos y pasa a minúsculas, para que "panama" encuentre "Panamá".
  // Copia de fxNormalize() en admin.html: ̀-ͯ es el bloque Unicode
  // de marcas diacríticas combinantes, escapado y no con los caracteres
  // literales, para que el patrón sobreviva a cualquier cambio de codificación.
  function fxNormalize(s) {
    return String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  }

  function fxOptionKey(o) { return `${o.flag}|${o.code}`; }

  // Opciones del selector: un país por entrada, con el nombre de su moneda
  // resuelto desde CODE_MAP. Orden alfabético por país (según localeCompare en
  // español), y con la moneda local antes que una "extra" (ej. Venezuela: VES
  // antes que USD). Copia del criterio de fxPickerOptions() en admin.html.
  function fxPickerOptions() {
    return FX_COUNTRIES.map(p => {
      const c = CODE_MAP[p.code];
      return { country: p.country, flag: p.flag, code: p.code,
               currency: (c && c.currency) || p.code, extra: p.extra || 0 };
    }).sort((a, b) => a.country.localeCompare(b.country, "es") || a.extra - b.extra || a.code.localeCompare(b.code));
  }

  // Filtra las opciones por país, moneda o código. Sin texto, las devuelve todas.
  function fxFilterOptions(options, query) {
    const q = fxNormalize(query);
    if (!q) return options;
    return options.filter(o =>
      fxNormalize(o.country).includes(q) ||
      fxNormalize(o.currency).includes(q) ||
      fxNormalize(o.code).includes(q));
  }

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

  // Busca, en un texto ya sin el código de moneda, el número que de verdad es
  // la tasa. Se recorre desde el FINAL hacia atrás: la tasa suele quedar como
  // el último número, el que estaba justo delante del código de moneda
  // ("... 3.650 COP" -> "... 3.650"). El ruido -dígitos sueltos en el nombre
  // de un agente de pago, como "4-72 Servici" en Ria, o un año en alguna
  // nota- va delante o tiene forma reconocible, y los filtros ya existentes
  // lo descartan igual. Antes se cogía el PRIMER número válido y "4-72
  // Servici 3.650 COP" devolvía "4" en vez de la tasa.
  // La usan extractRate() y extractAgent(): las dos tienen que estar de
  // acuerdo en qué número es la tasa, o el nombre del agente se cortaría en
  // el sitio equivocado.
  function findRateMatch(t) {
    const nums = Array.from(t.matchAll(/\d[\d.,]*\d|\d/g));
    for (let i = nums.length - 1; i >= 0; i--) {
      const m = nums[i];
      const val = normalizeRate(m[0]);
      if (val === null) continue;
      const v = parseFloat(val.replace(',', '.'));
      if (v > 100000) continue;                                    // enteros enormes: IDs
      if (/^\d{4}$/.test(m[0]) && v > 1900 && v < 2100) continue;  // descarta años
      return { index: m.index, raw: m[0], value: val };
    }
    return null;
  }

  // Extrae la tasa: el número plausible más cercano al código de moneda, ya
  // normalizado.
  function extractRate(text, cur) {
    const t = text.replace(new RegExp('\\b' + cur.code + '\\b', 'gi'), ' ');
    const m = findRateMatch(t);
    return m ? m.value : null;
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

  // Nombre del agente de pago antes de la tasa de la fila ("Ria Colombia
  // 3.650 COP" -> "Ria Colombia"; "4-72 Servici 3.650 COP" -> "4-72
  // Servici", sin confundir el "4" con el número de la tasa gracias a
  // findRateMatch()). Solo importa cuando una moneda tiene varias filas
  // (varios agentes, como en Ria); en una fila normal de "moneda + tasa" da
  // el nombre de la moneda, que se ignora salvo que haga falta desambiguar.
  function extractAgent(text, cur) {
    const sinMoneda = text.replace(new RegExp('\\b' + cur.code + '\\b', 'gi'), ' ');
    const m = findRateMatch(sinMoneda);
    if (!m) return null;
    const nombre = sinMoneda.slice(0, m.index).replace(/[\s.:,-]+$/, '').trim();
    return nombre || null;
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

  // Escanea la página: filas de tablas/listas/clases típicas y, si hace falta, todo el texto.
  //
  // Una moneda puede salir en VARIAS filas (Ria ofrece varios agentes de pago
  // por país). Se agrupan por código y, cuando hay más de un candidato, decide
  // elegirAgente() con la lista de preferencias del usuario para esa moneda —
  // la tasa más alta no siempre es la correcta, ver elegirAgente() arriba.
  // `preferencias` tiene forma { COP: ["Davivienda", "Bancolombia"], ... }.
  function scanPage(preferencias) {
    const prefs = preferencias || {};
    const porCodigo = {};
    const sel = 'tr, li, [class*="rate" i], [class*="currency" i], [class*="moneda" i], [class*="divisa" i], [class*="exchange" i], [class*="cambio" i], [class*="cotiz" i]';
    let els = [];
    try { els = Array.prototype.slice.call(document.querySelectorAll(sel)); }
    catch (e) { els = Array.prototype.slice.call(document.querySelectorAll('tr, li')); }
    for (const el of els) {
      const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      if (!text || text.length > 160) continue;
      const cur = matchCurrency(text);
      if (!cur) continue;
      const rate = extractRate(text, cur);
      if (rate === null) continue;
      (porCodigo[cur.code] = porCodigo[cur.code] || []).push({
        flag: cur.flag, country: cur.country, currencyName: cur.currency, code: cur.code,
        rate, agent: extractAgent(text, cur),
      });
    }
    // Fallback por líneas si encontramos pocas monedas distintas
    if (Object.keys(porCodigo).length < 2 && document.body) {
      detectInText(document.body.innerText).forEach(r => {
        if (!porCodigo[r.code]) {
          porCodigo[r.code] = [{ flag: r.flag, country: r.country, currencyName: r.currency,
                                  code: r.code, rate: r.rate, agent: null }];
        }
      });
    }
    return Object.keys(porCodigo).map(code => {
      const candidatos = porCodigo[code];
      const base = candidatos[0];
      // Caso normal: una sola fila para esta moneda. Se devuelve tal cual se
      // hacía antes, sin campos de agente que no aportarían nada.
      if (candidatos.length === 1) {
        return { flag: base.flag, country: base.country, currency: base.currencyName, code, rate: base.rate };
      }
      const paraElegir = candidatos.map(c => ({ agent: c.agent, rate: c.rate, currency: c.code }));
      const { elegido, motivo, mejorAlternativa } = elegirAgente(paraElegir, prefs[code] || [], code);
      if (!elegido) return null;
      return {
        flag: base.flag, country: base.country, currency: base.currencyName, code,
        rate: elegido.rate, agent: elegido.agent, agentMotivo: motivo, agentAlternativa: mejorAlternativa,
        // Todos los candidatos válidos de esta moneda (no solo el elegido), para
        // que el panel pueda ofrecerlos y el usuario marque su preferido con un
        // clic en vez de tener que escribir el nombre a mano.
        agentOpciones: paraElegir.map(c => ({ agent: c.agent, rate: c.rate })),
      };
    }).filter(Boolean);
  }

  return { CURRENCY_DB, CODE_MAP, matchCurrency, extractRate, extractAgent, detectInText, scanPage,
           normalizeRate, normalizeAgent, agentMatches, elegirAgente,
           FX_COUNTRIES, isoToEmoji, fxNormalize, fxOptionKey, fxPickerOptions, fxFilterOptions };
})();

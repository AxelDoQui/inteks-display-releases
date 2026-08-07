"""
Genera los bloques CURRENCY_DB y FX_COUNTRIES para admin.html a partir del
dataset mledoze/countries, acotado a los corredores de remesas.

Separa a propósito dos tablas:
  CURRENCY_DB  -> una entrada por MONEDA. Alimenta CODE_MAP, que usa el OCR.
                  El euro lo comparten 38 países: si hubiera una entrada por
                  país, CODE_MAP["EUR"] apuntaría a uno cualquiera.
  FX_COUNTRIES -> una entrada por PAÍS. Alimenta el selector del admin.

Salida: bloques JS listos para pegar + la lista de banderas a descargar.
"""
import json, sys, urllib.request, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATASET = "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"

# ── Corredores de remesas, por ISO-3166 alfa-2 ─────────────────────────────
LATAM = "MX GT HN SV NI CR PA CU DO HT JM TT BZ CO VE EC PE BO CL AR UY PY BR GY SR BB BS AG DM LC VC GD KN".split()
AFRICA = "MA DZ TN EG SN CI ML BF NE GH NG CM CD KE UG TZ ET ZA ZW MZ AO GM GN".split()
ASIA = "IN PK BD LK NP PH VN ID TH MY CN KH MM JO LB AE SA IL".split()
ESTE = "RO BG UA MD RS AL BA MK GE AM AZ UZ KG TJ KZ TR RU BY".split()
OESTE = "ES PT FR IT DE GB IE NL BE CH SE NO DK AT GR PL CZ HU US CA AU NZ JP KR".split()
PAISES = LATAM + AFRICA + ASIA + ESTE + OESTE

# ── Nombres de moneda en español (el dataset los trae en inglés) ───────────
MONEDA_ES = {
    "USD": "Dólar estadounidense", "EUR": "Euro", "GBP": "Libra esterlina",
    "CHF": "Franco suizo", "JPY": "Yen japonés", "CNY": "Yuan chino",
    "CAD": "Dólar canadiense", "AUD": "Dólar australiano", "NZD": "Dólar neozelandés",
    "SEK": "Corona sueca", "NOK": "Corona noruega", "DKK": "Corona danesa",
    "CZK": "Corona checa", "HUF": "Forinto húngaro", "PLN": "Esloti polaco",
    "RON": "Leu rumano", "BGN": "Lev búlgaro", "UAH": "Grivna ucraniana",
    "MDL": "Leu moldavo", "RSD": "Dinar serbio", "ALL": "Lek albanés",
    "BAM": "Marco convertible", "MKD": "Denar macedonio", "GEL": "Lari georgiano",
    "AMD": "Dram armenio", "AZN": "Manat azerbaiyano", "UZS": "Sum uzbeko",
    "KGS": "Som kirguís", "TJS": "Somoni tayiko", "KZT": "Tenge kazajo",
    "TRY": "Lira turca", "RUB": "Rublo ruso", "BYN": "Rublo bielorruso",
    "MXN": "Peso mexicano", "GTQ": "Quetzal guatemalteco", "HNL": "Lempira hondureño",
    "NIO": "Córdoba nicaragüense", "CRC": "Colón costarricense", "PAB": "Balboa panameño",
    "CUP": "Peso cubano", "DOP": "Peso dominicano", "HTG": "Gourde haitiano",
    "JMD": "Dólar jamaicano", "TTD": "Dólar trinitense", "BZD": "Dólar beliceño",
    "COP": "Peso colombiano", "VES": "Bolívar venezolano", "PEN": "Sol peruano",
    "BOB": "Boliviano", "CLP": "Peso chileno", "ARS": "Peso argentino",
    "UYU": "Peso uruguayo", "PYG": "Guaraní paraguayo", "BRL": "Real brasileño",
    "GYD": "Dólar guyanés", "SRD": "Dólar surinamés", "BBD": "Dólar de Barbados",
    "BSD": "Dólar bahameño", "XCD": "Dólar del Caribe Oriental",
    "MAD": "Dírham marroquí", "DZD": "Dinar argelino", "TND": "Dinar tunecino",
    "EGP": "Libra egipcia", "XOF": "Franco CFA de África Occidental",
    "XAF": "Franco CFA de África Central", "GHS": "Cedi ghanés",
    "NGN": "Naira nigeriana", "CDF": "Franco congoleño", "KES": "Chelín keniano",
    "UGX": "Chelín ugandés", "TZS": "Chelín tanzano", "ETB": "Birr etíope",
    "ZAR": "Rand sudafricano", "ZWL": "Dólar zimbabuense", "MZN": "Metical mozambiqueño",
    "AOA": "Kwanza angoleño", "GMD": "Dalasi gambiano", "GNF": "Franco guineano",
    "INR": "Rupia india", "PKR": "Rupia pakistaní", "BDT": "Taka bangladesí",
    "LKR": "Rupia esrilanquesa", "NPR": "Rupia nepalí", "PHP": "Peso filipino",
    "VND": "Dong vietnamita", "IDR": "Rupia indonesia", "THB": "Baht tailandés",
    "MYR": "Ringgit malayo", "KHR": "Riel camboyano", "MMK": "Kyat birmano",
    "JOD": "Dinar jordano", "LBP": "Libra libanesa", "AED": "Dírham emiratí",
    "SAR": "Riyal saudí", "ILS": "Séquel israelí", "KRW": "Won surcoreano",
    "BWP": "Pula de Botsuana", "CUC": "Peso cubano convertible",
}

# Para las monedas COMPARTIDAS, qué país representa a la moneda en CURRENCY_DB.
# Sin esto, el "país" de una moneda sería el primero de mi lista que la use, y
# el OCR etiquetaría como El Salvador cualquier dólar que detectase.
# (nombre, emoji o "" si no hay bandera de país que la represente)
CANONICO = {
    "USD": ("Estados Unidos", "US"),
    "EUR": ("Zona Euro", "EU"),
    "XCD": ("Caribe Oriental", ""),
    "XOF": ("África Occidental", ""),
    "XAF": ("África Central", ""),
}

# El dataset guarda las monedas en un diccionario y coger "la primera" depende
# del orden del JSON. En los países con varias hay que decidir explícitamente.
MONEDA_PREFERIDA = {
    "CU": "CUP",   # el CUC se retiró en 2021
    "ZW": "USD",   # Zimbabue opera de facto en dólares
    "PA": "PAB",   # el dólar se añade aparte como segunda moneda
    "SV": "USD",
    "EC": "USD",
}

# Emoji de bandera desde el ISO-2, para mantener el formato de CURRENCY_DB
def emoji(iso):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in iso.upper())

def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')

def alias(nombre):
    """Alias sencillos para el OCR: el nombre en minúsculas y sin tildes."""
    import unicodedata
    n = nombre.lower()
    sin = "".join(c for c in unicodedata.normalize("NFD", n)
                  if unicodedata.category(c) != "Mn")
    return sorted({n, sin} - {""})

# Países donde circula el dólar además de su moneda local.
DOBLE_USD = "VE AR CU BO PE PY PA".split()

ADMIN = r"c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\admin.html"

def entradas_existentes():
    """Líneas de CURRENCY_DB que ya están en admin.html, indexadas por código.
    Se conservan TAL CUAL: sus alias están afinados a mano y los usa el OCR."""
    import re
    s = open(ADMIN, encoding="utf-8").read()
    blk = s[s.index("const CURRENCY_DB = ["):s.index("const CODE_MAP")]
    out = {}
    for line in blk.splitlines():
        line = line.strip().rstrip(",")
        m = re.match(r'\{code:"([A-Z]{3})"', line)
        if m:
            out[m.group(1)] = line
    return out

def main():
    req = urllib.request.Request(DATASET, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=60).read())
    por_iso = {c["cca2"]: c for c in data if c.get("cca2")}
    previas = entradas_existentes()

    faltan_pais, faltan_moneda = [], set()
    monedas = {}     # code -> {country_ref, currency_es}
    paises = []      # {country, iso, code}

    for iso in PAISES:
        c = por_iso.get(iso)
        if not c:
            faltan_pais.append(iso); continue
        nombre = c.get("translations", {}).get("spa", {}).get("common") or c["name"]["common"]
        curs = list((c.get("currencies") or {}).keys())
        if not curs:
            faltan_pais.append(iso + " (sin moneda)"); continue
        code = MONEDA_PREFERIDA.get(iso) or curs[0]
        if code not in MONEDA_ES:
            faltan_moneda.add(f'{code} ({c.get("currencies")[code]["name"]})')
            continue
        monedas.setdefault(code, {"country": nombre, "iso": iso})
        paises.append({"country": nombre, "iso": iso.lower(), "code": code})

    if faltan_pais:
        print("// AVISO paises no resueltos:", faltan_pais, file=sys.stderr)
    if faltan_moneda:
        print("// AVISO monedas sin traducir:", sorted(faltan_moneda), file=sys.stderr)

    # Segunda moneda: países con circulación de dólar
    for iso in DOBLE_USD:
        c = por_iso.get(iso)
        if not c: continue
        nombre = c.get("translations", {}).get("spa", {}).get("common") or c["name"]["common"]
        if not any(p["country"] == nombre and p["code"] == "USD" for p in paises):
            paises.append({"country": nombre, "iso": iso.lower(), "code": "USD", "extra": 1})

    paises.sort(key=lambda p: (p["country"], p.get("extra", 0), p["code"]))

    nuevas, conservadas = [], []
    for code in sorted(monedas):
        if code in previas:
            conservadas.append("  " + previas[code] + ",")
            continue
        m = monedas[code]
        nombre_pais, iso_flag = CANONICO.get(code, (m["country"], m["iso"]))
        bandera = emoji(iso_flag) if iso_flag else ""
        al = sorted(set(alias(MONEDA_ES[code]) + alias(nombre_pais)))
        nuevas.append(f'  {{code:"{code}",country:"{esc(nombre_pais)}",'
                      f'currency:"{esc(MONEDA_ES[code])}",flag:"{bandera}",'
                      f'aliases:[{",".join(chr(34)+esc(a)+chr(34) for a in al)}]}},')

    out = []
    out.append("// ── MONEDAS: una entrada por moneda. Alimenta CODE_MAP, que usa el OCR.")
    out.append("//    El euro lo comparten decenas de países: aquí NO puede haber una")
    out.append("//    entrada por país o CODE_MAP apuntaría a uno cualquiera de ellos.")
    out.append("//    Las entradas anteriores se conservan tal cual: sus alias están")
    out.append("//    afinados a mano y son los que hacen funcionar la detección.")
    out.append("const CURRENCY_DB = [")
    out.extend(conservadas)
    out.extend(nuevas)
    out.append("];")
    out.append("")
    out.append("// ── PAÍSES: una entrada por país (y moneda). Alimenta el selector.")
    out.append("//    Varios países comparten moneda y algunos tienen dos, por eso")
    out.append("//    van en su propia tabla y no mezclados con las monedas.")
    out.append("const FX_COUNTRIES = [")
    for p in paises:
        # extra:1 marca una segunda moneda del país, para ordenarla tras la local
        ex = ",extra:1" if p.get("extra") else ""
        out.append(f'  {{country:"{esc(p["country"])}",flag:"{p["iso"]}",code:"{p["code"]}"{ex}}},')
    out.append("];")

    print("\n".join(out))
    print(f"// conservadas: {len(conservadas)}  nuevas: {len(nuevas)}  "
          f"total monedas: {len(conservadas)+len(nuevas)}  paises: {len(paises)}", file=sys.stderr)
    with open("flags_needed.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(sorted({p["iso"] for p in paises})))

main()

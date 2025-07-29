import math
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import Dict, Optional

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (LOCATIONIQ_TOKEN, RESTAURANT_LAT, RESTAURANT_LON, max_lat,
                    max_lon, min_lat, min_lon)

# --- Normalización de abreviaturas comunes en Colombia ---
_ABBR = [
    (r"\bcl\b\.?", "calle"),
    (r"\bcal\b\.?", "calle"),
    (r"\bcra\b\.?", "carrera"),
    (r"\bcr\b\.?", "carrera"),
    (r"\bkr\b\.?", "carrera"),
    (r"\bk\b\.?", "carrera"),
    (r"\bav\b\.?", "avenida"),
    (r"\bavda\b\.?", "avenida"),
    (r"\bdg\b\.?", "diagonal"),
    (r"\bdiag\b\.?", "diagonal"),
    (r"\btv\b\.?", "transversal"),
    (r"\btransv\b\.?", "transversal"),
    (r"\btrv\b\.?", "transversal"),
    (r"\baut\b\.?", "autopista"),
    (r"\bn[º°o]\b\.?", "#"),    # n°, nº, no -> #
    (r"\bnum\b\.?", "#"),
]

# Complementos (unidad) que NO deben ir a 'street' para el geocoder
_COMPLEMENTS = {
    "interior": r"(?:int\.?|interior)",
    "torre": r"(?:torre|tor\.?)",
    "apto": r"(?:apto\.?|apt\.?|apartamento)",
    "manzana": r"(?:manzana|mz\.?)",
    "casa": r"(?:casa)",
    "bloque": r"(?:bloque|blq\.?|bloq\.?)",
    "lote": r"(?:lote|lt\.?)",
    "oficina": r"(?:oficina|of\.?)",
    "piso": r"(?:piso|ps\.?)",
    # agrega "local", "bodega", etc. si los necesitas
}

# patrón de vía principal + numeración
# Ejemplos que cubre:
#   Calle 127A Bis Sur # 11B - 76
#   Carrera 7 # 123-45
#   Avenida 23 #78-90
#   Diagonal 62 sur # 15C-30
#   Transversal 25B No 61-30
_STREET_RE = re.compile(
    r"""
    (?P<type>calle|carrera|avenida|diagonal|transversal|autopista)\s+
    (?P<num>\d+[A-Za-z]?)                    # 123 o 123A
    (?:\s*(?P<bis>bis))?                     # 'bis' opcional
    (?:\s*(?P<sector>sur|norte|este|oeste))? # sector opcional
    (?:\s*(?:\#|n[ºo°]|no\.?)\s*             # <- \# ESCAPADO en modo VERBOSE
        (?P<sec>\d+[A-Za-z]?)                # 11 o 11B
        \s*-\s*
        (?P<ter>\d+[A-Za-z]?)                # 76 o 76A
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)

@dataclass
class AddressParts:
    raw: str
    street_type: Optional[str] = None
    street_number: Optional[str] = None
    bis: bool = False
    sector: Optional[str] = None           # sur/norte/este/oeste
    secondary: Optional[str] = None        # número después de #
    tertiary: Optional[str] = None         # número después del guion
    complements: Dict[str, str] = None     # interior/torre/apto/...

    def street_for_geocoder(self) -> Optional[str]:
        """Crea 'Calle 123 # 45-67' (sin complementos)."""
        if not self.street_type or not self.street_number:
            return None
        parts = [self.street_type.title(), self.street_number.upper()]
        if self.bis:
            parts.append("Bis")
        if self.sector:
            parts.append(self.sector.title())
        s = " ".join(parts)
        if self.secondary:
            s += f" # {self.secondary.upper()}"
            if self.tertiary:
                s += f"-{self.tertiary.upper()}"
        return s

def _normalize_text(s: str) -> str:
    s = s.strip()
    # normaliza separadores
    s = re.sub(r"[,\s]+", " ", s)      # colapsa espacios y comas
    # aplica abreviaturas
    for pat, rep in _ABBR:
        s = re.sub(pat, rep, s, flags=re.IGNORECASE)
    return s

def _extract_complements(s: str) -> (Dict[str, str], str):
    """Extrae complementos definidos en _COMPLEMENTS y devuelve (dict, resto_sin_complementos)."""
    comps = {}
    rest = s
    for key, pat in _COMPLEMENTS.items():
        # busca "clave valor" (p. ej. 'torre 9', 'apto 1001')
        regex = re.compile(rf"\b{pat}\s+([A-Za-z0-9\-]+)", re.IGNORECASE)
        while True:
            m = regex.search(rest)
            if not m:
                break
            value = m.group(1).strip().upper()
            comps[key] = value
            # elimina esa porción del string para no afectar otros match
            start, end = m.span()
            rest = (rest[:start] + " ").strip() + " " + rest[end:].strip()
            rest = re.sub(r"\s{2,}", " ", rest).strip()
    return comps, rest

def parse_colombian_address(address: str) -> AddressParts:
    norm = _normalize_text(address)
    # 1) extrae complementos (interior/torre/apto/etc.)
    complements, base = _extract_complements(norm)

    # 2) busca vía + numeración
    m = _STREET_RE.search(base)
    ap = AddressParts(raw=address, complements=complements or {})
    if not m:
        # no encontró patrón de vía; deja solo complementos
        return ap

    ap.street_type = m.group("type").lower()
    ap.street_number = m.group("num").upper()
    ap.bis = bool(m.group("bis"))
    ap.sector = (m.group("sector") or "").lower() or None
    ap.secondary = (m.group("sec") or "").upper() or None
    ap.tertiary = (m.group("ter") or "").upper() or None
    return ap


class DistanceCalculator:
    def __init__(self):
        self.restaurant_lat = RESTAURANT_LAT
        self.restaurant_lon = RESTAURANT_LON
        self.BASE = "https://us1.locationiq.com/v1/search"


    def get_coordinates(self, address, limit=1):
        params = {
            "key": LOCATIONIQ_TOKEN,
            "q": address,                 # e.g. "Prado Alto Bogota" o "Calle 127a #11b-76, Bogotá"
            "limit": limit,
            "format": "json",             # <- CLAVE para recibir JSON
            "countrycodes": "co",         # restringe a Colombia
            "accept-language": "es",      # salida en español (si hay datos en ese idioma)
            "viewbox": f"{max_lon},{max_lat},{min_lon},{min_lat}"
        }
        r = requests.get(self.BASE, params=params, timeout=10)
        # Útil al depurar si algo no cuadra:
        # print(r.status_code, r.headers.get("content-type"), r.text[:200])
        r.raise_for_status()
        data = r.json()                   # ahora sí es JSON
        if not data:
            raise ValueError("Sin resultados para esa dirección")
        print(data)
        return float(data[0]["lat"]), float(data[0]["lon"])



    def calculate_straight_distance(self, lat1, lon1, lat2=None, lon2=None):
        if lat2 is None:
            lat2 = self.restaurant_lat
        if lon2 is None:
            lon2 = self.restaurant_lon
            
        R = 6_371_000
        φm = math.radians((lat1 + lat2) / 2.0)
        x = math.radians(lon2 - lon1) * math.cos(φm)
        y = math.radians(lat2 - lat1)
        return R * math.hypot(x, y)
    

    def calculate_driving_distance(self, lat, lon):
        url = f"https://us1.locationiq.com/v1/directions/driving/{lon},{lat};{self.restaurant_lon},{self.restaurant_lat}?key={LOCATIONIQ_TOKEN}"
        headers = {"accept": "application/json"}
        response = requests.get(url, headers=headers)
        data = response.json()
        return data['routes'][0]['distance']
    
    def calculate_delivery_fee(self, address):
        parts = parse_colombian_address(address)
        lat, lon = self.get_coordinates(parts.street_for_geocoder())
        distance = self.calculate_driving_distance(lat, lon)
        if distance < 1000:
            return 10000
        elif distance < 2000:
            return 15000
        elif distance < 3000:
            return 20000
        else:
            return -1
            

if __name__ == "__main__":
    calculator = DistanceCalculator()
    lat, long = calculator.get_coordinates("Prado Alto")
    distance = calculator.calculate_straight_distance(lat, long)
    print(distance)









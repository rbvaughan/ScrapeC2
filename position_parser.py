import re
from typing import Optional, Tuple

def parse_position(text: str) -> Optional[Tuple[float, float, Optional[float]]]:
    text = text.strip()

    def dms_to_dd(degrees, minutes, seconds, direction):
        dd = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
        if direction.upper() in ['S', 'W']:
            dd *= -1
        return dd

    def dmm_to_dd(degrees, minutes, direction):
        dd = float(degrees) + float(minutes) / 60
        if direction.upper() in ['S', 'W']:
            dd *= -1
        return dd

    # Normalize whitespace and punctuation
    text = re.sub(r'[\t\n\r]+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)

    # Compact +Lat-Lon+Alt
    m = re.search(r'[+](\d+\.\d+)[-](\d+\.\d+)[+](\d+\.\d+)', text)
    if m:
        return float(m[1]), -float(m[2]), float(m[3])

    # Geo URI
    m = re.search(r'geo:([+-]?\d+\.\d+),([+-]?\d+\.\d+),([+-]?\d+\.?\d*)', text)
    if m:
        return float(m[1]), float(m[2]), float(m[3])

    # ISO 6709 format +34.0522-118.2437+0050/ or +34.0522-118.2437/
    m = re.search(r'\+([0-9]+\.?[0-9]*)\-([0-9]+\.?[0-9]*)(?:\+([0-9]+\.?[0-9]*))?/+', text)
    if m:
        lat = float(m[1])
        lon = -float(m[2])
        alt = float(m[3]) if m[3] else None
        return lat, lon, alt

    # JSON or KV format
    m = re.search(r'"?lat"?[:=]\s*([+-]?\d+\.\d+).*?"?lon"?[:=]\s*([+-]?\d+\.\d+).*?"?alt"?[:=]\s*([+-]?\d+\.?\d*)',
                  text, re.I | re.S)
    if m:
        return float(m[1]), float(m[2]), float(m[3])

    # GPX style
    m = re.search(r'lat=["\']([+-]?\d+\.\d+)["\']\s+lon=["\']([+-]?\d+\.\d+)["\'].*?<ele>([+-]?\d+\.?\d*)<', text, re.I)
    if m:
        return float(m[1]), float(m[2]), float(m[3])

    # KML <coordinates>
    m = re.search(r'<coordinates>\s*([+-]?\d+\.\d+),([+-]?\d+\.\d+),?([+-]?\d*\.?\d*)\s*</coordinates>', text, re.I)
    if m:
        lat = float(m[2])
        lon = float(m[1])
        alt = float(m[3]) if m[3] else None
        return lat, lon, alt

    # NMEA: 4807.038,N,01131.000,E,234
    m = re.search(r'(\d{2})(\d{2}\.\d+),(N|S),\s*(\d{3})(\d{2}\.\d+),(E|W)(?:,\s*(\d+\.?\d*))?', text)
    if m:
        lat = float(m[1]) + float(m[2]) / 60
        if m[3].upper() == 'S':
            lat *= -1
        lon = float(m[4]) + float(m[5]) / 60
        if m[6].upper() == 'W':
            lon *= -1
        alt = float(m[7]) if m[7] else None
        return lat, lon, alt

    # Decimal Degrees
    m = re.search(r'([+-]?\d+\.\d+)\s*[;,]\s*([+-]?\d+\.\d+)', text)
    if m:
        return float(m[1]), float(m[2]), None

    # Suffix notation (DD with NSWE letters)
    m = re.search(r'([+-]?\d+\.\d+)[\u00B0\s]*([NS])\s*([+-]?\d+\.\d+)[\u00B0\s]*([EW])', text, re.I)
    if m:
        lat = float(m[1]) * (-1 if m[2].upper() == 'S' else 1)
        lon = float(m[3]) * (-1 if m[4].upper() == 'W' else 1)
        return lat, lon, None

    # DMS (Degrees Minutes Seconds)
    m = re.search(r'''
        (\d{1,3})[ \u00B0:](\d{1,2})[ '\u2032′](\d{1,2}(?:\.\d+)?)[ \"\u2033″]?([NS])[^\d]*
        (\d{1,3})[ \u00B0:](\d{1,2})[ '\u2032′](\d{1,2}(?:\.\d+)?)[ \"\u2033″]?([EW])
        ''', text, re.I | re.VERBOSE)
    if m:
        lat = dms_to_dd(m[1], m[2], m[3], m[4])
        lon = dms_to_dd(m[5], m[6], m[7], m[8])
        alt_m = re.search(r'alt\s*(\d+\.?\d*)', text, re.I)
        alt = float(alt_m[1]) if alt_m else None
        return lat, lon, alt

    # DMM (Degrees Decimal Minutes)
    m = re.search(r'''
        (\d{1,3})[ \u00B0:](\d{1,2}\.\d+)[ '\u2032′]?\s*([NS]),?[^\d]*
        (\d{1,3})[ \u00B0:](\d{1,2}\.\d+)[ '\u2032′]?\s*([EW])
        ''', text, re.I | re.VERBOSE)
    if m:
        lat = dmm_to_dd(m[1], m[2], m[3])
        lon = dmm_to_dd(m[4], m[5], m[6])
        return lat, lon, None

    return None

# (optional) keep the old name for backward-compat
parse_gps = parse_position

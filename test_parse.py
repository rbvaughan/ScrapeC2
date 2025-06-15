import unittest
from position_parser import parse_position
from math import isclose

class TestGPSParser(unittest.TestCase):
    def assertGpsEqual(self, actual, expected, msg=""):
        self.assertIsNotNone(actual, f"{msg} → Expected non-None result")
        lat1, lon1, alt1 = actual
        lat2, lon2, alt2 = expected
        self.assertTrue(isclose(lat1, lat2, abs_tol=1e-5), f"{msg} → Latitude mismatch")
        self.assertTrue(isclose(lon1, lon2, abs_tol=1e-5), f"{msg} → Longitude mismatch")
        if alt1 is not None and alt2 is not None:
            self.assertTrue(isclose(alt1, alt2, abs_tol=0.1), f"{msg} → Altitude mismatch")
        else:
            self.assertEqual(alt1, alt2, f"{msg} → Altitude presence mismatch")

    def test_decimal_degrees(self):
        self.assertGpsEqual(parse_position("34.052235, -118.243683"), (34.052235, -118.243683, None), "Decimal Degrees")

    def test_kv_json(self):
        self.assertGpsEqual(parse_position('{"lat": 34.052235, "lon": -118.243683, "alt": 89.2}'),
                            (34.052235, -118.243683, 89.2), "JSON-style KV")

    def test_dms_spaces(self):
        self.assertGpsEqual(parse_position('34 03 08.05 N 118 14 37.26 W'),
                            (34.052236, -118.243683, None), "DMS with spaces")

    def test_dmm(self):
        self.assertGpsEqual(parse_position("34 03.132 N, 118 14.621 W"),
                            (34.0522, -118.243683, None), "DMM no altitude")

    def test_dms(self):
        self.assertGpsEqual(parse_position("34 3 08.05 N, 118 14 37.26 W alt 92"),
                            (34.052236, -118.243683, 92), "DMS with altitude")

    def test_suffix_notation(self):
        self.assertGpsEqual(parse_position("34.052235 N 118.243683 W"),
                            (34.052235, -118.243683, None), "Suffix Notation")

    def test_compact(self):
        self.assertGpsEqual(parse_position("+34.052235-118.243683+89.2"),
                            (34.052235, -118.243683, 89.2), "Compact +Lat-Lon+Alt")

    def test_geo_uri(self):
        self.assertGpsEqual(parse_position("geo:34.052235,-118.243683,89.2"),
                            (34.052235, -118.243683, 89.2), "Geo URI")

    def test_kml(self):
        self.assertGpsEqual(parse_position("<coordinates>-118.243683,34.052235,89.2</coordinates>"),
                            (34.052235, -118.243683, 89.2), "KML coordinates")

    def test_gpx(self):
        self.assertGpsEqual(parse_position('lat="34.052235" lon="-118.243683" <ele>89.2</ele>'),
                            (34.052235, -118.243683, 89.2), "GPX lat/lon/ele")

    def test_nmea(self):
        self.assertGpsEqual(parse_position("4807.038,N,01131.000,E,234"),
                            (48.1173, 11.5166667, 234), "NMEA format")

    def test_noise_handling(self):
        self.assertGpsEqual(parse_position("RANDOM <coordinates>-118.243683,34.052235,89.2</coordinates> JUNK"),
                            (34.052235, -118.243683, 89.2), "KML with noise")

    def test_iso_6709(self):
        self.assertGpsEqual(parse_position("+34.0522-118.2437+050.0/"),
                            (34.0522, -118.2437, 50.0), "ISO 6709 with altitude")

    def test_iso_6709_no_alt(self):
        self.assertGpsEqual(parse_position("+34.0522-118.2437/"),
                            (34.0522, -118.2437, None), "ISO 6709 without altitude")

if __name__ == '__main__':
    unittest.main()

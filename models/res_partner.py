import logging
import re
from urllib.parse import unquote

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

NUM = r'(-?\d{1,3}(?:\.\d+)?)'
# Most precise first: the place pin (!3d..!4d..), then a query, then the map centre (@lat,lng).
COORD_PATTERNS = [
    re.compile(r'!3d' + NUM + r'!4d' + NUM),
    re.compile(r'[?&](?:q|query|ll|sll|center|destination|daddr)=(?:loc:)?' + NUM + r'\s*,\s*\+?' + NUM),
    re.compile(r'/(?:place|search|dir/[^/]*)/' + NUM + r'\s*,\s*\+?' + NUM),
    re.compile(r'@' + NUM + r',' + NUM),
    re.compile(r'^\s*' + NUM + r'\s*,\s*' + NUM + r'\s*$'),
]
SHORT_LINK = re.compile(r'^https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|g\.co/kgs)/', re.I)


def parse_coordinates(text):
    """(latitude, longitude) found in a Google Maps link or a "lat, long" text, or None."""
    if not text:
        return None
    text = unquote(text.strip())
    for pattern in COORD_PATTERNS:
        match = pattern.search(text)
        if match:
            lat, lng = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180 and (lat or lng):
                return lat, lng
    return None


OLC_ALPHABET = '23456789CFGHJMPQRVWX'
# Plus code, full (8FVC9G8F+6X) or short (H5F3+QV6), optionally followed by a locality.
PLUS_CODE = re.compile(r'(?<![0-9A-Z])([' + OLC_ALPHABET + r']{2,8}\+[' + OLC_ALPHABET + r']{0,3})(?![0-9A-Z])',
                       re.I)


def _olc_decode(code):
    """Centre (lat, lng) of a full Open Location Code (8 digits + '+' + 0-3 digits)."""
    digits = code.replace('+', '').upper()
    lat = lng = 0.0
    value = 20.0
    for i in range(0, min(len(digits), 10), 2):
        lat += OLC_ALPHABET.index(digits[i]) * value
        lng += OLC_ALPHABET.index(digits[i + 1]) * value
        value /= 20
    lat_size = lng_size = value * 20
    if len(digits) > 10:  # grid refinement: 5 rows x 4 columns
        idx = OLC_ALPHABET.index(digits[10])
        lat_size, lng_size = lat_size / 5, lng_size / 4
        lat += (idx // 4) * lat_size
        lng += (idx % 4) * lng_size
    return lat - 90 + lat_size / 2, lng - 180 + lng_size / 2


def _olc_encode_prefix(lat, lng, length):
    """First `length` digits of the plus code of (lat, lng)."""
    lat = min(max(lat, -90), 89.9999999) + 90
    lng = ((lng + 180) % 360)
    out = ''
    value = 20.0
    while len(out) < length:
        d_lat, d_lng = int(lat // value), int(lng // value)
        out += OLC_ALPHABET[d_lat] + OLC_ALPHABET[d_lng]
        lat -= d_lat * value
        lng -= d_lng * value
        value /= 20
    return out[:length]


def plus_code_to_coordinates(code, reference=None):
    """(lat, lng) of a plus code. A short code needs a reference point near it (same city)."""
    code = code.upper()
    padding = 8 - code.index('+')
    if padding <= 0:
        return _olc_decode(code)
    if not reference:
        return None
    ref_lat, ref_lng = reference
    full = _olc_encode_prefix(ref_lat, ref_lng, padding) + code
    lat, lng = _olc_decode(full)
    resolution = 20.0 ** (2 - padding / 2)
    half = resolution / 2
    # Nearest match to the reference (the code may lie in the neighbouring cell).
    if ref_lat + half < lat and lat - resolution >= -90:
        lat -= resolution
    elif ref_lat - half > lat and lat + resolution <= 90:
        lat += resolution
    if ref_lng + half < lng:
        lng -= resolution
    elif ref_lng - half > lng:
        lng += resolution
    return lat, lng


def resolve_short_link(url):
    """All the URLs the short link redirects through (Google may end on a consent page)."""
    try:
        response = requests.get(url, allow_redirects=True, timeout=6,
                                headers={'User-Agent': 'Mozilla/5.0 (Odoo partner location)'})
        return [r.url for r in response.history] + [response.url]
    except requests.RequestException as e:
        _logger.info('Cannot resolve Google Maps short link %s: %s', url, e)
        return [url]


def coordinates_from_link(link, geocode=None):
    """(lat, lng) from a Google Maps link, "lat, long" or a plus code.
    `geocode(text)` gives a reference point for a short plus code ("H5F3+QV6 Jeddah")."""
    if not link:
        return None
    link = link.strip()
    candidates = [link]
    if SHORT_LINK.match(link):
        candidates = resolve_short_link(link) + candidates
    for text in candidates:
        coordinates = parse_coordinates(text)
        if coordinates:
            return coordinates
    for text in candidates:
        text = unquote(unquote(text)).replace('+', ' ') if text.startswith('http') else text
        # in a URL the '+' of the plus code became a space: put it back
        match = PLUS_CODE.search(re.sub(r'(?<=[' + OLC_ALPHABET + r']{4}) (?=[' + OLC_ALPHABET + r']{2,3}\b)',
                                        '+', text, flags=re.I))
        if not match:
            continue
        code = match.group(1)
        reference = None
        if code.index('+') < 8 and geocode:
            rest = re.split(r'[&#]', text[match.end():])[0]
            parts = [p.strip() for p in rest.split(',') if p.strip()]
            # most precise locality first: "Ar Rawdah, Jeddah 23435", then "Jeddah 23435"
            for i in range(max(len(parts) - 2, 0), len(parts)):
                reference = geocode(', '.join(parts[i:]))
                if reference:
                    break
        coordinates = plus_code_to_coordinates(code, reference)
        if coordinates:
            return coordinates
    return None


class ResPartner(models.Model):
    _inherit = 'res.partner'

    location_url = fields.Char(
        string='Location (Google Maps)',
        help='Paste the Google Maps share link of the customer location, or "latitude, longitude".')

    def _location_geocode(self, text):
        try:
            return self.env['base.geocoder'].geo_find(text)
        except Exception as e:  # noqa: BLE001 - geocoding is a best effort
            _logger.info('Geocoding of %s failed: %s', text, e)
            return None

    def _location_values(self, link):
        coordinates = coordinates_from_link(link, geocode=self._location_geocode)
        if not coordinates:
            return {}
        return {'partner_latitude': coordinates[0], 'partner_longitude': coordinates[1],
                'date_localization': fields.Date.context_today(self)}

    @api.onchange('location_url')
    def _onchange_location_url(self):
        values = self._location_values(self.location_url)
        if values:
            self.update(values)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('location_url') and 'partner_latitude' not in vals:
                vals.update(self._location_values(vals['location_url']))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('location_url') and 'partner_latitude' not in vals:
            vals = dict(vals, **self._location_values(vals['location_url']))
        return super().write(vals)

    def geo_localize(self):
        """The "Compute" button of the Geolocation section: the Google Maps link first, then the address."""
        from_address = self.env['res.partner']
        for partner in self:
            values = partner._location_values(partner.location_url) if partner.location_url else {}
            if values:
                partner.write(values)
            else:
                from_address |= partner
        if from_address:
            return super(ResPartner, from_address).geo_localize()
        return True

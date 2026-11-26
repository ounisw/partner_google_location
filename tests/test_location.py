from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.partner_google_location.models.res_partner import parse_coordinates, plus_code_to_coordinates


@tagged('post_install', '-at_install')
class TestPartnerLocation(TransactionCase):

    def test_parse_links(self):
        cases = {
            'https://www.google.com/maps/place/Jeddah/@21.4858,39.1925,12z/data=!3m1!4b1!4m6!3m5!1s0x15c3!8m2!3d21.5433!4d39.1728': (21.5433, 39.1728),
            'https://www.google.com/maps/@21.4858,39.1925,15z': (21.4858, 39.1925),
            'https://www.google.com/maps?q=21.5433,39.1728': (21.5433, 39.1728),
            'https://maps.google.com/?q=21.5433%2C39.1728': (21.5433, 39.1728),
            'https://www.google.com/maps/search/21.5433,+39.1728': (21.5433, 39.1728),
            '21.5433, 39.1728': (21.5433, 39.1728),
            'https://www.google.com/maps/place/Jeddah': None,
            'not a link': None,
        }
        for text, expected in cases.items():
            self.assertEqual(parse_coordinates(text), expected, text)

    def test_partner_coordinates_from_link(self):
        partner = self.env['res.partner'].create({
            'name': 'Client Jeddah', 'location_url': 'https://www.google.com/maps?q=21.5433,39.1728'})
        self.assertAlmostEqual(partner.partner_latitude, 21.5433)
        self.assertAlmostEqual(partner.partner_longitude, 39.1728)
        self.assertTrue(partner.date_localization)
        partner.location_url = '24.7136, 46.6753'
        self.assertAlmostEqual(partner.partner_latitude, 24.7136)

    def test_short_link_is_resolved(self):
        resolved = 'https://www.google.com/maps/place/X/@21.1,39.1,17z/data=!3d21.5433!4d39.1728'
        with patch('odoo.addons.partner_google_location.models.res_partner.resolve_short_link', return_value=[resolved]) as mock:
            partner = self.env['res.partner'].create({'name': 'X', 'location_url': 'https://maps.app.goo.gl/AbCdEf123'})
        mock.assert_called_once()
        self.assertAlmostEqual(partner.partner_latitude, 21.5433)

    def test_plus_code(self):
        self.assertAlmostEqual(plus_code_to_coordinates('8FVC9G8F+6X')[0], 47.36556, places=4)
        self.assertIsNone(plus_code_to_coordinates('9G8F+6X'))  # short code without reference
        self.assertEqual(plus_code_to_coordinates('9G8F+6X', (47.4, 8.6)), plus_code_to_coordinates('8FVC9G8F+6X'))
        # short link to a plus code with a locality (what Google gives for a shared place)
        resolved = [
            'https://maps.google.com?q=H5F3+QV6+%D9%85%D8%B4%D8%B1%D9%88%D8%B9,+Ar+Rawdah,+Jeddah+23435&ftid=0x15:0xac&entry=gps',
            'https://consent.google.com/ml?continue=https://maps.google.com/maps?q%3DH5F3%2BQV6%2BAr%2BRawdah,%2BJeddah',
        ]
        with patch('odoo.addons.partner_google_location.models.res_partner.resolve_short_link', return_value=resolved), \
                patch.object(type(self.env['base.geocoder']), 'geo_find', return_value=(21.5567630, 39.1457901)) as geo:
            partner = self.env['res.partner'].create({'name': 'Y', 'location_url': 'https://maps.app.goo.gl/j7Vt7Et4'})
        geo.assert_called()
        self.assertAlmostEqual(partner.partner_latitude, 21.57441, places=4)
        self.assertAlmostEqual(partner.partner_longitude, 39.15464, places=4)

    def test_compute_button_uses_link(self):
        partner = self.env['res.partner'].create({'name': 'Z'})
        partner.write({'location_url': '21.5433, 39.1728'})
        partner.write({'partner_latitude': 0, 'partner_longitude': 0})
        partner.geo_localize()
        self.assertAlmostEqual(partner.partner_latitude, 21.5433)
        self.assertAlmostEqual(partner.partner_longitude, 39.1728)

    def test_customer_map_query(self):
        """Same call as the Customer map page (static/src/customer_map.js)."""
        self.env['res.partner'].create({'name': 'Mapped', 'location_url': '21.5433, 39.1728'})
        rows = self.env['res.partner'].search_read(
            ['|', ['partner_latitude', '!=', 0], ['partner_longitude', '!=', 0]],
            ['display_name', 'phone', 'street', 'city', 'customer_rank', 'partner_latitude', 'partner_longitude'],
            order='name, id')
        self.assertIn('Mapped', [r['display_name'] for r in rows])

    def test_map_view_and_filters(self):
        Partner = self.env['res.partner']
        views = Partner.get_views([(False, 'map'), (False, 'search')])['views']
        self.assertIn('<map', views['map']['arch'])
        self.assertIn('name="not_located"', views['search']['arch'])
        self.assertIn('map', self.env['ir.ui.view'].get_view_info())
        self.assertIn('map', self.env.ref('contacts.action_contacts').view_mode.split(','))
        located = Partner.create({'name': 'In', 'location_url': '21.5433, 39.1728'})
        unlocated = Partner.create({'name': 'Out'})
        dom_located = ['|', ('partner_latitude', '!=', 0), ('partner_longitude', '!=', 0)]
        dom_not = ['&', '|', ('partner_latitude', '=', False), ('partner_latitude', '=', 0),
                   '|', ('partner_longitude', '=', False), ('partner_longitude', '=', 0)]
        both = located | unlocated
        self.assertEqual(Partner.search(dom_located + [('id', 'in', both.ids)]), located)
        self.assertEqual(Partner.search(dom_not + [('id', 'in', both.ids)]), unlocated)

    def test_vendor_map(self):
        self.assertIn('map', self.env.ref('account.res_partner_action_supplier').view_mode.split(','))
        action = self.env.ref('partner_google_location.action_supplier_map')
        self.assertEqual(action.view_mode.split(',')[0], 'map')
        self.assertIn("'search_default_supplier': 1", action.context)

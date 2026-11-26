{
    'name': 'Customer location (Google Maps)',
    'version': '19.0.1.7.1',
    'summary': "Customer location from a Google Maps link, with the map in the contact form",
    'description': """
Paste a Google Maps link (or "lat, long") on a contact: the coordinates are read from it
and a Google map is shown in the form, with a button to open the route in Google Maps
and a "My current position" button for the salespeople on site.
A "Map" view (Contacts, Customers, menu Customer map) shows the located contacts of the search (OpenStreetMap, Leaflet 1.9.4 BSD-2).
No Google API key is needed.

Author: Ounis Walid - ounis.walid@gmail.com - +966 54 992 4483
""",
    'category': 'Sales/CRM',
    'author': 'Ounis Walid',
    'maintainer': 'Ounis Walid',
    'support': 'ounis.walid@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base_geolocalize', 'contacts', 'account'],
    'data': [
        'views/res_partner_views.xml',
        'views/customer_map_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'partner_google_location/static/src/google_location_field.js',
            'partner_google_location/static/src/google_location_field.xml',
            'partner_google_location/static/src/map_view/map_view.js',
            'partner_google_location/static/src/map_view/map_view.xml',
        ],
    },
    'uninstall_hook': '_remove_map_view_mode',
    'installable': True,
}

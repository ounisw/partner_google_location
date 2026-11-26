from lxml import etree

from odoo import _, fields, models

MAP_VALID_ATTRIBUTES = {'string', 'js_class', 'sample', 'create', 'edit', 'delete', '__validate__'}


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    type = fields.Selection(selection_add=[('map', 'Map')], ondelete={'map': 'cascade'})

    def _validate_tag_map(self, node, name_manager, node_info):
        if not node_info['validate']:
            return
        for child in node.iterchildren(tag=etree.Element):
            if child.tag != 'field':
                self._raise_view_error(_('A map view can only contain fields, got %s', child.tag), child)
        remaining = set(node.attrib) - MAP_VALID_ATTRIBUTES
        if remaining:
            self._raise_view_error(_('Invalid attributes (%s) in map view.', ', '.join(sorted(remaining))), node)

    def _get_view_info(self):
        return {'map': {'icon': 'fa fa-map-marker'}} | super()._get_view_info()


class IrActionsActWindowView(models.Model):
    _inherit = 'ir.actions.act_window.view'

    view_mode = fields.Selection(selection_add=[('map', 'Map')], ondelete={'map': 'cascade'})

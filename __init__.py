from . import models


def _remove_map_view_mode(env):
    """On uninstall: take 'map' out of the window actions (the view type disappears)."""
    for action in env['ir.actions.act_window'].search([('view_mode', 'like', 'map')]):
        modes = [m for m in action.view_mode.split(',') if m != 'map']
        action.view_mode = ','.join(modes) or 'list,form'

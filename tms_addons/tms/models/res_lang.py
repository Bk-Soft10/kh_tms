
from odoo import models, fields, api
import odoo

class Language(models.Model):
    _inherit = 'res.lang'

    @api.model
    @odoo.tools.ormcache(skiparg=1)
    def _get_languages_dir(self):
        langs = self.search([('active', '=', True)])
        return dict([(lg.code, lg.direction) for lg in langs])

    # @api.multi
    def get_languages_dir(self):
        return self._get_languages_dir()
    
    # @api.multi
    def get_lang_dir(self, code):
        lang = self.search([('code', '=', code)])
        return lang.direction if lang else 'ltr'

    # @api.multi
    def write(self, vals):
        self._get_languages_dir.clear_cache(self)
        return super(Language, self).write(vals)
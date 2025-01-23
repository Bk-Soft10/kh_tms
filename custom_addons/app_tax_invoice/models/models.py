import qrcode
import base64
from io import BytesIO
from odoo import models, api, fields, _
import binascii
from odoo.tools import float_repr
from odoo.exceptions import UserError, ValidationError
from .qr_generator import generateQrCode
from odoo.tools import html2plaintext

import logging

_logger = logging.getLogger(__name__)


######################################################################################################################
######################################################################################################################


class invoiceQrFields(models.Model):
    _name = 'invoice.qr.fields'
    _description = "Invoice QR-Fields"
    _order = 'QR Fields'

    sequence = fields.Integer()
    field_id = fields.Many2one('ir.model.fields',
                               domain=[('model_id.model', '=', 'account.move'),
                                       ('ttype', 'not in', ['many2many', 'one2many', 'binary'])])
    company_id = fields.Many2one('res.company')


######################################################################################################################
######################################################################################################################


class ResCompany(models.Model):
    _inherit = 'res.company'

    invoice_qr_type = fields.Selection([('by_url', 'Invoice Url'), ('by_info', 'Invoice Text Information')],
                                       default='by_url', required=True)
    invoice_field_ids = fields.One2many('invoice.qr.fields', 'company_id', string="Invoice Fields")

    # @api.constrains('invoice_qr_type', 'invoice_field_ids')
    # def check_invoice_field_ids(self):
    #     for rec in self:
    #         if rec.invoice_qr_type == 'by_info' and not rec.invoice_field_ids:
    #             raise ValidationError(_("Please Add Invoice Field's"))


######################################################################################################################
######################################################################################################################


class AccountMoveLineInherit(models.Model):
    _inherit = 'account.move.line'

    tax_amount = fields.Float(string="Taxed Amount", compute="_compute_tax_amount")

    @api.depends('tax_ids', 'price_unit', 'quantity')
    def _compute_tax_amount(self):
        for line in self:
            if line.tax_ids:
                line.tax_amount = line.price_total - line.price_subtotal
            else:
                line.tax_amount = 0.0


######################################################################################################################
######################################################################################################################


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    qr_code = fields.Binary(string="QR Code", copy=False, store=True)

    custom_qr_code_str = fields.Char(string='Zatka QR Code', compute='_compute_qr_code_custom')
    custom_confirmation_datetime = fields.Datetime(string='Confirmation Date', readonly=True, copy=False)

    @api.depends('amount_total_signed', 'amount_tax_signed', 'custom_confirmation_datetime', 'company_id', 'company_id.vat')
    def _compute_qr_code_custom(self):
        for rec in self:
            qr_code_str = rec._calculate_custom_qr_code_str()
            _logger.info(qr_code_str)
            rec.custom_qr_code_str = qr_code_str

    def _calculate_custom_qr_code_str(self):
        def get_qr_encoding(tag, field):
            company_name_byte_array = field.encode()
            company_name_tag_encoding = tag.to_bytes(length=1, byteorder='big')
            company_name_length_encoding = len(company_name_byte_array).to_bytes(length=1, byteorder='big')
            return company_name_tag_encoding + company_name_length_encoding + company_name_byte_array
        self.ensure_one()
        record = self.sudo()
        qr_code_str = ''
        confirmation_datetime = record.custom_confirmation_datetime or fields.Datetime.now()
        if confirmation_datetime and record.company_id.vat:
            seller_name_enc = get_qr_encoding(1, record.company_id.display_name)
            company_vat_enc = get_qr_encoding(2, record.company_id.vat)
            time_sa = fields.Datetime.context_timestamp(self.with_context(tz='Asia/Riyadh'), confirmation_datetime)
            timestamp_enc = get_qr_encoding(3, time_sa.isoformat())
            invoice_total_enc = get_qr_encoding(4, float_repr(abs(record.amount_total_signed), 2))
            total_vat_enc = get_qr_encoding(5, float_repr(abs(record.amount_tax_signed), 2))

            str_to_encode = seller_name_enc + company_vat_enc + timestamp_enc + invoice_total_enc + total_vat_enc
            _logger.info(str_to_encode)
            qr_code_str = base64.b64encode(str_to_encode).decode()
            _logger.info("qr_code_str qr_code_str")
            _logger.info(qr_code_str)
        return qr_code_str

    # @api.depends('amount_total_signed', 'amount_tax_signed', 'custom_confirmation_datetime', 'company_id', 'company_id.vat')
    # def _compute_qr_code_str(self):
    #     def get_qr_encoding(tag, field):
    #         company_name_byte_array = field.encode()
    #         company_name_tag_encoding = tag.to_bytes(length=1, byteorder='big')
    #         company_name_length_encoding = len(company_name_byte_array).to_bytes(length=1, byteorder='big')
    #         return company_name_tag_encoding + company_name_length_encoding + company_name_byte_array
    #
    #     for record in self:
    #         qr_code_str = ''
    #         if record.custom_confirmation_datetime and record.company_id.vat:
    #             seller_name_enc = get_qr_encoding(1, record.company_id.display_name)
    #             company_vat_enc = get_qr_encoding(2, record.company_id.vat)
    #             time_sa = fields.Datetime.context_timestamp(self.with_context(tz='Asia/Riyadh'), record.custom_confirmation_datetime)
    #             timestamp_enc = get_qr_encoding(3, time_sa.isoformat())
    #             invoice_total_enc = get_qr_encoding(4, float_repr(abs(record.amount_total_signed), 2))
    #             total_vat_enc = get_qr_encoding(5, float_repr(abs(record.amount_tax_signed), 2))
    #
    #             str_to_encode = seller_name_enc + company_vat_enc + timestamp_enc + invoice_total_enc + total_vat_enc
    #             qr_code_str = base64.b64encode(str_to_encode).decode()
    #         record.custom_qr_code_str = qr_code_str

    def _post(self, soft=True):
        res = super()._post(soft)
        for move in self:
            if move.country_code == 'SA' and move.is_sale_document():
                vals = {'custom_confirmation_datetime': fields.Datetime.now()}
                move.write(vals)
        return res

    @api.onchange('partner_id')
    def _onchange_partner_warning_vat(self):
        if not self.partner_id:
            return
        partner = self.partner_id
        warning = {}
        if partner.company_type == 'company' and not partner.vat:
            title = ("Warning for %s") % partner.name
            message = _("Please add VAT ID for This Partner '%s' !") % (partner.name)
            warning = {
                'title': title,
                'message': message,
            }
        if warning:
            res = {'warning': warning}
            return res

    def _string_to_hex(self, value):
        if value:
            string = str(value)
            string_bytes = string.encode("UTF-8")
            encoded_hex_value = binascii.hexlify(string_bytes)
            hex_value = encoded_hex_value.decode("UTF-8")
            return hex_value

    def _get_hex(self, tag, length, value):
        if tag and length and value:
            hex_string = self._string_to_hex(value)
            length = int(len(hex_string) / 2)
            conversion_table = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f']
            hexadecimal = ''
            while (length > 0):
                remainder = length % 16
                hexadecimal = conversion_table[remainder] + hexadecimal
                length = length // 16
            if len(hexadecimal) == 1:
                hexadecimal = "0" + hexadecimal
            return tag + hexadecimal + hex_string

    def get_qr_code_data(self):
        self.ensure_one()
        rec_su = self.sudo()
        company_rec = rec_su.company_id if rec_su.company_id else self.env.company
        partner_rec = rec_su.partner_id if rec_su.partner_id else company_rec.partner_id
        sellername = str(company_rec.name) if rec_su.move_type in ('out_invoice', 'out_refund') else str(partner_rec.name)
        seller_vat_no = company_rec.vat or '' if rec_su.move_type in ('out_invoice', 'out_refund') else str(partner_rec.vat or '')
        if rec_su.move_type in ('out_invoice', 'out_refund') and rec_su.partner_id and rec_su.partner_id.company_type == 'company':
            customer_name = partner_rec.name
            customer_vat = partner_rec.vat
        seller_hex = self._get_hex("01", "0c", sellername)
        vat_hex = self._get_hex("02", "0f", seller_vat_no) or ""
        time_stamp = str(rec_su.invoice_date or self.create_date)
        date_hex = self._get_hex("03", "14", time_stamp)
        total_with_vat_hex = self._get_hex("04", "0a", str(round(rec_su.amount_total, 2))) or 0
        total_vat_hex = self._get_hex("05", "09", str(round(rec_su.amount_tax, 2))) or 0
        qr_hex = seller_hex + vat_hex + date_hex + total_with_vat_hex + total_vat_hex
        encoded_base64_bytes = base64.b64encode(bytes.fromhex(qr_hex)).decode()
        return encoded_base64_bytes

    def _get_qr_image(self):
        self.ensure_one()
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(self.get_qr_code_data())
        qr.make(fit=True)
        img = qr.make_image()
        temp = BytesIO()
        img.save(temp, format="PNG")
        qr_image = base64.b64encode(temp.getvalue())
        return qr_image

    # @api.onchange('invoice_line_ids', 'partner_id')
    def generate_qr_code(self):
        for rec in self:
            qr_image = rec._get_qr_image()
            rec.qr_code = qr_image

    # def _generate_qr_code(self):
    #     for rec in self:
    #         company_id = rec.company_id or self.env.company
    #         qr_info = ''
    #         if company_id.invoice_qr_type != 'by_info':
    #             qr_info = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #             qr_info += rec.get_portal_url()
    #         else:
    #             if company_id.invoice_field_ids:
    #                 dict_result = {}
    #                 for ffild in company_id.invoice_field_ids.mapped('field_id'):
    #                     if ffild.ttype == 'many2one':
    #                         dict_result[ffild.field_description] = rec[ffild.name].display_name
    #                     else:
    #                         dict_result[ffild.field_description] = rec[ffild.name]
    #                 for key, value in dict_result.items():
    #                     if str(key).__contains__('Partner') or str(key).__contains__(_('Partner')):
    #                         if rec.move_type in ['out_invoice', 'out_refund']:
    #                             key = str(key).replace(_('Partner'), _('Customer'))
    #                         elif rec.move_type in ['in_invoice', 'in_refund']:
    #                             key = str(key).replace(_('Partner'), _('Vendor'))
    #                     qr_info += f"{key} : {value} <br/>"
    #                 qr_info = html2plaintext(qr_info)
    #         rec.qr_code = generateQrCode.generate_qr_code(qr_info)

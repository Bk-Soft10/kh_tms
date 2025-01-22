
import base64
import os
from datetime import datetime
from datetime import date
from datetime import *
from io import BytesIO , StringIO
from odoo.exceptions import UserError, ValidationError

import xlsxwriter
from PIL import Image as Image
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from xlsxwriter.utility import xl_rowcol_to_cell

import logging
_logger = logging.getLogger(__name__)



class payrollreportexcelwiz(models.TransientModel):
    _name = 'documents.report.wiz'
    
    from_date = fields.Date('From Date', required=True)
    date_end= fields.Date('To Date', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee')
    document_type_id = fields.Many2one('document.type',
                                       string="Document Type",
                                       help="Type of the document.")
    filter = fields.Selection(
        string='Filter',
        selection=[('all', 'All'),
                   ('employee', 'Employee')],
        required=True, default="all")

    @api.onchange('filter')
    def _onchange_filter(self):
        if self.filter == 'all':
            self.employee_id = False

    def action_generate_report(self):
        """Generate the filtered report."""
        domain = []
        if self.filter == 'employee' and self.employee_id:
            domain.append(('employee_ref_id', '=', self.employee_id.id))
        if self.document_type_id:
            domain.append(('document_type_id', '=', self.document_type_id.id))
        if self.from_date:
            domain.append(('expiry_date', '>=', self.from_date))
        if self.date_end:
            domain.append(('expiry_date', '<=', self.date_end))

        documents = self.env['hr.employee.document'].search(domain)
        docs = self.env['hr.employee.document'].browse(documents.ids)

        document_data = [
            {
                'Emp_name': doc.employee_ref_id.name,
                'doc_name': doc.name,
                'doc_type' : doc.document_type_id.name,
                'expiry_date': doc.expiry_date,
                # Add other fields as needed
            }
            for doc in docs
        ]



        data = {
             'employee_documents': document_data,
            'doc_ids': document_data,
            'doc_model': 'hr.employee.document',
            'date_from': self.from_date,
            'date_to': self.date_end,
            'employee_id': self.employee_id.name if self.employee_id else 'All Employees'
        }


        _logger.info(f"Data being passed to report: {data}")

        return self.env.ref('oh_employee_documents_expiry.hr_document_report').with_context(
            from_transient_model=True).report_action(self, data=data)

    #@api.model
    #def get_report_values(self, docids, data=None):
    #    docs = self.env['your.model'].browse(docids)
    #    employee = self.env['hr.employee'].search(['user_id', '=', self.env.user.id], limit=1)
    #    return {
    #        'doc_ids': docids,
    #        'doc_model': 'your.model',
    #        'docs': docs,
    #        'employee': employee and employee[0]
    #    }






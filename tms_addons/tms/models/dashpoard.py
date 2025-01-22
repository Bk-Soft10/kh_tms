from werkzeug.urls import url_encode

from odoo import api, exceptions, fields, models, _

from datetime import date, datetime, timedelta

from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError

import logging
import json
import ast
from collections import defaultdict, OrderedDict
from collections.abc import MutableMapping
from odoo.osv import expression

try:
    from odoo.addons import decimal_precision as dp
except:
    from addons import decimal_precision as dp

from . import common

_logger = logging.getLogger(__name__)
werkzeug_log = logging.getLogger('werkzeug')
werkzeug_log.setLevel(logging.ERROR)


class Dashboard(models.AbstractModel):
    _name = 'tms.dashboard'

    rtr = {'d': _('Draft'),
           'b': _('In Branch'),
           'r': _('In Road'),
           't': _('Transient'),
           'a': _('Arrival'), }

    """
    name = fields.Char()
    
    receipt_group = fields.Text(compute='_compute_receipt_group')
    receiptsc = []
    receiptsi = []
    
    def _compute_receipt_group(self):
        #receiptscr, receiptsir = self._get_receipt_group()
        #self.receipt_group = json.dumps({'receiptsc': receiptscr,'receiptsi': receiptsir})
        pass
    """

    def create_dict(self):
        return {'b': [0, 'b', _('In Branch'), 'branch', 'hand-stop-o'], 'r': [0, 'r', _('In Road'), 'road', 'plane'],
                't': [0, 't', _('Transient'), 'trans', 'random'], 'a': [0, 'a', _('Arrival'), 'arrival', 'arrow-down'],
                'e': [0, 'e', _('Car Posted'), 'posted', 'check']}

    def _get_receipt_group(self):

        user = self.env.user
        branch = user.branch_id

        receiptsi = self.create_dict()

        receiptstoi = self.create_dict()

        receiptsc = self.create_dict()

        receiptstoc = self.create_dict()

        if not branch:
            return receiptsc, receiptsi, receiptstoc, receiptstoi

        states = ('d', 'e', 'c')
        ss = ('b', 'r', 'a')

        q = 'SELECT count(*) as count, state, is_comp FROM tms_receipt WHERE (state IN %s AND branch_id = %s) \
             OR (state=%s AND cur_branch_id=%s) GROUP BY state, is_comp'

        self.env.cr.execute(q, (tuple(ss), branch.id, 't', branch.id))
        for st in self.env.cr.dictfetchall():
            receipts = receiptsc if st['is_comp'] else receiptsi
            receipts[st['state']][0] = st['count']

        qq = 'SELECT count(*) as count, state, is_comp FROM tms_receipt WHERE state IN %s AND branch_to_id = %s \
              GROUP BY state, is_comp'

        self.env.cr.execute(qq, (tuple(ss), branch.id))
        for st in self.env.cr.dictfetchall():
            receiptst = receiptstoc if st['is_comp'] else receiptstoi
            receiptst[st['state']][0] = st['count']

        date = datetime.now() - timedelta(days=30)

        q = 'SELECT count(*) as count, is_comp FROM tms_receipt WHERE state = %s AND branch_id = %s \
             AND create_date >= %s  GROUP BY is_comp'
        self.env.cr.execute(q, ('e', branch.id, date))

        for st in self.env.cr.dictfetchall():
            receiptsx = receiptsc if st['is_comp'] else receiptsi
            receiptsx['e'][0] = st['count']

        q = 'SELECT count(*) as count, is_comp FROM tms_receipt WHERE state = %s AND branch_to_id = %s \
             AND create_date >= %s  GROUP BY is_comp'
        self.env.cr.execute(q, ('e', branch.id, date))

        for st in self.env.cr.dictfetchall():
            receiptsy = receiptstoc if st['is_comp'] else receiptstoi
            receiptsy['e'][0] = st['count']

        return receiptsc, receiptsi, receiptstoc, receiptstoi

    def _get_draft_receipt(self):
        branch = self.env.user.branch_id
        draft = {'drafti': 0, 'draftc': 0, 'draftt': _('draft')}
        qq = 'SELECT count(*) as count, is_comp FROM tms_receipt WHERE state=%s AND branch_id=%s\
              GROUP BY is_comp'

        self.env.cr.execute(qq, ('d', branch.id))
        for st in self.env.cr.dictfetchall():
            if st['is_comp']:
                draft['draftc'] = st['count']
            else:
                draft['drafti'] = st['count']

        return draft

    def _get_trip_group(self):

        user = self.env.user
        branch = user.branch_id

        states = ('b', 'r')

        trips = {'b': [0, 'b', _('In Branch'), 'branch', 'hand-stop-o'],
                 'a': [0, 'a', _('Arrival'), 'arrival', 'plane'], 'r': [0, 'r', _('Took off'), 'road', 'plane'],
                 't': [0, 't', _('Transient'), 'trans', 'random'],
                 'x': [0, 'x', _('In Arrival'), 'arrival', 'plane rotate175'],
                 'y': [0, 'y', _('On Route'), 'route', 'exchange']}

        if not branch:
            return trips

        q = 'SELECT count(*) as count, state FROM tms_trip WHERE (state IN %s AND (branch_id = %s OR cur_branch_id=%s)) \
             GROUP BY state'

        self.env.cr.execute(q, (tuple(states), branch.id, branch.id))
        for st in self.env.cr.dictfetchall():
            trips[st['state']][0] = st['count']

        date = datetime.now() - timedelta(days=31)

        q = 'SELECT count(*) as count FROM tms_trip WHERE state = %s AND branch_to_id = %s AND arrival_date>%s'
        self.env.cr.execute(q, ('a', branch.id, date))
        for st in self.env.cr.dictfetchall():
            trips['a'][0] += st['count']

        q = 'SELECT count(*) as count FROM tms_trip WHERE state = %s AND next_branch_id = %s GROUP BY state'
        self.env.cr.execute(q, ('r', branch.id))
        for st in self.env.cr.dictfetchall():
            trips['x'][0] += st['count']

        q = 'SELECT count(*) as count FROM tms_trip WHERE state = %s AND cur_branch_id = %s'
        self.env.cr.execute(q, ('t', branch.id))
        for st in self.env.cr.dictfetchall():
            trips['t'][0] += st['count']
        id = branch.id
        q = """SELECT DISTINCT x.id as id 
                FROM tms_trip x
                LEFT JOIN tms_trip_route y ON y.trip_id = x.id
                WHERE x.state IN ('r', 't') AND x.next_branch_id!=%s AND x.cur_branch_id!=%s 
                AND y.arrival_date IS NULL AND (y.branch_id=%s OR y.branch_to_id=%s OR x.branch_to_id=%s)"""

        self.env.cr.execute(q, (id, id, id, id, id))
        for st in self.env.cr.dictfetchall():
            trips['y'][0] += 1

        return trips

    def open_action(self):
        """return action based on type for related journals"""
        action_name = self._context.get('action_name', False)
        ctx = self._context.copy()
        ctx.pop('group_by', None)
        ctx.update({
            'journal_type': self.type,
            'default_journal_id': self.id,
            'search_default_journal_id': self.id,
        })

        [action] = self.env.ref('tms.%s' % action_name).read()
        action['context'] = ctx
        action['domain'] = self._context.get('use_domain', [])
        account_invoice_filter = self.env.ref('account.view_account_invoice_filter', False)
        if action_name in ['action_invoice_tree1', 'action_invoice_tree2']:
            action['search_view_id'] = account_invoice_filter and account_invoice_filter.id or False
        if action_name in ['action_bank_statement_tree', 'action_view_bank_statement_tree']:
            action['views'] = False
            action['view_id'] = False
        return action

    def render(self, item):
        return '<a type="object" name="open_action" context="{\'action_name\': \'%s\'}">%s</a>' % item[1], item[2]

    @api.model
    def get_dashboard_data(self):
        print("get_dashboard_data")
        access_obj = self.env['ir.model.access']
        create_receipt = access_obj.check('tms.receipt', 'create', False)
        create_itans = access_obj.check('tms.itrans', 'create', False)
        create_trip = access_obj.check('tms.trip', 'create', False)
        receiptscr, receiptsir, receiptstoc, receiptstoi = self._get_receipt_group()
        trips = self._get_trip_group()
        draft = self._get_draft_receipt()
        res_data = dict(self._context)
        cc_dict = {
            'test_name': 'BKBKBK',
            'receiptsc': receiptscr,
            'receiptsi': receiptsir,
            'receiptstoc': receiptstoc,
            'receiptstoi': receiptstoi,
            'trips': trips,
            'rkys': ['b', 't', 'r', 'a', 'e'], 'tkys': ['b', 'a', 't', 'r', 'x', 'y'],
            'create_receipt': create_receipt,
            'create_itans': create_itans,
            'create_trip': create_trip,
            'draft': draft
        }
        print(cc_dict)
        res_data.update(cc_dict)
        if create_receipt:
            # res_data['commission'] = self.env['tms.commission'].get_branch_info()
            res_data['commission'] = {}
        return res_data

    def get_html_dashboard(self, args):
        _logger.info("Call get_html_dashboard")
        access_obj = self.env['ir.model.access']
        create_receipt = access_obj.check('tms.receipt', 'create', False)
        create_itans = access_obj.check('tms.itrans', 'create', False)
        create_trip = access_obj.check('tms.trip', 'create', False)

        receiptscr, receiptsir, receiptstoc, receiptstoi = self._get_receipt_group()

        trips = self._get_trip_group()
        draft = self._get_draft_receipt()

        ctx = dict(self._context)
        create_receipt = False
        cc_dict = {'receiptsc': receiptscr, 'receiptsi': receiptsir, 'receiptstoc': receiptstoc,
                   'receiptstoi': receiptstoi, 'trips': trips,
                   'rkys': ['b', 't', 'r', 'a', 'e'], 'tkys': ['b', 'a', 't', 'r', 'x', 'y'],
                   'create_receipt': create_receipt,
                   'create_itans': create_itans,
                   'create_trip': create_trip,
                   'draft': draft}
        print(cc_dict)
        ctx.update(cc_dict)

        if create_receipt:
            ctx['commission'] = self.env['tms.commission'].get_branch_info()

        html = self.env['ir.ui.view'].render_template('tms.tms_dashboard', values=ctx)

        # _logger.info("Dashboard html: %s", html)
        # return ''
        return {'html': html, 'context': str(self._context)}

    def open_receipts_i(self, args):
        ctx = self._context.copy()
        ctx.pop('group_by', None)
        user = self.env.user
        branch = user.branch_id
        domain = [('state', '=', ctx.get('state'))]

        if ctx.get('state') == 't':
            domain.append(('cur_branch_id', '=', branch.id))
        elif ctx.get('to'):
            domain.append(('branch_to_id', '=', branch.id))
        elif ctx.get('state') == 'n':
            domain = []
        else:
            domain.append(('branch_id', '=', branch.id))
        domain.append(('is_comp', '=', False))

        [action] = self.env.ref('tms.action_tms_receipt_indev').read()
        action['target'] = 'main'
        action['domain'] = domain
        if ctx.get('state') != 'n':
            action['views'] = [[False, 'list'], [False, 'form']]  # important to view as list view
            ctx = ast.literal_eval(action.get('context')) if action.get('context') else {}
            ctx['edit'] = 1
            ctx['current'] = False
            ctx['search_default_r_30_days'] = 0
            action['context'] = ctx

        return action

    def open_receipts_c(self, args):
        ctx = self._context.copy()
        user = self.env.user
        branch = user.branch_id
        domain = [('state', '=', ctx.get('state'))]

        if ctx.get('state') == 't':
            domain.append(('cur_branch_id', '=', branch.id))
        elif ctx.get('to'):
            domain.append(('branch_to_id', '=', branch.id))
        elif ctx.get('state') == 'n':
            domain = []
        else:
            domain.append(('branch_id', '=', branch.id))
        domain.append(('is_comp', '=', True))

        [action] = self.env.ref('tms.action_tms_receipt_comp').read()
        action['target'] = 'main'
        if ctx.get('state') != 'n':
            action['views'] = [[False, 'list'], [False, 'form']]  # important to view as list view
            action['domain'] = domain
            ctx = ast.literal_eval(action.get('context')) if action.get('context') else {}
            ctx['edit'] = 1
            ctx['current'] = False
            ctx['search_default_r_30_days'] = 0
            action['context'] = ctx

        return action

    def open_trips(self, args):
        ctx = self._context.copy()
        user = self.env.user
        branch = user.branch_id
        state = ctx.get('state')

        domain = [('state', '=', state)]
        if state == 'b':
            # domain = ['|', '&', ('branch_id', '=', branch.id), ('state', '=', 'b'), '&', ('branch_to_id', '=', branch.id), ('state', '=', 'a')]
            domain = [('state', '=', state)]
        elif state == 'r':
            q = 'SELECT id FROM tms_trip WHERE (state =%s AND (branch_id = %s OR cur_branch_id=%s))'
            ids = []
            self.env.cr.execute(q, ('r', branch.id, branch.id))
            for st in self.env.cr.dictfetchall():
                ids.append(st['id'])
            domain = [('id', 'in', ids)]
        elif state == 'a':
            domain = [('state', '=', 'a'), ('branch_to_id', '=', branch.id)]
        elif state == 't':
            domain.append(('cur_branch_id', '=', branch.id))
        elif state == 'x':
            q = 'SELECT id FROM tms_trip WHERE state = %s AND next_branch_id = %s GROUP BY id'
            ids = []
            self.env.cr.execute(q, ('r', branch.id))
            for st in self.env.cr.dictfetchall():
                ids.append(st['id'])
            domain = [('id', 'in', ids)]
        elif state == 'y':
            id = branch.id
            q = """SELECT DISTINCT x.id as id 
                FROM tms_trip x
                LEFT JOIN tms_trip_route y ON y.trip_id = x.id
                WHERE x.state IN ('r', 't') AND x.next_branch_id!=%s AND x.cur_branch_id!=%s 
                AND y.arrival_date IS NULL AND (y.branch_id=%s OR y.branch_to_id=%s OR x.branch_to_id=%s)"""
            ids = []
            self.env.cr.execute(q, (id, id, id, id, id))
            for st in self.env.cr.dictfetchall():
                ids.append(st['id'])
            domain = [('id', 'in', ids)]

        else:
            domain.append(('cur_branch_id', '=', branch.id))

        [action] = self.env.ref('tms.action_tms_trip').read()
        action['target'] = 'main'
        action['views'] = [[False, 'list'], [False, 'form']]  # important to view as list view

        action['domain'] = domain

        ctx = ast.literal_eval(action.get('context')) if action.get('context') else {}

        if state == 'a':
            ctx['search_default_arrival_30_days'] = 1

        ctx['current'] = False
        ctx['search_default_r_30_days'] = 0
        action['context'] = ctx
        _logger.info("open_trips: %s", action.get('context'))

        return action

    def create_trip(self, args):
        [action] = self.env.ref('tms.action_tms_trip').read()
        action['target'] = 'main'
        return action

    def create_itrans(self, args):
        [action] = self.env.ref('tms.action_tms_itrans').read()
        action['target'] = 'main'
        return action

    def do_search(self, args):
        search = self._context.get('search', '')
        [action] = self.env.ref('tms.action_tms_receipt_indev').read()
        res = None
        qq = ""
        if len(search) == 13 or search.find('-') > 0:
            is_receipt = True if search[4] == '1' else False
            table = 'tms_receipt' if is_receipt else 'tms_itrans'
            qq = """SELECT id, is_comp FROM %s WHERE receipt_no='%s' OR name='%s'""" % (table, search, search)
            self._cr.execute(qq)
            res = self._cr.fetchone()
            if res:
                if is_receipt:
                    [action] = self.env.ref(
                        'tms.action_tms_receipt_comp' if res[1] else 'tms.action_tms_receipt_indev').read()
                else:
                    [action] = self.env.ref('tms.action_tms_all_itrans').read()
        else:
            qq = """SELECT id FROM tms_trip WHERE trip_no='%s'""" % (search)
            self._cr.execute(qq)
            res = self._cr.fetchone()
            if res:
                [action] = self.env.ref('tms.action_tms_all_trip').read()

        if action and res:
            # del action['views']
            action['res_id'] = res[0]
            return action

        raise ValidationError("Unable to find %s" % search)

    """
    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        return [1]
    
    @api.model
    def search_count(self, args):
        return 1
    
    @api.model
    def create(self, vals):
        return self
    
    
    def write(self, vals):
        return [self]
    """

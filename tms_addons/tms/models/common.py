from odoo.exceptions import AccessError, UserError, ValidationError
from odoo import models, fields, api, _
from datetime import datetime
from datetime import date
import pytz
from odoo.addons.bus.models.bus import json_dump
from odoo import tools
from odoo.tools import pycompat
from odoo.tools.float_utils import float_repr
from ..sms import sender,account,sms,utilities
import logging
import math
import requests

_logger = logging.getLogger(__name__)
def tms_check_plate_number(pn):
   
    if pn and len(pn.strip()):
        pn = pn.strip()
        if len(pn) > 6 and len(pn) < 11 :
            num = pn[6:]
            if pn[0].isalpha() and pn[1] == ' ' and pn[2].isalpha() and pn[3] == ' ' and pn[4].isalpha() and pn[5] == ' ':
                ok = True
                for c in  num:
                    ok = ok and tms_is_number(c) 
                if ok:
                    return True
    
    raise ValidationError(_('(%s) is not valid plate number '% pn))
    #return True

def tms_is_number(s):
    
    if s == '.':
        return False
    
    try:
        int(s)
        return True
    except ValueError:
        pass
    
    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    
    return False 


def print_receipt(r): 
    receipt_no = ''
    receipt_date = ''
    dest = ''
    shipping_type = 'نقل داخلي'
    pay_branch = ''
    go_receipt_no = ''
    amount_total = ''
    payment = ''
    payment_date = ''
    resv1_name = ''
    resv1_mobile =''
    resv1_id = ''
    arrival = ''
    sss = '0.0'
    amount_untaxed = '0.0'
    payment_ids = None
    discount = '0.0'
    comment = r.comment or ' '
    
    if r._name == 'tms.itrans':
        receipt_no = r.receipt_no
        receipt_date = timestamp_company_timestamp_st(r, r.receipt_date)
        if r.shipping_type != 4:
            dest = r.to or ''
        else:
            dest = r.branch_to_id.name
        amount_total = str(r.amount_total)
        payment = str(r.payment_total)
        resv1_name = r.resv_name or ''
        resv1_mobile =r.resv_mobile or ''
        resv1_id = r.resv_id or ''
        payment_ids = r.trans_payment_ids
        #sss = float_repr(r.currency_id.round(r.amount - r.discount_amount), 2)
        amount_untaxed = r.amount
        
    else:
        receipt_no = r.receipt_no
        receipt_date = timestamp_company_timestamp_st(r, r.receipt_date)
        dest = r.branch_to_id.name
        pay_branch = r.pay_branch_id.name
        go_receipt_no = r.go_receipt_id.receipt_no if r.go_receipt_id else ''
        amount_total = str(r.amount_total)
        payment = str(r.payment_total)
        resv1_name = r.resv1_name or ''
        resv1_mobile = r.resv1_mobile or ''
        resv1_id = r.resv1_id or ''
        arrival = r.days_to_arrival
        payment_ids = r.payment_ids
        sss = float_repr(r.currency_id.round(r.amount_untaxed - r.discount_amount), 2)
        sss = ''
        amount_untaxed = r.amount_untaxed
        
        discount = r.discount_amount
        if r.shipping_type == 1:
            shipping_type = 'ذهاب فقط'
        elif r.shipping_type == 2:
            shipping_type = 'ذهاب وعودة'
        elif r.shipping_type == 3:    
            shipping_type = 'عودة'
        if r.add_price_ids:
            for a in r.add_price_ids:
                comment = "%s %s  " % (comment, a.description)
        """
        if not r.is_comp and r.amount_total > 0 and (str(r.date) >= '2018-09-20' and str(r.date) < '2018-09-24'):
            comment = comment + ' (خصم اضافي 25% بمناسبة اليوم الوطني)'
        
        _logger.info("add_price_ids count: %s, comment: %s", len(r.add_price_ids), comment)
         """		
    
    amount_tax = r.amount_tax
    
    tax_id = r.branch_id.tax_id if r.amount_tax > 0 else ''
    if payment_ids:
        payment_date = payment_ids[len(payment_ids)-1].date
        
    #t = sss.index(".")
    
    data = {'branch': r.branch_id.name,
            'partner': "%s %s" %   (r.partner_id.name, r.contract_no or ''),
            'tax_license': (tax_id.license_id or '') if tax_id else '',
            'partner_tax_license': r.partner_id.tax_license or '',
            'receipt_no': receipt_no,
            'receipt_date': receipt_date,
            'dest': dest,
            'shipping_type': shipping_type,
            'tax_rate': tax_id.description if tax_id else '' ,
            'pay_branch': pay_branch,
            'tax_amount': str(amount_tax),
            'go_receipt_no': go_receipt_no,
            'amount_untax': str(amount_untaxed),
            'amount_total': amount_total,
            'payment': payment,
            'discount': str(discount),
            'gross': sss,
            'payment_date': payment_date,
            'emp_no': r.create_uid.sudo().emp_code or '',
            'residual': str(r.residual),
            'color': r.color or '',
            'issue_year': r.issue_year or '',
            'body_no': r.body_no or '',
            'car_model': "%s - %s" % (r.brand_id.name, r.model_id.name),
            'shipper': r.partner_id.name if r.partner_id else '',
            'shipper_mobile': r.partner_id.mobile or '',
            'shipper_id': r.partner_id.ssn or '',
            'resv1_name': resv1_name or '',
            'resv1_mobile': resv1_mobile or '',
            'resv1_id':  resv1_id or '',
            'note': comment,
            'arrival': str(arrival),
            'car_id': r.car_id or ''}
    
    report = r.env['ir.actions.report'].search([('report_name', '=', 'tms.receipt')], limit=1)
    
    if report :
        return report.report_action(r, json_dump(data))
    
    raise ValidationError(_('No report found for (%s)') % r._name)
        


def timestamp_to_utc_00(self, d1, d2):
    d2 = '%s 23:59:59' % d2
    timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz)
    
    ds1 = fields.Datetime.from_string(d1)
    ds2 = fields.Datetime.from_string(d2)
    
    d1 = timezone.localize(ds1).astimezone(pytz.UTC)
    d2 = timezone.localize(ds2).astimezone(pytz.UTC)
    d1 = fields.Datetime.to_string(d1)
    d2 = fields.Datetime.to_string(d2)
    return d1, d2

def dates_to_utc_timestamps(rec, d1, d2):
    d2 = '%s 23:59:59' % d2
    timezone = pytz.timezone(rec._context.get('tz') or rec.env.user.tz)
    
    ds1 = fields.Datetime.from_string(d1)
    ds2 = fields.Datetime.from_string(d2)
    
    d1 = timezone.localize(ds1).astimezone(pytz.UTC)
    d2 = timezone.localize(ds2).astimezone(pytz.UTC)
    d1 = fields.Datetime.to_string(d1)
    d2 = fields.Datetime.to_string(d2)
    return d1, d2


def timestamp_to_utc(rec, d1):
    if not isinstance(d1, datetime) and isinstance(d1, date):
        d1 = datetime(year=d1.year, month=d1.month,day=d1.day)
    timezone = pytz.timezone(rec._context.get('tz') or rec.env.user.tz)
    ds1 = d1 if isinstance(d1, datetime) else  fields.Datetime.from_string(d1)    
    d1 = timezone.localize(ds1).astimezone(pytz.UTC)
    d1 = fields.Datetime.to_string(d1)
    return d1

def date_to_utc(rec, d1):
    timezone = pytz.timezone(rec._context.get('tz') or rec.env.user.tz)
    ds1 = d1 if isinstance(d1, datetime.date) else  fields.Datetime.from_string(d1)    
    d1 = timezone.localize(ds1).astimezone(pytz.UTC)
    d1 = fields.Date.to_string(d1)
    return d1

def timestamp_company_timestamp(rec, timestamp=lambda: datetime.now()):
    if not isinstance(timestamp, datetime):
        timestamp = fields.Datetime.from_string(timestamp)
    
    assert isinstance(timestamp, datetime), 'Datetime instance expected'
    tz_name = rec.env.user.company_id.tz or "Asia/Riyadh"
    utc_timestamp = pytz.utc.localize(timestamp, is_dst=False)  # UTC = no DST
    if tz_name:
        try:
            utc_timestamp = utc_timestamp.astimezone(pytz.timezone(tz_name))
        except Exception:
            _logger.debug("failed to compute context/client-specific timestamp, "
                          "using the UTC value",
                          exc_info=True)
    return utc_timestamp

def timestamp_company_date_st(rec, timestamp=lambda: datetime.now()):
    timestamp = timestamp_company_timestamp(rec, timestamp)
    return fields.Date.to_string(timestamp)

def timestamp_company_timestamp_st(rec, timestamp=lambda: datetime.now()):
    timestamp = timestamp_company_timestamp(rec, timestamp)
    return fields.Datetime.to_string(timestamp)


def is_same_date(rec, r_date, p_date):
    receipt_date = fields.Date.from_string(r_date)
    payment_date = fields.Date.from_string(p_date)
    is_same = (payment_date == receipt_date)
    receipt_date2 = ''
    payment_date2 = ''
    
    if not is_same:
        #r_date = r_date[:fields.DATE_LENGTH]
        payment_date = timestamp_to_utc(rec, "%s 23:59:59.9999" % p_date)[:fields.DATE_LENGTH]
        receipt_date = fields.Date.to_string(fields.Datetime.context_timestamp(rec, fields.Datetime.from_string(r_date)))
        is_same = (payment_date == receipt_date)
        if not is_same:
            payment_date = fields.Date.to_string(fields.Datetime.context_timestamp(rec, fields.Datetime.from_string("%s 23:59:59.9999" % p_date)))
            is_same = (payment_date == receipt_date)
    #if True:
    #    raise ValidationError("(r_date: %s - p_date: %s) (receipt_date: %s - receipt_date: %s) is_same: %s" % (r_date, p_date, payment_date, receipt_date, is_same))
    return is_same


def send_sms(mobile, message):
    
    if not mobile:
        return "Invalid mobile number"
    
    if mobile.startswith("05"):
        mobile = "966" + mobile[1:len(mobile)]
    
    result = requests.get('https://mshastra.com/sendurl.aspx', params = {
        'user': '20097325',
        'mobileno': mobile,
        'msgtext': message,
        'pwd': 'Hani@123',
        'CountryCode': 'ALL',
        'priority': 'High'
        })
    
    return result.text
        #Successful

def tms_action_send_sms(self):
    auth = utilities.MobilyApiAuth('smb', 'asQW123')
    
    ICP = self.env['ir.config_parameter'].sudo()    
    new_receipt_msg = ICP.get_param('tms.new_receipt_msg')
    try:
        
        ffrom = "%s / %s" % (self.branch_id.city_id.name, self.branch_id.name)
        tto = "%s / %s" % (self.branch_to_id.city_id.name, self.branch_to_id.name)
        
        ffrom = ffrom.replace("فرع ", "").replace("مدينة ", "")
        tto = tto.replace("فرع ", "").replace("مدينة ", "")
        
        new_receipt_msg = new_receipt_msg.format(self.resv1_name.split()[0], self.car_id, ffrom,
                                                  tto, self.name) 
        #sender = sms.MobilySMS(auth, [self.resv1_mobile], 'SMB', new_receipt_msg)
    except Exception as e:
        _logger.error(e)
        raise ValidationError("{0}".format(e))
    try:
       
        #response = sender.send()
        result = send_sms(self.resv1_mobile, new_receipt_msg)
        self.post_receipt_message("Sending New Receipt SMS to: %s with result: %s"% (self.resv1_name, result))
    except Exception as e:
        self.post_receipt_message("Sending New Receipt SMS to (%s) error: %s"% (self.resv1_mobile, "{0}".format(e)))
        raise ValidationError("{0}".format(e))
    
    
def tms_action_send_post_sms(self):
    #_logger.error("Try to Sending Arrival SMS")
    auth = utilities.MobilyApiAuth('smb', 'asQW123')
    
    ICP = self.env['ir.config_parameter'].sudo()    
    new_receipt_msg = ICP.get_param('tms.arrival_msg')
    try:
        new_receipt_msg = new_receipt_msg.format(self.resv1_name.split()[0], self.car_id, self.branch_to_id.name, self.branch_to_id.address or '', self.name) 
        #sender = sms.MobilySMS(auth, [self.resv1_mobile], 'SMB', new_receipt_msg)
    except Exception as e:
        return 'erore'
    try:
        result = send_sms(self.resv1_mobile, new_receipt_msg)
        self.post_receipt_message("Sending Arrival SMS to (%s) with result: %s"% (self.resv1_name, result), commit=False)
    except Exception as e:
        
        self.post_receipt_message("Sending Arrival SMS to (%s) error: %s"% (self.resv1_mobile, "{0}".format(e)), commit=False)
        
        #raise ValidationError("{0}".format(e))
        
        
        
def tms_get_trip_distance(t, validate=False):
    if t.is_internal:
        return 0
    tr_obj = t.env['tms.trip.route'] 
    trs = tr_obj.search([('trip_id', '=', t.id)])
    if not trs and t.city_id == t.city_to_id:
        return 0
    distance_city_obj = t.env['tms.freight.price'] 
    distance = tms_compute_trip_distance(t, trs, {}, distance_city_obj, validate)
    return distance
   
def tms_process_trip_distance(trips, validate=False):
    nowds = datetime.now()
    
    distance_city_obj = trips.env['tms.freight.price'] 
    #trm_obj = trips.env['tms.trip.receipt.mapping'] 
    rr_obj = trips.env['tms.receipt.route'] 
    tr_obj = trips.env['tms.trip.route'] 
    trip_post_obj = trips.env['tms.trip.post'] 
    distance_map = {}
    triptopost = []
    triptopostinternal = []
    receipts = trips.env['tms.receipt'] 
    calculated = 0;
    for t in trips:
                
        if t.calculated:
            continue
        
        if t.state not in ('a', 'e'):
            continue
        
        if t.is_internal:
            t.write({'calculated': True})
            calculated += 1
            triptopostinternal.append(t)
            continue
        
        trs = tr_obj.search([('trip_id', '=', t.id)])
        
        if not trs and t.city_id == t.city_to_id:
            t.write({'calculated': True})
            calculated += 1
            triptopostinternal.append(t)
            continue
        
        distance = t.distance if t.distance > 0 else tms_compute_trip_distance(t, trs, distance_map, distance_city_obj, validate)
        
        if distance <= 0:
            t.write({'calculated': True})
            calculated += 1
            triptopostinternal.append(t)
            continue
        
        receipt_rrs = rr_obj.search([('trip_id', '=', t.id)])
        if not receipt_rrs:
            t.write({'distance': distance, 'calculated': True})
            calculated += 1
            triptopostinternal.append(t)
            continue
        tdata = {'distance': distance}
                
        can_calc = True
        counter = 0;
        for receipt_rr in receipt_rrs:
            
            if receipt_rr.receipt_id.state == 'c':
                continue
            
            if receipt_rr.receipt_id.state not in ('a', 'e'):
                can_calc = False
                break
            
            counter +=1
                        
        if can_calc:
            if counter > 0:
                triptopost.append(t)
                for rr in receipt_rrs:
                    receipts |= rr.receipt_id
                tdata['calc_date'] = fields.Date.context_today(t)
            else:
                triptopostinternal.append(t)
            tdata['calculated'] = True
            calculated += 1
        
        t.write(tdata)
            
        
        
    date = fields.Date.today()
    
    topostids = []
    for trip in triptopost:
        topostids.append(trip.id)         
    
    if topostids:
        tripstr = ', '.join(str(id) for id in topostids)
        query = '''UPDATE tms_receipt_route trr SET distance = (SELECT SUM(distance) 
        FROM tms_trip_receipt_mapping WHERE receipt_route_id=trr.id) WHERE trr.trip_id IN(%s)''' % tripstr
        trips._cr.execute(query)
        receipts.refresh()
    
    """
    for trip in triptopost:
        tms = trip.arrival_date or trip.expected_arrival or trip.last_departure_date
        date = fields.Date.context_today(trip, fields.Datetime.from_string(tms))
        trip_post_obj.create({'trip_id': trip.id, 'postall': True, 'date': date})
    
    for trip in triptopostinternal:
        tms = trip.arrival_date or trip.expected_arrival or trip.last_departure_date
        date = fields.Date.context_today(trip, fields.Datetime.from_string(tms))
        trip_post_obj.create({'trip_id': trip.id, 'postall': False, 'date': date})
    """
     
    for r in receipts:
        amount = r.amount_untaxed
        if r.shipping_type == 2:
            amount = r.go_price
            if r.amount_tax > 0:
                amount -= amount * 5/105      
        
        rtrips = []
        distance = 0
        for rr in r.receipt_trip_ids:
            distance += rr.distance
        if distance > 0:
            for rr in r.receipt_trip_ids:
                if rr.trip_id.distance > 0:
                    div = amount/distance * min(rr.distance, distance)
                    rr.write({'amount': round(div, 3)})
        #elif r.state in ('a', 'e') and len(r.receipt_trip_ids)==1:
        #    r.receipt_trip_ids[0].write({'amount': round(amount, 3)})
            
    if topostids:
        tripstr = ', '.join(str(id) for id in topostids)
        query = '''UPDATE tms_trip t SET total_income = (SELECT SUM(amount) 
        FROM tms_receipt_route WHERE trip_id=t.id) WHERE t.id IN(%s)''' % tripstr
        trips._cr.execute(query)
    
    return calculated      
            
def tms_get_distance(distance_map, city_id, city_to_id, distance_city_obj): 
    
    if city_id == city_to_id:
        return 0
    key1 = str(city_id.id)+"-"+str(city_to_id.id)
    distance = distance_map.get(key1, None) 
    if distance is None:
        city_dist = distance_city_obj.search(['|', '&', ('city_id', '=', city_id.id), ('city_to_id', '=', city_to_id.id),
                                              '&', ('city_id', '=', city_to_id.id), ('city_to_id', '=', city_id.id)], limit=1)
        #if not city_dist:
        #raise ValidationError(_('No distance between city: %s and city: %s') % (city_id.name, city_to_id.name))
        key2 = str(city_to_id.id)+"-"+str(city_id.id)
        if city_dist:
            distance = city_dist.distance
            distance_map.update({key1: distance, key2: distance}) 
        else:
            distance_map.update({key1: 0, key2: 0})       
    
    return distance

def tms_get_distance_no_cache(city_id, city_to_id): 
    if city_id == city_to_id:
        return 0
    distance_city_obj = city_id.env['tms.freight.price'] 
    city_dist = distance_city_obj.search(['|', '&', ('city_id', '=', city_id.id), ('city_to_id', '=', city_to_id.id),
                                              '&', ('city_id', '=', city_to_id.id), ('city_to_id', '=', city_id.id)], limit=1)
    
    return city_dist.distance if city_dist else 0
    

def tms_procees_ruck_income(trips, validate=False):
    
    pass


def tms_compute_trip_distance(t, trip_route_ids, distance_map, freight_city_obj, validate):
        
    if trip_route_ids:
        distance = 0 
        last = None
        for r in trip_route_ids:
            r.distance = tms_get_distance(distance_map, r.city_id, r.city_to_id, freight_city_obj)
            distance += r.distance
            if r.city_to_id.id != t.city_to_id.id:
                last = r
        if last:
            dist = tms_get_distance(distance_map, last.city_to_id, t.city_to_id, freight_city_obj)
            if dist:
                return distance + dist
            if validate:
                raise ValidationError(_('No distance between city: %s and city: %s') % (last.city_to_id.name, t.city_to_id.name)) 
            return 0    
    
    if t.city_id ==  t.city_to_id or not t.city_id or not t.city_to_id:
        return 0
    
    dist = tms_get_distance(distance_map, t.city_id, t.city_to_id, freight_city_obj)
    if dist:
        return dist
    if validate:
        raise ValidationError(_('No distance between city: %s and city: %s') % (t.city_id.name, t.city_to_id.name))
    
    return 0 

def tms_common_round(val, scale): 
    d = math.pow(10, scale)
    return round(val * d)/d

def get_default_journal_domain(self):
        ids = []
        #if branch_id.bank_journal_id:
        #    ids.append(branch_id.bank_journal_id.id)
        ICP = self.env['ir.config_parameter'].sudo()
        if self.env.user.has_group('tms.group_tms_company_accountant'):
            company_journal_id = ICP.get_param('tms.company_journal_id')
            if company_journal_id:
                ids.append(company_journal_id)
        
        cash_journal_id = ICP.get_param('tms.cash_journal_id')
        if cash_journal_id:
            ids.append(cash_journal_id)
        
        #for j in obj_journal.search([('company_cash', '=', False), ('default_cash', '=', True), ('type', '=', 'cash')], limit=1):
        #    ids.append(j.id)
        
        return [('id', 'in', ids)]

    
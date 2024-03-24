import simplejson as json
from django import template
from django.utils.safestring import mark_safe
from web.models import Record 
from datetime import datetime 
import logging

logger = logging.getLogger(__name__)

register = template.Library()

@register.filter()
def json_format(j):
	return json.dumps(j, indent=4).replace(',', ',<br />').replace('{', '{<br />&nbsp;&nbsp;').replace('}', '<br />&nbsp&nbsp}')

@register.filter()
def call(obj, args):
	args = args.split(',')
	fn = getattr(obj, args[0])
	return fn(*args[1:])

@register.filter()
def monthlynonzeroslice(monthlies, key): #, sliceparts="0,0"):
	sliceparts="0,0"
	start_index = int(sliceparts.split(',')[0])
	end_index = int(sliceparts.split(',')[1])

	return [ m for m in monthlies if m[key] != 0 ][start_index:end_index]

@register.filter()
def mult(a, b):
	return a*b

@register.filter()
def sum_numbers(numbers):
	return sum(numbers)

@register.filter()
def meta_to_record(recordmetas):
	records = []
	for m in recordmetas:
		found_records = m.records()
		for found_record in found_records:
			if found_record and found_record.id not in [ r.id for r in records ]:
				records.append(found_record)
	return records

@register.filter()
def gt(than, num):
	return than < num 

@register.filter()
def dirme(thing):
	return dir(thing)

@register.filter()
def tabindex(bound_field, index):
	bound_field.field.widget.attrs['tabindex'] = index 
	return bound_field 

@register.filter()
def dec_out(number):

	out = "$%.2f" % number
	
	if number < 0:
		out = "<span class='negative'>($%.2f)</span>" % -number
	
	return mark_safe(out)

@register.filter()
def array_split(array, split_by):
	return array.split(split_by)

@register.filter()
def format_currency(val):
	if not val:
		val = 0
	return f'{float(val):.2f}'

@register.filter()
def lookup(obj, key):
	# logger.debug(f'looking up {key} in object')
	keys = str(key).split('.')	
	val = None 

	for key in keys:
		if val != None:
			obj = val 
		try:
			# -- map
			if type(obj) == list:
				val = [ o.__getattribute__(str(key)) for o in obj ]
			# -- dict value
			elif type(obj) == dict:			
				val = obj[str(key)]
				# val = obj.__getattribute__(str(key))
			# -- Object value 
			else:			
				val = obj.__getattribute__(str(key))
				
			# if key == 'date':
			# 	val = datetime.strftime(val, "%n/%d/%y")
		except KeyError as ke:
			pass
		except AttributeError as ae:
			pass
	return val 

@register.filter()
def genrange(count):
	return range(1,count+1)

@register.filter()
def mod(base, div):
	return base % div

@register.filter()
def map(list_of_dict, attribute):
	return ",".join([str(i.__getattribute__(attribute)) for i in list_of_dict])

@register.filter()
def monthly_amount(transaction):
	if transaction.recurringtransaction:
		return transaction.recurringtransaction.monthly_amount()
	else:
		raise Exception("This transaction does not recur, and so a monthly amount does not apply.")

@register.filter()
def real_amount(transaction, payment_at):
	return transaction.real_amount(payment_at)

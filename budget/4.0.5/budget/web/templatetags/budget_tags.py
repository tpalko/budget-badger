from django import template
from django.utils.safestring import mark_safe
from web.models import RecurringTransaction
from datetime import datetime 

register = template.Library()

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
	return f'{val:.2f}'

@register.filter()
def lookup(obj, key):
	val = None 
	try:
		if type(obj) == dict:			
			val = obj[str(key)]
			# val = obj.__getattribute__(str(key))
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

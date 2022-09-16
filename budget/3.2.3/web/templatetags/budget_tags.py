from django import template
from django.utils.safestring import mark_safe
from web.models import RecurringTransaction

register = template.Library()

@register.filter()
def dec_out(number):

	out = "$%.2f" % number
	
	if number < 0:
		out = "<span class='negative'>($%.2f)</span>" % -number
	
	return mark_safe(out)

@register.filter()
def map(items, attribute):
	return ",".join([str(i.__getattribute__(attribute)) for i in items])

@register.filter()
def monthly_amount(transaction):
	if transaction.recurringtransaction:
		return transaction.recurringtransaction.monthly_amount()
	else:
		raise Exception("This transaction does not recur, and so a monthly amount does not apply.")

@register.filter()
def real_amount(transaction, payment_at):
	return transaction.real_amount(payment_at)

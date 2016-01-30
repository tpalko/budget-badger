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
def real_amount(transaction):
	return transaction.real_amount()*RecurringTransaction.period_monthly_occurrence[transaction.period]
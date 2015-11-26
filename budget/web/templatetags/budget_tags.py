from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter()
def dec_out(number):

	out = "$%s" % number
	
	if number < 0:
		out = "<span class='negative'>($%s)</span>" % -number
	
	return mark_safe(out)

@register.filter()
def map(items, attribute):
	return ",".join([str(i.__getattribute__(attribute)) for i in items])
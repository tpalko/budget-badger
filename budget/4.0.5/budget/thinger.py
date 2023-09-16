from web.models import *

r = Record.objects.all()

s = r[124]

print(s.description)

print(s.meta_description)

print(s.full_description)

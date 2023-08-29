import sys
import os 

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import resolve 
from django.db.models import Q

from web.util.viewutil import get_querystring

def budget_context(request_context):
    '''Dynamically determine conventionally named js include file'''

    query_debug = get_querystring(request_context, 'debug')
    env_debug = str(os.getenv('DEBUG')).lower() in [ "1" ]
    debug = query_debug or env_debug

    return {
        'debug': debug
    }

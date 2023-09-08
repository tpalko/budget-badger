import sys
import os 

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import resolve 
from django.db.models import Q

from web.util.viewutil import get_querystring
from web.models import RecordMeta

def budget_context(request_context):
    '''Dynamically determine conventionally named js include file'''

    query_debug = get_querystring(request_context, 'debug')
    env_debug = str(os.getenv('DEBUG')).lower() in [ "1" ]
    debug = query_debug or env_debug

    menu = [
        { 
            'url': 'model_list',
            'display': 'Accounts/Cards'
        },
        { 
            'url': 'files',
            'display': 'Files'
        },
        { 
            'url': 'records',
            'display': 'Records'
        },
        { 
            'url': 'filters',
            'display': 'Filters'
        },
        { 
            'url': 'sorter',
            'display': 'Sorter'
        },
        { 
            'url': 'transactionrulesets_list',
            'display': 'Rules'
        },
        { 
            'url': 'transactionrulesets_auto',
            'display': 'Auto Groups'
        },
        { 
            'url': 'transactions',
            'display': 'Transactions'
        },
        { 
            'url': 'projection',
            'display': 'Projection'
        },
        { 
            'url': 'settings',
            'display': 'Settings'
        },
    ]

    return {
        'debug': debug,
        'menu': menu,
        'record_types': RecordMeta.RECORD_TYPES
    }

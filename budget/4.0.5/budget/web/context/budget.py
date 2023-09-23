import sys
import os 

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import resolve, reverse
from django.db.models import Q

from web.util.viewutil import get_querystring
from web.models import Event, RecordMeta, TransactionRuleSet

def format_url(view_name, kwargs={}):
    kwargs.update({'tenant_id': 1})
    return reverse(view_name, kwargs=kwargs)

def budget_context(request_context):
    '''Dynamically determine conventionally named js include file'''

    query_debug = get_querystring(request_context, 'debug')
    env_debug = str(os.getenv('DEBUG')).lower() in [ "1" ]
    debug = query_debug or env_debug

    menu = [
        { 
            'url': format_url('model_list'),
            'display': 'Accounts/Cards'
        },
        { 
            'url': format_url('files'),
            'display': 'Files'
        },
        { 
            'url': format_url('records'),
            'display': 'Records'
        },
        { 
            'url': format_url('tracing'),
            'display': 'Tracing'
        },
        { 
            'url': format_url('record_typing'),
            'display': 'Record Typing'
        },
        { 
            'url': format_url('sorter'),
            'display': 'Sorter'
        },
        { 
            'url': format_url('transactionrulesets_list'),
            'display': 'Rules'
        },        
        { 
            'url': format_url('alignment'),
            'display': 'Alignment'
        },        
        # { 
        #     'url': format_url('transactionrulesets_auto'),
        #     'display': 'Auto Groups'
        # },
        { 
            'url': format_url('transactions'),
            'display': 'Transactions'
        },
        { 
            'url': format_url('projection'),
            'display': 'Projection'
        },
        { 
            'url': format_url('settings'),
            'display': 'Settings'
        },
    ]

    return {
        'debug': debug,
        'menu': menu,
        'record_types': RecordMeta.RECORD_TYPES,
        'join_operators': TransactionRuleSet.join_operator_choices,
        'events': Event.objects.all()
    }

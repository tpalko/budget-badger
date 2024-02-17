import math 
import json 
import re
import base64
from web.util.recordgrouper import RecordGrouper
from web.util.modelutil import TransactionTypes
from django.core.exceptions import ValidationError
from django.db.models import Q
from web.util.csvparse import get_record_dicts_and_raw_data_lines_from_csv
from web.util.modelutil import record_hash
from web.util.stats import get_all_stats_for_rule_set
from web.models import Account, CreditCard, UploadedFile, Record, Transaction, RecordFormat, TransactionRuleSet, TransactionRule, ProtoTransaction
from web.forms import RecordForm, TransactionRuleForm, TransactionRuleSetForm, new_transaction_rule_form_set

from datetime import datetime, timedelta
import logging 
import sys 
import traceback 
from decimal import Decimal
from enum import Enum


logger = logging.getLogger(__name__)

class Searches(Enum):
    SEARCH_CC_ACCT_CREDITS = 'cc_acct_credits'
    SEARCH_TX_CC_PAYMENTS = 'tx_cc_payments'
    SEARCH_ALL_CREDITS = 'all_credits'
    SEARCH_ALL_DEBITS = 'all_debits'
    SEARCH_LARGE_AMOUNTS = 'large_amounts'

SEARCH_OPTIONS = [
    ("credit card and account credits", Searches.SEARCH_CC_ACCT_CREDITS.value,),
    ("transfers and credit card payments", Searches.SEARCH_TX_CC_PAYMENTS.value,),
    ("all credits", Searches.SEARCH_ALL_CREDITS.value,),
    ("all debits", Searches.SEARCH_ALL_DEBITS.value,),
    ("large amounts", Searches.SEARCH_LARGE_AMOUNTS.value,)
]

SEARCH_QUERIES = {
    Searches.SEARCH_CC_ACCT_CREDITS.value: Q(
                Q(uploaded_file__creditcard__isnull=False) \
                    | Q(
                        Q(uploaded_file__account__isnull=False) \
                            & (
                                Q(description__iregex=r"Interest Payment") | \
                                    Q(description__iregex=r"Internet transfer from") | \
                                    Q(description__iregex=r"FROM|TO.+CHECKING|SAVINGS")
                            )
                    )
            )
            & Q(amount__gt=0),
    Searches.SEARCH_TX_CC_PAYMENTS.value: Q(
        Q(description__iregex=r"Interest Payment") \
            | Q(description__iregex=r"Internet transfer from") \
            | Q(description__iregex=r"FROM|TO.+CHECKING|SAVINGS") \
            | Q(description__iregex=r"thank\s?you")
    ) & Q(amount__lt=0),
    Searches.SEARCH_ALL_CREDITS.value: Q(amount__gt=0),
    Searches.SEARCH_ALL_DEBITS.value: Q(amount__lt=0),
    Searches.SEARCH_LARGE_AMOUNTS.value: Q(amount__gte=400) | Q(amount__lte=-400)
}

#wholes = [1,2,3,5,10,15,20,50,80,85,90,95,97,98,99,100]
wholes = [4,5,6,7,8,10,12,20,30,40,50,60,70,80,90,100]
def nearest_whole(val):
    lastdiff = 101
    choice_w = None 
    for w in wholes:
        diff = abs(w - val)
        if diff < lastdiff:
            lastdiff = diff 
            choice_w = w
    return choice_w

def fuzzy_comparator(obj, all_fields, fuzzy_fields):
    our_fields = { f: getattr(obj, f) for f in all_fields }
    fuzzy_matches = {}
    for f in fuzzy_fields:
        test = our_fields.copy()
        del test[f]
        fuzzy_matches[f] = type(obj).objects.filter(~Q(id=obj.id), **test)
    return fuzzy_matches 

def transaction_type_display(transaction_type):
    return [ choice_tuple[1] for choice_tuple in TransactionTypes.transaction_type_choices if choice_tuple[0] == transaction_type ][0]

def get_querystring(request, key, default=""):
    val = default
    full_path = request.get_full_path()
    if '?' in full_path:
        querystring = { e.split('=')[0]: e.split('=')[1] for e in full_path.split('?')[1].split('&') }
        if key in querystring:
            val = querystring[key]
    return val

def _get_heatmap_region_lookup(heatmap, heatmap_normalized):
                
    heatmap_region_by_day = {}
    heat_by_region = {}
    current_heat = None
    region_index = 0
    max_region = 0
    for day in [ str(day) for day in range(1, 32) ]:
        
        if day not in heatmap_normalized:
            heatmap_region_by_day[day] = 0        
            continue         
        
        this_day_heat = int(heatmap_normalized[day])
        
        if current_heat is None or current_heat != this_day_heat:
            if this_day_heat not in heat_by_region:                
                region_index = max_region + 1
                max_region += 1                
                heat_by_region[this_day_heat] = region_index 
            else:
                region_index = heat_by_region[this_day_heat]
            current_heat = this_day_heat 
        
        heatmap_region_by_day[day] = region_index 
        
    return heatmap_region_by_day

def get_records_for_filter(records, attribute_filter, heatmap_region_filter=0):

    filtered_records = [ r for r in records ]    

    if attribute_filter:
        filter_parts = attribute_filter.split('=')
        if len(filter_parts) > 1:
            filter_key = attribute_filter.split('=')[0]
            filter_value = attribute_filter.split('=')[1]
            print(f'Filtering on {filter_key}={filter_value}')
            filtered_records = [ r for r in records if str(r.__getattribute__(filter_key)) == str(filter_value) ]

    if heatmap_region_filter > 0:
        heatmap_data = get_heatmap_data(filtered_records)
        heatmap_filtered_days = [ int(day) for day in heatmap_data['heatmap_region_lookup'] if heatmap_region_filter == 0 or heatmap_data['heatmap_region_lookup'][day] == heatmap_region_filter ]
        filtered_records = [ r for r in filtered_records if r.transaction_date.day in heatmap_filtered_days ]

    return filtered_records

def get_heatmap_data(filtered_records):

    date_list = [ r.transaction_date for r in filtered_records ]
    
    day_list = [ d.day for d in date_list ]
    month_list = [ datetime.strftime(d, "%b") for d in date_list ]
    weekday_list = [ datetime.strftime(d, "%a") for d in date_list ]

    month_heatmap = { m: month_list.count(m) for m in set(month_list) }
    month_heatmap_normalized = { m: nearest_whole(month_heatmap[m]*100.0/len(filtered_records)) for m in month_heatmap }

    weekday_heatmap = { j: weekday_list.count(j) for j in set(weekday_list) }
    weekday_heatmap_normalized = { j: nearest_whole(weekday_heatmap[j]*100.0/len(filtered_records)) for j in weekday_heatmap }
    
    day_set = list(set(day_list))
    day_set.sort()
    day_heatmap = { str(day): day_list.count(day) for day in day_set }    
    day_heatmap_normalized = { n: nearest_whole(day_heatmap[n]*100.0/len(filtered_records)) for n in day_heatmap }

    day_heatmap_region_lookup = _get_heatmap_region_lookup(day_heatmap, day_heatmap_normalized)

    all_weekdays = [ datetime.strftime(datetime.strptime("0", "%w") + timedelta(days=w), "%a") for w in range(7) ]
    all_months = [ datetime.strftime(datetime.strptime(f'{0 if m + 1 < 10 else ""}{m + 1}', "%m"), "%b") for m in range(12) ]

    return {
        'day_heatmap_normalized': day_heatmap_normalized,
        'day_heatmap': day_heatmap,
        'day_heatmap_region_lookup': day_heatmap_region_lookup,
        'weekday_heatmap': weekday_heatmap,
        'weekday_heatmap_normalized': weekday_heatmap_normalized,
        'month_heatmap': month_heatmap,
        'month_heatmap_normalized': month_heatmap_normalized,
        'all_weekdays': all_weekdays,
        'all_months': all_months
    }

# def get_recordgroup_data():

#     record_group_columns = ""
#     record_group_exclude_columns = ['records', 'record_ids', 'recent_amounts', 'weights', 'hist', 'bins', 'min_amount', 'max_amount', 'avg_amount', 'outliers_removed', 'is_variable', 'average_gap', 'five_percent', 'ten_percent', 'most_frequent_date', 'most_frequent_date_probability']

#     record_groups_with_stats = [ RecordGrouper.get_record_group_stats(rg.id) for rg in RecordGroup.objects.all() ]
#     sorted_record_groups_with_stats = sorted(record_groups_with_stats, key=lambda rg: rg['recurring_amount'], reverse=True)

#     if len(sorted_record_groups_with_stats) > 0:
#         record_group_columns = ",".join([ k for k in sorted_record_groups_with_stats[0].keys() if k not in record_group_exclude_columns ])

#     return {
#         'record_groups': sorted_record_groups_with_stats,
#         'record_group_columns': record_group_columns
#     }

def init_transaction_rule_forms(request, transactionruleset_id=None):

    # load ID
    transactionruleset = None 
    if transactionruleset_id:                
        transactionruleset = TransactionRuleSet.objects.get(pk=transactionruleset_id)
   
    # form defaults 
    transactionruleset_form = TransactionRuleSetForm()        
    TransactionRuleFormSet = new_transaction_rule_form_set(extra=0)
    transactionrule_formset = None 

    # form init
    if transactionruleset:
        # -- load form and formset for edit 
        transactionruleset_form = TransactionRuleSetForm(instance=transactionruleset)            
        transactionrule_formset = TransactionRuleFormSet(queryset=transactionruleset.transactionrules.all())
    else:
        # -- load formset for create
        TransactionRuleFormSet = new_transaction_rule_form_set(extra=1)
        transactionrule_formset = TransactionRuleFormSet(queryset=TransactionRule.objects.none())

        if 'month' in request.GET:
            month = request.GET['month']
            transactionrule_formset.forms[0].inclusion = 'filter'
            transactionrule_formset.forms[0].record_field = 'transaction_date'
            # , 'record_field':'transaction_date', 'match_operator':'>', 'match_value':month}))

    if request.method == "POST":
        
        # form init + populate 
        if transactionruleset:
            # -- handle posted edits 
            transactionruleset_form = TransactionRuleSetForm(request.POST, instance=transactionruleset)            
            transactionrule_formset = TransactionRuleFormSet(request.POST, queryset=transactionruleset.transactionrules.all())
        else:
            # -- handle posted create
            transactionruleset_form = TransactionRuleSetForm(request.POST)            
            transactionrule_formset = TransactionRuleFormSet(request.POST)
    
    return transactionruleset, transactionruleset_form, transactionrule_formset 

def process_transaction_rule_forms(ruleset_form, rule_formset):

    # model refresh/persist from forms 

    transactionruleset = ruleset_form.save()

    # -- TODO: verify the is_valid() above actually does everything to ensure the save() below never, ever fails
    # -- TODO: maybe do a match/replace only on the deleted/changed rules instead of deleting everything 
    for transactionrule in transactionruleset.transactionrules.all():
        transactionrule.delete()

    for form in rule_formset:
        trf = TransactionRuleForm({ **form.cleaned_data, 'transactionruleset': transactionruleset })
        trf.is_valid()
        trf.save()
    
    transactionruleset = ruleset_form.save()
    
    return transactionruleset

def handle_transaction_rule_form_request(request, transactionruleset_id=None):

    transactionruleset, transactionruleset_form, transactionrule_formset = init_transaction_rule_forms(request, transactionruleset_id)

    if request.method == "POST":

        transactionruleset_form.is_valid() 
        transactionrule_formset.is_valid(preRuleSet=transactionruleset is None)

        transactionruleset = process_transaction_rule_forms(transactionruleset_form, transactionrule_formset)
        
        transactionruleset.refresh_from_db()

        prototransaction = refresh_prototransaction(transactionruleset)        

        return True, transactionruleset_form, transactionrule_formset

    return False, transactionruleset_form, transactionrule_formset

def refresh_prototransaction(transactionruleset):

    stats = get_all_stats_for_rule_set(transactionruleset)

    # records = transactionruleset.records(refresh=True)
    
    # records, removed = RecordGrouper.filter_accounted_records(
    #     records=records, 
    #     less_than_priority=transactionruleset.priority, 
    #     is_auto=False)
    
    # stats = RecordGrouper.get_stats(records)

    proto_transaction = ProtoTransaction.objects.filter(transactionruleset=transactionruleset).first()
    if proto_transaction:
        proto_transaction.name = transactionruleset.name
        proto_transaction.update_stats(stats)
        proto_transaction.save()
    else:
        proto_transaction = ProtoTransaction.new_from(transactionruleset.name, stats, transactionruleset)
    
    return proto_transaction

def accounts_and_cards_for_records(records):

    accounts = [ r.uploaded_file.account for r in records if r.uploaded_file.account ]
    cards = [ r.uploaded_file.creditcard for r in records if r.uploaded_file.creditcard ]

    return set([ a.id for a in accounts ]), set([ c.id for c in cards ])

def get_type_display_brackets(hold_type_brackets, start_date, last_date):
    account_coverage = []

    def _get_segment_end_margin(bracket_margin, cursor):
        end = cursor 
        if bracket_margin > cursor and bracket_margin < last_date:
            end = bracket_margin                
        elif bracket_margin > last_date:
            end = last_date                 
        # elif bracket_margin < cursor:
        #     end = cursor                 
        return end 
            
    for a in hold_type_brackets.keys():

        segments = {
            'name': hold_type_brackets[a]['name'],
            'account_number': hold_type_brackets[a]['account_number'],
            'segments': []
        }

        def _add_segment(cursor, end, class_name):
            # logger.debug(f'adding {cursor} to {end}')
            width = end - cursor
            if width.days > 0:
                segments['segments'].append({
                    'class': class_name,
                    'width': width.days,
                    'title': f'[{cursor}, {end})'
                })
        
        cursor = start_date        
        
        for b in hold_type_brackets[a]['brackets']:                

            end = _get_segment_end_margin(b[0], cursor)
            
            _add_segment(cursor, end, 'off')
            
            cursor = end

            end = _get_segment_end_margin(b[1], cursor)

            _add_segment(cursor, end, 'on')
            
            cursor = end 

            if cursor >= last_date:
                break 
        
        if last_date > cursor:
            _add_segment(cursor, last_date, 'off')
            
        account_coverage.append(segments)


    return account_coverage 

def generate_display_brackets(account_brackets, card_brackets, start_date, end_date):

    brackets = []

    brackets.extend(get_type_display_brackets(account_brackets, start_date, end_date))
    brackets.extend(get_type_display_brackets(card_brackets, start_date, end_date))
    
    return brackets 

def coverage_brackets():

    accounts = Account.objects.all() # [ r.uploaded_file.account for r in records if r.uploaded_file.account ]
    cards = CreditCard.objects.all() # [ r.uploaded_file.creditcard for r in records if r.uploaded_file.creditcard ]

    return { 
        n.id: { 
            'name': n.name, 
            'account_number': n.account_number,
            'brackets': n.continuous_record_brackets() 
        } for n in accounts 
    }, { 
        n.id: { 
            'name': n.name, 
            'account_number': n.account_number,
            'brackets': n.continuous_record_brackets() 
        } for n in cards 
    }

def get_ruleset_breakout(transactionrulesets_manual):

    credit_rulesets = []
    debit_rulesets = []
    nostat_rulesets = []

    for rs in transactionrulesets_manual:

        if not rs.prototransaction_safe() or not rs.prototransaction.is_active():
            nostat_rulesets.append(rs)
            continue 

        if rs.prototransaction.direction == ProtoTransaction.DIRECTION_CREDIT:
            credit_rulesets.append(rs)
        elif rs.prototransaction.direction == ProtoTransaction.DIRECTION_DEBIT:
            debit_rulesets.append(rs)
        elif rs.prototransaction.direction == ProtoTransaction.DIRECTION_BIDIRECTIONAL:
            if rs.prototransaction.force_direction() == ProtoTransaction.DIRECTION_CREDIT:
                credit_rulesets.append(rs)
            else:
                credit_rulesets.append(rs)
        else:
            nostat_rulesets.append(rs)
            
        # if 'credit' in rs.prototransaction.stats:
        #     if 'average_for_month' in rs.prototransaction.stats['credit']:
        #         credit_avg = abs(rs.prototransaction.stats['credit']['average_for_month']) or 0
        # if 'debit' in rs.prototransaction.stats:
        #     if 'average_for_month' in rs.prototransaction.stats['debit']:
        #         debit_avg = abs(rs.prototransaction.stats['debit']['average_for_month']) or 0
        # if rs.direction == ProtoTransaction.DIRECTION_UNSET or rs.direction == ProtoTransaction.DIRECTION_BIDIRECTIONAL:

        #     credit_avg = abs(rs.prototransaction.average_for_month(ProtoTransaction.DIRECTION_CREDIT) or 0)
        #     debit_avg = abs(rs.prototransaction.average_for_month(ProtoTransaction.DIRECTION_DEBIT) or 0)

        #     if credit_avg > debit_avg:
        #         credit_rulesets.append(rs)
        #     elif debit_avg > credit_avg:
        #         debit_rulesets.append(rs)
        #     else:
        #         nostat_rulesets.append(rs)
        # else:

        #     if rs.direction == ProtoTransaction.DIRECTION_CREDIT:
        #         credit_rulesets.append(rs)
        #     elif rs.direction == ProtoTransaction.DIRECTION_DEBIT:
        #         debit_rulesets.append(rs)


    # credit_rulesets = [ rs for rs in transactionrulesets_manual 
    #                    if rs.prototransaction_safe() 
    #                    and 'average_for_month' in rs.prototransaction.stats['credit'] 
    #                    and 'average_for_month' in rs.prototransaction.stats['debit'] 
    #                    and rs.prototransaction.stats['credit']['average_for_month'] is not None 
    #                    and rs.prototransaction.stats['debit']['average_for_month'] is not None 
    #                    and abs(rs.prototransaction.stats['credit']['average_for_month']) > abs(rs.prototransaction.stats['debit']['average_for_month']) 
    # ]
    # debit_rulesets = [ rs for rs in transactionrulesets_manual 
    #                   if rs.prototransaction_safe() 
    #                     and 'average_for_month' in rs.prototransaction.stats['credit'] 
    #                     and 'average_for_month' in rs.prototransaction.stats['debit'] 
    #                     and rs.prototransaction.stats['credit']['average_for_month'] is not None 
    #                     and rs.prototransaction.stats['debit']['average_for_month'] is not None 
    #                     and abs(rs.prototransaction.stats['credit']['average_for_month']) < abs(rs.prototransaction.stats['debit']['average_for_month']) 
    # ]
    # nostat_rulesets = [ rs for rs in transactionrulesets_manual 
    #                    if rs.id not in [ r.id for r in credit_rulesets ] and rs.id not in [ r.id for r in debit_rulesets ] ]

    return {
        'credit_stats': ruleset_stats(credit_rulesets),
        'credit_rulesets': _ruleset_by_criticality(sorted(credit_rulesets, key=lambda t: t.priority, reverse=False)),
        'debit_stats': ruleset_stats(debit_rulesets),
        'debit_rulesets': _ruleset_by_criticality(sorted(debit_rulesets, key=lambda t: t.priority, reverse=False)),        
        'nostat_rulesets': _ruleset_by_criticality(sorted(nostat_rulesets, key=lambda t: t.priority, reverse=False)),    
    }

def _ruleset_by_criticality(ruleset):
    return { c[1]: [ r for r in ruleset if r.prototransaction.criticality == c[0] ] for c in TransactionTypes.criticality_choices }

def ruleset_stats(rulesets):
    
    total_earn = sum([ (trs.prototransaction_safe() and trs.prototransaction.average_for_month(ProtoTransaction.DIRECTION_CREDIT)) or 0 for trs in rulesets if trs.prototransaction.is_active ])
    total_spend = sum([ (trs.prototransaction_safe() and trs.prototransaction.average_for_month(ProtoTransaction.DIRECTION_DEBIT)) or 0 for trs in rulesets if trs.prototransaction.is_active ])
    total_records = sum([ len(transactionruleset.records(refresh=True)) for transactionruleset in rulesets if transactionruleset.prototransaction_safe() and transactionruleset.prototransaction.is_active ])

    return {
        'totals': {
            'earn': total_earn,
            'spend': total_spend,
            'total': total_earn + total_spend,
            'records': total_records
        }
    }    

def get_records_template_data(filtered_records):
    '''Extraction from database and conversion to view template'''

    template_data = {}

    if len(filtered_records) > 0:

        total = sum([ r.amount for r in filtered_records])

        desc_stats = [
            {
                'full_description': desc,
                'stats': { 
                    'percentage': 100*sum([ r.amount for r in filtered_records if r.full_description() == desc ])/total, 
                    'sum': sum([ r.amount for r in filtered_records if r.full_description() == desc ]),
                    'count': len([ r for r in filtered_records if r.full_description() == desc ])
                } 
            } for desc in set([ o.full_description() for o in filtered_records ])
        ]
        
        date_list = [ r.transaction_date for r in filtered_records ]
        
        # -- stats 
        amount_sum = sum([ r.amount for r in filtered_records ])
        earliest_date = min(date_list)
        latest_date = max(date_list)
        earliest_date_formatted = datetime.strftime(earliest_date, '%m/%d/%Y')
        latest_date_formatted = datetime.strftime(latest_date, '%m/%d/%Y')        
        days = (latest_date - earliest_date).total_seconds()*1.0 / (60*60*24) + 1
        months = days / 30        
        records_per_month = len(filtered_records) / months

        template_data = {
            'amount_sum': amount_sum,
            'distinct_names': sorted(desc_stats, key=lambda a: a['stats']['sum'], reverse=True),
            'earliest_date': earliest_date_formatted,
            'latest_date': latest_date_formatted,
            'days': f'{days:.1f}',
            'months': f'{months:.1f}',
            'records_per_month': f'{records_per_month:.1f}'
        }
    
    return template_data

def _floatify(val):
    return float(str(val).replace('$', '').replace(',', '').replace('"', '') or 0.00)

def _must_amount(record, flow_convention):

    # -- all record types so far have either amount or gross - OR - debit+credit
    flow_based_fields = ['amount', 'gross']
    explicit_fields = ['debit', 'credit']
    
    amount = _floatify(0)

    for f in flow_based_fields + explicit_fields:
        if f in record:
            amount = _floatify(record[f])
            if amount:
                if (f == 'debit' and amount > 0) or (f == 'credit' and amount < 0):
                    amount = -amount 
                elif f in flow_based_fields and flow_convention == RecordFormat.FLOW_CONVENTION_REVERSE:
                    amount = -amount 
                break 
    
    return amount

def alphaize_filename(filename):
    nums = re.findall('[0-9]+', filename)
    nums.sort(key=lambda a: int(a), reverse=True)
    for n in nums:
        filename = filename.replace(n, '')
    return filename.replace('-', '').replace('_', '')

def base64_encode(val, truncate_digits=16):
    return base64.standard_b64encode(bytes(val, 'utf-8')).decode()[0:truncate_digits]

def _process_records(records, csv_date_format, flow_convention):
    '''Field conversions, formatting (and potentially additions)'''

    # -- expand and amend particular fields 
    # -- we can normalize between multiple fields (description <-- description || name)
    # -- parse date strings into Date objects or float values from strings 
    # -- we expand everything we got (i.e. CSV columns)
    # -- and overwrite the only non-FK Record fields with massaged values     
    processed_records = [ {
        **record['record_dict'],
        'description': record['record_dict']['description'].replace('\t', '') if 'description' in record['record_dict'] else record['record_dict']['name'].replace('\t', ''),
        'transaction_date': datetime.strptime(record['record_dict']['transaction_date'], csv_date_format) if 'transaction_date' in record['record_dict'] else datetime.strptime(record['record_dict']['date'], csv_date_format),
        'post_date': datetime.strptime(record['record_dict']['post_date'] if 'post_date' in record['record_dict'] else record['record_dict']['date'] if 'date' in record['record_dict'] else record['record_dict']['posting_date'], csv_date_format),
        'amount': _must_amount(record['record_dict'], flow_convention),
        'raw_data_line': record['raw_data_line']
    } for record in records if 'status' not in record['record_dict'] or record['record_dict']['status'].lower() != "pending" ]

    # -- just more conditional post-processing
    for processed_record in processed_records:
        for float_potential in ['credits', 'debits']:
            if float_potential in processed_record:
                processed_record[float_potential] = _floatify(processed_record[float_potential])
    
    return processed_records 

def process_file(uploadedfile):
    '''Processes the provided file and saves the resulting records'''
    details = process_uploaded_file(uploadedfile)    
    logger.info(f'Reprocessing {uploadedfile.original_filename}/{uploadedfile.account_name()} found {len(details["records"])} records')    
    logger.info(f'Saving {len(details["records"])} records from reprocessing uploaded file {uploadedfile.original_filename}')
    save_processed_records(details['records'], uploadedfile)

def cleanup_file(uploadedfile):
    '''Deletes all database records associated with the provided file'''
    db_records = uploadedfile.records.all()
    logger.warning(f'Deleting {len(db_records)} from {uploadedfile.account_name()} -- {len(db_records)} currently in database')
    db_records.delete()

def process_uploaded_file(uploaded_file):
    '''Ingestion of CSV file to database'''

    try:
        file_contents = uploaded_file.upload.read().decode('utf-8').split('\n')
    except:
        raise Exception("Could not read and parse the uploaded file contents")

    this_format = None 

    if uploaded_file.account:
        this_format = uploaded_file.account.recordformat 
    elif uploaded_file.creditcard:
        this_format = uploaded_file.creditcard.recordformat 
    elif uploaded_file.header_included:
        first_line = file_contents[0]
        cleaned_tokens = ",".join([ t.strip().lower().replace(' ', '_').replace('/', '_') for t in first_line.split(',') ])
        formats = RecordFormat.objects.filter(csv_columns=cleaned_tokens)
        
        if len(formats) > 1:
            raise Exception("CSV columns in the provided file match more than one record format on file")
        if len(formats) == 0:
            this_format = RecordFormat.objects.create(
                name=alphaize_filename(uploaded_file.original_filename), 
                csv_columns=cleaned_tokens
            )
        if len(formats) == 1:
            this_format = formats[0]
    
    records = [] 

    try:
        # -- do a little preprocessing so we can avoid duplicating uploaded files 
        # -- the existence of a composite object with the record information + the raw data line exists only between these
        # -- two function calls.. after _process_records() we have pure Record type dicts
        raw_records = get_record_dicts_and_raw_data_lines_from_csv(file_contents, this_format.csv_columns.split(','), uploaded_file.header_included)
        if len(raw_records) == 0:
            raise Exception(f'No records found in {uploaded_file.name}')
        records = _process_records(raw_records, this_format.csv_date_format, this_format.flow_convention)
    except:      
        error_msg = f'{sys.exc_info()[0]} {sys.exc_info()[1]}'
        logger.error(error_msg)
        traceback.print_tb(sys.exc_info()[2])  
        raise Exception(f'No records could be processed from this uploaded file: {error_msg}')
        # logger.warning(f'failed to process with assigned record type, will try amex basic and combined (god help you if these are not amex transactions)')
        # basic_recordformat = Recordformat.objects.filter(name='amex basic').first()
        # combined_recordformat = Recordformat.objects.filter(name='amex combined').first()
        # for t in [ t for t in [basic_recordformat, combined_recordformat] if t ]:
        #     try:                
        #         logger.warning(f'failed, will try again with {t.name}: {t.csv_columns}')
        #         raw_records = get_records_from_csv(file_contents, t.csv_columns.split(','), header_included)
        #         records = _process_records(raw_records, t.csv_date_format)
        #         break 
        #     except:
        #         logger.warning(f'processing records with {t.name} failed')

    records_dates = [ r['transaction_date'] for r in records ]
    first_date = min(records_dates)
    last_date = max(records_dates)

    return {
        'first_date': first_date,
        'last_date': last_date,
        'records': records,
        'recordformat': this_format
    } 

def save_processed_records(records, uploadedfile):

    for record in records:

        try:

            found_by_raw_data_line = Record.objects.filter(raw_data_line=record['raw_data_line']).first()
            found_by_raw_data_line_hash = Record.objects.filter(raw_data_line_hash=record_hash(record['raw_data_line'])).first()

            was_found_by_raw_data_line = False 

            if found_by_raw_data_line:
                was_found_by_raw_data_line = True 
                logger.info(f'Found existing records based on the raw data line: {found_by_raw_data_line.id}')                
            if found_by_raw_data_line_hash:
                was_found_by_raw_data_line = True 
                logger.info(f'Found existing records based on the HASHED raw data line: {found_by_raw_data_line_hash.id}')

            if was_found_by_raw_data_line:
                continue 

            # potential_record_form = RecordForm(record)
            
            # -- the filter will not find database records unless the types match exactly
            lookup_dict = { 
                f: Decimal(str(record[f])) if f == 'amount' 
                    else datetime.strftime(record[f], '%Y-%m-%d') if f.find('_date') > 0 
                    else record[f] 
                for f in ['transaction_date', 'post_date', 'description', 'amount']
            }

            # extra_fields_lookups = {
            #     f'extra_fields__{f}': potential_record_form.instance.extra_fields[f]
            #     for f in potential_record_form.instance.extra_fields.keys()
            # }

            # lookup_dict.update(extra_fields_lookups)

            # lookup_dict = { 
            #     f: record[f] 
            #     for f in record.keys() 
            #     if f in [ 'transaction_date', 'post_date', 'description', 'amount' ] 
            # }

            logger.debug(f'looking up record with {lookup_dict}')

            db_records = Record.objects.filter(**lookup_dict) # transaction_date=record['transaction_date'], post_date=record['post_date'], description=record['description'], amount=Decimal(record['amount']))

            if len(db_records) > 0:
                logger.info(f'will attempt record validate and save, but {len(db_records)} match(es) ({",".join([ str(r.id) for r in db_records ]) }) found for {record}')
                # -- if there is only one, we can assume the incoming raw data line is actually this one 
                # if len(db_records) == 1:
                #     logger.warning(f'single core fields match record {db_records[0].id} already has raw_data_line: {db_records[0].raw_data_line}')
                #     if not db_records[0].raw_data_line:
                #         logger.warning(f'single core fields match record {db_records[0].id} no raw_data_line, setting to {record["raw_data_line"]}')
                #         db_records[0].raw_data_line = record['raw_data_line']
                #     logger.warning(f'saving single core fields match record {db_records[0].id}')
                #     db_records[0].save()
                # else:
                #     logger.warning(f'MULTIPLE_CORE_FIELDS_MATCH_TO_ONE_RAW_LINE')
                #     for db_record in db_records:
                #         logger.warning(f'checking extra fields between {db_record.extra_fields} and incoming {record}')
                #         extra_field_matches = [ ef in record and record[ef] == db_record.extra_fields[ef] for ef in db_record.extra_fields.keys() ]
                #         if all(extra_field_matches):
                #             logger.warning(f'all extra fields matched, setting raw_data_line here')
                #             db_record.raw_data_line = record['raw_data_line']
                #             db_record.save()                            
                #         else:
                #             logger.warning(f'not all extra fields matched')                        
                # continue 

            record_data = { 
                **record, 
                'uploaded_file': uploadedfile
            }
            
            # formatted
            # logger.debug(json.dumps({ k: str(v) for k,v in record_data.items() }, indent=4))
            # one-line
            logger.debug({ k: str(v) for k,v in record_data.items() })
            
            record_form = RecordForm(record_data)
            record_form.is_valid()
            if record_form.errors:
                logger.warning(record_form.errors)
            record_form.save()

        except ValidationError as ve:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])
        except:
            logger.error(sys.exc_info()[0])
            logger.error(sys.exc_info()[1])
            traceback.print_tb(sys.exc_info()[2])

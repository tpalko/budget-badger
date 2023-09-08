import json 
import re
import base64
from web.util.stats import nearest_whole
from web.util.recordgrouper import RecordGrouper
from web.util.modelutil import TransactionTypes
from django.core.exceptions import ValidationError
from web.util.csvparse import get_records_from_csv
from web.models import UploadedFile, Record, Transaction, RecordFormat
from web.forms import RecordForm

from datetime import datetime, timedelta
import logging 
import sys 
import traceback 


logger = logging.getLogger(__name__)

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
        
    weekdays = [ datetime.strftime(d, "%a") for d in date_list ]
    weekday_heatmap = { j: weekdays.count(j) for j in set(weekdays) }
    weekday_heatmap_normalized = { j: nearest_whole(weekday_heatmap[j]*100.0/len(filtered_records)) for j in weekday_heatmap }

    day_list = [ d.day for d in date_list ]
    day_set = list(set(day_list))
    day_set.sort()
    heatmap = { str(day): day_list.count(day) for day in day_set }
    
    heatmap_normalized = { n: nearest_whole(heatmap[n]*100.0/len(filtered_records)) for n in heatmap }

    heatmap_region_lookup = _get_heatmap_region_lookup(heatmap, heatmap_normalized)

    all_weekdays = [ datetime.strftime(datetime.strptime(str(0), "%w") + timedelta(days=w), "%a") for w in range(7) ]

    return {
        'heatmap_normalized': heatmap_normalized,
        'heatmap': heatmap,
        'heatmap_region_lookup': heatmap_region_lookup,
        'weekday_heatmap': weekday_heatmap,
        'weekday_heatmap_normalized': weekday_heatmap_normalized,
        'all_weekdays': all_weekdays
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

def ruleset_stats(rulesets):
    
    total_amount = sum([ transactionruleset.prototransaction_safe().stats['monthly_amount'] for transactionruleset in rulesets if transactionruleset.prototransaction_safe() ])
    total_records = sum([ len(transactionruleset.records()) for transactionruleset in rulesets ])

    return {
        'totals': {
            'amount': total_amount,
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
                'description': desc,
                'stats': { 
                    'percentage': 100*sum([ r.amount for r in filtered_records if r.description == desc ])/total, 
                    'sum': sum([ r.amount for r in filtered_records if r.description == desc ]),
                    'count': len([ r for r in filtered_records if r.description == desc ])
                } 
            } for desc in set([ o.description for o in filtered_records ])
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
    records = [ {
        **record,
        'description': record['description'].replace('\t', '') if 'description' in record else record['name'].replace('\t', ''),
        'transaction_date': datetime.strptime(record['transaction_date'], csv_date_format) if 'transaction_date' in record else datetime.strptime(record['date'], csv_date_format),
        'post_date': datetime.strptime(record['post_date'] if 'post_date' in record else record['date'] if 'date' in record else record['posting_date'], csv_date_format),
        'amount': _must_amount(record, flow_convention)        
    } for record in records ]

    # -- just more conditional post-processing
    for record in records:
        for float_potential in ['credits', 'debits']:
            if float_potential in record:
                record[float_potential] = _floatify(record[float_potential])
    
    return records 

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
        raw_records = get_records_from_csv(file_contents, this_format.csv_columns.split(','), uploaded_file.header_included)
        records = _process_records(raw_records, this_format.csv_date_format, this_format.flow_convention)
    except e:      
        logger.error(f'{sys.exc_info()[0]} {sys.exc_info()[1]}')
        traceback.print_tb(sys.exc_info()[2])  
        raise Exception(f'No records could be processed from this uploaded file: {e}')
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
            record_data = { 
                **record, 
                'uploaded_file': uploadedfile,
                # 'account': uploadedfile.account,
                # 'creditcard': uploadedfile.creditcard,
                'description': record['description'] or ''
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

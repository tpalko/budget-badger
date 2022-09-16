import json 
from web.util.stats import nearest_whole
from web.util.recordgrouper import RecordGrouper

from web.models import UploadedFile, Record, Transaction, RecordGroup
from datetime import datetime, timedelta
import logging 

UPLOADED_FILE_DEFAULT_COLUMNS = "account,transaction,transaction_date,post_date,description,amount,extra_fields"
CREDITCARD_COLUMNS = "creditcard,transaction_date,post_date,description,amount,extra_fields"

logger = logging.getLogger(__name__)

def transaction_type_display(transaction_type):
    return [ choice_tuple[1] for choice_tuple in Transaction.type_choices if choice_tuple[0] == transaction_type ][0]

def _get_heatmap_region_lookup(heatmap):
                
    heatmap_region_lookup = {}
    region_index = 0
    in_region = False
    gap_threshold = 2
    gap = 0
    for day in [ str(day) for day in range(1, 32) ]:
        if day in heatmap and int(heatmap[day]) > 0:
            gap = 0
            if not in_region:
                in_region = True 
                region_index += 1
            # if region_index not in heatmap_regions:
            #     heatmap_regions[region_index] = []
            heatmap_region_lookup[day] = region_index
        else:
            heatmap_region_lookup[day] = 0
            gap += 1
            if gap >= gap_threshold and in_region:
                in_region = False 

    return heatmap_region_lookup

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
    
    heatmap_region_lookup = _get_heatmap_region_lookup(heatmap)

    heatmap_normalized = { n: nearest_whole(heatmap[n]*100.0/len(filtered_records)) for n in heatmap }

    all_weekdays = [ datetime.strftime(datetime.strptime(str(0), "%w") + timedelta(days=w), "%a") for w in range(7) ]

    return {
        'heatmap_normalized': heatmap_normalized,
        'heatmap': heatmap,
        'heatmap_region_lookup': heatmap_region_lookup,
        'weekday_heatmap': weekday_heatmap,
        'weekday_heatmap_normalized': weekday_heatmap_normalized,
        'all_weekdays': all_weekdays
    }

def get_recordgroup_data():
    record_groups = []
    all_recordgroups = RecordGroup.objects.all()
    record_group_columns = ""
    if len(all_recordgroups) > 0:
        logger.warning(f'Getting stats for {len(all_recordgroups)} record groups')
        record_groups_with_stats = [ RecordGrouper.get_record_group_stats(rg.id) for rg in all_recordgroups ]
        logger.warning(f'Sorting {len(record_groups_with_stats)} record groups with stats')
        record_groups = sorted(record_groups_with_stats, key=lambda rg: rg['record_count'], reverse=True)
        record_group_exclude_columns = ['records']
        
        if len(record_groups) > 0:
            record_group_columns = ",".join([ k for k in record_groups[0].keys() if k not in record_group_exclude_columns ])

    return {
        'record_groups': record_groups,
        'record_group_columns': record_group_columns
    }

def get_records_template_data(filtered_records):
    '''Extraction from database and conversion to view template'''

    template_data = {
        'account_columns': UPLOADED_FILE_DEFAULT_COLUMNS,
        'creditcard_columns': CREDITCARD_COLUMNS
    }

    if len(filtered_records) > 0:
        
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
            **template_data,
            'stats': {
                'amount_sum': amount_sum,
                'earliest_date': earliest_date_formatted,
                'latest_date': latest_date_formatted,
                'days': f'{days:.1f}',
                'months': f'{months:.1f}',
                'records_per_month': f'{records_per_month:.1f}',
            }
        }
    
    return template_data
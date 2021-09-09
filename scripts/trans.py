#!/usr/bin/env python3 

import sys 
import json

from datetime import datetime, timedelta
import numpy as np
import csvparse


def split_accounts(tran):
    '''
    Flags (for non-transfer transactions that occur under a single header):
        - multiple amounts, each one occurring multiple times and roughly the same number of times
        - more transactions in a period of time that would qualify as bi-weekly or even weekly 
        - multiple distinct groupings of payment dates 
    '''
    
    accounts = []
    
    split_threshold = 28
    date_grouping_attempts = [ 365, 180, 90, 60, 30, 15 ]
    if all([ t == 'DEBIT' for t in tran['type'] ]) and len(tran['date']) > split_threshold:
        
        print(f"more than {split_threshold} transactions and all DEBIT.. attempt to split..")
        # dates = sorted([ int(datetime.strftime(d, '%d')) for d in [ datetime.strptime(d, "%m/%d/%y") for d in tran['date'] ] if datetime.now() - d < timedelta(days=90) ])
        # amounts = sorted([ abs(float(a)) for a in tran['amount'] ])
        
        grouping_data = {}
        for grouping_attempt in date_grouping_attempts:
            recent_amounts = sorted([ abs(float(r['amount'])) for r in tran['_records'] if datetime.now() - datetime.strptime(r['date'], "%m/%d/%y") < timedelta(days=grouping_attempt) ])
            data = np.array(recent_amounts)
            grouping_data[grouping_attempt] = { '_count': len(data) }
            if len(data) > 1:
                amount_groups = np.split(data, np.where(np.diff(data) != 0)[0]+1)
                print(f'At {grouping_attempt} found {len(amount_groups)} groups')
                # print(amount_groups)
                # print([ len(g) for g in amount_groups ])
                grouping_data[grouping_attempt]['_groups'] = len(amount_groups)
                grouping_data[grouping_attempt]['_group_lengths'] = { g[0]: len(g) for g in amount_groups }
            elif len(data) == 1:
                print(f'At {grouping_attempt}, there is one record')
                print(data)
                grouping_data[grouping_attempt]['_groups'] = 1
                grouping_data[grouping_attempt]['_group_lengths'][data[0]] = 1
            else:
                print(f'At {grouping_attempt}, there are no records')
                grouping_data[grouping_attempt]['_groups'] = 0
                grouping_data[grouping_attempt]['_group_lengths'] = {}
        print(json.dumps(grouping_data, indent=4))
                
                
        # print(dates)
        # print(amounts)
        
        date_data = np.array(dates)
        amount_data = np.array(amounts)
        
        date_groups = np.split(date_data, np.where(np.diff(date_data) > 3)[0]+1)
        amount_groups = np.split(amount_data, np.where(np.diff(amount_data) != 0)[0]+1)
        
        print(f'date groups: {date_groups}')
        print(f'amount_groups: {amount_groups}')
        
        accounts.append(tran)
        
    else:
        accounts.append(tran)
    
    return accounts 
    
def get_timings(dates):
    
    sorted_dates = sorted([ datetime.strptime(d, "%m/%d/%y") for d in dates ])
    print([ datetime.strftime(d, "%m/%d/%y") for d in sorted_dates ])
    
    dates_of_month = [ int(datetime.strftime(d, '%d')) for d in sorted_dates ]
    
    date_counts = {}
    for d in dates_of_month:
        if d not in date_counts:
            date_counts[d] = 0
        date_counts[d] += 1
    
    most_frequent_date = sorted(date_counts, key=lambda d: date_counts[d], reverse=True)[0]
    most_frequent_date_occurrence = date_counts[most_frequent_date]
    most_frequent_date_probability = most_frequent_date_occurrence*100.0 / len(dates_of_month)
    earliest_date = min(dates_of_month)
    
    dates = sorted([ int(datetime.strftime(d, '%d')) for d in [ datetime.strptime(d, "%m/%d/%y") for d in dates ] if datetime.now() - d < timedelta(days=90) ])
    avg_gap = 0
    if len(dates) > 1:
        date_data = np.array(dates)
        avg_gap = np.average(np.diff(date_data)[0])
    
    frequency = 'unknown'
    
    if avg_gap > 12 and avg_gap < 16:
        frequency = 'bi-weekly'
    elif avg_gap > 25 and avg_gap < 40:
        frequency = 'monthly'
    elif avg_gap > 70 and avg_gap < 100:
        frequency = 'quarterly'
        
    return frequency, most_frequent_date, most_frequent_date_probability, earliest_date

def get_avg_amount(amounts):
    abs_amounts = [ abs(a) for a in amounts ]
    avg_amount = "%.2f" % (sum(abs_amounts)*1.0 / len(abs_amounts))
    # , 'min': min(abs_amounts), 'max': max(abs_amounts)
    return avg_amount

def get_cat(tran):
    all_debit = all([ t == 'DEBIT' for t in tran['type'] ])
    all_dd = all([ t == 'DIRECT DEPOSIT' for t in tran['type'] ])
    count = tran['_count']
    cat = 'unknown'
    if all_dd:
        cat = 'income'
    elif all_debit and count >= 3:
        cat = 'utility'
    return cat
    
def run(transactionfile):

    records = []
    with open(transactionfile, 'r') as f:        
        records = csvparse.get_records(f.read())

    counts = {}
    # -- it may be helpful to organize by something other than description 
    # -- date or amount, if description or date/amount (other) pattern could be seen 
    # -- description assumes all transactions share this for an "account"
    top_headers = ['description']
    # -- sub headers are anything we can use to further break out lines of accounting 
    # -- logic below will omit matching top/sub headers
    sub_headers = ['type', 'date', 'description', 'amount']

    for h in top_headers:
        sel_sub_headers = [ c for c in sub_headers if c != h ]
        counts[h] = {}
        for val in [ r[h] for r in records if r['type'] != 'CHECK' ]:
            #print(f"Parsing {h}: {val}..")
            if val not in counts[h]:
                val_records = [ r for r in records if r[h] == val ]
                counts[h][val] = { '_count': len(val_records), '_records': sorted(val_records, key=lambda r: datetime.strptime(r['date'], "%m/%d/%y")) }
                # - convenience mappings 
                for subh in sel_sub_headers:
                    counts[h][val][subh] = [ r[subh] for r in val_records ]
    
    # trans = {}
    for desc in counts['description']:
        # if 'brightwheel' not in desc:
        #     continue
        print(desc)
        trans = counts['description'][desc]
        print(json.dumps(trans['_records'], indent=4))
        
        accounts = split_accounts(trans)
        print("")
        
        for account in accounts:
        
            print(f'transactions: {account["_count"]}')
        
            cat = get_cat(account)
            print(f'cat: {cat}')
            frequency, most_frequent_date, most_frequent_date_probability, earliest_date = get_timings(account['date'])
            print(f'freq: {frequency}')
            avg_amount = get_avg_amount(account['amount'])
        
            entry = {'name': desc, 'avg_amount': avg_amount, 'common date': f'{most_frequent_date} ({most_frequent_date_probability}%)', 'earliest date': earliest_date}
        
            print(entry)
            # if cat not in trans:
            #     trans[cat] = {}
            # if frequency not in trans[cat]:
            #     trans[cat][frequency] = []
            # 
            # trans[cat][frequency].append(entry)
            print("")
    
    # print(json.dumps(trans, indent=4))
    '''
    utilities
        - type: all debit, count: 3+
        - capture frequency, date range and earliest date
            - if irregular frequency, may be multiple accounts 
                - sort by date and walk, look for pattern
        - capture average amount, min, max 
        
    income
        - type: all direct deposit, 3+
    
    old 
        - 3+, last date > 3 months ago 
        
    scheduled transfers 
        - by description, type: all transfer
        - dates should all match or be close 
        - amounts should be exact
    '''
    #print(sorted(counts['amount']))
    #print(json.dumps(counts, indent=4))
if __name__ == "__main__":
    run(sys.argv[1])

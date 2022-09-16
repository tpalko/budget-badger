#!/usr/bin/env python3 

import sys 
import os 

from django.db.models import Q
import django
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'budget.settings_dev'
django.setup()

import json
from web.models import RecordGroup, Record, TransactionRuleSet
from datetime import datetime, timedelta
import numpy as np
import logging 

logger = logging.getLogger(__name__)

class RecordGrouper(object):
    
    # # -- records_by_header is a convenince mapping for all records, primarily by description and then for each distinct description: type, date, amount
    # records_by_header = None 
    # # -- accounts is a list of distinct entities with which transactions occur: billers, other accounts, including typical/likely payment information
    # accounts = None 
    # # -- accounts_by_transaction_type are accounts grouped by transaction_type and frequency of transaction
    # accounts_by_transaction_type = None 

    def __init__(self, *args, **kwargs):
        pass 
        # self.accounts = []
        # self.accounts_by_transaction_type = {}
        # self.records_by_header = {}

    @staticmethod
    def _split_accounts(tran):
        '''
        Flags (for non-transfer transactions that occur under a single header):
            - multiple amounts, each one occurring multiple times and roughly the same number of times
            - more transactions in a period of time that would qualify as bi-weekly or even weekly 
            - multiple distinct groupings of payment dates 
        '''
        
        accounts = []
        
        if len(set(tran['type'])) == 1:
            

            grouping_data = {}
            date_grouping_attempts = [ 365, 180, 90, 60, 30, 15 ]
            for grouping_attempt in date_grouping_attempts:
                # -- collect and sort the amounts only for the records in the last <grouping_attempt> days 
                amounts_in_window = sorted([ float(r.amount) for r in tran['_records'] if datetime.now().date() - r.transaction_date < timedelta(days=grouping_attempt) ])
                grouping_data[grouping_attempt] = { '_count': len(amounts_in_window), '_groups': 0, '_group_lengths': {} }

                if len(amounts_in_window) == 0:
                    # print(f'No records found in {grouping_attempt} days, skipping the rest')
                    break 

                data = np.array(amounts_in_window)
                
                # -- if we have multiple records 
                # if len(data) > 0:
                    # -- with sorted data, this will condense any repeated values into groups 
                amount_groups = np.split(data, np.where(np.diff(data) != 0)[0]+1)
                # print(f'In {grouping_attempt} days, found {len(amount_groups)} groups ({",".join([ str(g[0]) for g in amount_groups ])})')
                # print(amount_groups)
                # print([ len(g) for g in amount_groups ])
                grouping_data[grouping_attempt]['_groups'] = len(amount_groups)
                grouping_data[grouping_attempt]['_group_lengths'] = { g[0]: len(g) for g in amount_groups }
                # elif len(data) == 1:
                #     print(f'In {grouping_attempt} days, there is one record')
                #     # print(data)
                #     grouping_data[grouping_attempt]['_groups'] = 1
                #     grouping_data[grouping_attempt]['_group_lengths'][data[0]] = 1

            # print(json.dumps(grouping_data, indent=4))
                    
            # print(dates)
            # print(amounts)
            
            dates_in_month = sorted([ int(datetime.strftime(d, '%d')) for d in tran['date'] ]) # if datetime.now().date() - d < timedelta(days=90) ])
            amounts = sorted([ float(a) for a in tran['amount'] ])

            date_data = np.array(dates_in_month)
            amount_data = np.array(amounts)
            
            date_groups = np.split(date_data, np.where(np.diff(date_data) > 3)[0]+1)
            amount_groups = np.split(amount_data, np.where(np.diff(amount_data) != 0)[0]+1)
            
            # print(f'date groups: {date_groups}')
            # print(f'amount_groups: {amount_groups}')
            
            accounts.append(tran)
            
        else:
            accounts.append(tran)
        
        return accounts 
        
    @staticmethod
    def _get_timings(dates):

        sorted_dates = sorted([ d for d in dates ])
        # print([ datetime.strftime(d, "%m/%d/%y") for d in sorted_dates ])
        
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
        
        # dates = sorted([ int(datetime.strftime(d, '%d')) for d in dates if datetime.now().date() - d < timedelta(days=90) ])
        avg_gap = 0
        five_percent = 0
        ten_percent = 0
        if len(dates) > 1:
            date_data = np.array(sorted(dates))
            day_gaps = [ abs(d.days) for d in np.diff(date_data) ]
            avg_gap = np.average(day_gaps)
            five_percent = 100*sum([ 1 for g in day_gaps if g >= avg_gap*.95 and g <= avg_gap*1.05 ]) / len(day_gaps)
            ten_percent = 100*sum([ 1 for g in day_gaps if g >= avg_gap*.90 and g <= avg_gap*1.1 ]) / len(day_gaps)

        frequency = 'unknown'
        
        if avg_gap > 12 and avg_gap < 16:
            frequency = 'bi-weekly'
        elif avg_gap > 25 and avg_gap < 40:
            frequency = 'monthly'
        elif avg_gap > 70 and avg_gap < 100:
            frequency = 'quarterly'
            
        return {
            'average_gap': f'{avg_gap:.0f} days',
            'five_percent': f'{five_percent:.0f}%',
            'ten_percent': f'{ten_percent:.0f}%',
            'period': frequency, 
            'most_frequent_date': most_frequent_date, 
            'most_frequent_date_probability': most_frequent_date_probability, 
            'earliest_date': earliest_date,
            'started_at': datetime.strftime(sorted_dates[0], "%m/%d/%Y")
        }

    @staticmethod 
    def _remove_outliers(array):
        if len(array) < 2:
            return array 
        array = sorted(array)
        # print(array)
        # print(len(array))
        median = int(len(array)/2)
        # print(median)
        Q1 = np.median(array[0:median])
        Q3 = np.median(array[median:])
        # print(f'Q1: {Q1} ({type(Q1)}) Q3: {Q3} ({type(Q3)})')
        IQR = float(Q3 - Q1)
        fence_margin = 1.5*IQR 
        # print(f'IQR: {IQR} ({type(IQR)}), fence margin: {fence_margin} ({type(fence_margin)})')
        upper_fence = float(Q3) + fence_margin
        lower_fence = float(Q1) - fence_margin
        # print(f'upper: {upper_fence} / lower: {lower_fence}')
        kept = [ a for a in array if float(a) >= lower_fence and float(a) <= upper_fence ]
        left = [ a for a in array if float(a) < lower_fence and float(a) > upper_fence ]
        return kept, left 
    
    @staticmethod
    def _get_amount_stats(records, remove_outliers=False):
        '''
        if count over a threshold
        and amounts are variable 
        and histogram has a clear winner (not multiple bins scoring in a similar range)
        
        '''
        
        recent_records = sorted(records, key=lambda r: r.transaction_date, reverse=True)
        recent_amounts = [ float(abs(r.amount)) for r in recent_records ]
        
        sorted_amounts = sorted([ float(abs(r.amount)) for r in records ])
        amount_bins = np.split(sorted_amounts, np.where(np.diff(sorted_amounts) > np.average(sorted_amounts)*.1)[0]+1)
        bin_edges = [ min(bin) for bin in amount_bins ]
        bin_edges.append(max(amount_bins[-1]))

        now = datetime.now()
        relevance_timer = timedelta(days=365).total_seconds()
        weights = [ (relevance_timer - (now.date() - r.transaction_date).total_seconds()) / relevance_timer for r in recent_records ]
        weights = [ w if w>=0 else 0 for w in weights ]
        
        hist, bins = np.histogram(recent_amounts, weights=weights)

        low = bins[hist.argmax()]
        high = bins[hist.argmax() + 1]

        recurring_amount = max([ a for a in sorted_amounts if a >= low and a <= high ] or [0])

        removed_outliers_count = 0
        if remove_outliers:
            amounts_removed_outliers, left = RecordGrouper._remove_outliers(recent_amounts)
            removed_outliers_count = len(left)

        return {
            'recent_amounts': recent_amounts,
            'weights': weights,
            'hist': [ float(h) for h in list(hist) ],
            'bins': list(bins),
            'recurring_amount': recurring_amount,
            'min_amount': min(sorted_amounts),
            'max_amount': max(sorted_amounts),
            'avg_amount': np.average(sorted_amounts),
            'outliers_removed': removed_outliers_count,
            'is_variable': len(set(recent_amounts)) > 1
        }

    @staticmethod
    def _guess_transaction_type(records):
        # -- in: income, misc cash, transfer
        # -- out: utility, credit card, transfer
        all_debit_check = all([ r.type in ['DEBIT','CHECK'] for r in records ])
        all_dd = all([ r.type == 'DIRECT DEPOSIT' for r in records ])
        all_income = all([ r.amount > 0 for r in records ])

        count = len(records)
        cat = 'unknown'
        if all_dd or all_income:
            cat = 'income'
        elif all_debit_check and count >= 3:
            cat = 'utility'
        return cat
    
    @staticmethod 
    def get_stats(records):
        '''Collect enough information about the given set of records to populate a transaction form.'''

        '''
            name: description 
            amount:    
                - bin up recent amounts, take highest value from most populated bin                 
            started_at: earliest date 
            period:
                - bin up periods (see notes elsewhere on guessing period)
            cycle_due_date: earliest date of region 
            transaction_type: (see notes elsewhere on guessing type)
            is_variable: useless?
            is_active: any transaction within a recency threshold depending on the determined period 

            a collection of records possibly represents multiple transactions 
                - amount
                - date 
        '''

        transaction_type = RecordGrouper._guess_transaction_type(records)
        
        timings = RecordGrouper._get_timings([ r.transaction_date for r in records ])        
        amount_stats = RecordGrouper._get_amount_stats(records)
        
        descriptions = [ r.description or '' for r in records ]
        description_set = list(set(descriptions))
        description = description_set[np.array([ descriptions.count(d) for d in description_set ]).argmax()]
        
        # ['name', 'amount', 'transaction_type', 'is_active', 'is_imported', 'period', 'started_at', 'cycle_due_date', 'is_variable'
        '''
            the stats dict returned here directly informs the TransactionIntakeForm
            which is designed to be a catch-all form for any kind of transaction type
            whatever fields sent here that match will show as form fields 
            everything else will show as "stats" to inform the user 
            based on the transaction_type submitted (guessed at here, confirmed on the page)
            the correct, specific transaction form is then shown 
            and fields sent here will inform that one as well

            type:
                utility 
                income
                debt
                credit card 
            recurring 

            if record count > 3, 10% date consistency toleration is > 55% 
            or if record count > 1, 10% date consistency toleration is 100% 
            

        '''
        return {
            'description': description,             
            'transaction_type': transaction_type, 
            'record_count': len(records),            
            **amount_stats,
            **timings
        }

    @staticmethod
    def get_record_group_stats(record_group_id, ignore_cache=False, dry_run=False):
        '''Spaghetti logic to support non-destructive testing'''

        recordgroup = RecordGroup.objects.get(pk=record_group_id)
        
        stats = None 

        # -- will always compute stats (when needed) during normal operation
        # -- and can be forced to compute to test new code 
        if not recordgroup.stats or ignore_cache:
            records = Record.objects.filter(record_group=record_group_id)
            stats = RecordGrouper.get_stats(records)
        
        # -- will always save stats if they've been computed during normal operation 
        # -- and save can be skipped to test new code 
        if not dry_run and stats:
            recordgroup.stats = stats 
            recordgroup.save()

        # -- results of latest code always returns during testing 
        # -- and when computed during normal operation 
        # -- model field is there otherwise 
        return stats or recordgroup.stats
    
    @staticmethod 
    def get_record_rule_index():
        rule_sets = [ [ r.id for r in trs.records() ] for trs in TransactionRuleSet.objects.all() ]
        record_ids = set([ i for s in rule_sets for i in s ])
        return { str(i): len([ s for s in rule_sets if i in s ]) for i in record_ids }
        
    @staticmethod
    def group_records(force_regroup_all=False):
        '''Create and assign RecordGroups for distinct record descriptions'''
        
        # -- by default this function will only process records without an assigned record group 
        if force_regroup_all:
            RecordGroup.objects.all().delete()            
        
        records = Record.objects.filter(Q(record_group__isnull=True) & ~Q(extra_fields__type="TRANSFER"))
        record_rule_index = RecordGrouper.get_record_rule_index()

        logger.warning(record_rule_index)

        logger.warning(f'{len(records)} records')
        total_amount = sum([ r.amount for r in records ])
        records = [ r for r in records if str(r.id) not in record_rule_index or record_rule_index[str(r.id)] == 0 ]
        logger.warning(f'{len(records)} records')
        unaccounted_amount = sum([ r.amount for r in records ])

        for description in set([ r.description or '' for r in records ]):

            # -- if we want to enable 'split accounts' again 
            # -- this is what it consumes 
            # account = {
            #     '_count': len(desc_records),
            #     '_records': sorted(desc_records, key=lambda r: r.date)
            # }
            # for subh in ['type', 'date', 'amount']:
            #     account[subh] = [ r.__getattribute__(subh) for r in desc_records ]
            
            desc_records = sorted([ r for r in records if description in [r.description, ''] ], key=lambda r: r.transaction_date)
            # record_stats = RecordGrouper.get_stats(desc_records)

            record_group = RecordGroup.objects.filter(name=description).first()

            if not record_group:
                record_group = RecordGroup.objects.create(name=description)

            for record in desc_records:
                record.record_group = record_group 
                record.save()

        # # -- multi-stage account identification 
        # # -- stage 1: by description 
        # for desc in self.records_by_description:
            
        #     description_records = self.records_by_description[desc]
            
        #     # -- stage 2: within a description, could there be multiple transaction groupings?
        #     accounts = self._split_accounts(description_records)

        #     # -- stage 3: (TODO) without a description, can we find patterns in amounts and dates 

        #     # -- one 'account' here is a best attempt at a Transaction/RecurringTransaction, etc. 
        #     for account in accounts:

        #         # -- what do we actually want?
        #         # the period of the data 
        #         # if data is roughly periodic, we can expect 
        #         # - the average of date diffs to be roughly the period 
        #         #       - may need to drop outliers 
        #         #       - st. dev. may be helpful?
        #         #       - instead of average, binned values / histogram 
        #         # - most diffs to fall within a margin of the actual period 
        #         #       - reverse calculate a margin of what value most diffs fall within ? 
        #         #       - again, histogram?

        #         # -- sort dates and get deltas between them 
        #         # -- generate histogram or maybe just bin edges for deltas  

        #         # -- pull together as much pertinent information to fill in TransactionForm

        #         record_group = RecordGroup.objects.create(name=desc)
        #         for record in account["_records"]:
        #             record.record_group = record_group 
        #             record.save()

        #         # account_entry = self.get_record_group_stats(record_group.id)

        #         # self.accounts.append(account_entry)
            
        #         # if transaction_type not in self.accounts_by_transaction_type:
        #         #     self.accounts_by_transaction_type[transaction_type] = []
        #         # self.accounts_by_transaction_type[transaction_type].append(account_entry)
        
if __name__ == "__main__":

    # -- 27, 28, 33, 40
    record_groups = RecordGroup.objects.all()

    for record_group in [ g for g in record_groups ]: # if g.id in [27, 28, 33, 40] ]:
        stats = RecordGrouper.get_record_group_stats(record_group.id, ignore_cache=True, dry_run=True)
        print(f'Record group: {record_group.name} ({record_group.id})')
        print(json.dumps(stats, indent=4))

#!/usr/bin/env python3 

from decimal import InvalidOperation
import sys 
import math
import os 
import traceback 

from django.db.models import Q

import django
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'budget.settings_dev'
django.setup()

from django.conf import settings 

import json
from web.models import Record, RecordMeta, TransactionRuleSet, ProtoTransaction, TransactionRule
from web.util.modelutil import TransactionTypes
from web.util.ruleindex import get_rule_index
import web.util.dates as utildates
from datetime import datetime, timedelta
import numpy as np
import logging 

logger = logging.getLogger(__name__)
stats_logger = logging.getLogger('stats')

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
    def _get_period_for_gap(gap):
        period = TransactionTypes.PERIOD_UNKNOWN
        for p in utildates.period_day_ranges.keys():
            low, high = utildates.period_day_ranges[p]
            if gap >= low and gap < high:
                period = p
                break 
        return period

    @staticmethod 
    def _get_recency_weights(time_sorted_records):
        now = datetime.now()
        relevance_timer = timedelta(days=settings.CONFIG.INACTIVE_DAYS).total_seconds()
        # -- build list of weights corresponding to records, from 1 (now) to zero (relevance_timer ago)
        weights = [ (relevance_timer - (now.date() - r.transaction_date).total_seconds()) / relevance_timer for r in time_sorted_records ]
        # -- no negatives
        # logger.warning(f'timing weights: {weights}')
        weights = [ w if w>=0 else 0 for w in weights ]
        # logger.warning(f'timing weights: {weights}')
        return weights 

    @staticmethod 
    def _get_values_in_winning_bin(values, weights):
        hist, bins = np.histogram(values, weights=weights)
        low = bins[hist.argmax()]
        high = bins[hist.argmax() + 1]

        stats_logger.debug(f'low: {low} high: {high}')

        return [ a for a in values if a >= low and a <= high ]

    @staticmethod
    def _get_timings(records):

        # sorted_dates = sorted([ d for d in dates ])
        # print([ datetime.strftime(d, "%m/%d/%y") for d in sorted_dates ])
        
        # dates_of_month = [ int(datetime.strftime(d, '%d')) for d in sorted_dates ]
        
        # date_counts = {}
        # for d in dates_of_month:
        #     if d not in date_counts:
        #         date_counts[d] = 0
        #     date_counts[d] += 1
        
        # most_frequent_date = sorted(date_counts, key=lambda d: date_counts[d], reverse=True)[0]
        # most_frequent_date_occurrence = date_counts[most_frequent_date]
        # most_frequent_date_probability = most_frequent_date_occurrence*100.0 / len(dates_of_month)
        
        # -- questionable.. if the span of dates wraps around the turn of the month
        # earliest_date = min(dates_of_month)
        
        # dates = sorted([ int(datetime.strftime(d, '%d')) for d in dates if datetime.now().date() - d < timedelta(days=90) ])
        now = datetime.now()

        '''
        -70
            20
        -50
            10
        -40
            10
        -30
            10
        -20
            10
        -10
        '''
        recent_records = sorted(records, key=lambda r: r.transaction_date, reverse=False)
        recent_dates = [ r.transaction_date for r in recent_records ]
        recent_dates_from_now = np.array(recent_dates)
        # recent_dates_from_now.extend(recent_dates)
        stats_logger.debug(f'recent dates: {recent_dates_from_now}')
        recent_dates_gaps = [ g.total_seconds()/(60*60*24) for g in np.diff(recent_dates_from_now) ]
        stats_logger.debug(f'recent dates gaps: {recent_dates_gaps}')

        avg_gap = np.average(recent_dates_gaps)
        
        # relevance_timer = timedelta(days=365).total_seconds()
        # -- build list of weights corresponding to records, from 1 (now) to zero (relevance_timer ago)
        # weights = [ (relevance_timer - (now.date() - r.transaction_date).total_seconds()) / relevance_timer for r in recent_records ]
        # -- no negatives
        # stats_logger.warning(f'timing weights: {weights}')
        # weights = [ w if w>=0 else 0 for w in weights ]
        # stats_logger.warning(f'timing weights: {weights}')

        weights = RecordGrouper._get_recency_weights(recent_records)

        stats_logger.debug(f'weights: {weights}')

        is_active = False 
        high_period = None 
        low_period = None 
        period = TransactionTypes.PERIOD_UNKNOWN 
        low_gap = None 
        high_gap = None     

        # -- if there's at least one nonzero weight 
        if not all([ w == 0 for w in weights ]):

            gaps_in_bin = RecordGrouper._get_values_in_winning_bin(recent_dates_gaps, weights[0:-1])

            # -- get the max of all the amounts in the winning bin
            low_gap = min(gaps_in_bin or [0])
            high_gap = max(gaps_in_bin or [0])

            stats_logger.debug(f'binned gaps: {gaps_in_bin} ({low_gap}/{high_gap})')

            low_period = RecordGrouper._get_period_for_gap(low_gap)
            high_period = RecordGrouper._get_period_for_gap(high_gap)

            if low_period == high_period:
                period = low_period 
            elif low_period == TransactionTypes.PERIOD_UNKNOWN:
                period = high_period
            elif high_period == TransactionTypes.PERIOD_UNKNOWN:
                period = low_period

            is_active = True 

        started_at = None 
        ended_at = None 

        if len(recent_dates) > 0:
            started_at = datetime.strftime(recent_dates[0], "%m/%d/%Y") if len(recent_dates) > 0 else None
            ended_at = datetime.strftime(recent_dates[-1], "%m/%d/%Y") if len(recent_dates) > 0 else None
        
        return {
            'average_gap': f'{avg_gap:.0f} days',
            'low_period': low_period, 
            'high_period': high_period, 
            'low_period_days': low_gap,
            'high_period_days': high_gap,
            'period': period, 
            'timing_is_active': is_active,
            # 'most_frequent_date': most_frequent_date, 
            # 'most_frequent_date_probability': most_frequent_date_probability, 
            # 'earliest_date': earliest_date,
            'started_at': started_at,
            'ended_at': ended_at
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

        recent_records = sorted(records, key=lambda r: r.transaction_date, reverse=True)
        recent_amounts = [ float(r.amount) for r in recent_records ]        
        monthly_spend = 0

        if len(recent_records) > 0:
            end = recent_records[0].transaction_date
            start = recent_records[-1].transaction_date 
            range_seconds = (end - start).total_seconds()
            of_month = (range_seconds*1.0) / (60*60*24*30)

            total_amount = sum(recent_amounts)

            monthly_spend = total_amount 

            if len(recent_records) > 1:
                if of_month >= 3:
                    monthly_spend = total_amount / of_month
                elif of_month >= 1:
                    pass 
                    # -- default to total.. up to 2 months
            
            stats_logger.info(f'total: {total_amount} over {range_seconds} seconds')
        # -- fancy custom binning, but uncooperative distributions spoil it
        # amount_bins = np.split(sorted_amounts, np.where(np.diff(sorted_amounts) > np.average(sorted_amounts)*.1)[0]+1)
        # bin_edges = [ min(bin) for bin in amount_bins ]
        # bin_edges.append(max(amount_bins[-1]))

        # now = datetime.now()
        # relevance_timer = timedelta(days=365).total_seconds()
        # -- build list of weights corresponding to records, from 1 (now) to zero (relevance_timer ago)
        # weights = [ (relevance_timer - (now.date() - r.transaction_date).total_seconds()) / relevance_timer for r in recent_records ]
        # -- no negatives
        # weights = [ w if w>=0 else 0 for w in weights ]
        
        weights = RecordGrouper._get_recency_weights(recent_records)

        is_active = False 
        recurring_amount = 0

        if not all([ w == 0 for w in weights ]):
            
            # -- get the max of all the amounts in the winning bin
            recurring_amount = max(RecordGrouper._get_values_in_winning_bin(recent_amounts, weights) or [0])

            is_active = True 

        removed_outliers_count = 0
        if remove_outliers:
            amounts_removed_outliers, left = RecordGrouper._remove_outliers(recent_amounts)
            removed_outliers_count = len(left)

        return {
            # 'recent_amounts': recent_amounts,
            # 'weights': weights,
            # 'hist': [ float(h) for h in list(hist) ],
            # 'bins': list(bins),
            'monthly_amount': monthly_spend,
            'recurring_amount': recurring_amount,
            # 'min_amount': min(recent_amounts),
            # 'max_amount': max(recent_amounts),
            'avg_amount': np.average(recent_amounts) if len(recent_amounts) > 0 else 0,
            'outliers_removed': removed_outliers_count,
            'is_variable': len(set(recent_amounts)) > 1,
            'amount_is_active': is_active
        }

    @staticmethod
    def _guess_transaction_type(records):
        
        cat = TransactionTypes.TRANSACTION_TYPE_UNKNOWN
        count = len(records)

        # -- in: income, misc cash, transfer
        # -- out: utility, credit card, transfer
        all_debit_check = all([ 'type' in r.extra_fields and r.extra_fields['type'] in ['DEBIT','CHECK'] for r in records ])
        all_dd = all([ 'type' in r.extra_fields and r.extra_fields['type'] == 'DIRECT DEPOSIT' for r in records ])
        all_income = all([ r.amount > 0 for r in records ])
        # all_expense = all([ r.amount < 0 for r in records ])        
        all_cc = all([ any([ r.description.lower().find(cc) >= 0 for cc in ['american express', 'chase', 'synchrony', 'citibank'] ]) for r in records ])
        
        if count == 1:
            cat = TransactionTypes.TRANSACTION_TYPE_SINGLE
        elif all_cc and all_debit_check:
            cat = TransactionTypes.TRANSACTION_TYPE_CREDITCARD
        elif all_dd or all_income:
            cat = TransactionTypes.TRANSACTION_TYPE_INCOME
        elif all_debit_check:
            cat = TransactionTypes.TRANSACTION_TYPE_UTILITY # or DEBT 
        
        return cat
    
    @staticmethod 
    def get_meaningful_stats(records):
        recent_records = sorted(records, key=lambda r: r.transaction_date, reverse=False)
        recent_records_dates = [ r.transaction_date for r in recent_records ]
        recent_dates_np = np.array(recent_records_dates)
        
        recent_dates_gaps = [ g.total_seconds()/(60*60*24) for g in np.diff(recent_dates_np) ]
        
        weights = RecordGrouper._get_recency_weights(recent_records)
        
        timing_bins = [
            0, # -- start of daily
            5, # -- start of weekly
            10, # -- start of bi-weekly
            20, # -- start of monthly
            40, # -- dead space between monthly and semi-annually
            160, # -- start of semi-annually
            200, # -- dead space between semi-annually and annually
            300, # -- start of annually
            400 
        ]

        DAILY = 0
        WEEKLY = 1
        BIWEEKLY = 2
        MONTHLY = 3

        if len(recent_dates_gaps) == 0:
            logger.warning(f'no gaps!')
            return 
            
        hist, bins = np.histogram(recent_dates_gaps, bins=timing_bins) #, weights=weights[0:-1])

        # nonzero_buckets = [ h for h in hist if h > 0 ]

        dist = [ int(float(f'{n/sum(hist):.2f}')*100) for n in hist ]

        # bucket_count_over_threshold = { 
        #     t*10: [ b for b in dist if b >= t*10 and b < (t+1)*10 ]
        #     for t in range(11) }

        logger.debug(json.dumps([ datetime.strftime(d, "%Y-%m-%d") for d in recent_records_dates ], indent=2))
        logger.debug(f'recent_dates_gaps {recent_dates_gaps}')
        logger.debug(f'hist {hist}')
        logger.debug(f'bins {bins}')
        logger.debug(f'dist {dist}')

        '''
        - one record = single
        - 100% in one bucket = periodic
        - between 30-50% in each of two buckets separated by at least one bucket, no more than 20% in any other
            - OR >= 40% in one bucket and no more than 20% in at least one other separated by at least one bucket
            - OR <= 20% in any bucket
            - AND at least one every 30 days on average = chaotic frequent
            - AND less than = chaotic rare
        '''

        # if any([ d for d in dist if d >= 90 ]):

        # logger.debug(json.dumps(bucket_count_over_threshold, indent=2))

    @staticmethod 
    def get_stats(records):

        stats = {
            'record_count': len(records),
            'record_ids': ",".join([ str(r.id) for r in records ]),
            'description': ''
        }

        # if len(records) == 0:
        #     raise InvalidOperation(f'No records provided')

        '''Collect enough information about the given set of records to populate a transaction form.'''

        '''
            required:
                amount:    
                    - bin up recent amounts, take highest value from most populated bin                 
                account:            
                    - 
                period:
                    - bin up periods (see notes elsewhere on guessing period)
                transaction_type: 
                    - (see notes elsewhere on guessing type)

            name: description 
            cycle_due_date: earliest date of region 
            started_at: earliest date 
            is_variable: useless?
            is_active: any transaction within a recency threshold depending on the determined period 

            a collection of records possibly represents multiple transactions 
                - amount
                - date 
        '''

        stats['transaction_type'] = RecordGrouper._guess_transaction_type(records)
        
        '''
        8/31/2023

        timings and amounts are pretty closely related, they shouldn't be separated here
        what we want to figure out from this set of records is
        1. what amount, if any, can be reliably thought of in monthly terms
        2. if not periodically at all, what is the timing?
            a. periodic - a repeating charge at a regular pace
            b. chaotic frequent - no identifiable period but frequent enough to have a monthly average
            c. chaotic rare - no identifiable period and more often than not longer than 45 days between
            d. single - one record
        3. will it occur again, or is this spending/income in the past?

        - find the gap distribution and fit it into a profile        
            - one record = single
            - 100% in one bucket = periodic
            - between 30-50% in each of two buckets separated by at least one bucket, no more than 20% in any other
                - OR >= 40% in one bucket and no more than 20% in at least one other separated by at least one bucket
                - OR <= 20% in any bucket
                - AND at least one every 30 days on average = chaotic frequent
                - AND less than = chaotic rare
        - answer #2 
        - if periodic or chaotic frequent, find a monthly amount
        - compare time since last record with the gap distribution and answer #3
        - store appropriate values in prototransaction.stats
            - first record at
            - last record at
            - record count
            - some info about the gap distribution
            - timing 
            - is_active
        
        '''

        stats = { **stats, **RecordGrouper._get_timings(records) }
        stats = { **stats, **RecordGrouper._get_amount_stats(records) }

        RecordGrouper.get_meaningful_stats(records)
        
        if len(records) > 0:
            descriptions = [ r.description or '' for r in records ]
            description_set = list(set(descriptions))
            stats['description'] = description_set[np.array([ descriptions.count(d) for d in description_set ]).argmax()]
        
        stats['accounts'] = list(set([ str(r.uploaded_file.account) for r in records if r.uploaded_file.account ]))
        stats['creditcards'] = list(set([ str(r.uploaded_file.creditcard) for r in records if r.uploaded_file.creditcard ]))

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

        stats_logger.debug(f'Stats returned: {json.dumps(stats, sort_keys=True, indent=2)}')
        return stats

    # @staticmethod
    # def get_record_group_stats(record_group_id, ignore_cache=False, dry_run=False):


    #     recordgroup = RecordGroup.objects.get(pk=record_group_id)
    #     stats = None 

    #     # -- vvv Spaghetti logic to support non-destructive testing vvv

    #     # -- will always compute stats (when needed) during normal operation
    #     # -- and can be forced to compute to test new code 
    #     if not recordgroup.stats or ignore_cache:
    #         records = Record.objects.filter(record_group=record_group_id)
    #         stats = RecordGrouper.get_stats(records)
        
    #     # -- will always save stats if they've been computed during normal operation 
    #     # -- and save can be skipped to test new code 
    #     if not dry_run and stats:
    #         recordgroup.stats = stats 
    #         recordgroup.save()

    #     # -- results of latest code always returns during testing 
    #     # -- and when computed during normal operation 
    #     # -- model field is there otherwise 
    #     return stats or recordgroup.stats
    
    @staticmethod
    def filter_accounted_records(records, less_than_priority=None, is_auto=None, refresh_cache=True, refresh_records=True):
        

        '''
        To get to this point (See models.records_from_rules)
        1. get the rules in a rule set
        2. construct a big query 
        3. execute the query
        4. pass the records in here
        vvvv -- CACHE this result by priority + is_auto 
        5. get ALL rule sets, pare down to those at a higher (1 is highest) priority and by user/machine (is_auto)
        6. get ALL records for remaining rule sets into a lookup dict with rule set ID -> its record IDs
        7. combine and flatten record IDs to get distinct set of records
        8. make a lookup dict with record ID -> rule set IDs it is contained within
        ^^^^ -- end CACHE 
        9. filter out any records in that lookup dict from the records passed in here 

        '''
        tx_rule_sets = TransactionRuleSet.objects.all()

        rule_index = get_rule_index(
            tx_rule_sets=tx_rule_sets,
            lt_priority=less_than_priority, 
            is_auto=is_auto, 
            refresh_cache=refresh_cache, 
            refresh_records=refresh_records
        )

        # -- this is the actual removal of accounted records 
        pared = [ r for r in records if str(r.id) not in rule_index ]
        logger.info(f'Pared {len(records)} records to {len(pared)} by {len(rule_index)} accounted')

        '''
        TODO: RecordMeta.is_accounted should be integer, not boolean
        when we calculate a set of records that is accounted (the keys of rule_index here) 
        _less than a priority_, is_accounted should be set to that priority. Future queries 
        can come in with a priority that...
        '''
        return pared 

    @staticmethod 
    def _prototransaction_rule_attempt(match_operator, match_value):

        is_modified_description = False 

        while match_value != '' and match_value.lower() not in ['the', 'to', 'a']:
            
            yield is_modified_description, {
                'record_field': 'description',
                'match_operator': match_operator,
                'match_value': match_value            
            }

            match_value = ' '.join(match_value.strip().split(' ')[0:-1]).strip()
            match_operator = TransactionRule.MATCH_OPERATOR_CONTAINS_HUMAN
            is_modified_description = True 
        
    @staticmethod
    def group_records(force_regroup_all=False, is_auto=None):
        '''Create and assign RecordGroups for distinct record descriptions'''

        # -- MANUAL rule sets

        if is_auto is None or not is_auto:
                
            manual_rule_sets = TransactionRuleSet.objects.filter(is_auto=False).order_by('priority')
            for rule_set in manual_rule_sets:
                logger.debug(f'recalculating stats for manual rule set {rule_set.name} with priority {rule_set.priority}')
                records = rule_set.records(refresh=True)
                records = RecordGrouper.filter_accounted_records(
                    records, 
                    less_than_priority=rule_set.priority, 
                    is_auto=False)
                
                stats = RecordGrouper.get_stats(records)
                # stats = { k: stats[k] if stats[k] and stats[k] != "NaN" else 0 for k in stats.keys() }
                # logger.debug(f'avg amount -- {stats["avg_amount"]}')
                # logger.debug(f'stats for {rule_set.name}: {json.dumps(stats, indent=4)}')
                # del stats['avg_amount']
                proto_transaction = ProtoTransaction.objects.filter(transactionruleset=rule_set).first()
                if proto_transaction:
                    proto_transaction.update_stats(stats)
                    proto_transaction.save()
                else:
                    proto_transaction = ProtoTransaction.new_from(rule_set.name, stats, rule_set)

            logger.info(f'All done regrouping manual rule sets!')    

        # -- AUTO rule sets 

        if is_auto is None or is_auto:
                
            # -- by default this function will only process records without an assigned record group 
            if force_regroup_all:
                TransactionRuleSet.objects.filter(is_auto=True).delete()
            
            true_loop = 1

            while True:
                
                records = Record.budgeting.all()
                
                # logger.warning(f'{len(records)} records')
                # total_amount = sum([ r.amount for r in records ])

                # -- filter out records which are accounted for already by rules/rulesets 
                # TODO: unfortunately, even though we remove records already accounted
                # for in rule sets, this auto-grouping method may ultimately match those records 
                # because we modify (shorten) the working description to find matches
                # we can continue to limit these records below as they are found, but which 
                # grouping should "win" and own a record? arguably the user groups (manual) should have 
                # their own priority ranking and only allow any one record to be a part of one group
                # and any records left over can live in multiple auto groups? however if we want to eventually
                # elevate the auto groups and prototransactions to take part in forecasting/projection, a
                # single group-per-record must be held everywhere 
                records = RecordGrouper.filter_accounted_records(records)

                logger.debug(f'True loop {true_loop} -- Using {len(records)} records as as base for description matching')
                true_loop += 1

                # logger.warning(f'{len(records)} records')

                # unaccounted_amount = sum([ r.amount for r in records ])

                # -- 
                reset_loop = False 

                # -- this is a rough method to get initial groups together.. 
                # -- maybe in a few cases another feature would be better 
                # -- checks have no description, so maybe go for all checks first and group by amount
                distinct_descriptions = set([ r.description or '' for r in records ])
                distinct_description_length = len(distinct_descriptions)

                logger.debug(f'Have {distinct_description_length} distinct descriptions')

                for i, description in enumerate(distinct_descriptions, 1):

                    logger.info(f'Trying description "{description}" {i}/{distinct_description_length}')

                    # -- if we want to enable 'split accounts' again 
                    # -- this is what it consumes 
                    # account = {
                    #     '_count': len(desc_records),
                    #     '_records': sorted(desc_records, key=lambda r: r.date)
                    # }
                    # for subh in ['type', 'date', 'amount']:
                    #     account[subh] = [ r.__getattribute__(subh) for r in desc_records ]
                    
                    # desc_records = sorted([ r for r in records if description in [r.description, ''] ], key=lambda r: r.transaction_date)
                    # record_stats = RecordGrouper.get_stats(desc_records)

                    # proto_transaction = ProtoTransaction.objects.filter(name=description).first()

                    # if not proto_transaction:
                    
                    '''
                    the idea here is:
                        - make a rule set, placeholder for now
                        - fetch records, perform stats on records, and if stats are sufficient, make a prototransaction
                        - starting with `description = description`
                        - and progressively truncating as `description contains [description minus one word]`
                        - if nothing works, delete the placeholder rule set 
                    '''
                    transaction_rule_set = TransactionRuleSet.objects.create(
                        name=description, 
                        join_operator=TransactionRuleSet.JOIN_OPERATOR_AND, 
                        is_auto=True
                    )
                    logger.info(f'Created rule set {transaction_rule_set.id}')
                    
                    match_operator = TransactionRule.MATCH_OPERATOR_EQUALS_HUMAN
                    match_value = description 

                    proto_transaction = None 
                    
                    for is_modified_description, rule_attempt in RecordGrouper._prototransaction_rule_attempt(match_operator, match_value):
                        
                        TransactionRule.objects.create(transactionruleset=transaction_rule_set, **rule_attempt)
                        transaction_rule_set.refresh_from_db()
                        logger.debug("\n".join([ str(r) for r in transaction_rule_set.transactionrules.all() ]))
                        
                        records = transaction_rule_set.records(refresh=True)
                        records = RecordGrouper.filter_accounted_records(records)

                        logger.info(f'Attempting rule {rule_attempt} -> {len(records)} records')
                        logger.debug("\n".join([ str(r) for r in records ]))

                        # record_rule_index = RecordGrouper.get_record_rule_index(refresh=True)                    
                        # records = [ r for r in records if str(r.id) not in record_rule_index or record_rule_index[str(r.id)] == 0 ]
                        # logger.warning(f'Removed used records and now have {len(records)}')
                        
                        try:
                            stats = RecordGrouper.get_stats(records)

                            logger.debug(stats)

                            required_fields = ['timing_is_active', 'amount_is_active', 'recurring_amount', 'transaction_type', 'period', 'record_count']
                            for f in required_fields:
                                if not stats[f]:
                                    raise ValueError(f'The stats calculated are insufficient. Reason: {f} = {stats[f]}.')
                            
                            proto_transaction = ProtoTransaction.new_from_rule_attempt(rule_attempt, stats, transaction_rule_set)
                            
                            logger.info(f'Seems ok.. made prototransaction {proto_transaction.id}')
                            reset_loop = is_modified_description
                            break 
                        
                        except KeyError as ke:
                            raise ke 

                        except:
                            logger.error(sys.exc_info()[0])
                            logger.error(sys.exc_info()[1])
                            traceback.print_tb(sys.exc_info()[2])
                            logger.warning(f'Deleting all rules from transactionruleset {transaction_rule_set.name}')
                            transaction_rule_set.transactionrules.all().delete()

                    # -- if we made a prototransaction
                    # -- and it was from a modified description
                    # -- we need to break to the outer forever loop and recpature a fresh set of descriptions to work with 
                    if proto_transaction:
                        if reset_loop:
                            logger.debug(f'Prototransaction was made modifying the description, starting over')
                            break 
                        else:
                            logger.debug(f'Prototransaction was made without modification to description')
                    else:
                        logger.warning(f'No prototransaction could be created, deleting the rule set and moving on')
                        transaction_rule_set.delete()

                # -- if we're here not because we created a prototransaction with a modified description
                # -- and needed to recapture a fresh set of descriptions to work with 
                # -- but rather, we just ran out of descriptions
                # -- then quit for good 
                if not reset_loop:
                    logger.debug(f'Done with that set of descriptions, and breaking out of True since we finished naturally')
                    break 
                else:
                    logger.debug(f'Done with descriptions, but taking another pass since a description was modified')

            logger.info(f'All done regrouping auto rule sets!')    

                    # record_group = RecordGroup.objects.filter(name=description).first()

                    # if not record_group:
                    #     record_group = RecordGroup.objects.create(name=description)

                    # for record in desc_records:
                    #     record.record_group = record_group 
                    #     record.save()

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
            
# if __name__ == "__main__":




#     match = sys.argv[1]

#     # -- 27, 28, 33, 40
#     record_groups = RecordGroup.objects.all()

#     for record_group in [ g for g in record_groups ]: # if g.id in [27, 28, 33, 40] ]:
#         stats = RecordGrouper.get_record_group_stats(record_group.id, ignore_cache=True, dry_run=True)
#         print(f'Record group: {record_group.name} ({record_group.id})')
#         print(json.dumps(stats, indent=4))

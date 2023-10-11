#!/usr/bin/env python3 

from decimal import InvalidOperation
import sys 
import math
import os 
import traceback 
from contextlib import contextmanager

from django.db.models import Q

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'budget.settings_dev'

from django.conf import settings 

import django
django.setup()

import json
from web.models import Record, UploadedFile, TransactionRuleSet, ProtoTransaction, TransactionRule
from web.util.modelutil import TransactionTypes
from web.util.ruleindex import get_record_rule_index
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
    def _get_values_in_winning_bin(hist, bins, values):
        # hist, bins = np.histogram(values, bins=bins, weights=weights)
        low = bins[hist.argmax()]
        high = bins[hist.argmax() + 1]

        stats_logger.debug(f'low: {low} high: {high}')

        return [ int(a) for a in values if a >= low and a <= high ], hist.argmax()

    @staticmethod 
    def _get_values_in_largest_bin(hist, bins, values):

        bincount = None 
        na = list(hist)
        if all([ v == 0 for v in na ]):
            return None 
        
        bin_index = len(hist) - 1

        while True:
            bincount = na.pop()
            if bincount > 0 or bin_index == 0:
                break 
            bin_index -= 1

        return [ int(a) for a in values if a >= bins[bin_index] and a <= bins[bin_index + 1] ], bin_index 
    
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

            hist, bins = np.histogram(recent_dates_gaps, weights=weights[0:-1])
            gaps_in_bin, winning_bin_index = RecordGrouper._get_values_in_winning_bin(hist, bins, recent_dates_gaps)

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
            hist, bins = np.histogram(recent_amounts, weights=weights)
            recurring_amount, winning_bin_index = max(RecordGrouper._get_values_in_winning_bin(hist, bins, recent_amounts) or [0])

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
    def months(stop_after_passing_date):
    
        now = datetime.now()
        year = now.year 
        month = now.month

        while True:
                    
            month_start = datetime.strptime(f'{year}-{month}-1', '%Y-%m-%d')

            next_month = month + 1
            next_year = year 
            if next_month > 12:
                next_month = 1
                next_year = year + 1

            month_end = datetime.strptime(f'{next_year}-{next_month}-1', '%Y-%m-%d')

            yield month_start, month_end

            if month_start.date() < stop_after_passing_date:
                break 

            month = month - 1
            if month == 0:
                month = 12
                year = year - 1        
                
    @staticmethod
    def record_magnitude(records):
        '''For given records, returns the absolute magnitude of all'''

        return sum([ abs(r.amount) for r in records ])

    @staticmethod
    def record_split(records):
        '''For given records, returns the split of credit and debit records'''

        credit_records = [ r for r in records if r.amount > 0 ]
        debit_records = [ r for r in records if r.amount < 0 ]

        return credit_records, debit_records

    @staticmethod
    def record_magnitude_split(records):
        '''For given records, returns credit sum, credit count, debit sum, debit count'''

        credit_records, debit_records = RecordGrouper.record_split(records)

        total_credit = RecordGrouper.record_magnitude(credit_records)
        total_debit = RecordGrouper.record_magnitude(debit_records)

        return total_credit, len(credit_records), total_debit, len(debit_records)

    @contextmanager
    def timer(event_name):
        start = datetime.utcnow()
        yield 
        end = datetime.utcnow()
        logger.debug(f'{event_name}: {(end - start).total_seconds()}s')

    @staticmethod 
    def get_monthly_stats(rule_set):
        '''Iterate back through all records, month by month, tallying credit and debit sums'''

        # misses = 0
        monthly_stats = []

        first_record = rule_set.records().order_by('transaction_date').first()

        if not first_record:
            return monthly_stats 
        
        rule_index = get_record_rule_index(TransactionRuleSet.objects.all(), rule_set.priority, False, False)
        records = rule_set.records(refresh=False) # .filter(transaction_date__gte=month_start, transaction_date__lt=month_end)
        records, removed = RecordGrouper.filter_accounted_records(
            records=records,
            filter_by_rule_index=rule_index,
            less_than_priority=rule_set.priority,
            is_auto=False,
            refresh_cache=False
        )

        for month_start, month_end in RecordGrouper.months(first_record.transaction_date):

            # records, removed, recent_records = None, None, None

            # with RecordGrouper.timer('fetching month of records'):    
            #     records = rule_set.records(refresh=False).filter(transaction_date__gte=month_start, transaction_date__lt=month_end)

            # if len(records) == 0:
            #     misses += 1

            # with RecordGrouper.timer('filtering accounted-filtered records by month'):
            month_filtered_records = [ r for r in records if r.transaction_date >= month_start.date() and r.transaction_date < month_end.date() ]

            # with RecordGrouper.timer('filtering accounted records with prefetched rule index'):
            #     records, removed = RecordGrouper.filter_accounted_records(
            #         records=records, 
            #         filter_by_rule_index=rule_index,
            #         less_than_priority=rule_set.priority, 
            #         is_auto=False,
            #         refresh_cache=False)

            # with RecordGrouper.timer('sorting filtered records for recency'):
            recent_records = sorted(month_filtered_records, key=lambda r: r.transaction_date, reverse=False)

            # credit_sum, credit_count, debit_sum, debit_count = 0, 0, 0, 0

            # with RecordGrouper.timer('splitting recent records for magnitude and count'):
            credit_sum, credit_count, debit_sum, debit_count = RecordGrouper.record_magnitude_split(recent_records)

            # of_month = 0

            # if len(recent_records) > 1:
            #     start = recent_records[0].transaction_date
            #     end = recent_records[-1].transaction_date 
            #     range_seconds = (end - start).total_seconds()
            #     of_month = (range_seconds*1.0) / (60*60*24*30)

            # for d in amount_split.keys():
            #     if len(amount_split[d]['amounts']) > 1:
            #         if of_month >= 0.8:
            #             amount_split[d]['monthly_average'] = sum(amount_split[d]['amounts']) / of_month
            #         else: 
            #             amount_split[d]['monthly_average'] = sum(amount_split[d]['amounts'])
            #     else:
            #         amount_split[d]['monthly_average'] = 0

            #         # elif of_month >= 0.8:
            #         #     amounts[d]['monthly_average'] = sum(amounts[d])

            monthly_stats.append({
                'month': datetime.strftime(month_start, "%Y-%m"),
                'debit': -float(debit_sum),
                'credit': float(credit_sum),
                'debit_count': debit_count,
                'credit_count': credit_count
            })

            # if misses >= break_after_misses:
            #     break 
        
        return monthly_stats

    @staticmethod 
    def get_meaningful_stats(records):

        '''
            is it active?
                find the typical gap between records 
                find the latest record in this set
                find the latest imported date shared by all accounts/cards represented in this set 
                if the latest imported date is later than that latest record by more than 10% greater than the typical gap
                it's inactive 

            if active, what is the expected amount per week, month, year?
                if the records are frequent and fairly regular, (total / days) * 30 = monthly
                if spanning a year or more, do some months total more by a significant amount? does this bear out for the same month over years?
                if not so frequent, bin up the gaps. if there's a clear winner on the order of weekly, biweekly, monthly, etc. this is the overall period
                if too scattered, bin up the amounts first and then bin up the gaps within the amount bins
                if there's a clear winner, the records in this amount bin may be grouped separately 

        '''

        stats = {
            'messages': [],
            'debit': {},
            'credit': {}
        }
        
        credit_records, debit_records = RecordGrouper.record_split(records)

        split_sets = {
            'debit': debit_records,
            'credit': credit_records
        }

        timing_bins = list(TransactionTypes.PERIOD_TIMING_BINS_LOOKUP.keys())

        for split_key in split_sets.keys():
            records = split_sets[split_key]
            split_stats = {
                'messages': []
            }

            if len(records) < 2:
                split_stats['messages'].append(f'{split_key} record count {len(records)} does not allow for stats calculations')
                logger.warning(split_stats['messages'])                      

            else:
                    
                recent_records = sorted(records, key=lambda r: r.transaction_date, reverse=False)
                recent_records_dates = [ r.transaction_date for r in recent_records ]
                recent_dates_np = np.array(recent_records_dates)
                
                recent_dates_gaps = [ g.total_seconds()/(60*60*24) for g in np.diff(recent_dates_np) ]
                
                # weights = RecordGrouper._get_recency_weights(recent_records)
                
                # DAILY = 0
                # WEEKLY = 1
                # BIWEEKLY = 2
                # MONTHLY = 3

                hist, bins = np.histogram(recent_dates_gaps, bins=timing_bins) #, weights=weights[0:-1])
                common_gaps, winning_bin_index = RecordGrouper._get_values_in_winning_bin(hist, bins, recent_dates_gaps)
                biggest_gaps, biggest_bin_index = RecordGrouper._get_values_in_largest_bin(hist, bins, recent_dates_gaps)

                period = TransactionTypes.PERIOD_TIMING_BINS_LOOKUP[timing_bins[winning_bin_index]]
                largest_typical_gap = max(common_gaps)
                largest_overall_gap = max(biggest_gaps)

                logger.debug(f'common gaps: {common_gaps}, winning bin index: {winning_bin_index}, period: {period}, timing bins: {timing_bins}, largest typical gap: {largest_typical_gap}, largest overall gap: {largest_overall_gap}')
                # # -- start with the bin representing the largest values 
                # bin = len(hist) - 1
                # # -- and move left (smaller values) until we find a bin with values 
                # while bin > -1:
                #     if hist[bin] > 0:
                #         break 
                #     bin -= 1
                
                '''
                the problem with the above approach is that it will use the largest gap amongst all data.. so if a ruleset captures 
                a set of records that _happens_ to have a month gap, where it's typically daily or weekly at most, the prototransaction 
                will be monthly. or if the files uploaded have provided for a large gap simply for missing data.
                what we need to do is first: detect what date ranges there possibly are, even, given the coverage of the accounts _expected_
                by the records that are being observed. and then, within those ranges, find a reasonable rate (or period) that describes the
                observed records. it's not enough to _omit_ gaps because they fall within missing date ranges, outside coverage; it's not the
                gap that's missing as much as the records bookending it - we don't know how big (or small) that gap really is, only _at most_
                so big, which doesn't say much.
                '''
                
                # period = TransactionTypes.PERIOD_UNKNOWN
                # largest_typical_gap = min(recent_dates_gaps)

                # if hist[bin] > 0:
                #     largest_typical_gap = max([ g for g in recent_dates_gaps if g >= bins[bin] and g < bins[bin+1] ])
                #     period = TransactionTypes.PERIOD_LOOKUP[timing_bins[bin]]

                
                
                # largest_typical_gap = max(common_gaps)

                # TODO: wow this is a PITA
                first_record = recent_records[0]
                latest_record = recent_records[-1]

                distinct_accounts = set([ r.uploaded_file.account.id for r in records if r.uploaded_file.account ])
                distinct_cards = set([ r.uploaded_file.creditcard.id for r in records if r.uploaded_file.creditcard ])

                account_last_dates = [ UploadedFile.objects.filter(account_id=id).order_by('-last_date').first().last_date for id in distinct_accounts ]
                card_last_dates = [ UploadedFile.objects.filter(creditcard_id=id).order_by('-last_date').first().last_date for id in distinct_cards ]

                all_last_dates = account_last_dates + card_last_dates

                # last_dates = [ r.uploaded_file.last_date for r in records ]
                last_common_date = min(all_last_dates)

                # -- this all uses a variable length of time based on the period of spending
                # -- to collect a set of records voluminous enough to calculate a reasonable average
                average_for_period = 0
                average_for_month = 0
                range_total_seconds = 0
                records_in_average_range = Record.objects.none()
                curr_period = None
                averaging_period = None 

                while len(records_in_average_range) < 2 or range_total_seconds == 0:

                    if not curr_period:
                        curr_period = period 
                    else:                        
                        next_biggest_period = TransactionTypes.next_period_lookup(curr_period)
                        logger.debug(f'getting next period up from {curr_period} -> {next_biggest_period}')                        
                        if not next_biggest_period:
                            break 
                        curr_period = next_biggest_period

                    averaging_period = TransactionTypes.AVERAGING_PERIOD_LOOKUP[curr_period]
                    average_start = last_common_date - timedelta(days=TransactionTypes.period_days_lookup(averaging_period))
                    records_in_average_range = [ r for r in recent_records if r.transaction_date >= average_start and r.transaction_date < last_common_date ]
                
                    if len(records_in_average_range) > 1:
                        # actual_range = records_in_average_range[-1].transaction_date - records_in_average_range[0].transaction_date
                        actual_range = last_common_date - average_start
                        range_total_seconds = actual_range.total_seconds()
                    
                if len(records_in_average_range) > 1 and range_total_seconds > 0:
                    dollars_per_second = (float(sum([ r.amount for r in records_in_average_range])) / range_total_seconds)
                    seconds_per_day = 60*60*24
                    average_for_period = dollars_per_second * seconds_per_day*TransactionTypes.period_days_lookup(period)
                    average_for_month = dollars_per_second * seconds_per_day*TransactionTypes.period_days_lookup(TransactionTypes.PERIOD_MONTHLY)
                else:
                    if not len(records_in_average_range) > 1:
                        split_stats['messages'].append(f'only {len(records_in_average_range)}/{len(recent_records)} records in range ({average_start} to {last_common_date}) to calculate average')
                    else:
                        split_stats['messages'].append(f'the time difference between the first and last transaction is zero, cannot calculate averages')

                # last_common_date = datetime.now() 

                # -- we need to be able to actually observe the missing data, not just "have no data"
                gap_from_last_transaction_to_latest_upload = (last_common_date - latest_record.transaction_date).days                                
                is_active = gap_from_last_transaction_to_latest_upload < 2*largest_typical_gap or gap_from_last_transaction_to_latest_upload < largest_overall_gap

                split_stats.update({
                    'first_transaction': datetime.strftime(first_record.transaction_date, '%Y-%m-%d'),
                    'last_transaction': datetime.strftime(latest_record.transaction_date, '%Y-%m-%d'),
                    'largest_typical_gap': largest_typical_gap,
                    'largest_overall_gap': largest_overall_gap,
                    'last_common_date': datetime.strftime(last_common_date, '%Y-%m-%d'),
                    'last_transaction_date': datetime.strftime(latest_record.transaction_date, '%Y-%m-%d'),
                    'is_active': is_active,
                    'period': period,
                    'average_calculation_period_used': averaging_period,
                    'average_for_period': average_for_period,
                    'average_for_month': average_for_month,
                    # 'monthly_spend': amount_split['negative']['monthly_average'],
                    # 'monthly_earn': amount_split['positive']['monthly_average']
                })
                
                # nonzero_buckets = [ h for h in hist if h > 0 ]

                # dist = [ int(float(f'{n/sum(hist):.2f}')*100) for n in hist ]

                # bucket_count_over_threshold = { 
                #     t*10: [ b for b in dist if b >= t*10 and b < (t+1)*10 ]
                #     for t in range(11) }

                # print(json.dumps([ datetime.strftime(d, "%Y-%m-%d") for d in recent_records_dates ], indent=2))
                # print(f'recent_dates_gaps {recent_dates_gaps}')
                # print(f'hist {hist}')
                # print(f'bins {bins}')
                # print(f'dist {dist}')

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

            stats[split_key].update(split_stats)

        return stats 
    
    @staticmethod 
    def get_stats(records, stats={}):
        '''Basic info gleaned from records: IDs, count, related accounts and cards, common description'''

        stats = {
            **stats,
            'record_count': len(records),
            'record_ids': ",".join([ str(r.id) for r in records ]),
            # 'description': ''
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

        # stats['transaction_type'] = RecordGrouper._guess_transaction_type(records)
        
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

        # stats = { **stats, **RecordGrouper._get_timings(records) }
        # stats = { **stats, **RecordGrouper._get_amount_stats(records) }

        if len(records) > 0:
            descriptions = [ r.description or '' for r in records ]
            description_set = list(set(descriptions))
            stats['common_description'] = description_set[np.array([ descriptions.count(d) for d in description_set ]).argmax()]
        
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

        # stats_logger.debug(f'Stats returned: {json.dumps(stats, sort_keys=True, indent=2)}')
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
    def filter_accounted_records(records, filter_by_rule_index=None, less_than_priority=None, is_auto=None, refresh_cache=True, refresh_records=True):
        

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

        if not filter_by_rule_index:

            tx_rule_sets = TransactionRuleSet.objects.all()

            filter_by_rule_index = get_record_rule_index(
                tx_rule_sets,
                less_than_priority=less_than_priority, 
                is_auto=is_auto, 
                refresh_records=refresh_records
            )
            
        # rule_index = get_rule_index(
        #     tx_rule_sets=tx_rule_sets,
        #     lt_priority=less_than_priority, 
        #     is_auto=is_auto, 
        #     refresh_cache=refresh_cache, 
        #     refresh_records=refresh_records
        # )

        # -- this is the actual removal of accounted records 
        pared = [ r for r in records if str(r.id) not in filter_by_rule_index ]
        removed = [ r for r in records if str(r.id) in filter_by_rule_index ]
        logger.info(f'Pared {len(records)} records to {len(pared)} by {len(filter_by_rule_index)} accounted')

        '''
        TODO: RecordMeta.is_accounted should be integer, not boolean
        when we calculate a set of records that is accounted (the keys of rule_index here) 
        _less than a priority_, is_accounted should be set to that priority. Future queries 
        can come in with a priority that...
        '''
        return pared, removed

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
    def test_meaningful_stats(transactionruleset_id):

        trs = TransactionRuleSet.objects.get(pk=transactionruleset_id)
        records = trs.records(refresh=True)
        records, removed = RecordGrouper.filter_accounted_records(
            records=records,
            less_than_priority=trs.priority,
            is_auto=trs.is_auto
        )
        stats = RecordGrouper.get_meaningful_stats(records)
        print(f'rule set: {trs.name}')
        print(json.dumps(stats, sort_keys=True, ensure_ascii=True, indent=4))

    @staticmethod 
    def get_all_stats_for_rule_set(rule_set):

        records = rule_set.records(refresh=True)
        records, removed = RecordGrouper.filter_accounted_records(
            records=records, 
            less_than_priority=rule_set.priority, 
            is_auto=False
        )
        
        stats = {} 

        stats.update({ 'monthly': RecordGrouper.get_monthly_stats(rule_set) })

        stats.update(RecordGrouper.get_stats(records, stats))

        stats.update(RecordGrouper.get_meaningful_stats(records))

        return stats 

    @staticmethod
    def group_records(force_regroup_all=False, is_auto=None):
        '''Create and assign RecordGroups for distinct record descriptions'''

        # -- MANUAL rule sets

        if is_auto is None or not is_auto:
                
            manual_rule_sets = TransactionRuleSet.objects.filter(is_auto=False).order_by('priority')
            
            for rule_set in manual_rule_sets:
                logger.debug(f'recalculating stats for manual rule set {rule_set.name} with priority {rule_set.priority}')
                
                stats = RecordGrouper.get_all_stats_for_rule_set(rule_set)
                
                # period_days = TransactionTypes.period_reverse_lookup(stats['period'])
                # break_after_misses = math.ceil(period_days / 30)
                # break_after_misses = 3 if break_after_misses < 3 else break_after_misses
                
                
                # stats = { k: stats[k] if stats[k] and stats[k] != "NaN" else 0 for k in stats.keys() }
                # logger.debug(f'avg amount -- {stats["avg_amount"]}')
                # logger.debug(f'stats for {rule_set.name}: {json.dumps(stats, indent=4)}')
                # del stats['avg_amount']

                logger.debug(f'updating rule set {rule_set.id} at priority {rule_set.priority} with stats {stats}')

                proto_transaction = ProtoTransaction.objects.filter(transactionruleset=rule_set).first()
                if proto_transaction:
                    proto_transaction.name = rule_set.name
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
                records, removed = RecordGrouper.filter_accounted_records(records=records)

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
                        records, removed = RecordGrouper.filter_accounted_records(records=records)

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
            
if __name__ == "__main__":

    trses = TransactionRuleSet.objects.filter(is_auto=False)

    for trs in trses:
        print(f'{trs.id}: {trs.name}')
    
    trs_id = input('? ')

    RecordGrouper.test_meaningful_stats(trs_id)


#     match = sys.argv[1]

#     # -- 27, 28, 33, 40
#     record_groups = RecordGroup.objects.all()

#     for record_group in [ g for g in record_groups ]: # if g.id in [27, 28, 33, 40] ]:
#         stats = RecordGrouper.get_record_group_stats(record_group.id, ignore_cache=True, dry_run=True)
#         print(f'Record group: {record_group.name} ({record_group.id})')
#         print(json.dumps(stats, indent=4))

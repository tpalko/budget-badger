#!/usr/bin/env python3 

from decimal import InvalidOperation
import sys 
import os 
import traceback 

from django.db.models import Q
import django
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'budget.settings_dev'
django.setup()

import json
from web.models import Record, TransactionRuleSet, ProtoTransaction, TransactionRule
from web.util.modelutil import TransactionTypes
import web.util.dates as utildates
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
        relevance_timer = timedelta(days=365).total_seconds()
        # -- build list of weights corresponding to records, from 1 (now) to zero (relevance_timer ago)
        weights = [ (relevance_timer - (now.date() - r.transaction_date).total_seconds()) / relevance_timer for r in time_sorted_records ]
        # -- no negatives
        # logger.warning(f'timing weights: {weights}')
        weights = [ w if w>=0 else 0 for w in weights ]
        # logger.warning(f'timing weights: {weights}')
        return weights 

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

        recent_records = sorted(records, key=lambda r: r.transaction_date, reverse=False)
        recent_dates = np.array([ r.transaction_date for r in recent_records ])
        recent_dates_from_now = [ now.date() ]
        recent_dates_from_now.extend(recent_dates)
        recent_dates_gaps = [ g.total_seconds()/(60*60*24) for g in np.diff(recent_dates_from_now) ]

        avg_gap = np.average(recent_dates_gaps)
        
        # relevance_timer = timedelta(days=365).total_seconds()
        # -- build list of weights corresponding to records, from 1 (now) to zero (relevance_timer ago)
        # weights = [ (relevance_timer - (now.date() - r.transaction_date).total_seconds()) / relevance_timer for r in recent_records ]
        # -- no negatives
        # logger.warning(f'timing weights: {weights}')
        # weights = [ w if w>=0 else 0 for w in weights ]
        # logger.warning(f'timing weights: {weights}')

        weights = RecordGrouper._get_recency_weights(recent_records)

        is_active = False 
        high_period = None 
        low_period = None 
        period = None     
        low_gap = None 
        high_gap = None     

        # -- if there's at least one nonzero weight 
        if not all([ w == 0 for w in weights ]):

            hist, bins = np.histogram(recent_dates_gaps, weights=weights)

            # -- find the edges of the winning bin, argmax is the index of the highest scoring bin, bins are the edges
            low = bins[hist.argmax()]
            high = bins[hist.argmax() + 1]

            gaps_in_bin = [ a for a in recent_dates_gaps if a >= low and a <= high ]

            # -- get the max of all the amounts in the winning bin
            low_gap = min(gaps_in_bin or [0])
            high_gap = max(gaps_in_bin or [0])

            low_period = RecordGrouper._get_period_for_gap(low_gap)
            high_period = RecordGrouper._get_period_for_gap(high_gap)

            period = TransactionTypes.PERIOD_UNKNOWN 

            if low_period == high_period:
                period = low_period 
            elif low_period == TransactionTypes.PERIOD_UNKNOWN:
                period = high_period
            elif high_period == TransactionTypes.PERIOD_UNKNOWN:
                period = low_period

            is_active = True 

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
            'started_at': datetime.strftime(recent_dates[0], "%m/%d/%Y") if len(recent_dates) > 0 else None,
            'ended_at': datetime.strftime(recent_dates[-1], "%m/%d/%Y") if len(recent_dates) > 0 else None
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
        recent_amounts = [ float(abs(r.amount)) for r in recent_records ]        

        end = recent_records[0].transaction_date
        start = recent_records[-1].transaction_date 
        range_seconds = (end - start).total_seconds()
        of_month = (range_seconds*1.0) / (60*60*24*30)
        total_amount = sum(recent_amounts)

        monthly_spend = total_amount 

        if len(recent_records) > 1:
            monthly_spend = total_amount / of_month

        logger.info(f'total: {total_amount} over {range_seconds} seconds')
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
            
            hist, bins = np.histogram(recent_amounts, weights=weights)

            # -- find the edges of the winning bin, argmax is the index of the highest scoring bin, bins are the edges
            low = bins[hist.argmax()]
            high = bins[hist.argmax() + 1]

            # -- get the max of all the amounts in the winning bin
            recurring_amount = max([ a for a in recent_amounts if a >= low and a <= high ] or [0])

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
            'amount': recurring_amount,
            # 'min_amount': min(recent_amounts),
            # 'max_amount': max(recent_amounts),
            'avg_amount': np.average(recent_amounts),
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
    def get_stats(records):

        stats = {
            'record_count': len(records),
            'record_ids': ",".join([ str(r.id) for r in records ])
        }

        if len(records) == 0:
            raise InvalidOperation(f'No records provided')

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
        
        stats = { **stats, **RecordGrouper._get_timings(records) }
        stats = { **stats, **RecordGrouper._get_amount_stats(records) }
        
        descriptions = [ r.description or '' for r in records ]
        description_set = list(set(descriptions))
        stats['description'] = description_set[np.array([ descriptions.count(d) for d in description_set ]).argmax()]
        
        stats['accounts'] = list(set([ str(r.account) for r in records if r.account ]))
        stats['creditcards'] = list(set([ str(r.creditcard) for r in records if r.creditcard ]))

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
    def get_record_rule_index(refresh=False):
        '''Creates an index of all records => # of TransactionRuleSets it appears in. Useful for weeding out records that have rule set
        attachments and for a quick "rules matched" lookup.'''

        rule_sets = [ [ r.id for r in trs.records(refresh=refresh) ] for trs in TransactionRuleSet.objects.all() ]
        record_ids = set([ i for s in rule_sets for i in s ])
        return { str(i): len([ s for s in rule_sets if i in s ]) for i in record_ids }
    
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
    def group_records(force_regroup_all=False):
        '''Create and assign RecordGroups for distinct record descriptions'''
        
        # -- MANUAL rule sets

        manual_rule_sets = TransactionRuleSet.objects.filter(is_auto=False)
        for rule_set in manual_rule_sets:
            stats = RecordGrouper.get_stats(rule_set.records(refresh=True))
            if rule_set.prototransaction:
                rule_set.prototransaction.update_stats(stats)
                rule_set.prototransaction.save()
            else:
                proto_transaction = ProtoTransaction.new_from(rule_set.name, stats, rule_set)

        # -- AUTO rule sets 

        # -- by default this function will only process records without an assigned record group 
        if force_regroup_all:
            TransactionRuleSet.objects.filter(is_auto=True).delete()
        
        while True:
            
            records = Record.objects.filter(
                ~Q(extra_fields__type="TRANSFER") \
                & ~Q(extra_fields__type="ONLINE TRANSFER") \
                & ~Q(extra_fields__type="ONLINE BANKING TRANSFER") \
                & ~Q(extra_fields__type="CHECK") \
            )

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
            record_rule_index = RecordGrouper.get_record_rule_index(refresh=True)
            records = [ r for r in records if str(r.id) not in record_rule_index or record_rule_index[str(r.id)] == 0 ]
            # logger.warning(f'{len(records)} records')

            # unaccounted_amount = sum([ r.amount for r in records ])

            # -- 
            reset_loop = False 

            # -- this is a rough method to get initial groups together.. 
            # -- maybe in a few cases another feature would be better 
            # -- checks have no description, so maybe go for all checks first and group by amount
            distinct_descriptions = set([ r.description or '' for r in records ])

            for description in distinct_descriptions:

                logger.warning(f'\nTrying {description}')
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
                logger.warning(f'Created rule set {transaction_rule_set.id}')
                
                match_operator = TransactionRule.MATCH_OPERATOR_EQUALS_HUMAN
                match_value = description 

                proto_transaction = None 
                
                for is_modified_description, rule_attempt in RecordGrouper._prototransaction_rule_attempt(match_operator, match_value):
                    
                    TransactionRule.objects.create(transactionruleset=transaction_rule_set, **rule_attempt)
                    transaction_rule_set.refresh_from_db()
                    logger.warning("\n".join([ str(r) for r in transaction_rule_set.transactionrules.all() ]))
                    
                    records = transaction_rule_set.records(refresh=True)

                    logger.warning(f'Attempting rule {rule_attempt} -> {len(records)} records')
                    logger.warning("\n".join([ str(r) for r in records ]))

                    # record_rule_index = RecordGrouper.get_record_rule_index(refresh=True)                    
                    # records = [ r for r in records if str(r.id) not in record_rule_index or record_rule_index[str(r.id)] == 0 ]
                    # logger.warning(f'Removed used records and now have {len(records)}')
                    
                    try:
                        stats = RecordGrouper.get_stats(records)

                        logger.warning(stats)

                        required_fields = ['timing_is_active', 'amount_is_active', 'amount', 'transaction_type', 'period', 'record_count']
                        for f in required_fields:
                            if not stats[f]:
                                raise ValueError(f'The stats calculated are insufficient. Reason: missing, false or zero {f}.')
                        
                        proto_transaction = ProtoTransaction.new_from_rule_attempt(rule_attempt, stats, transaction_rule_set)
                        
                        logger.warning(f'Seems ok.. made prototransaction {proto_transaction.id}')
                        reset_loop = is_modified_description
                        break 
                    
                    except KeyError as ke:
                        raise ke 

                    except:
                        logger.error(sys.exc_info()[0])
                        logger.error(sys.exc_info()[1])
                        traceback.print_tb(sys.exc_info()[2])
                        logger.error(f'The transactionruleset {transaction_rule_set.name} is cleared of rules.')
                        transaction_rule_set.transactionrules.all().delete()

                # -- if we made a prototransaction
                # -- and it was from a modified description
                # -- we need to break to the outer forever loop and recpature a fresh set of descriptions to work with 
                if proto_transaction:
                    if reset_loop:
                        break 
                else:
                    logger.warning(f'Nothing worked, deleting the rule set')
                    transaction_rule_set.delete()

            # -- if we're here not because we created a prototransaction with a modified description
            # -- and needed to recapture a fresh set of descriptions to work with 
            # -- but rather, we just ran out of descriptions
            # -- then quit for good 
            if not reset_loop:
                break 
            
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

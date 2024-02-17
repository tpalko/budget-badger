#!/usr/bin/env python3 

from contextlib import contextmanager

from web.models import TransactionRuleSet
from web.util.ruleindex import get_record_rule_index
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

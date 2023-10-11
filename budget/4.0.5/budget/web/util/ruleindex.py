import logging 
from web.util.cache import Cache 

logger = logging.getLogger(__name__)

# def get_rule_index(tx_rule_sets, lt_priority, is_auto, refresh_cache=True, refresh_records=True):
    

#     # -- METHOD B: use Cache 
#     # index, key = Cache.fetch_by_kwargs(lt_priority=lt_priority, is_auto=is_auto)
#     # if not index:
#     #     logger.debug(f'record/rule index {key} CACHE MISS or REFRESH')
#     #     index = Cache.store_by_kwargs(get_record_rule_index(
#     #         tx_rule_sets,
#     #         less_than_priority=lt_priority, 
#     #         is_auto=is_auto, 
#     #         refresh_records=refresh_records
#     #     ), lt_priority=lt_priority, is_auto=is_auto)
#     # else:
#     #     logger.debug(f'record/rule index {key} CACHE HIT')
#     # return index 

#     # -- METHOD A: manage a global dict      
#     # key = get_rule_index_cache_key(lt_priority=lt_priority, is_auto=is_auto)    
#     # if key not in _rule_index_cache or refresh_cache:        
#     #     logger.debug(f'record/rule index {key} CACHE MISS or REFRESH')
#     #     _rule_index_cache[key] = get_record_rule_index(
#     #         tx_rule_sets,
#     #         less_than_priority=lt_priority, 
#     #         is_auto=is_auto, 
#     #         refresh_records=refresh_records
#     #     )
#     # else:
#     #     logger.debug(f'record/rule index {key} CACHE HIT')
#     # return _rule_index_cache[key]

#     # -- METHOD C: don't cache the entire index built on "all rule sets of a priority or less"
#     # -- because the whole thing needs to be rebuilt if any rule sets change rules _or_ priority
#     return get_record_rule_index(
#         tx_rule_sets,
#         less_than_priority=lt_priority, 
#         is_auto=is_auto, 
#         refresh_records=refresh_records
#     )

def get_record_rule_index(tx_rule_sets, less_than_priority=None, is_auto=None, refresh_records=True):
    '''Creates an index of all records => # of TransactionRuleSets it appears in. Useful for weeding out records that have rule set
    attachments and for a quick "rules matched" lookup.'''

    logger.info(f'Generating record/rule index on rulesets < priority {less_than_priority}, is_auto={is_auto}')

    if less_than_priority is not None:
        tx_rule_sets = tx_rule_sets.filter(priority__lt=less_than_priority)
    if is_auto is not None:
        tx_rule_sets = tx_rule_sets.filter(is_auto=is_auto)

    prefetched_rule_sets = tx_rule_sets.prefetch_related('transactionrules')

    rule_set_ids = {} 

    for trs in prefetched_rule_sets:
        
        kwargs_dict = {
            'transactionruleset_id': trs.id
        }
        
        record_ids, key = Cache.fetch_by_kwargs(**kwargs_dict)
        
        if not record_ids:
            # -- this set of records invalidates only on the rules changing
            # -- we are building an index of all rule set records below a priority
            # -- and expect to get duplicates which we remove below 
            record_ids = [ r.id for r in trs.records(refresh=refresh_records) ]
            key = Cache.store_by_kwargs(record_ids, **kwargs_dict)            

        rule_set_ids[trs.id] = record_ids 

    # -- list of lists of record IDs for each rule set 
    # rule_sets = [ [ r.id for r in trs.records(refresh=refresh) ] for trs in tx_rule_sets ]
    # rule_set_ids = { 
    #     trs.id: [ 
    #         r.id for r in trs.records(refresh=refresh_records) 
    #     ] for trs in prefetched_rule_sets 
    # }

    # -- flatten and deduplicate list of lists 
    record_ids = set([ i for s in rule_set_ids.values() for i in s ])
    # -- mapping of record ID to the count of lists it's a part of
    record_id_map = { str(i): [ trs_id for trs_id in rule_set_ids if i in rule_set_ids[trs_id] ] for i in record_ids }
    return { record_id: record_id_map[record_id] for record_id in record_id_map if len(record_id_map[record_id]) > 0 }
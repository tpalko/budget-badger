import logging 

logger = logging.getLogger(__name__)

_rule_index_cache = {}

def get_rule_index_cache_key(lt_priority=None, is_auto=None):
    is_auto_key = 'any'
    if is_auto:
        is_auto_key = 'true'
    elif is_auto is not None and not is_auto:
        is_auto_key = 'false'
    
    priority_key = 'any'
    if lt_priority is not None:
        priority_key = lt_priority 

    return f'priority-{priority_key}-auto-{is_auto_key}'

def parse_rule_index_cache_key(key):
    parts = key.split('-')
    priority = parts[1]
    is_auto = parts[3]
    if priority == 'any':
        priority = None 
    if is_auto == 'any':
        is_auto = None 
    else:
        is_auto = True if is_auto == 'true' else False         
    return { 'less_than_priority': priority, 'is_auto': is_auto }

def wipe_rule_index_cache():
    _rule_index_cache = {}

def get_rule_index(tx_rule_sets, lt_priority, is_auto, refresh_cache=False, refresh_records=False):
    
    key = get_rule_index_cache_key(lt_priority=lt_priority, is_auto=is_auto)    
    if key not in _rule_index_cache or refresh_cache:        
        logger.debug(f'record/rule index CACHE MISS or REFRESH')
        _rule_index_cache[key] = get_record_rule_index(
            tx_rule_sets,
            less_than_priority=lt_priority, 
            is_auto=is_auto, 
            refresh_records=refresh_records
        )
    else:
        logger.debug(f'record/rule index CACHE HIT')
    return _rule_index_cache[key]

def get_record_rule_index(tx_rule_sets, less_than_priority=None, is_auto=None, refresh_records=False):
    '''Creates an index of all records => # of TransactionRuleSets it appears in. Useful for weeding out records that have rule set
    attachments and for a quick "rules matched" lookup.'''

    logger.info(f'Generating record/rule index on rulesets < priority {less_than_priority}, is_auto={is_auto}')

    if less_than_priority:
        tx_rule_sets = tx_rule_sets.filter(priority__lt=less_than_priority)
    if is_auto is not None:
        tx_rule_sets = tx_rule_sets.filter(is_auto=is_auto)

    prefetched_rule_sets = tx_rule_sets.prefetch_related('transactionrules')

    # -- list of lists of record IDs for each rule set 
    # rule_sets = [ [ r.id for r in trs.records(refresh=refresh) ] for trs in tx_rule_sets ]
    rule_set_ids = { trs.id: [ r.id for r in trs.records(refresh=refresh_records) ] for trs in prefetched_rule_sets }
    # -- flatten and deduplicate list of lists 
    record_ids = set([ i for s in rule_set_ids.values() for i in s ])
    # -- mapping of record ID to the count of lists it's a part of
    record_id_map = { str(i): [ trs_id for trs_id in rule_set_ids if i in rule_set_ids[trs_id] ] for i in record_ids }
    return { record_id: record_id_map[record_id] for record_id in record_id_map if len(record_id_map[record_id]) > 0 }
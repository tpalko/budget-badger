import logging 
import numpy as np

logger = logging.getLogger(__name__)

def tokenize_records(records):

    amounts = [ abs(r.amount) for r in records ]
    max_amount = max(amounts) if amounts else 0

    descs = set([ r.full_description() for r in records ])

    tokens = [
        { 
            'description': d,
            'total': sum([ abs(r.amount) for r in records if r.full_description() == d ])            
        } for d in descs 
    ]

    sorted_token = sorted(tokens, key=lambda token: token['total'])
    # token_map.sort(key='total')
    totals = [ float(d['total'] if d['total'] >= 1 else 1) for d in tokens ]
    log_totals = np.log(totals)
    
    # logger.debug(sorted_token)
    log_amounts = [ n/max(log_totals.tolist()) for n in log_totals.tolist() ]

    for i, d in enumerate(tokens):
        d['log_norm_amt'] = log_amounts[i]

    # log_list = [ (n)/max(np.log(a).tolist()) for n in np.log(a).tolist() ]

    # for desc in token_map.keys():
    #     token_map[desc]['norm_amount'] = token_map[desc]['total'] / max_amount

    return tokens
    
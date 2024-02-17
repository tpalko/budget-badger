import logging 
import hashlib
import simplejson as json 

logger = logging.getLogger(__name__)

def choiceify(choices):
    return tuple([ [c, f'{c[0].upper()}{c[1:]}'] for c in choices ])

def record_hash(val_or_dict):
    return hashlib.md5(            
            json.dumps(val_or_dict, sort_keys=True, ensure_ascii=True, use_decimal=True).encode('utf-8')
        ).hexdigest()

class TransactionTypes(object):

    TRANSACTION_TIMING_PERIODIC = 'periodic' # - a repeating charge at a regular pace
    TRANSACTION_TIMING_CHAOTIC_FREQUENT = 'chaotic_frequent' # frequent - no identifiable period but frequent enough to have a monthly average
    TRANSACTION_TIMING_CHAOTIC_RARE = 'chaotic_rare' # rare - no identifiable period and more often than not longer than 45 days between
    TRANSACTION_TIMING_SINGLE = 'single' # - one record

    CRITICALITY_TAXES = 'taxes'
    CRITICALITY_NECESSARY = 'necessary'
    CRITICALITY_FLEXIBLE = 'flexible'
    CRITICALITY_OPTIONAL = 'optional'

    # -- transaction types are closely related to record types
    # -- generally, a rule set should-ish only match records of a single record type
    # -- and the prototransaction for that rule set would then be that type
    # -- but it is possible to have a mix, and the ProtoTransaction.transaction_type would then 
    # -- help classify the spread of record types it represents??
    # -- but the transaction type would necessarily be more general, and the record types
    # -- would be more specific.. transaction type would also be deterministic, and we lose
    # -- information.. so better to simply represent the group of records by enumerating its types
    TRANSACTION_TYPE_SINGLE = 'single'
    TRANSACTION_TYPE_INCOME = 'income'
    TRANSACTION_TYPE_UTILITY = 'utility'
    TRANSACTION_TYPE_TAX = 'tax'
    TRANSACTION_TYPE_INSURANCE = 'insurance'
    TRANSACTION_TYPE_REGULAR_EXPENSE = 'regularexpense'
    TRANSACTION_TYPE_DEBT = 'debt'
    TRANSACTION_TYPE_CREDITCARD = 'creditcard'
    TRANSACTION_TYPE_UNKNOWN = 'unknown'

    TAX_CATEGORY_NONE = 'none'
    TAX_CATEGORY_TAX = 'tax'
    TAX_CATEGORY_UTILITY = 'utility'
    TAX_CATEGORY_REPAIR = 'repair'
    TAX_CATEGORY_MAINTENANCE = 'maintenance'
    TAX_CATEGORY_INSURANCE = 'insurance'

    PERIOD_UNKNOWN = 'unknown'
    PERIOD_DAILY = 'daily'
    PERIOD_WEEKLY = 'weekly'
    PERIOD_BIWEEKLY = 'bi-weekly'
    PERIOD_MONTHLY = 'monthly'
    PERIOD_TWO_MONTHS = 'two-months'
    PERIOD_QUARTERLY = 'quarterly'
    PERIOD_FOUR_TO_SIX_MONTHS = 'four-to-six-months'
    PERIOD_SEMIANNUALLY = 'semiannually'
    PERIOD_SEVEN_TO_TWELVE_MONTHS = 'seven-to-twelve-months'
    PERIOD_YEARLY = 'yearly'
    PERIOD_THIRTEEN_TO_TWENTY_THREE_MONTHS = 'thirteen-to-twenty-three-months'
    PERIOD_BIENNIALLY = 'biennial'
    PERIOD_INACTIVE = 'inactive'

    PERIODS = {
        1: PERIOD_DAILY, 
        7: PERIOD_WEEKLY, 
        14: PERIOD_BIWEEKLY, 
        30: PERIOD_MONTHLY, 
        60: PERIOD_TWO_MONTHS,
        90: PERIOD_QUARTERLY,         
        150: PERIOD_FOUR_TO_SIX_MONTHS,
        182: PERIOD_SEMIANNUALLY, 
        282: PERIOD_SEVEN_TO_TWELVE_MONTHS,
        365: PERIOD_YEARLY,
        565: PERIOD_THIRTEEN_TO_TWENTY_THREE_MONTHS,
        730: PERIOD_BIENNIALLY,
        761: PERIOD_INACTIVE
    }    

    AVERAGING_PERIOD_LOOKUP = {
        PERIOD_DAILY: PERIOD_BIWEEKLY,
        PERIOD_WEEKLY: PERIOD_MONTHLY,
        PERIOD_BIWEEKLY: PERIOD_TWO_MONTHS,
        PERIOD_MONTHLY: PERIOD_QUARTERLY,
        PERIOD_TWO_MONTHS: PERIOD_FOUR_TO_SIX_MONTHS,
        PERIOD_QUARTERLY: PERIOD_SEMIANNUALLY,
        PERIOD_FOUR_TO_SIX_MONTHS: PERIOD_YEARLY,
        PERIOD_SEMIANNUALLY: PERIOD_THIRTEEN_TO_TWENTY_THREE_MONTHS,
        PERIOD_SEVEN_TO_TWELVE_MONTHS: PERIOD_BIENNIALLY,
        PERIOD_YEARLY: PERIOD_BIENNIALLY
    }

    PERIOD_TIMING_BINS_LOOKUP = {
        0: PERIOD_DAILY, # -- start of daily
        5: PERIOD_WEEKLY, # -- start of weekly
        10: PERIOD_BIWEEKLY, # -- start of bi-weekly
        20: PERIOD_MONTHLY, # -- start of monthly
        40: PERIOD_TWO_MONTHS,
        75: PERIOD_QUARTERLY, 
        105: PERIOD_FOUR_TO_SIX_MONTHS,
        160: PERIOD_SEMIANNUALLY, # -- start of semi-annually
        200: PERIOD_SEVEN_TO_TWELVE_MONTHS,
        300: PERIOD_YEARLY, # -- start of annually
        430: PERIOD_THIRTEEN_TO_TWENTY_THREE_MONTHS,
        700: PERIOD_BIENNIALLY, # -- start of biennial
        760: PERIOD_INACTIVE 
    }

    criticality_choices = choiceify([CRITICALITY_TAXES, CRITICALITY_NECESSARY, CRITICALITY_FLEXIBLE, CRITICALITY_OPTIONAL])
    timing_choices = choiceify([TRANSACTION_TIMING_PERIODIC, TRANSACTION_TIMING_CHAOTIC_FREQUENT, TRANSACTION_TIMING_CHAOTIC_RARE, TRANSACTION_TIMING_SINGLE])
    period_choices = choiceify([PERIOD_UNKNOWN, PERIOD_DAILY, PERIOD_WEEKLY, PERIOD_BIWEEKLY, PERIOD_MONTHLY, PERIOD_QUARTERLY, PERIOD_SEMIANNUALLY, PERIOD_YEARLY])
    transaction_type_choices = choiceify([TRANSACTION_TYPE_SINGLE, TRANSACTION_TYPE_INCOME, TRANSACTION_TYPE_UTILITY, TRANSACTION_TYPE_DEBT, TRANSACTION_TYPE_CREDITCARD, TRANSACTION_TYPE_UNKNOWN])
    tax_category_choices = choiceify([TAX_CATEGORY_NONE, TAX_CATEGORY_TAX, TAX_CATEGORY_UTILITY, TAX_CATEGORY_REPAIR, TAX_CATEGORY_MAINTENANCE, TAX_CATEGORY_INSURANCE])

    @staticmethod
    def next_period_lookup(period):
        curr_days = TransactionTypes.period_days_lookup(period)
        next_days = None 
        for d in TransactionTypes.PERIODS.keys():
            if d <= curr_days:
                continue 
            if not next_days:
                next_days = d 
                continue 
            if d - curr_days < next_days - curr_days:
                next_days = d 
        return TransactionTypes.PERIODS[next_days]            
    
    @staticmethod
    def period_days_lookup(period):
        lookup = { TransactionTypes.PERIODS[d]: d for d in TransactionTypes.PERIODS.keys() }
        return lookup[period]
        
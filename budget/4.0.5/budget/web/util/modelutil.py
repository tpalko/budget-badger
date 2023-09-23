import logging 

logger = logging.getLogger(__name__)

def choiceify(choices):
    return tuple([ [c, f'{c[0].upper()}{c[1:]}'] for c in choices ])

class TransactionTypes(object):

    TRANSACTION_TIMING_PERIODIC = 'periodic' # - a repeating charge at a regular pace
    TRANSACTION_TIMING_CHAOTIC_FREQUENT = 'chaotic_frequent' # frequent - no identifiable period but frequent enough to have a monthly average
    TRANSACTION_TIMING_CHAOTIC_RARE = 'chaotic_rare' # rare - no identifiable period and more often than not longer than 45 days between
    TRANSACTION_TIMING_SINGLE = 'single' # - one record

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
    PERIOD_INACTIVE = 'inactive'

    PERIOD_LOOKUP = {
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
        400: PERIOD_INACTIVE 
    }

    timing_choices = choiceify([TRANSACTION_TIMING_PERIODIC, TRANSACTION_TIMING_CHAOTIC_FREQUENT, TRANSACTION_TIMING_CHAOTIC_RARE, TRANSACTION_TIMING_SINGLE])
    period_choices = choiceify([PERIOD_UNKNOWN, PERIOD_DAILY, PERIOD_WEEKLY, PERIOD_BIWEEKLY, PERIOD_MONTHLY, PERIOD_QUARTERLY, PERIOD_SEMIANNUALLY, PERIOD_YEARLY])
    transaction_type_choices = choiceify([TRANSACTION_TYPE_SINGLE, TRANSACTION_TYPE_INCOME, TRANSACTION_TYPE_UTILITY, TRANSACTION_TYPE_DEBT, TRANSACTION_TYPE_CREDITCARD, TRANSACTION_TYPE_UNKNOWN])
    tax_category_choices = choiceify([TAX_CATEGORY_NONE, TAX_CATEGORY_TAX, TAX_CATEGORY_UTILITY, TAX_CATEGORY_REPAIR, TAX_CATEGORY_MAINTENANCE, TAX_CATEGORY_INSURANCE])

    @staticmethod
    def period_reverse_lookup(v):
        lookup = { TransactionTypes.PERIOD_LOOKUP[v]: v for v in TransactionTypes.PERIOD_LOOKUP.keys() }
        return lookup[v]
        
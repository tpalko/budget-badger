import logging 

logger = logging.getLogger(__name__)

def choiceify(choices):
    return tuple([ [c, f'{c[0].upper()}{c[1:]}'] for c in choices ])

class TransactionTypes(object):

    TRANSACTION_TIMING_PERIODIC = 'periodic' # - a repeating charge at a regular pace
    TRANSACTION_TIMING_CHAOTIC = 'chaotic' # frequent - no identifiable period but frequent enough to have a monthly average
    TRANSACTION_TIMING_CHAOTIC = 'chaotic' # rare - no identifiable period and more often than not longer than 45 days between
    TRANSACTION_TIMING_SINGLE = 'single' # - one record

    TRANSACTION_TYPE_SINGLE = 'single'
    TRANSACTION_TYPE_INCOME = 'income'
    TRANSACTION_TYPE_UTILITY = 'utility'
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
    PERIOD_QUARTERLY = 'quarterly'
    PERIOD_SEMIANNUALLY = 'semiannually'
    PERIOD_YEARLY = 'yearly'

    timing_choices = choiceify([TRANSACTION_TIMING_PERIODIC, TRANSACTION_TIMING_CHAOTIC, TRANSACTION_TIMING_CHAOTIC, TRANSACTION_TIMING_SINGLE])
    period_choices = choiceify([PERIOD_UNKNOWN, PERIOD_DAILY, PERIOD_WEEKLY, PERIOD_BIWEEKLY, PERIOD_MONTHLY, PERIOD_QUARTERLY, PERIOD_SEMIANNUALLY, PERIOD_YEARLY])
    transaction_type_choices = choiceify([TRANSACTION_TYPE_SINGLE, TRANSACTION_TYPE_INCOME, TRANSACTION_TYPE_UTILITY, TRANSACTION_TYPE_DEBT, TRANSACTION_TYPE_CREDITCARD, TRANSACTION_TYPE_UNKNOWN])
    tax_category_choices = choiceify([TAX_CATEGORY_NONE, TAX_CATEGORY_TAX, TAX_CATEGORY_UTILITY, TAX_CATEGORY_REPAIR, TAX_CATEGORY_MAINTENANCE, TAX_CATEGORY_INSURANCE])


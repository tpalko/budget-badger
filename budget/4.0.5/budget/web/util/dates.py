from decimal import Decimal 
from web.util.modelutil import TransactionTypes

period_month_lengths = {
    TransactionTypes.PERIOD_MONTHLY: 1,
    TransactionTypes.PERIOD_QUARTERLY: 3,
    TransactionTypes.PERIOD_SEMIANNUALLY: 6,
    TransactionTypes.PERIOD_YEARLY: 12
}

period_day_ranges = {
    TransactionTypes.PERIOD_DAILY: (0,2,),              # 1
    TransactionTypes.PERIOD_WEEKLY: (2,10,),            # 7
    TransactionTypes.PERIOD_BIWEEKLY: (10,20,),         # 14
    TransactionTypes.PERIOD_MONTHLY: (20,50,),          # 30
    TransactionTypes.PERIOD_QUARTERLY: (50,135,),       # 90
    TransactionTypes.PERIOD_SEMIANNUALLY: (135,215,),   # 180
    TransactionTypes.PERIOD_YEARLY: (215,365,)          # 365
}

period_week_lengths = {
    TransactionTypes.PERIOD_WEEKLY: 7,
    TransactionTypes.PERIOD_BIWEEKLY: 14
}

period_monthly_occurrence = {
    TransactionTypes.PERIOD_UNKNOWN: Decimal(1.0),
    TransactionTypes.PERIOD_DAILY: Decimal(365.0/12),
    TransactionTypes.PERIOD_WEEKLY: Decimal(52.0/12),
    TransactionTypes.PERIOD_BIWEEKLY: Decimal(26.0/12),
    TransactionTypes.PERIOD_MONTHLY: Decimal(1.0),
    TransactionTypes.PERIOD_QUARTERLY: Decimal(1.0/3),
    TransactionTypes.PERIOD_SEMIANNUALLY: Decimal(1.0/6),
    TransactionTypes.PERIOD_YEARLY: Decimal(1.0/12)
}

def next_month(date, period):

    return (date.month + period_month_lengths[period]) % 12 or 12


def next_year(date, period):

    if date.month + period_month_lengths[period] > 12:
        return date.year + 1

    return date.year


def previous_month(date, period):
    return (date.month - period_month_lengths[period]) % 12 or 12


def previous_year(date, period):
    if date.month - period_month_lengths[period] < 1:
        return date.year - 1

    return date.year
PERIOD_UNKNOWN = 'unknown'
PERIOD_WEEKLY = 'weekly'
PERIOD_BIWEEKLY = 'bi-weekly'
PERIOD_MONTHLY = 'monthly'
PERIOD_QUARTERLY = 'quarterly'
PERIOD_SEMIYEARLY = 'semi-yearly'
PERIOD_YEARLY = 'yearly'

period_month_lengths = {
    PERIOD_MONTHLY: 1,
    PERIOD_QUARTERLY: 3,
    PERIOD_SEMIYEARLY: 6,
    PERIOD_YEARLY: 12
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
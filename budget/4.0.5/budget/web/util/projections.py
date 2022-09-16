from datetime import timedelta
from web.models import PlannedPayment, SingleTransaction, RecurringTransaction, Account, DebtTransaction, Transaction
import logging 

logger = logging.getLogger(__name__)

def mark_overpayments(until, start_date, minimum_balance):
    '''Find low balance points, mark debt payments with maximum overpayment'''

    cursor = start_date

    logger.warning("Making call for highest-interest debt..")

    highest_interest_debt = DebtTransaction.objects.filter(transaction_type=Transaction.TRANSACTION_TYPE_DEBT).order_by('-interest_rate').first()

    if not highest_interest_debt:
        logger.warning("No highest-interest debt found")
    else:
        logger.warning("Found highest-interest debt: %s" %(highest_interest_debt.id))

        while True:

            logger.warning("A pass for highest-interest debt payoff..")

            # - Next, find the transactions that align with the lowest balances
            # - These are the transactions we want to use as indicators for how much we can overpay on debts
            lowest_balance_transactions = PlannedPayment.objects.filter(payment_at__gt=cursor, payment_at__lt=until, balance__gt=minimum_balance).order_by('balance')

            if len(lowest_balance_transactions) == 0:
                logger.warning(f'No more transactions in this range, quitting overpayment targeting.')
                break

            logger.warning(f'{len(lowest_balance_transactions)} lowest balance transactions from {cursor} to {until}')

            hit = False

            for lbt in lowest_balance_transactions:

                # - find a payment for our chosen highest-interest debt that occurs before this LBT to which we can apply our overpayment
                # -- get the first planned payment for our high-interest debt between the cursor (starting now) and the future lowest balance point
                next_highest_interest_payment = PlannedPayment.objects.filter(payment_at__gt=cursor, payment_at__lte=lbt.payment_at, transaction__id=highest_interest_debt.transaction_ptr_id).order_by('payment_at').first()

                if next_highest_interest_payment:

                    next_highest_interest_payment.overpayment = -(lbt.balance - minimum_balance)
                    next_highest_interest_payment.save()

                    logger.warning("Applying %s from %s on %s to %s on %s" % (next_highest_interest_payment.overpayment, lbt.transaction.name, lbt.payment_at, next_highest_interest_payment.transaction.name, next_highest_interest_payment.payment_at))

                    cursor = lbt.payment_at
                    hit = True

                    break

            if not hit:
                logger.warning("No hits..")
                break

def fill_planned_payments():
        
    PlannedPayment.objects.all().delete()
    
    for account in Account.objects.all():    

        single_transactions = SingleTransaction.objects.filter(account=account, creditcardtransaction__isnull=True)

        logger.warning("Adding %s single transactions" %(len(single_transactions)))

        for s in single_transactions:

            due_date = s.due_date()

            if due_date > account.balance_at:
                plannedpayment = PlannedPayment(transaction=s, payment_at=due_date)
                plannedpayment.save()
                logger.warning("Planned payment %s saved" % (plannedpayment.id))

        recurring_transactions = RecurringTransaction.objects.filter(account=account, is_active=True)

        logger.warning("Adding %s recurring transactions" %(len(recurring_transactions)))

        one_year = account.balance_at + timedelta(days=365)

        for e in recurring_transactions:

            logger.warning("Adding transactions for %s" %(e.name))

            payment_at = e.next_payment_date()

            while payment_at < one_year:
                plannedpayment = PlannedPayment(transaction=e, payment_at=payment_at)
                plannedpayment.save()
                next_payment_at = e.advance_payment_date(payment_at)
                logger.warning("Payment date moving from %s to %s" %(payment_at, next_payment_at))
                payment_at = next_payment_at
                logger.warning("Planned payment %s saved" % (plannedpayment.id))

        # - First, calculate the running balance for all schedule transactions
        planned_payments = PlannedPayment.objects.filter(transaction__account=account).order_by('payment_at', 'transaction__amount')

        running_balance = account.balance

        for planned_payment in planned_payments:
            real_amount = planned_payment.transaction.real_amount(planned_payment.payment_at)
            logger.warning(f'Increasing balance {running_balance} + {real_amount} + {planned_payment.overpayment}')
            running_balance += real_amount + planned_payment.overpayment
            planned_payment.balance = running_balance
            planned_payment.save()

        mark_overpayments(until=one_year, start_date=account.balance_at, minimum_balance=account.minimum_balance)
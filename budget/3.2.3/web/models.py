from django.db import models
from autoslug import AutoSlugField
from django.core.validators import MinValueValidator, MaxValueValidator
import logging
from datetime import datetime, timedelta, date
from decimal import *
import calendar
import re

logger = logging.getLogger(__name__)


def next_month(date, period):

    return (date.month+RecurringTransaction.period_month_lengths[period]) % 12 or 12


def next_year(date, period):

    if date.month + RecurringTransaction.period_month_lengths[period] > 12:
        return date.year + 1

    return date.year


def previous_month(date, period):
    return (date.month-RecurringTransaction.period_month_lengths[period]) % 12 or 12


def previous_year(date, period):
    if date.month - RecurringTransaction.period_month_lengths[period] < 1:
        return date.year - 1

    return date.year


class BudgetManager(models.Manager):
    def all(self):
        return super(BudgetManager, self).using('frankendeb').all()


class Transaction(models.Model):

    TRANSACTION_TYPE_SINGLE = 'single'
    TRANSACTION_TYPE_INCOME = 'income'
    TRANSACTION_TYPE_UTILITY = 'utility'
    TRANSACTION_TYPE_DEBT = 'debt'
    TRANSACTION_TYPE_CREDITCARD = 'creditcard'

    type_choices = (
        (TRANSACTION_TYPE_SINGLE, 'Single'),
        (TRANSACTION_TYPE_INCOME, 'Income'),
        (TRANSACTION_TYPE_UTILITY, 'Utility'),
        (TRANSACTION_TYPE_DEBT, 'Debt'),
        (TRANSACTION_TYPE_CREDITCARD, 'Credit Card')
    )

    name = models.CharField(max_length=200, unique=True)
    slug = AutoSlugField(null=False, default=None, unique=True, populate_from='name')
    amount = models.DecimalField(decimal_places=2, max_digits=20, null=True)
    transaction_type = models.CharField(max_length=50, choices=type_choices, default=TRANSACTION_TYPE_DEBT)
    is_active = models.BooleanField(null=False, default=True)

    def real_amount(self, payment_at=None):

        if self.transaction_type == Transaction.TRANSACTION_TYPE_CREDITCARD:
            return self.recurringtransaction.creditcardtransaction.expense_total(payment_at)
        else:
            return self.amount

    def __unicode__(self):
        return self.name


class RecurringTransaction(Transaction):

    PERIOD_WEEKLY = 'weekly'
    PERIOD_BIWEEKLY = 'bi-weekly'
    PERIOD_MONTHLY = 'monthly'
    PERIOD_QUARTERLY = 'quarterly'
    PERIOD_SEMIYEARLY = 'semi-yearly'
    PERIOD_YEARLY = 'yearly'

    period_choices = (
        (PERIOD_WEEKLY, 'Weekly'),
        (PERIOD_BIWEEKLY, 'Bi-Weekly'),
        (PERIOD_MONTHLY, 'Monthly'),
        (PERIOD_QUARTERLY, 'Quarterly'),
        (PERIOD_SEMIYEARLY, 'Semi-Yearly'),
        (PERIOD_YEARLY, 'Yearly')
    )

    period_week_lengths = {
        PERIOD_WEEKLY: 7,
        PERIOD_BIWEEKLY: 14
    }

    period_month_lengths = {
        PERIOD_MONTHLY: 1,
        PERIOD_QUARTERLY: 3,
        PERIOD_SEMIYEARLY: 6,
        PERIOD_YEARLY: 12
    }

    period_monthly_occurrence = {
        PERIOD_WEEKLY: Decimal(52.0/12),
        PERIOD_BIWEEKLY: Decimal(26.0/12),
        PERIOD_MONTHLY: Decimal(1.0),
        PERIOD_QUARTERLY: Decimal(1.0/3),
        PERIOD_SEMIYEARLY: Decimal(1.0/6),
        PERIOD_YEARLY: Decimal(1.0/12)
    }

    started_at = models.DateField(default=date.today, blank=True, null=True)
    cycle_due_date = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1, blank=True, null=True)
    period = models.CharField(max_length=50, choices=period_choices, default=PERIOD_MONTHLY)
    is_variable = models.BooleanField(null=False, default=False)

    def monthly_amount(self):
        return self.real_amount()*RecurringTransaction.period_monthly_occurrence[self.period]

    def next_payment_date(self):
        '''Calculates and returns the next date this transaction will occur'''
        now = datetime.now()

        start_date = (now - timedelta(days=1)).date()

        if self.period == self.PERIOD_MONTHLY:
            if self.cycle_due_date >= now.day:
                (first_day, days) = calendar.monthrange(now.year, now.month)
                if self.cycle_due_date > days:
                    start_date = now.replace(day=days).date()
                else:
                    start_date = now.replace(day=self.cycle_due_date).date()
            elif self.cycle_due_date < now.day:
                new_month = next_month(now, self.period)
                new_year = next_year(now, self.period)
                start_date = now.replace(day=self.cycle_due_date, month=new_month, year=new_year).date()
        elif self.period in (self.PERIOD_WEEKLY, self.PERIOD_BIWEEKLY):
            start_date = self.started_at
            while start_date < now.date():
                start_date += timedelta(days=self.period_week_lengths[self.period])
        else:
            start_date = self.started_at
        while start_date < now.date():
            start_date = start_date.replace(month=next_month(start_date, self.period), year=next_year(start_date, self.period))#.date()

        return start_date

    def advance_payment_date(self, start_date):

        if self.period in (self.PERIOD_WEEKLY, self.PERIOD_BIWEEKLY):
            start_date += timedelta(days=self.period_week_lengths[self.period])
        else:
            new_month = next_month(start_date, self.period)
            new_year = next_year(start_date, self.period)
            (first_day, days) = calendar.monthrange(new_year, new_month)
            if start_date.day > days:
                start_date = start_date.replace(day=days)
            start_date = start_date.replace(month=new_month, year=new_year)

        return start_date


class CashTransaction(Transaction):
    pass


class CreditCardTransaction(RecurringTransaction):

    interest_rate = models.DecimalField(decimal_places=2, max_digits=5, default=0)
    cycle_billing_date = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1, blank=True, null=True)

    def expense_total(self, payment_at=None):

        total_expense = 0

        total_expense = total_expense + sum([e.amount for e in self.creditcardexpense_set.all()])

        if payment_at:
            # - if paying on Nov 13
            # - find cycle billing date that ends before Nov 13 -> end_date
            end_date = payment_at.replace(day=self.cycle_billing_date)

            if self.cycle_billing_date > payment_at.day:
                end_date = payment_at.replace(month=previous_month(end_date, self.period), year=previous_year(end_date, self.period))

            # - find cycle billing date before end_date -> start_date
            start_date = end_date.replace(month=previous_month(end_date, self.period), year=previous_year(end_date, self.period))

            total_expense = total_expense + sum([e.amount for e in self.singletransaction_set.filter(transaction_at__gt=start_date, transaction_at__lt=end_date)])

        return total_expense


class DebtTransaction(RecurringTransaction):

    principal = models.DecimalField(decimal_places=2, max_digits=20, default=0)
    principal_at = models.DateField()
    interest_rate = models.DecimalField(decimal_places=2, max_digits=5, default=0)


class SingleTransaction(Transaction):

    creditcardtransaction = models.ForeignKey(CreditCardTransaction, null=True, blank=True, on_delete=models.CASCADE)
    transaction_at = models.DateField()

    def due_date(self):
        billing_date = None
        due_date = None

        if not self.creditcardtransaction:
            return self.transaction_at

        if self.creditcardtransaction.cycle_billing_date >= self.transaction_at.day:
            billing_date = self.transaction_at.replace(day=self.creditcardtransaction.cycle_billing_date)
        else:
            new_month = next_month(self.transaction_at, RecurringTransaction.PERIOD_MONTHLY)
            new_year = next_year(self.transaction_at, RecurringTransaction.PERIOD_MONTHLY)
            billing_date = self.transaction_at.replace(day=self.creditcardtransaction.cycle_billing_date, month=new_month, year=new_year)

        if self.creditcardtransaction.cycle_due_date >= billing_date.day:
            due_date = billing_date.replace(day=self.creditcardtransaction.cycle_due_date)
        else:
            new_month = next_month(billing_date, RecurringTransaction.PERIOD_MONTHLY)
            new_year = next_year(billing_date, RecurringTransaction.PERIOD_MONTHLY)
            due_date = billing_date.replace(day=self.creditcardtransaction.cycle_due_date, month=new_month, year=new_year)
        return due_date


class CreditCardExpense(models.Model):
    creditcardtransaction = models.ForeignKey(CreditCardTransaction, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    amount = models.DecimalField(decimal_places=2, max_digits=20, default=0)

    def __unicode__(self):
        return self.name


class PlannedPayment(models.Model):

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    # period = models.ForeignKey(Period)
    overpayment = models.DecimalField(decimal_places=2, max_digits=20, default=0)
    payment_at = models.DateField()
    balance = models.DecimalField(decimal_places=2, max_digits=20, default=0)

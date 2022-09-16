from django.db.models import Q
from django.db import models
from django.utils.translation import gettext_lazy as _
from autoslug import AutoSlugField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
import logging
from datetime import datetime, timedelta, date
from decimal import *
import calendar
import re
import json 
import web.util.dates as utildates
from web.modelutil import choiceify

logger = logging.getLogger(__name__)

class BudgetManager(models.Manager):
    def all(self):
        return super(BudgetManager, self).using('frankendeb').all()

class BaseModel(models.Model):

    class Meta:
        abstract = True 

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True)

class RecordType(BaseModel):

    name = models.CharField(max_length=50)
    csv_columns = models.CharField(max_length=1024, null=True)
    csv_date_format = models.CharField(max_length=20, null=True)

    def __str__(self):
        return f'{self.name}'

class Account(BaseModel):

    recordtype = models.ForeignKey(RecordType, related_name='accounts', on_delete=models.RESTRICT, null=True)
    name = models.CharField(max_length=255, null=False)
    account_number = models.CharField(max_length=50, null=True)
    balance = models.DecimalField(decimal_places=2, max_digits=20)
    balance_at = models.DateField()
    minimum_balance = models.DecimalField(decimal_places=2, max_digits=20, null=False, default=0.00)    

    def __str__(self):
        return self.name

    def accounted_records(self):
        return self.records.filter(transaction__isnull=False)

class CreditCard(BaseModel):

    recordtype = models.ForeignKey(RecordType, related_name='creditcards', on_delete=models.RESTRICT, null=True)
    name = models.CharField(max_length=255, null=False)
    account_number = models.CharField(max_length=50, null=True)
    interest_rate = models.DecimalField(decimal_places=2, max_digits=5, default=0)
    cycle_due_date = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1, blank=True, null=True)
    cycle_billing_date = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1, blank=True, null=True)

    def __str__(self):
        return self.name

    def accounted_records(self):
        return self.records.filter(creditcardexpense__isnull=False)

class Property(BaseModel):

    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, null=True)
    is_rented = models.BooleanField(null=False, default=False)

class Vehicle(BaseModel):

    name = models.CharField(max_length=255)
    make = models.CharField(max_length=255, null=True)
    model = models.CharField(max_length=255, null=True)
    year = models.IntegerField(null=True)

class Transaction(BaseModel):

    TRANSACTION_TYPE_SINGLE = 'single'
    TRANSACTION_TYPE_INCOME = 'income'
    TRANSACTION_TYPE_UTILITY = 'utility'
    TRANSACTION_TYPE_DEBT = 'debt'
    TRANSACTION_TYPE_CREDITCARD = 'creditcard'
    TRANSACTION_TYPE_UNKNOWN = 'unknown'

    type_choices = (
        (TRANSACTION_TYPE_SINGLE, 'Single'),
        (TRANSACTION_TYPE_INCOME, 'Income'),
        (TRANSACTION_TYPE_UTILITY, 'Utility'),
        (TRANSACTION_TYPE_DEBT, 'Debt'),
        (TRANSACTION_TYPE_CREDITCARD, 'Credit Card'),
        (TRANSACTION_TYPE_UNKNOWN, 'Unknown'),
    )

    TAX_CATEGORY_NONE = 'none'
    TAX_CATEGORY_TAX = 'tax'
    TAX_CATEGORY_UTILITY = 'utility'
    TAX_CATEGORY_REPAIR = 'repair'
    TAX_CATEGORY_MAINTENANCE = 'maintenance'
    TAX_CATEGORY_INSURANCE = 'insurance'

    tax_category_choices = choiceify([TAX_CATEGORY_NONE, TAX_CATEGORY_TAX, TAX_CATEGORY_UTILITY, TAX_CATEGORY_REPAIR, TAX_CATEGORY_MAINTENANCE, TAX_CATEGORY_INSURANCE])

    # (
    #     (TAX_CATEGORY_TAX, f'{TAX_CATEGORY_TAX[0].upper()}{TAX_CATEGORY_TAX[1:]}'),
    #     (TAX_CATEGORY_UTILITY, f'{TAX_CATEGORY_UTILITY[0].upper()}{TAX_CATEGORY_UTILITY[1:]}'),
    #     (TAX_CATEGORY_REPAIR, f'{TAX_CATEGORY_REPAIR[0].upper()}{TAX_CATEGORY_REPAIR[1:]}'),
    #     (TAX_CATEGORY_MAINTENANCE, f'{TAX_CATEGORY_MAINTENANCE[0].upper()}{TAX_CATEGORY_MAINTENANCE[1:]}'),
    #     (TAX_CATEGORY_INSURANCE, f'{TAX_CATEGORY_INSURANCE[0].upper()}{TAX_CATEGORY_INSURANCE[1:]}')
    # )

    name = models.CharField(max_length=200, unique=True)
    slug = AutoSlugField(null=False, default=None, unique=True, populate_from='name')
    tag = models.CharField(max_length=50, null=True)
    amount = models.DecimalField(decimal_places=2, max_digits=20, null=True)
    account = models.ForeignKey(to=Account, related_name='transactions', on_delete=models.SET_NULL, null=True)
    property = models.ForeignKey(to=Property, related_name='transactions', on_delete=models.SET_NULL, null=True)
    tax_category = models.CharField(max_length=50, choices=tax_category_choices, default=TAX_CATEGORY_NONE, null=True)
    transaction_type = models.CharField(max_length=50, choices=type_choices, default=TRANSACTION_TYPE_DEBT)
    is_active = models.BooleanField(null=False, default=True)
    is_imported = models.BooleanField(null=False, default=False)

    def real_amount(self, payment_at=None):

        if self.transaction_type == Transaction.TRANSACTION_TYPE_CREDITCARD:
            return self.recurringtransaction.creditcardtransaction.expense_total(payment_at)
        else:
            return self.amount
    
    def from_stats(self, stats):
        pass 

    def __str__(self):
        return self.name

class TransactionRuleSet(BaseModel):

    operation_map = {
        '<': '__lt',
        '=': '',
        '>': '__gt',
        'contains': '__icontains'
    }

    JOIN_OPERATOR_AND = 'and'
    JOIN_OPERATOR_OR = 'or'

    join_operator_choices = choiceify([JOIN_OPERATOR_AND, JOIN_OPERATOR_OR])

    name = models.CharField(max_length=255, null=True)
    join_operator = models.CharField(max_length=3, choices=join_operator_choices, null=False)

    records = None 
    transaction = None 

    def evaluate(self, force=False):

        if not self.records or force:
                
            record_queryset = None 
            filterresult_sets = []

            filters = [ { f'{tr.record_field}{self.operation_map[tr.match_operator]}': tr.match_value } for tr in self.transactionrules.all() ]
            # logger.warning(self.id)
            # logger.warning(json.dumps(filters, indent=4))

            records = [] 

            if self.join_operator == TransactionRuleSet.JOIN_OPERATOR_AND:
                record_queryset = Record.objects.all()
                for filter in filters:
                    record_queryset = record_queryset.filter(**filter)
                records = list(record_queryset)
            elif self.join_operator == TransactionRuleSet.JOIN_OPERATOR_OR:
                record_querysets = [ Record.objects.filter(**filter) for filter in filters ]
                records = []
                for rq in record_querysets:
                    records = set(list(records) + list(rq))

            self.records = list(records)

        # for tr in self.transactionrules.all():

        #     filter = {
        #         f'{tr.record_field}{self.operation_map[tr.match_operator]}': tr.match_value
        #     }

        #     if self.join_operator == TransactionRuleSet.JOIN_OPERATOR_AND:
        #         if record_queryset:
        #             record_queryset = record_queryset.filter(**filter)
        #         else:
        #             record_queryset = Record.objects.filter(**filter)                 
        #     elif self.join_operator == TransactionRuleSet.JOIN_OPERATOR_OR:
        #         filterresult_sets.append(Record.objects.filter(**filter))  
        
        # if self.join_operator == TransactionRuleSet.JOIN_OPERATOR_OR:
        #     record_queryset = set([ fr for fr in filterresult_sets ])
        
        # return record_queryset
                
class TransactionRule(BaseModel):

    transactionruleset = models.ForeignKey(TransactionRuleSet, related_name='transactionrules', on_delete=models.CASCADE)
    record_field = models.CharField(max_length=50, null=True)
    match_operator = models.CharField(max_length=20, null=True)
    match_value = models.CharField(max_length=100, null=True)    

class RecurringTransaction(Transaction):

    period_choices = (
        (utildates.PERIOD_UNKNOWN, 'Unknown'),
        (utildates.PERIOD_WEEKLY, 'Weekly'),
        (utildates.PERIOD_BIWEEKLY, 'Bi-Weekly'),
        (utildates.PERIOD_MONTHLY, 'Monthly'),
        (utildates.PERIOD_QUARTERLY, 'Quarterly'),
        (utildates.PERIOD_SEMIYEARLY, 'Semi-Yearly'),
        (utildates.PERIOD_YEARLY, 'Yearly')
    )

    period_week_lengths = {
        utildates.PERIOD_WEEKLY: 7,
        utildates.PERIOD_BIWEEKLY: 14
    }

    period_monthly_occurrence = {
        utildates.PERIOD_WEEKLY: Decimal(52.0/12),
        utildates.PERIOD_BIWEEKLY: Decimal(26.0/12),
        utildates.PERIOD_MONTHLY: Decimal(1.0),
        utildates.PERIOD_QUARTERLY: Decimal(1.0/3),
        utildates.PERIOD_SEMIYEARLY: Decimal(1.0/6),
        utildates.PERIOD_YEARLY: Decimal(1.0/12)
    }

    transactionruleset = models.OneToOneField(TransactionRuleSet, related_name='recurringtransaction', on_delete=models.SET_NULL, null=True)
    started_at = models.DateField(default=date.today, blank=True, null=True)
    cycle_due_date = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1, blank=True, null=True)
    period = models.CharField(max_length=50, choices=period_choices, default=utildates.PERIOD_MONTHLY)
    is_variable = models.BooleanField(null=False, default=False)
    
    def monthly_amount(self):
        return self.real_amount()*RecurringTransaction.period_monthly_occurrence[self.period]

    def next_payment_date(self):
        '''Calculates and returns the next date this transaction will occur'''
        now = datetime.now()

        start_date = (now - timedelta(days=1)).date()

        if self.period == utildates.PERIOD_MONTHLY:
            if self.cycle_due_date >= now.day:
                (first_day, days) = calendar.monthrange(now.year, now.month)
                if self.cycle_due_date > days:
                    start_date = now.replace(day=days).date()
                else:
                    start_date = now.replace(day=self.cycle_due_date).date()
            elif self.cycle_due_date < now.day:
                new_month = utildates.next_month(now, self.period)
                new_year = utildates.next_year(now, self.period)
                start_date = now.replace(day=self.cycle_due_date, month=new_month, year=new_year).date()
        elif self.period in (utildates.PERIOD_WEEKLY, utildates.PERIOD_BIWEEKLY):
            start_date = self.started_at
            while start_date < now.date():
                start_date += timedelta(days=self.period_week_lengths[self.period])
        else:
            start_date = self.started_at
        while start_date < now.date():
            start_date = start_date.replace(month=utildates.next_month(start_date, self.period), year=utildates.next_year(start_date, self.period))#.date()

        return start_date

    def advance_payment_date(self, start_date):

        if self.period in (utildates.PERIOD_WEEKLY, utildates.PERIOD_BIWEEKLY):
            start_date += timedelta(days=self.period_week_lengths[self.period])
        else:
            new_month = utildates.next_month(start_date, self.period)
            new_year = utildates.next_year(start_date, self.period)
            (first_day, days) = calendar.monthrange(new_year, new_month)
            if start_date.day > days:
                start_date = start_date.replace(day=days)
            start_date = start_date.replace(month=new_month, year=new_year)

        return start_date

class CreditCardTransaction(RecurringTransaction):

    creditcard = models.ForeignKey(CreditCard, related_name='creditcardtransactions', on_delete=models.RESTRICT, null=True)    
    cycle_billing_date = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1, blank=True, null=True)

    def expense_total(self, payment_at=None):

        total_expense = 0

        total_expense = total_expense + sum([e.amount for e in self.creditcardexpenses.all()])

        if payment_at:
            # - if paying on Nov 13
            # - find cycle billing date that ends before Nov 13 -> end_date
            end_date = payment_at.replace(day=self.cycle_billing_date)

            if self.cycle_billing_date > payment_at.day:
                end_date = payment_at.replace(month=utildates.previous_month(end_date, self.period), year=utildates.previous_year(end_date, self.period))

            # - find cycle billing date before end_date -> start_date
            start_date = end_date.replace(month=utildates.previous_month(end_date, self.period), year=utildates.previous_year(end_date, self.period))

            total_expense = total_expense + sum([e.amount for e in self.singletransactions.filter(transaction_at__gt=start_date, transaction_at__lt=end_date)])

        return total_expense
    
    def __str__(self):
        return self.name
    
class DebtTransaction(RecurringTransaction):

    principal = models.DecimalField(decimal_places=2, max_digits=20, default=0)
    principal_at = models.DateField()
    interest_rate = models.DecimalField(decimal_places=2, max_digits=5, default=0)

class SingleTransaction(Transaction):
    '''
    As opposed to CreditCardExpense: a predictable, pattern expense expected on a CC bill such as gas or groceries,
    a SingleTransaction with a CC association is a one-off purchase on a credit card
    which is anomalous per se - most everything charged on CCs falls into some budgeted category
    even emergency home repairs and big travel bills
    exceptions are a new piano, new car - large and rare
    and the 'due date' attempts to figure the actual, lag date it will be paid based on the CC billing/due cycle terms 
    or, without a CC association, it's just an in-the-moment expense on the associated account
    '''
    creditcardtransaction = models.ForeignKey(CreditCardTransaction, related_name='singletransactions', null=True, blank=True, on_delete=models.CASCADE)
    transaction_at = models.DateField()

    def due_date(self):
        billing_date = None
        due_date = None

        # -- if no associated credit card transaction, truly a one-time transaction 
        if not self.creditcardtransaction:
            return self.transaction_at

        # -- if associated with a credit card transaction, this drives the due date calculated 
        # -- modify 'transaction at' through modifiers CC billing date and CC due date
        # -- at each step, if the modifier date-in-month is >= the current date-in-month
        # -- the current date-in-month is simply progressed to the modifier date-in-month 
        # -- if < current date-in-month, we bump to the next month 
        # -- e.g. transaction at 5/13/20, billing date is 20, due date is 3
        # -- final due date is 6/3/20
        # -- if 5/13/20, 9, and 4, final date is 7/4/20 - billed on 6/9/20 but not due til July, unlikely 
        # -- more likely 5/13/20, 9, and 23, final date being 6/23/20
        if self.creditcardtransaction.cycle_billing_date >= self.transaction_at.day:
            billing_date = self.transaction_at.replace(day=self.creditcardtransaction.cycle_billing_date)
        else:
            new_month = utildates.next_month(self.transaction_at, RecurringTransaction.PERIOD_MONTHLY)
            new_year = utildates.next_year(self.transaction_at, RecurringTransaction.PERIOD_MONTHLY)
            billing_date = self.transaction_at.replace(day=self.creditcardtransaction.cycle_billing_date, month=new_month, year=new_year)

        if self.creditcardtransaction.cycle_due_date >= billing_date.day:
            due_date = billing_date.replace(day=self.creditcardtransaction.cycle_due_date)
        else:
            new_month = utildates.next_month(billing_date, RecurringTransaction.PERIOD_MONTHLY)
            new_year = utildates.next_year(billing_date, RecurringTransaction.PERIOD_MONTHLY)
            due_date = billing_date.replace(day=self.creditcardtransaction.cycle_due_date, month=new_month, year=new_year)
        return due_date

class CreditCardExpense(BaseModel):

    creditcardtransaction = models.ForeignKey(CreditCardTransaction, related_name='creditcardexpenses', on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=50, null=False)
    amount = models.DecimalField(decimal_places=2, max_digits=20, null=False)

    def __unicode__(self):
        return self.name

class PlannedPayment(models.Model):

    transaction = models.ForeignKey(Transaction, related_name='plannedplayments', on_delete=models.CASCADE)
    # period = models.ForeignKey(Period)
    overpayment = models.DecimalField(decimal_places=2, max_digits=20, default=0)
    payment_at = models.DateField()
    balance = models.DecimalField(decimal_places=2, max_digits=20, default=0)

class UploadedFile(BaseModel):

    recordtype = None 

    upload = models.FileField(upload_to='uploads/')
    account = models.ForeignKey(to=Account, related_name='uploadedfiles', on_delete=models.CASCADE, null=True, blank=True)
    creditcard = models.ForeignKey(to=CreditCard, related_name='uploadedfiles', on_delete=models.PROTECT, null=True, blank=True)
    original_filename = models.CharField(max_length=255, unique=True, null=True)    
    first_date = models.DateField(null=True)
    last_date = models.DateField(null=True)
    record_count = models.IntegerField(null=False, default=0)

    def __init__(self, *args, **kwargs):
        super(UploadedFile, self).__init__(*args, **kwargs)
        if self.account:
            self.recordtype = self.account.recordtype 
        elif self.creditcard:
            self.recordtype = self.creditcard.recordtype 
    
class RecordGroup(BaseModel):
    name = models.CharField(max_length=255)
    stats = models.JSONField(null=True)
    
class Record(BaseModel):

    record_group = models.ForeignKey(to=RecordGroup, related_name='records', on_delete=models.SET_NULL, null=True)
    uploaded_file = models.ForeignKey(to=UploadedFile, related_name='records', on_delete=models.RESTRICT)    
    transaction = models.ForeignKey(to=Transaction, related_name='records', on_delete=models.SET_NULL, null=True)
    creditcardexpense = models.ForeignKey(to=CreditCardExpense, related_name='records', on_delete=models.SET_NULL, null=True)
    account = models.ForeignKey(to=Account, related_name='records', on_delete=models.RESTRICT, null=True)
    creditcard = models.ForeignKey(to=CreditCard, related_name='records', on_delete=models.RESTRICT, null=True)
    transaction_date = models.DateField()
    post_date = models.DateField(null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(decimal_places=2, max_digits=20)

    extra_fields = models.JSONField(null=True)

    # -- delete vvv
    type = models.CharField(max_length=255, null=True)    
    account_type = models.CharField(max_length=255, null=True)    
    ref = models.CharField(max_length=255, blank=True, null=True)
    credits = models.DecimalField(decimal_places=2, max_digits=20, null=True)
    debits = models.DecimalField(decimal_places=2, max_digits=20, null=True)

    # def __init__(self, *args, **kwargs):
    #     super(Record, self).__init__(*args, **kwargs)
        # if self.uploaded_file_id:
        #     self.account = self.uploaded_file.account

    def __str__(self):
        return f'{self.id}, {self.transaction_date}, {self.description}, {self.amount}' #, {self.account_type}, {self.type}, {self.ref}, {self.credits}, {self.debits}'

    # def save(self, *args, **kwargs):        
    #     self.clean()
    #     matches = Record.objects.filter(
    #         ~Q(uploaded_file=self.uploaded_file),
    #         date=self.date, 
    #         description=self.description, 
    #         amount=self.amount
    #     )
    #     if len(matches) > 0:
    #         raise ValidationError(_(f'Record.save: Another record(s) {",".join([ str(m.id) for m in matches ])} for a different upload (them:{",".join([ str(m.uploaded_file.id) for m in matches ])}, us:{self.uploaded_file.id}) matching all fields already exists in the database.'))
    #     super(Record, self).save(*args, **kwargs)

class TransactionTag(BaseModel):

    name = models.CharField(max_length=255, null=False)

class RequiredTransactionTag(BaseModel):

    transaction_tag = models.ForeignKey(TransactionTag, related_name='requiredtransactiontags', on_delete=models.CASCADE, null=False)

class TransactionSet(BaseModel):

    name = models.CharField(max_length=255, null=False)
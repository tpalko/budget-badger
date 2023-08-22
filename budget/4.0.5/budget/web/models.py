from django.db.models import Q
from django.db import models
from django.utils.translation import gettext_lazy as _
from autoslug import AutoSlugField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
import logging
from datetime import datetime, timedelta, date
import calendar
import json 
import web.util.dates as utildates
from web.util.modelutil import choiceify, TransactionTypes

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
    
    def continuous_record_brackets(self):
        brackets = []
        start = None 
        end = None 
        for uploadedfile in self.uploadedfiles.all().order_by('first_date'):
            if not start and not end:                
                start = uploadedfile.first_date
                end = uploadedfile.last_date
                continue 
            if uploadedfile.first_date > start and uploadedfile.first_date < end and uploadedfile.last_date > end:
                end = uploadedfile.last_date
                continue 
            if uploadedfile.first_date > end:
                brackets.append((start, end,))
                start = uploadedfile.first_date
                end = uploadedfile.last_date
                continue 
        if start and end:
            brackets.append((start, end,))
        return brackets 
        
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

def records_from_rules(filters, join_operator):
    
    # logger.warning(f'matching records on {json.dumps(filters, indent=4)}')
    qs = None 

    if join_operator == TransactionRuleSet.JOIN_OPERATOR_AND:

        qs = Record.objects.all()
        for filter in filters:
            qs = qs.filter(**filter)
        
        qs = qs.order_by('-transaction_date')
        
    elif join_operator == TransactionRuleSet.JOIN_OPERATOR_OR:
        
        q = Q()
        for filter in filters:
            q = Q(q | Q(**filter))

        qs = Record.objects.filter(q).order_by('-transaction_date')
    
    return list(qs)

class TransactionRuleSet(BaseModel):
    '''A general filter for records'''

    JOIN_OPERATOR_AND = 'and'
    JOIN_OPERATOR_OR = 'or'

    join_operator_choices = choiceify([JOIN_OPERATOR_AND, JOIN_OPERATOR_OR])

    name = models.CharField(max_length=255, null=False)
    join_operator = models.CharField(max_length=3, choices=join_operator_choices, null=False)
    is_auto = models.BooleanField(null=False, default=False)
    priority = models.IntegerField(null=False, default=0)
    _records = None 
    # transaction = None 

    def records(self, refresh=False):

        if not self._records or refresh:
            filters = [ tr.filter() for tr in self.transactionrules.all() ]
            self._records = records_from_rules(filters, self.join_operator)
        
        return self._records 

class TransactionRule(BaseModel):
    '''A building block for TransactionRuleSet'''

    MATCH_OPERATOR_LT_HUMAN = '<'
    MATCH_OPERATOR_EQUALS_HUMAN = '='
    MATCH_OPERATOR_GT_HUMAN = '>'
    MATCH_OPERATOR_CONTAINS_HUMAN = 'contains'

    MATCH_OPERATOR_LT_DJANGO = '__lt'
    MATCH_OPERATOR_EQUALS_DJANGO = ''
    MATCH_OPERATOR_GT_DJANGO = '__gt'
    MATCH_OPERATOR_CONTAINS_DJANGO = '__icontains'

    match_operator_lookup = {
        MATCH_OPERATOR_LT_HUMAN: MATCH_OPERATOR_LT_DJANGO,
        MATCH_OPERATOR_EQUALS_HUMAN: MATCH_OPERATOR_EQUALS_DJANGO,
        MATCH_OPERATOR_GT_HUMAN: MATCH_OPERATOR_GT_DJANGO,
        MATCH_OPERATOR_CONTAINS_HUMAN: MATCH_OPERATOR_CONTAINS_DJANGO
    }

    match_operator_choices = (
        (MATCH_OPERATOR_GT_HUMAN, MATCH_OPERATOR_GT_HUMAN),
        (MATCH_OPERATOR_EQUALS_HUMAN, MATCH_OPERATOR_EQUALS_HUMAN),
        (MATCH_OPERATOR_LT_HUMAN, MATCH_OPERATOR_LT_HUMAN),
        (MATCH_OPERATOR_CONTAINS_HUMAN, MATCH_OPERATOR_CONTAINS_HUMAN),
    )

    transactionruleset = models.ForeignKey(TransactionRuleSet, related_name='transactionrules', on_delete=models.CASCADE)
    record_field = models.CharField(max_length=50, null=True)
    match_operator = models.CharField(max_length=20, null=True, choices=match_operator_choices)
    match_value = models.CharField(max_length=100, null=True)    

    def __str__(self):
        return f'{self.record_field}{self.match_operator}{self.match_value}'

    def filter(self):
        return { f'{self.record_field.lower()}{self.match_operator_lookup[self.match_operator]}': self.match_value }

class ProtoTransaction(BaseModel):
    '''A transitional object between a rule set -- a logical grouping of records, and a full-on transaction -- a budgetable spending abstraction'''

    EXCLUDE_STAT_FIELDS = ['record_count', 'record_ids']

    name = models.CharField(max_length=200, unique=True)
    amount = models.DecimalField(decimal_places=2, max_digits=20, null=True)
    period = models.CharField(max_length=50, choices=TransactionTypes.period_choices, default=TransactionTypes.PERIOD_MONTHLY)
    # account = models.ForeignKey(to=Account, related_name='prototransactions', on_delete=models.SET_NULL, null=True)    
    stats = models.JSONField(null=True)
    property = models.ForeignKey(to=Property, related_name='prototransactions', on_delete=models.SET_NULL, null=True)
    tax_category = models.CharField(max_length=50, choices=TransactionTypes.tax_category_choices, default=TransactionTypes.TAX_CATEGORY_NONE, null=True)
    transaction_type = models.CharField(max_length=50, choices=TransactionTypes.transaction_type_choices, default=TransactionTypes.TRANSACTION_TYPE_DEBT)
    transactionruleset = models.OneToOneField(to=TransactionRuleSet, related_name='prototransaction', on_delete=models.CASCADE, null=True)
    
    def cross_account(self):
        all = self.stats['accounts'] + self.stats['creditcards']
        return len(all) != 1

    def update_stats(self, stats):
        fields = [ f.name for f in ProtoTransaction._meta.fields ]
        self.stats = { s: stats[s] for s in stats if s not in fields and s not in ProtoTransaction.EXCLUDE_STAT_FIELDS }

    @staticmethod
    def new_from(name, stats, transaction_rule_set):
        
        fields = [ f.name for f in ProtoTransaction._meta.fields ]

        pt_dict = {
            'name': name,
            'stats': { s: stats[s] for s in stats if s not in fields and s not in ProtoTransaction.EXCLUDE_STAT_FIELDS },
            'transactionruleset': transaction_rule_set,
            **{ s: stats[s] for s in stats if s in fields }
        }

        return ProtoTransaction.objects.create(**pt_dict)

    @staticmethod
    def new_from_rule_attempt(rule_attempt, stats, transaction_rule_set):

        name = f'{rule_attempt["record_field"]} {rule_attempt["match_operator"]} {rule_attempt["match_value"]}'
        return ProtoTransaction.new_from(name, stats, transaction_rule_set)

    def __str__(self):
        return self.name 

class Transaction(BaseModel):

    name = models.CharField(max_length=200, unique=True)
    slug = AutoSlugField(null=False, default=None, unique=True, populate_from='name')
    tag = models.CharField(max_length=50, null=True)
    amount = models.DecimalField(decimal_places=2, max_digits=20, null=True)
    account = models.ForeignKey(to=Account, related_name='transactions', on_delete=models.SET_NULL, null=True)
    property = models.ForeignKey(to=Property, related_name='transactions', on_delete=models.SET_NULL, null=True)
    prototransaction = models.OneToOneField(to=ProtoTransaction, related_name='transaction', on_delete=models.CASCADE, null=True)
    tax_category = models.CharField(max_length=50, choices=TransactionTypes.tax_category_choices, default=TransactionTypes.TAX_CATEGORY_NONE, null=True)
    transaction_type = models.CharField(max_length=50, choices=TransactionTypes.transaction_type_choices, default=TransactionTypes.TRANSACTION_TYPE_DEBT)
    is_active = models.BooleanField(null=False, default=True)
    is_imported = models.BooleanField(null=False, default=False)

    def real_amount(self, payment_at=None):

        if self.transaction_type == TransactionTypes.TRANSACTION_TYPE_CREDITCARD:
            return self.recurringtransaction.creditcardtransaction.expense_total(payment_at)
        else:
            return self.amount
    
    def from_stats(self, stats):
        pass 

    def __str__(self):
        return self.name

class RecurringTransaction(Transaction):

    transactionruleset = models.OneToOneField(TransactionRuleSet, related_name='recurringtransaction', on_delete=models.SET_NULL, null=True)
    started_at = models.DateField(default=date.today, blank=True, null=True)
    cycle_due_date = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1, blank=True, null=True)
    period = models.CharField(max_length=50, choices=TransactionTypes.period_choices, default=TransactionTypes.PERIOD_MONTHLY)
    is_variable = models.BooleanField(null=False, default=False)
    
    def monthly_amount(self):
        return self.real_amount()*utildates.period_monthly_occurrence[self.period]

    def next_payment_date(self):
        '''Calculates and returns the next date this transaction will occur'''
        now = datetime.now()

        start_date = (now - timedelta(days=1)).date()

        if self.period == TransactionTypes.PERIOD_MONTHLY:
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
        elif self.period in (TransactionTypes.PERIOD_WEEKLY, TransactionTypes.PERIOD_BIWEEKLY):
            start_date = self.started_at
            while start_date < now.date():
                start_date += timedelta(days=self.period_week_lengths[self.period])
        else:
            start_date = self.started_at
        while start_date < now.date():
            start_date = start_date.replace(month=utildates.next_month(start_date, self.period), year=utildates.next_year(start_date, self.period))#.date()

        return start_date

    def advance_payment_date(self, start_date):

        if self.period in (TransactionTypes.PERIOD_WEEKLY, TransactionTypes.PERIOD_BIWEEKLY):
            start_date += timedelta(days=self.period_week_lengths[self.period])
        else:
            new_month = utildates.next_month(start_date, self.period)
            new_year = utildates.next_year(start_date, self.period)
            (first_day, days) = calendar.monthrange(new_year, new_month)
            if start_date.day > days:
                start_date = start_date.replace(day=days)
            start_date = start_date.replace(month=new_month, year=new_year)

        return start_date

class UtilityTransaction(RecurringTransaction):
    pass 

class CreditCardTransaction(RecurringTransaction):
    '''The analogue of RecurringTransaction as spending pertains to a credit card instead of a checking or savings account.
    The base type is Transaction, tied to Account which feeds the actual expense (paying off the credit card) while this 
    derivative type establishes the relationship with the specific credit card.'''

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
            new_month = utildates.next_month(self.transaction_at, TransactionTypes.PERIOD_MONTHLY)
            new_year = utildates.next_year(self.transaction_at, TransactionTypes.PERIOD_MONTHLY)
            billing_date = self.transaction_at.replace(day=self.creditcardtransaction.cycle_billing_date, month=new_month, year=new_year)

        if self.creditcardtransaction.cycle_due_date >= billing_date.day:
            due_date = billing_date.replace(day=self.creditcardtransaction.cycle_due_date)
        else:
            new_month = utildates.next_month(billing_date, TransactionTypes.PERIOD_MONTHLY)
            new_year = utildates.next_year(billing_date, TransactionTypes.PERIOD_MONTHLY)
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
    header_included = models.BooleanField(null=False, default=True)
    first_date = models.DateField(null=True)
    last_date = models.DateField(null=True)
    record_count = models.IntegerField(null=False, default=0)

    def __init__(self, *args, **kwargs):
        super(UploadedFile, self).__init__(*args, **kwargs)
        if self.account:
            self.recordtype = self.account.recordtype 
        elif self.creditcard:
            self.recordtype = self.creditcard.recordtype 
    
# class RecordGroup(BaseModel):
#     name = models.CharField(max_length=255)
#     stats = models.JSONField(null=True)
    
class Record(BaseModel):
    '''A normalized representation of a single historical transaction'''

    # record_group = models.ForeignKey(to=RecordGroup, related_name='records', on_delete=models.SET_NULL, null=True)
    uploaded_file = models.ForeignKey(to=UploadedFile, related_name='records', on_delete=models.RESTRICT)    
    # transaction = models.ForeignKey(to=Transaction, related_name='records', on_delete=models.SET_NULL, null=True)
    creditcardexpense = models.ForeignKey(to=CreditCardExpense, related_name='records', on_delete=models.SET_NULL, null=True)    
    transaction_date = models.DateField()
    post_date = models.DateField(null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(decimal_places=2, max_digits=20)

    extra_fields = models.JSONField(null=True)

    # def __init__(self, *args, **kwargs):
    #     super(Record, self).__init__(*args, **kwargs)
        # if self.uploaded_file_id:
        #     self.account = self.uploaded_file.account

    def __str__(self):
        return f'{self.id}, {self.uploaded_file.account or self.uploaded_file.creditcard}, {self.transaction_date}, {self.description}, {self.amount}' #, {self.account_type}, {self.type}, {self.ref}, {self.credits}, {self.debits}'

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
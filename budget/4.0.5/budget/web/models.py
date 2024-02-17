from django.db.models import Q, F, DEFERRED
from django.db import models
from django.db.models import OuterRef, F
from django.utils.translation import gettext_lazy as _
from autoslug import AutoSlugField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
import logging
from datetime import datetime, timedelta, date
import calendar
import web.util.dates as utildates
from web.util.modelutil import choiceify, TransactionTypes, record_hash
from web.util.ruleindex import Cache 

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

class RecordFormat(BaseModel):

    # -- the signage of amount/gross column
    # -- normal: positive is flow in, negative is flow out
    FLOW_CONVENTION_NORMAL = 'normal'
    FLOW_CONVENTION_REVERSE = 'reverse'

    name = models.CharField(max_length=50)
    csv_columns = models.CharField(max_length=1024, null=True)
    flow_convention = models.CharField(max_length=10, choices=choiceify([FLOW_CONVENTION_NORMAL, FLOW_CONVENTION_REVERSE]), null=False, default=FLOW_CONVENTION_NORMAL)
    csv_date_format = models.CharField(max_length=20, null=False, default="%m/%d/%Y")

    def __str__(self):
        return f'{self.name}'

def _continuous_record_brackets(ordered_uploaded_files):

    brackets = []
    # start = None 
    # end = None 
    margin = timedelta(days=6)

    for uploadedfile in ordered_uploaded_files:
        handled = False 
        for bracket in brackets:
            # -- this file starts after the bracket start, ends after the bracket end
            # -- could be overlapping, or not 
            if uploadedfile.first_date > bracket[0] and uploadedfile.last_date > bracket[1]:

                # -- overlapping the bracket (at least by margin)
                if uploadedfile.first_date - margin < bracket[1]:
                    # -- extends this bracket
                    bracket[1] = uploadedfile.last_date
                    handled = True 
                    break 
                
            if uploadedfile.first_date > bracket[0] and uploadedfile.last_date < bracket[1]:
                # -- contained by this bracket, do nothing
                handled = True 
                break                                 
            
        if not handled:
            brackets.append([uploadedfile.first_date, uploadedfile.last_date])
        
    # if start and end:
    #     brackets.append((start, end,))

    return brackets 

class Account(BaseModel):

    recordformat = models.ForeignKey(RecordFormat, related_name='accounts', on_delete=models.RESTRICT, null=True)
    name = models.CharField(max_length=255, null=False)
    account_number = models.CharField(max_length=50, null=True)
    comments = models.TextField(null=True)
    balance = models.DecimalField(decimal_places=2, max_digits=20)
    balance_at = models.DateField()
    minimum_balance = models.DecimalField(decimal_places=2, max_digits=20, null=False, default=0.00)    

    def __str__(self):
        return self.name

    # def accounted_records(self):
    #     return self.records.filter(transaction__isnull=False)
    
    def continuous_record_brackets(self):
        return _continuous_record_brackets(self.uploadedfiles.all().order_by('first_date'))
        
class CreditCard(BaseModel):

    recordformat = models.ForeignKey(RecordFormat, related_name='creditcards', on_delete=models.RESTRICT, null=True)
    name = models.CharField(max_length=255, null=False)
    account_number = models.CharField(max_length=50, null=True)
    comments = models.TextField(null=True)
    interest_rate = models.DecimalField(decimal_places=2, max_digits=5, default=0)
    cycle_due_date = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1, blank=True, null=True)
    cycle_billing_date = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1, blank=True, null=True)

    def __str__(self):
        return self.name

    def accounted_records(self):
        return self.records.filter(creditcardexpense__isnull=False)

    def continuous_record_brackets(self):
        return _continuous_record_brackets(self.uploadedfiles.all().order_by('first_date'))
    
class UploadedFile(BaseModel):

    recordformat = None 

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
            self.recordformat = self.account.recordformat 
        elif self.creditcard:
            self.recordformat = self.creditcard.recordformat 
    
    def account_name(self):
        return self.account.name if self.account else self.creditcard.name if self.creditcard else "-no acct/cc-"

    def account_number(self):
        return self.account.account_number if self.account else self.creditcard.account_number if self.creditcard else "-no acct/cc #-"
    
class Event(BaseModel):

    name = models.CharField(max_length=255)
    started_at = models.DateField(null=True)
    ended_at = models.DateField(null=True)

class Property(BaseModel):

    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, null=True)
    is_rented = models.BooleanField(null=False, default=False)

class Vehicle(BaseModel):

    name = models.CharField(max_length=255)
    make = models.CharField(max_length=255, null=True)
    model = models.CharField(max_length=255, null=True)
    year = models.IntegerField(null=True)

# def records_from_accounted_priority(priority):
    
#     return Record.budgeting.filter(meta_accounted_at=priority)

def records_from_rules(rule_logics, join_operator):
    
    '''
    See RecordGrouper.filter_accounted_records for some insight on this
    '''

    qset = None 
    this_qs = []

    for logic in rule_logics:

        # -- 'full_description' must be digested - this field doesn't exist, it's just a shortcut for "all description fields"
        # -- this is why 'full_description' cannot be used reliably with 'and'.. the set of all description fields must be OR'd
        # -- to capture faithfully, but if the user says 'AND', the logic is broken, until a parentheses feature is built
        if logic.tr.record_field == "full_description":
            new_logics = [ 
                TransactionRuleLogic(TransactionRule(record_field='description', inclusion=logic.tr.inclusion, match_operator=logic.tr.match_operator, match_value=logic.tr.match_value)),
                TransactionRuleLogic(TransactionRule(record_field='meta_description', inclusion=logic.tr.inclusion, match_operator=logic.tr.match_operator, match_value=logic.tr.match_value))
            ]
            for l in new_logics:
                this_qs.append(l.key_arg_dict())
        else:
            this_qs.append(logic.key_arg_dict())

    # logger.debug(f'Q dicts: {this_qs}')

    for i, qdict in enumerate(this_qs):
        q = Q(**qdict)
        if i == 0:
            qset = q
        else:
            if join_operator == TransactionRuleSet.JOIN_OPERATOR_AND:
                qset = qset & q 
            elif join_operator == TransactionRuleSet.JOIN_OPERATOR_OR:
                qset = qset | q 

    qs = Record.budgeting.filter(qset).order_by('-transaction_date')

    return qs

class TransactionRuleSet(BaseModel):
    '''A general filter for records'''

    JOIN_OPERATOR_AND = 'and'
    JOIN_OPERATOR_OR = 'or'

    join_operator_choices = choiceify([JOIN_OPERATOR_AND, JOIN_OPERATOR_OR])

    name = models.CharField(max_length=255, null=False)
    join_operator = models.CharField(max_length=3, choices=join_operator_choices, null=False, default=JOIN_OPERATOR_OR)
    is_auto = models.BooleanField(null=False, default=False)
    priority = models.IntegerField(null=False, default=0)
    _records = None 
    # transaction = None 

    def records(self, refresh=False):

        if not self._records or refresh:
            logger.debug(f'Refetching records for transactionruleset {self.id}')
            
            ## sorter page: 23s cold, 14s subsequent
            filters = [ TransactionRuleLogic(tr) for tr in self.transactionrules.all() ]
            self._records = records_from_rules(filters, self.join_operator)

            ## sorter page: 13s cold, 9s subsequent
            # self._records = records_from_accounted_priority(self.priority)
        # else:
        #     logger.debug(f'Using cached records for transactionruleset {self.id}')

        return self._records 

    def __str__(self):
        return self.name      

    def prototransaction_safe(self):
        try:
            return self.prototransaction 
        except:
            return None 
    
    # @classmethod
    # def from_db(cls, db, field_names, values):
    #     # Default implementation of from_db() (subject to change and could
    #     # be replaced with super()).
    #     if len(values) != len(cls._meta.concrete_fields):
    #         values = list(values)
    #         values.reverse()
    #         values = [
    #             values.pop() if f.attname in field_names else DEFERRED
    #             for f in cls._meta.concrete_fields
    #         ]
    #     instance = cls(*values)
    #     instance._state.adding = False
    #     instance._state.db = db
    #     # customization to store the original field values on the instance
    #     instance._loaded_values = dict(
    #         zip(field_names, (value for value in values if value is not DEFERRED))
    #     )
    #     return instance

    def save(self, *args, **kwargs):

        # previous_priority = None 

        # if not self._state.adding:
        #     previous_priority = self._loaded_values['priority']

        super(TransactionRuleSet, self).save(*args, **kwargs)

        # wipe_above_priority = self.priority 

        # if previous_priority and wipe_above_priority > previous_priority:
        #     wipe_above_priority = previous_priority

        # for trs in TransactionRuleSet.objects.filter(is_auto=self.is_auto, priority__gte=wipe_above_priority):
        #     Cache.invalidate_by_kwargs(transactionruleset_id=trs.id)

        Cache.invalidate()

        # logger.debug(f'Wiping accounted priority from records in ruleset {self.id}')
        # for record in self.records():
        #     record_meta = RecordMeta.objects.filter(core_fields_hash=record.core_fields_hash).first()
        #     record_meta.accounted_at = None
        #     record_meta.save()

        # trs = TransactionRuleSet.objects.filter(priority__gte=self.priority, is_auto=False).order_by('-priority')
        # logger.debug(f'Cycling through {len(trs)} rulesets to reset accounted priority')
        # for tr in trs:
        #     for record in tr.records():
        #         record_meta = RecordMeta.objects.filter(core_fields_hash=record.core_fields_hash).first()
        #         if record_meta.accounted_at is None or record_meta.accounted_at > tr.priority:
        #             logger.debug(f'Setting record meta {record_meta.id} (was {record_meta.accounted_at}) accounted at {tr.priority}')
        #             record_meta.accounted_at = tr.priority 
        #             record_meta.save()
        #         else:
        #             logger.debug(f'Record meta {record_meta.id} is set to {record_meta.accounted_at}, lower than or equal to {tr.priority}')

        # trs = TransactionRuleSet.objects.all().order_by('priority')
        # curr = None 
        # for rs in trs:
        #     if not curr:
        #         curr = rs.priority 
        #         continue 
            
        #     if curr == rs.priority:
        #         rs.priority += 1            
        #         rs.save()
            
        #     curr = rs.priority

class TransactionRuleLogic(object):

    tr = None 
    operator_fn = None 
    fn_key = None 
    fn_arg = None 

    def __init__(self, *args, **kwargs):        
        if len(args) < 1:
            raise Exception("TransactionRuleLogic must be provided with a TransactionRule")
        self.tr = args[0]
        self.operator_fn = self.tr.inclusion
        self.fn_key = f'{self.tr.record_field.lower()}{self.tr.match_operator_lookup[self.tr.match_operator]}'
        self.fn_arg = self.tr.match_value

    def key_arg_dict(self):
        return {self.fn_key: self.fn_arg}

    def apply(self, query_set):
        if self.operator_fn == TransactionRule.INCLUSION_FILTER:
            return query_set.filter(**self.key_arg_dict())
        elif self.operator_fn == TransactionRule.INCLUSION_EXCLUDE:
            return query_set.exclude(**self.key_arg_dict())

class TransactionRule(BaseModel):
    '''A building block for TransactionRuleSet'''

    INCLUSION_FILTER = 'filter'
    INCLUSION_EXCLUDE = 'exclude'

    MATCH_OPERATOR_LT_HUMAN = '<'
    MATCH_OPERATOR_EQUALS_HUMAN = '='
    MATCH_OPERATOR_GT_HUMAN = '>'
    MATCH_OPERATOR_CONTAINS_HUMAN = 'contains'
    MATCH_OPERATOR_REGEX_HUMAN = 'regex'

    MATCH_OPERATOR_LT_DJANGO = '__lt'
    MATCH_OPERATOR_EQUALS_DJANGO = ''
    MATCH_OPERATOR_GT_DJANGO = '__gt'
    MATCH_OPERATOR_CONTAINS_DJANGO = '__icontains'
    MATCH_OPERATOR_REGEX_DJANGO = '__iregex'

    match_operator_lookup = {
        MATCH_OPERATOR_LT_HUMAN: MATCH_OPERATOR_LT_DJANGO,
        MATCH_OPERATOR_EQUALS_HUMAN: MATCH_OPERATOR_EQUALS_DJANGO,
        MATCH_OPERATOR_GT_HUMAN: MATCH_OPERATOR_GT_DJANGO,
        MATCH_OPERATOR_CONTAINS_HUMAN: MATCH_OPERATOR_CONTAINS_DJANGO,
        MATCH_OPERATOR_REGEX_HUMAN: MATCH_OPERATOR_REGEX_DJANGO
    }

    match_operator_choices = (
        (MATCH_OPERATOR_GT_HUMAN, MATCH_OPERATOR_GT_HUMAN),
        (MATCH_OPERATOR_EQUALS_HUMAN, MATCH_OPERATOR_EQUALS_HUMAN),
        (MATCH_OPERATOR_LT_HUMAN, MATCH_OPERATOR_LT_HUMAN),
        (MATCH_OPERATOR_CONTAINS_HUMAN, MATCH_OPERATOR_CONTAINS_HUMAN),
        (MATCH_OPERATOR_REGEX_HUMAN, MATCH_OPERATOR_REGEX_HUMAN)
    )

    transactionruleset = models.ForeignKey(TransactionRuleSet, related_name='transactionrules', on_delete=models.CASCADE)
    inclusion = models.CharField(null=False, choices=choiceify([INCLUSION_EXCLUDE, INCLUSION_FILTER]), default=INCLUSION_FILTER, max_length=10)
    record_field = models.CharField(max_length=50, null=True)
    match_operator = models.CharField(max_length=20, null=True, choices=match_operator_choices)
    match_value = models.CharField(max_length=100, null=True)    

    def __str__(self):
        return f'{self.record_field} {self.match_operator} {self.match_value}'

    # def filter(self):
    #     return { f'{self.record_field.lower()}{self.match_operator_lookup[self.match_operator]}': self.match_value }

class ProtoTransaction(BaseModel):
    '''A transitional object between a rule set -- a logical grouping of records, and a full-on transaction -- a budgetable spending abstraction'''

    DIRECTION_CREDIT = 'credit'
    DIRECTION_DEBIT = 'debit'
    DIRECTION_BIDIRECTIONAL = 'bidirectional'
    DIRECTION_UNSET = 'unset'

    EXCLUDE_STAT_FIELDS = ['record_count', 'record_ids']

    transactionruleset = models.OneToOneField(to=TransactionRuleSet, related_name='prototransaction', on_delete=models.CASCADE, null=True)        
    name = models.CharField(max_length=200, unique=True)

    # -- emitted from stats (not anymore, debit/credit split)
    # is_active = models.BooleanField(null=False, default=True)
    # -- 
    # -- tax_category to categorize expenses for tax purposes
    tax_category = models.CharField(max_length=50, choices=TransactionTypes.tax_category_choices, default=TransactionTypes.TAX_CATEGORY_NONE, null=True)
    # -- we can guess at this
    # period = models.CharField(max_length=50, choices=TransactionTypes.period_choices, default=TransactionTypes.PERIOD_MONTHLY)
    # monthly_spend = models.DecimalField(decimal_places=2, max_digits=20, null=True)
    # monthly_earn = models.DecimalField(decimal_places=2, max_digits=20, null=True)
    
    # -- probably trash transaction_type
    transaction_type = models.CharField(max_length=50, choices=TransactionTypes.transaction_type_choices, default=TransactionTypes.TRANSACTION_TYPE_DEBT)
    timing = models.CharField(max_length=20, choices=TransactionTypes.timing_choices, default=TransactionTypes.TRANSACTION_TIMING_SINGLE)
    # -- recurring_amount means little, very few expenses repeat to the penny, and the fact that they do is insignificant
    recurring_amount = models.DecimalField(decimal_places=2, max_digits=20, null=True)

    criticality = models.CharField(max_length=20, choices=TransactionTypes.criticality_choices, null=False, default=TransactionTypes.CRITICALITY_OPTIONAL)
    direction = models.CharField(max_length=20, choices=choiceify([DIRECTION_CREDIT, DIRECTION_DEBIT, DIRECTION_BIDIRECTIONAL, DIRECTION_UNSET]), null=False, default=DIRECTION_UNSET)

    # -- stats contains 'debit' and 'credit', each of which have 'average_for_period' and 'average_for_month'    
    stats = models.JSONField(null=True)
    
    def is_active(self):
        return ('is_active' in self.stats['debit'] and self.stats['debit']['is_active']) \
            or ('is_active' in self.stats['credit'] and self.stats['credit']['is_active'])

    def period(self, direction):
        if direction in self.stats and 'period' in self.stats[direction]:
            return self.stats[direction]['period']
        return None
    
    def force_direction(self):
        credit_avg = abs(self.average_for_month(ProtoTransaction.DIRECTION_CREDIT) or 0)
        debit_avg = abs(self.average_for_month(ProtoTransaction.DIRECTION_DEBIT) or 0)

        return ProtoTransaction.DIRECTION_CREDIT if credit_avg > debit_avg else ProtoTransaction.DIRECTION_DEBIT
        
    def average_for_month(self, direction):
        if direction in self.stats and 'average_for_month' in self.stats[direction]:
            return self.stats[direction]['average_for_month']
        return None

    def average_for_period(self, direction):
        if direction in self.stats and 'average_for_period' in self.stats[direction]:
            return self.stats[direction]['average_for_period']
        return None

    def cross_account(self):
        return len(self.stats['accounts'] + self.stats['creditcards']) > 1

    '''
    stats sample (8/31/23)
    {
        "accounts": [],
        "amount_is_active": true,
        "average_gap": "nan days",
        "avg_amount": -138.57,
        "creditcards": [
            "amex - tim"
        ],
        "description": "BRILLIANT.ORG - EDU SAN FRANCISCO       CA",
        "ended_at": "05/06/2023",
        "high_period": "daily",
        "high_period_days": 0,
        "is_variable": false,
        "low_period": "daily",
        "low_period_days": 0,
        "monthly_amount": -138.57,
        "outliers_removed": 0,
        "period": "daily",
        "record_count": 1,
        "record_ids": "70597",
        "recurring_amount": -138.57,
        "started_at": "05/06/2023",
        "timing_is_active": true,
        "transaction_type": "single"
        }

    '''
    def update_stats(self, stats):
        '''
        Updates all common fields between given stats dict and the ProtoTransaction object 
        and puts everything else (not excluded by ProtoTransaction.EXCLUDE_STAT_FIELDS) into ProtoTransaction.stats
        '''
        fields = [ f.name for f in ProtoTransaction._meta.fields ]        
        self.stats = { s: stats[s] for s in stats if s not in fields and s not in ProtoTransaction.EXCLUDE_STAT_FIELDS }
        for stat_field in [ s for s in stats.keys() if s in fields ]:
            self.__setattr__(stat_field, stats[stat_field])

    @staticmethod
    def new_from(name, stats, transaction_rule_set):
        '''
        Creates a new ProtoTransaction with given name, populating all common fields between given stats dict and the ProtoTransaction model
        and putting everything else (not excluded by ProtoTransaction.EXCLUDE_STAT_FIELDS) into ProtoTransaction.stats
        '''
        prototransaction_fields = [ f.name for f in ProtoTransaction._meta.fields ]

        pt_dict = {
            'name': name,
            'stats': { s: stats[s] for s in stats if s not in prototransaction_fields and s not in ProtoTransaction.EXCLUDE_STAT_FIELDS },
            'transactionruleset': transaction_rule_set,
            **{ s: stats[s] for s in stats if s in prototransaction_fields }
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

# class RecordGroup(BaseModel):
#     name = models.CharField(max_length=255)
#     stats = models.JSONField(null=True)

class RecordMeta(BaseModel):

    class Meta:
        indexes = [
            models.Index(fields=['core_fields_hash']),
            models.Index(fields=['raw_data_line_hash']),
            models.Index(fields=['core_fields_hash', 'raw_data_line_hash'])
        ]

    # -- income, refunds, any amount from an external source to the system 
    RECORD_TYPE_UNKNOWN = 'unknown'
    # -- refund is weird.. if an amount is returned as part of an 'expense' it should count as reducing 'expenses', not as independent income
    # -- i.e. tallying up all records typed as 'expense' should be accurate on its own, not needing to combine record types
    # -- so a refund for a purchase is simply a positive 'expense'
    # -- and what's a refund? is there such a thing?
    RECORD_TYPE_REFUND = 'refund'
    RECORD_TYPE_GIFT = 'gift'
    RECORD_TYPE_EARNEDINTEREST = 'earnedinterest'
    # -- income earned by selling something? other than services via employment?
    RECORD_TYPE_SALE = 'sale'
    RECORD_TYPE_INCOME = 'income'
    # -- spending, payments, any amount to an external source from the system 
    RECORD_TYPE_EXPENSE = 'expense'
    RECORD_TYPE_PENALTY = 'penalty'

    # -- transfers, amount staying within the system 
    RECORD_TYPE_INTERNAL = 'internal'

    RECORD_TYPES = [
        RECORD_TYPE_UNKNOWN,
        RECORD_TYPE_REFUND,
        RECORD_TYPE_GIFT,
        RECORD_TYPE_EARNEDINTEREST,
        RECORD_TYPE_SALE,
        RECORD_TYPE_INCOME,
        RECORD_TYPE_EXPENSE,
        RECORD_TYPE_PENALTY,
        RECORD_TYPE_INTERNAL    
    ]

    TAX_CLASSIFICATION_DEDUCTIBLE_EXPENSE               = 'deductible-expense'
    TAX_CLASSIFICATION_DEDUCTIBLE_EXPENSE_UTILITY       = 'deductible-expense-utility'
    TAX_CLASSIFICATION_DEDUCTIBLE_EXPENSE_REPAIR        = 'deductible-expense-repair'
    TAX_CLASSIFICATION_DEDUCTIBLE_EXPENSE_MAINTENANCE   = 'deductible-expense-maintenance'
    TAX_CLASSIFICATION_DEDUCTIBLE_EXPENSE_INSURANCE     = 'deductible-expense-insurance'
    TAX_CLASSIFICATION_PROPERTY_COUNTY      = 'property-county'
    TAX_CLASSIFICATION_PROPERTY_BOROUGH     = 'property-borough'
    TAX_CLASSIFICATION_PROPERTY_SCHOOL      = 'property-school'
    TAX_CLASSIFICATION_INCOME_FEDERAL       = 'income-federal'
    TAX_CLASSIFICATION_INCOME_STATE         = 'income-state'
    TAX_CLASSIFICATION_INCOME_CITY          = 'income-city'
    TAX_CLASSIFICATION_INCOME_LOCAL         = 'income-local'
    TAX_CLASSIFICATION_TRANSFER             = 'transfer'
    TAX_CLASSIFICATION_CAPITAL_GAINS        = 'capital-gains'

    TAX_CLASSIFICATIONS = [
        TAX_CLASSIFICATION_DEDUCTIBLE_EXPENSE,
        TAX_CLASSIFICATION_PROPERTY_COUNTY,
        TAX_CLASSIFICATION_PROPERTY_BOROUGH,
        TAX_CLASSIFICATION_PROPERTY_SCHOOL,
        TAX_CLASSIFICATION_INCOME_FEDERAL,
        TAX_CLASSIFICATION_INCOME_STATE,
        TAX_CLASSIFICATION_INCOME_CITY,
        TAX_CLASSIFICATION_INCOME_LOCAL,
        TAX_CLASSIFICATION_TRANSFER,
        TAX_CLASSIFICATION_CAPITAL_GAINS
    ]

    extra_fields_hash = models.CharField(max_length=32, null=True)
    core_fields_hash = models.CharField(max_length=32, null=True)
    raw_data_line_hash = models.CharField(max_length=32, null=True)
    record_type = models.CharField(max_length=15, null=False, choices=choiceify(RECORD_TYPES), default=RECORD_TYPE_UNKNOWN)
    property = models.ForeignKey(to=Property, related_name='recordmetas', on_delete=models.SET_NULL, null=True)
    vehicle = models.ForeignKey(to=Vehicle, related_name='recordmetas', on_delete=models.SET_NULL, null=True)
    event = models.ForeignKey(to=Event, related_name='recordmetas', on_delete=models.SET_NULL, null=True)
    tax_classification = models.CharField(max_length=30, null=True, choices=choiceify(TAX_CLASSIFICATIONS))
    target = models.CharField(max_length=50, null=True)
    description = models.CharField(max_length=255, blank=True, null=False)
    detail = models.TextField(null=False, blank=True)
    # accounted_at = models.IntegerField(null=True)

    def records(self):
        # RECORDMETA_RELATIONSHIP_POINT
        if not self.raw_data_line_hash:
            logger.warning(f'No raw_data_line_hash value on meta record {self.id}, cannot lookup Records')
            return Record.objects.none()
        return Record.objects.filter(raw_data_line_hash=self.raw_data_line_hash)
    
    def save(self, *args, **kwargs):
        super(RecordMeta, self).save(*args, **kwargs)
        Cache.invalidate()

class RecordTypeManager(models.Manager):

    '''
    -- cancelling double records where a re-upload had a description and the original was blank
    update web_record r 
    inner join web_record r2 on r2.amount = r.amount and r2.transaction_date = r.transaction_date 
    set r.is_valid = 0
    where (r.description = '') 
    and r.id <> r2.id 
    order by r.transaction_date, r.amount;
    '''
    # RECORDMETA_RELATIONSHIP_POINT
    def get_queryset(self):
        meta_join = RecordMeta.objects.filter(raw_data_line_hash=OuterRef('raw_data_line_hash'))
        annotated = super().get_queryset() \
            .filter(is_valid=True) \
            .annotate(meta_description=meta_join.values('description')) \
            .annotate(meta_record_type=meta_join.values('record_type')) \
            .annotate(meta_event_id=meta_join.values('event_id')) \
            .annotate(meta_vehicle_id=meta_join.values('vehicle_id')) \
            .annotate(meta_property_id=meta_join.values('property_id')) \
            .annotate(meta_tax_classification=meta_join.values('tax_classification'))

        # .annotate(meta_accounted_at=meta_join.values('accounted_at')) \

        return annotated # .filter(transaction_date__gte='2022-01-01', transaction_date__lt='2023-01-01')

    # def filter_type(self, record_type):        
    #     return self.filter(meta_record_type=record_type)

    # def exclude_type(self, record_type):
    #     return self.exclude(meta_record_type=record_type)

class BudgetingManager(RecordTypeManager):

    # -- TODO: REFUND had been excluded for a while, why? if an expense and refund are paired, they cancel each other out? (2/16/24)
    def get_queryset(self):
        return super().get_queryset() \
            .exclude(meta_record_type=RecordMeta.RECORD_TYPE_INTERNAL) \
            .exclude(meta_record_type=RecordMeta.RECORD_TYPE_REFUND) \
            .exclude(meta_event_id__isnull=False)
            
            # .exclude(Q(meta_record_type=RecordMeta.RECORD_TYPE_REFUND) | Q(meta_record_type=RecordMeta.RECORD_TYPE_INTERNAL))
        
class Record(BaseModel):
    '''A normalized representation of a single historical transaction'''

    objects = RecordTypeManager()
    budgeting = BudgetingManager()

    class Meta:
        indexes = [
            models.Index(fields=['description']),
            # models.Index(fields=['record_type', 'accounted_at']),
            models.Index(fields=['extra_fields_hash']),
            models.Index(fields=['core_fields_hash']),
            models.Index(fields=['raw_data_line_hash']),
            models.Index(fields=['core_fields_hash', 'raw_data_line_hash'])
        ]

    # record_group = models.ForeignKey(to=RecordGroup, related_name='records', on_delete=models.SET_NULL, null=True)
    uploaded_file = models.ForeignKey(to=UploadedFile, related_name='records', on_delete=models.RESTRICT)    
    # transaction = models.ForeignKey(to=Transaction, related_name='records', on_delete=models.SET_NULL, null=True)
    # creditcardexpense = models.ForeignKey(to=CreditCardExpense, related_name='records', on_delete=models.SET_NULL, null=True)    
    # record_type = models.CharField(max_length=15, null=False, choices=choiceify(RecordMeta.RECORD_TYPES), default=RecordMeta.RECORD_TYPE_UNKNOWN)
    # accounted_at = models.IntegerField(null=True)
    transaction_date = models.DateField()
    post_date = models.DateField(null=True)
    description = models.CharField(max_length=255, blank=True, null=False)
    amount = models.DecimalField(decimal_places=2, max_digits=20)    
    # record_type = models.CharField(max_length=15, null=False, choices=choiceify(RecordMeta.RECORD_TYPES), default=RecordMeta.RECORD_TYPE_UNKNOWN)        
    extra_fields = models.JSONField(null=True)
    is_valid = models.BooleanField(null=False, default=True)
    extra_fields_hash = models.CharField(max_length=32, null=True)
    core_fields_hash = models.CharField(max_length=32, null=True)
    raw_data_line = models.TextField(null=True)
    raw_data_line_hash = models.CharField(max_length=32, null=True)
    
    '''
    select transaction_date, description, amount, count(*) from web_record group by transaction_date, description, amount order by count(*);
    select transaction_date, description, amount, md5(extra_fields) as extra_fields_hash, count(*) from web_record group by transaction_date, description, amount, extra_fields_hash order by count(*);
    '''
    # def __init__(self, *args, **kwargs):
    #     super(Record, self).__init__(*args, **kwargs)
        # if self.uploaded_file_id:
        #     self.account = self.uploaded_file.account
    
    def __str__(self):
        return f'{self.id}, {self.uploaded_file.account or self.uploaded_file.creditcard}, {self.transaction_date}, {self.description}, {self.amount}, {self.extra_fields}' #, {self.account_type}, {self.type}, {self.ref}, {self.credits}, {self.debits}'

    def full_description(self):
        return self.description if self.meta_description == "" else f'{self.description} - {self.meta_description}'

    def record_meta(self):
        # RECORDMETA_RELATIONSHIP_POINT
        if not self.raw_data_line_hash:            
            logger.warning(f'No raw_data_line_hash value on record {self.id}, cannot lookup RecordMeta')
            return RecordMeta.objects.none()
        return RecordMeta.objects.filter(raw_data_line_hash=self.raw_data_line_hash).first()
    
    def save(self, *args, **kwargs):
        
        # -- when shifting the relationship between Record<->RecordMeta on different hash values
        # -- it is critical to remember that RecordMeta are not necessarily distinct, and this
        # -- is a flaw, absolutely, but without a solid solution. because of this indistinction
        # -- one RecordMeta has the potential to represent multiple Records, and on improving 
        # -- the process of finding a distinct fingerprint for a Record, we cannot simply 
        # -- add the new fingerprint for a Record to its existing RecordMeta - the other Records
        # -- represented by that RecordMeta will need to do the same thing - so we must each time 
        # -- we improve create a new RecordMeta and copy the fields from the old one.
        # -- this wasn't wordy enough, really 

        if self.extra_fields is None:
            self.extra_fields = {}
        
        self.extra_fields_hash = record_hash(self.extra_fields)

        core_fields_dict = {
            'transaction_date': datetime.strftime(self.transaction_date, "%s"), 
            'description': self.description, 
            'amount': self.amount, 
            **self.extra_fields
        }
    
        self.core_fields_hash = record_hash(core_fields_dict)
        core_meta = RecordMeta.objects.filter(core_fields_hash=self.core_fields_hash).first()   

        raw_meta = None 

        if self.raw_data_line:

            raw_data_line_hash = record_hash(self.raw_data_line)

            if self.raw_data_line_hash and raw_data_line_hash != self.raw_data_line_hash:
                raise Exception(f'record attempted to save with altered raw_data_line: ')

            logger.debug(f'record raw line: {self.raw_data_line} / {self.raw_data_line_hash}')

            if not self.raw_data_line_hash:
                logger.debug(f'record does not have raw_data_line_hash set, so setting that')
                self.raw_data_line_hash = raw_data_line_hash

            raw_meta = RecordMeta.objects.filter(raw_data_line_hash=self.raw_data_line_hash).first()
            
             
            # meta = RecordMeta.objects.filter(extra_fields_hash=self.extra_fields_hash).first()

            # meta_copy = {}
            # if meta:            
            #     meta_copy = { 
            #         d: meta.__dict__[d] 
            #         for d in meta.__dict__.keys() 
            #             if d in [ 
            #                 f.name 
            #                 for f in RecordMeta._meta.fields 
            #             ] and d not in [
            #                 'id', 
            #                 'created_at', 
            #                 'updated_at', 
            #                 'deleted_at', 
            #                 'extra_fields_hash' 
            #             ] 
            #     }

            # meta_copy.update({'core_fields_hash': self.core_fields_hash})

            # if not core_meta:
            #     logger.debug(f'record core fields: {core_fields_dict}')
            #     core_meta = RecordMeta.objects.create(**meta_copy)
            #     logger.info(f'missing core meta record {core_meta.id} created')

        meta_copy_fields = ['record_type', 'property_id', 'vehicle_id', 'event_id', 'target', 'description', 'detail']

        core_meta_copy = {}
        if core_meta:            

            core_meta_copy = { f: core_meta.__dict__[f] for f in meta_copy_fields }

            # core_meta_copy = { 
            #     d: core_meta.__dict__[d] 
            #     for d in core_meta.__dict__.keys() 
            #         if d in [ 
            #             f.name 
            #             for f in RecordMeta._meta.fields 
            #         ] and d not in [
            #             'id', 
            #             'created_at', 
            #             'updated_at', 
            #             'deleted_at', 
            #             'extra_fields_hash',
            #             'core_fields_hash'
            #         ] 
            # }

        core_meta_copy.update({'raw_data_line_hash': self.raw_data_line_hash})

        if not raw_meta:
            raw_meta = RecordMeta.objects.create(**core_meta_copy)
            logger.info(f'missing raw meta record {raw_meta.id} created with {core_meta_copy}')
        else:
            for c in core_meta_copy.keys():
                if getattr(raw_meta, c):
                    logger.warning(f'meta {raw_meta.id} has {c} = {getattr(raw_meta, c)}')
                else:
                    logger.warning(f'meta {raw_meta.id} -- setting {c} = {core_meta_copy[c]}')
                    setattr(raw_meta, c, core_meta_copy[c])
                logger.warning(f'meta {raw_meta.id} saving')
                raw_meta.save()

        '''
        comparison of core fields meta with raw data line meta:
        select r.id, r.transaction_date, r.description, r.amount, r.raw_data_line, r.raw_data_line_hash, m.id, m.record_type, m.event_id, m.description from web_record r left join web_recordmeta m on (m.core_fields_hash = r.core_fields_hash or m.raw_data_line_hash = r.raw_data_line_hash) where r.uploaded_file_id = 190 order by r.id;
        '''            
            # raw_meta.update(**core_meta_copy)
            # raw_meta.save()


        # if self.record_type == RecordMeta.RECORD_TYPE_UNKNOWN:
        #     self.record_type = core_meta.record_type 
        
        # if self.accounted_at is None:
        #     self.accounted_at = core_meta.accounted_at

        logger.info(f'record saving with extra_fields_hash {self.extra_fields_hash}, core_fields_hash {self.core_fields_hash}, raw_data_line_hash {self.raw_data_line_hash}: {args}')

        super(Record, self).save(*args, **kwargs)

        Cache.invalidate()

    #     self.clean()
    #     matches = Record.objects.filter(
    #         ~Q(uploaded_file=self.uploaded_file),
    #         date=self.date, 
    #         description=self.description, 
    #         amount=self.amount
    #     )
    #     if len(matches) > 0:
    #         raise ValidationError(_(f'Record.save: Another record(s) {",".join([ str(m.id) for m in matches ])} for a different upload (them:{",".join([ str(m.uploaded_file.id) for m in matches ])}, us:{self.uploaded_file.id}) matching all fields already exists in the database.'))
        


# MANAGER_METHOD_LOOKUP = {
#     TransactionRule.INCLUSION_FILTER: Record.objects.filter,
#     TransactionRule.INCLUSION_EXCLUDE: Record.objects.exclude,
# }

class Settings(BaseModel):

    SETTINGS_WORKING_BRACKET = 'working_bracket'
    SETTINGS_NULL = 'null'

    SETTINGS_CHOICES = [
        (SETTINGS_WORKING_BRACKET, 'working bracket',)
    ]

    SETTINGS_TYPES = {
        SETTINGS_WORKING_BRACKET: 'fromto'
    }

    name = models.CharField(choices=SETTINGS_CHOICES, max_length=255, null=False, default=SETTINGS_NULL)
    value = models.CharField(max_length=255, null=True)    

class TransactionTag(BaseModel):

    name = models.CharField(max_length=255, null=False)

class RequiredTransactionTag(BaseModel):

    transaction_tag = models.ForeignKey(TransactionTag, related_name='requiredtransactiontags', on_delete=models.CASCADE, null=False)

class TransactionSet(BaseModel):

    name = models.CharField(max_length=255, null=False)

class TracingResults(BaseModel):

    data = models.JSONField(null=False)
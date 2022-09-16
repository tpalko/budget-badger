from turtle import hideturtle
from django.db.models import Q
from django.forms import Form, ModelChoiceField, ModelForm, HiddenInput, CharField, ChoiceField, BaseFormSet, DecimalField, formset_factory
from django.forms.models import modelformset_factory, BaseModelFormSet
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from web.models import BaseModel, TransactionRule, TransactionRuleSet, RecordType, CreditCard, Record, Property, UploadedFile, Account, Transaction, RecurringTransaction, CreditCardExpense, SingleTransaction, CreditCardTransaction, DebtTransaction
import logging 
import web.util.dates as utildates

logger = logging.getLogger(__name__)

class BaseTransactionRuleFormSet(BaseModelFormSet):

    def is_valid(self, preRuleSet=False):        
        # super(BaseTransactionRuleFormSet, self).is_valid()

        exclude = []
        if preRuleSet:
            exclude.append('transactionruleset')
        
        for form in self.forms:
            form.is_valid(preRuleSet=preRuleSet)

class TransactionRuleForm(ModelForm):

    class Meta:
        model = TransactionRule 
        fields = ('id', 'record_field', 'match_operator', 'match_value', 'transactionruleset')
    
    id = CharField(widget=HiddenInput(), required=False)
    transactionruleset = ModelChoiceField(widget=HiddenInput(), queryset=TransactionRuleSet.objects.all())

    def is_valid(self, preRuleSet=False):        
        super(TransactionRuleForm, self).is_valid()

        exclude = []
        if preRuleSet:
            exclude.append('transactionruleset')

        for field in [ f for f in self.fields if f not in exclude ]:
            if field not in self.cleaned_data:
                raise ValidationError({field: _('All fields are required')})

class TransactionRuleSetForm(ModelForm):

    class Meta:
        model = TransactionRuleSet 
        fields = ['id', 'name', 'join_operator']
    
    join_operator = ChoiceField(choices=TransactionRuleSet.join_operator_choices)
    
    id = CharField(widget=HiddenInput(), required=False)
    
class RecordTypeForm(ModelForm):

    class Meta:
        model = RecordType 
        fields = ['name', 'csv_columns', 'csv_date_format']

class CreditCardForm(ModelForm):

    class Meta:
        model = CreditCard 
        fields = ['recordtype', 'name', 'account_number', 'interest_rate']
    
    recordtype = ModelChoiceField(queryset=RecordType.objects.all(), required=False)

class RecordForm(ModelForm):

    class Meta:
        model = Record 
        fields = ['transaction_date', 'post_date', 'description', 'amount', 'extra_fields', 'uploaded_file', 'account', 'creditcard'] #'account_type', 'type', 'ref', 'credits', 'debits', ]

    account = ModelChoiceField(queryset=Account.objects.all(), required=False)
    creditcard = ModelChoiceField(queryset=CreditCard.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        
        super(RecordForm, self).__init__(*args, **kwargs)
        exclude_extras = ['uploaded_file', 'account', 'creditcard']        

        extra_fields = { k: args[0][k] for k in args[0] if k not in self.fields.keys() and k not in exclude_extras }
        if 'extra_fields' not in args:
            args[0]['extra_fields'] = {}
        args[0]['extra_fields'] = { **extra_fields, **args[0]['extra_fields'] }

    def is_valid(self):

        super(RecordForm, self).is_valid()

        # -- if a match is found under the same uploaded file, it's OK. 
        # -- one CSV download from the bank or CC agency should not have duplicates 
        # -- but it's conceivable that two transactions in that CSV match all fields 
        # -- however, if a match is found under a different file, 
        # -- it's likely this CSV download overlaps with a previous CSV download 
        matches = Record.objects.filter(
            ~Q(uploaded_file=self.cleaned_data['uploaded_file']),
            transaction_date=self.cleaned_data['transaction_date'] if 'transaction_date' in self.cleaned_data else None, 
            description=self.cleaned_data['description'] if 'description' in self.cleaned_data else None, 
            amount=self.cleaned_data['amount'] if 'amount' in self.cleaned_data else None
        )
        #     account_type=self.cleaned_data['account_type'] if 'account_type' in self.cleaned_data else None, 
        #     type=self.cleaned_data['type'] if 'type' in self.cleaned_data else None, 
        #     ref=self.cleaned_data['ref'] if 'ref' in self.cleaned_data else None, 
        #     credits=self.cleaned_data['credits'] if 'credits' in self.cleaned_data else None, 
        #     debits=self.cleaned_data['debits'] if 'debits' in self.cleaned_data else None
        # )

        if len(matches) > 0:
            raise ValidationError(_(f'RecordForm.is_valid: Another record(s) {",".join([ str(m.id) for m in matches ])} for a different upload (them:{",".join([ str(m.uploaded_file_id) for m in matches ])}, us:{self.cleaned_data["uploaded_file_id"] if "uploaded_file_id" in self.cleaned_data else self.cleaned_data["uploaded_file"]}) matching all fields already exists in the database.'))
        
        return True

class UploadedFileForm(ModelForm):

    class Meta:
        model = UploadedFile 
        fields = ['upload', 'account', 'creditcard', 'original_filename']
    
    original_filename = CharField(widget=HiddenInput())

    def __init__(self, *args, **kwargs):
        post_copy = None 
        for arg in args:
            if 'account' in arg:
                post_copy = arg.copy()
            if 'upload' in arg:                
                original_filename = arg['upload'].name 
        if post_copy:
            post_copy.__setitem__('original_filename', original_filename)
            args = (post_copy, args[1],)
        
        super(UploadedFileForm, self).__init__(*args, **kwargs)
    
    def is_valid(self):

        super(UploadedFileForm, self).is_valid()

        if not self.cleaned_data['account'] and not self.cleaned_data['creditcard']:
            raise ValidationError(_('One of account or creditcard must be set.'))
        
        return True 
    
class AccountForm(ModelForm):

    class Meta:
        model = Account 
        fields = ['name', 'balance', 'balance_at', 'minimum_balance', 'account_number', 'recordtype']

BASE_TRANSACTION_FIELDS = ['id', 'name', 'amount', 'account', 'transaction_type', 'is_active', 'is_imported']

class TransactionForm(ModelForm):

    class Meta:
        model = Transaction
        fields = BASE_TRANSACTION_FIELDS

    # transaction_type = ChoiceField(choices=Transaction.type_choices)
    id = CharField(widget=HiddenInput(), required=False)
    is_imported = CharField(widget=HiddenInput())
    record_ids = CharField(widget=HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        
        if 'initial' in kwargs:
            self.stats = { key: kwargs['initial'][key] for key in sorted(kwargs['initial'].keys()) if key not in self.base_fields.keys() }
        
        super(TransactionForm, self).__init__(*args, **kwargs)

    def clean(self):
        ''' Pre-save processing: fixing 'amount' sign. '''

        super(TransactionForm, self).clean()

        if 'amount' in self.cleaned_data:
            amount = self.cleaned_data['amount']
            transaction_type = self.cleaned_data['transaction_type']
            # logger.warning(f'Amount for {transaction_type}: {amount}')
            amount_sign = "positive" if amount > 0 else "negative" if amount < 0 else None 
            
            if transaction_type == Transaction.TRANSACTION_TYPE_INCOME and amount_sign == "negative" \
                or transaction_type != Transaction.TRANSACTION_TYPE_INCOME and amount_sign == "positive":
                
                self.cleaned_data['amount'] = -self.cleaned_data['amount']
                # name = self.cleaned_data["name"]
                # raise ValidationError({'amount': _(f'{name}: Amount for {transaction_type} cannot be {amount_sign}.')})
            # else:
            #     logger.warning(f'Amount sign {amount_sign} appears to be appropriate for transaction type {transaction_type}')

class TransactionIntakeForm(TransactionForm):
    
    class Meta:
        model = Transaction
        fields = ['id', 'name', 'amount', 'account', 'transaction_type']

    # frequency = ChoiceField(choices=RecurringTransaction.period_choices)
    # transaction_type = ChoiceField(choices=Transaction.type_choices)

    stats = {}
    record_group_id = CharField(widget=HiddenInput())
    is_imported = CharField(widget=HiddenInput())
    
    def save(self):
        transaction_type = self['transaction_type'].value()
        logger.warning(f'Loading typed form for {transaction_type}')
        logger.warning(dir(self))        
        logger.warning(self.cleaned_data)
        logger.warning(self.data)
        logger.warning(self.fields)
        logger.warning(self.initial)
        logger.warning(self.instance)
        typed_form = form_types[transaction_type]({ **self.cleaned_data, 'period': utildates.PERIOD_MONTHLY})
        if typed_form.is_valid():
            logger.warning(f'Form is valid!')
            # super(TransactionIntakeForm, self).save()
            typed_form.save()
        else:
            logger.warning(f'Form is NOT valid')
            logger.warning(dir(typed_form))
            logger.warning(f'typed form errors: {len(typed_form.errors)}')
            logger.warning(typed_form.errors)
            logger.warning(f'typed form non-field errors:')
            logger.warning(typed_form.non_field_errors())

class SingleTransactionForm(TransactionForm):

    class Meta:
        model = SingleTransaction
        fields = BASE_TRANSACTION_FIELDS + ['transaction_at', 'creditcardtransaction', 'property', 'tax_category']
    
    tax_category = ChoiceField(choices=Transaction.tax_category_choices, required=False)
    property = ModelChoiceField(queryset=Property.objects.all(), required=False)

class RecurringTransactionForm(TransactionForm):

    class Meta:
        model = RecurringTransaction
        fields = BASE_TRANSACTION_FIELDS + ['period', 'started_at', 'cycle_due_date', 'is_variable', 'property', 'tax_category'] #, 'transactionruleset']

    period = ChoiceField(choices=RecurringTransaction.period_choices)
    tax_category = ChoiceField(choices=Transaction.tax_category_choices, required=False)
    property = ModelChoiceField(queryset=Property.objects.all(), required=False)
    # transactionruleset = ModelChoiceField(queryset=TransactionRuleSet.objects.all(), required=False)

class IncomeForm(RecurringTransactionForm):

    class Meta:
        model = RecurringTransaction
        fields = BASE_TRANSACTION_FIELDS + ['period', 'started_at', 'is_variable']

class CreditCardTransactionForm(RecurringTransactionForm):
    class Meta:
        model = CreditCardTransaction
        fields = BASE_TRANSACTION_FIELDS + ['period', 'started_at', 'cycle_due_date', 'is_variable', 'cycle_billing_date', 'creditcard']
        exclude = ['amount']
    
    def __init__(self, *args, **kwargs):
        instance = kwargs['instance'] if 'instance' in kwargs else None 
        # if args and 'amount' not in args and instance:
        #     args['amount'] = instance.expense_total()
        super(CreditCardTransactionForm, self).__init__(*args, **kwargs)

class DebtTransactionForm(RecurringTransactionForm):

    class Meta:
        model = DebtTransaction
        fields = BASE_TRANSACTION_FIELDS + ['period', 'started_at', 'cycle_due_date', 'is_variable', 'interest_rate', 'principal', 'principal_at']

class CreditCardExpenseForm(ModelForm):

    class Meta:
        model = CreditCardExpense
        fields = ['name', 'amount', 'creditcardtransaction']
        labels = {'name': 'Name', 'amount': 'Amount', 'creditcardtransaction': 'Credit Card'}

    def clean(self):
        print(f'Cleaning CreditCardExpenseForm..')
        super(CreditCardExpenseForm, self).clean()
        if 'amount' in self.cleaned_data and self.cleaned_data['amount'] > 0:
            self.cleaned_data['amount'] = -self.cleaned_data['amount']
            self.instance.amount = self.cleaned_data['amount']
            logger.info("cleaned: %s and instance: %s" %(self.cleaned_data['amount'], self.instance.amount))

credit_card_expense_model_field_lookup = {
    'name': CharField,
    'amount': DecimalField,
    'creditcardtransaction': ChoiceField
}

def credit_card_expense_model_field_choices_callback():
    return [ (cct.id, cct.name) for cct in CreditCardTransaction.objects.all() ]

def credit_card_expense_model_field_callback(model_field, label):
    if credit_card_expense_model_field_lookup[model_field.name] == ChoiceField:
        return credit_card_expense_model_field_lookup[model_field.name](label=label, choices=credit_card_expense_model_field_choices_callback)
    else:
        return credit_card_expense_model_field_lookup[model_field.name](label=label)

CreditCardExpenseFormSet = modelformset_factory(
    model = CreditCardExpense,
    form = CreditCardExpenseForm,    
    can_delete = True
    # formfield_callback = credit_card_expense_model_field_callback
)


form_types = {
    Transaction.TRANSACTION_TYPE_SINGLE: SingleTransactionForm,
    Transaction.TRANSACTION_TYPE_INCOME: IncomeForm,
    Transaction.TRANSACTION_TYPE_UTILITY: RecurringTransactionForm,
    Transaction.TRANSACTION_TYPE_CREDITCARD: CreditCardTransactionForm,
    Transaction.TRANSACTION_TYPE_DEBT: DebtTransactionForm,
    Transaction.TRANSACTION_TYPE_UNKNOWN: SingleTransactionForm,
}

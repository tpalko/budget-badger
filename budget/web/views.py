from django.shortcuts import render, render_to_response, redirect
from django.template import Context, RequestContext
from django.template.loader import get_template
from django.forms import ModelForm, BooleanField, DateField, HiddenInput, CharField
from django.forms.models import modelformset_factory, BaseModelFormSet
from django.http import JsonResponse
from django.contrib import messages
from django.core import serializers
from django.db.models import Sum, Q, Func, F
import sys
from models import *
from decimal import Decimal
from datetime import datetime, timedelta
import logging
import traceback

logger = logging.getLogger(__name__)

class TransactionForm(ModelForm):

	class Meta:
		model = Transaction
		fields = ['name', 'amount', 'transaction_type', 'is_active']
	
	transaction_type = CharField(widget=HiddenInput())

	def clean(self):
		''' Pre-save processing: fixing 'amount' sign. '''

		super(TransactionForm, self).clean()

		if 'amount' in self.cleaned_data:
			# - make sure the sign of the amount is correct, based on the transaction type
			switch_sign = (self.cleaned_data['transaction_type'] == Transaction.TRANSACTION_TYPE_INCOME and self.cleaned_data['amount'] < 0) or (self.cleaned_data['transaction_type'] != Transaction.TRANSACTION_TYPE_INCOME and self.cleaned_data['amount'] > 0)

			if switch_sign:
				self.cleaned_data['amount'] = -self.cleaned_data['amount']
				self.instance.amount = self.cleaned_data['amount']

class RecurringTransactionForm(TransactionForm):

	class Meta:
		model = RecurringTransaction
		fields = ['name', 'amount', 'period', 'started_at', 'cycle_due_date', 'is_variable', 'transaction_type', 'is_active']

	transaction_type = CharField(widget=HiddenInput())

	def __init__(self, *args, **kwargs):
		''' This doesn't do anything at the moment.. don't remember what it used to do.. '''

		#is_income = False
		
		if 'instance' in kwargs:
			instance = kwargs.get('instance')
			#is_income = instance.transaction_type == 'income'

		if len(args) > 0:
			post = args[0]
			#is_income = post.get('transaction_type') == 'income'

		initial = kwargs.get('initial', {})
		#initial['is_income'] = is_income
		kwargs['initial'] = initial

		super(RecurringTransactionForm, self).__init__(*args, **kwargs)

class CreditCardTransactionForm(RecurringTransactionForm):
	 
	 class Meta:
	 	model = CreditCardTransaction
	 	fields = ['name', 'period', 'started_at', 'cycle_due_date','interest_rate', 'is_variable', 'transaction_type', 'cycle_billing_date']

class DebtTransactionForm(RecurringTransactionForm):

	class Meta:
		model = DebtTransaction
		fields = ['name', 'amount','period', 'started_at', 'cycle_due_date','interest_rate', 'is_variable', 'transaction_type', 'principal', 'principal_at']

class SingleTransactionForm(TransactionForm):
	
	class Meta:
		model = SingleTransaction
		fields = ['name', 'amount', 'transaction_at', 'creditcardtransaction', 'transaction_type']

class BaseCreditCardExpenseFormSet(BaseModelFormSet):

	class Meta:
		model = CreditCardExpense

	def clean(self):
		super(BaseCreditCardExpenseFormSet, self).clean()
		for form in self.forms:
			if 'amount' in form.cleaned_data and form.cleaned_data['amount'] > 0:
				form.cleaned_data['amount'] = -form.cleaned_data['amount']
				form.instance.amount = form.cleaned_data['amount']
				logger.info("cleaned: %s and instance: %s" %(form.cleaned_data['amount'], form.instance.amount))
		
CreditCardExpenseFormSet = modelformset_factory(CreditCardExpense, fields = ('name', 'amount', 'creditcardtransaction'), formset=BaseCreditCardExpenseFormSet)

form_types = {
	Transaction.TRANSACTION_TYPE_SINGLE: SingleTransactionForm,	
	Transaction.TRANSACTION_TYPE_INCOME: RecurringTransactionForm,
	Transaction.TRANSACTION_TYPE_UTILITY: RecurringTransactionForm,
	Transaction.TRANSACTION_TYPE_CREDITCARD: CreditCardTransactionForm,
	Transaction.TRANSACTION_TYPE_DEBT: DebtTransactionForm
}

transaction_types = {
	Transaction.TRANSACTION_TYPE_SINGLE: SingleTransaction,
	Transaction.TRANSACTION_TYPE_INCOME: RecurringTransaction,
	Transaction.TRANSACTION_TYPE_UTILITY: RecurringTransaction,
	Transaction.TRANSACTION_TYPE_CREDITCARD: CreditCardTransaction,
	Transaction.TRANSACTION_TYPE_DEBT: DebtTransaction
}

def home(request):

	return redirect('projection')
	
def projection(request):

	payments = PlannedPayment.objects.order_by('payment_at', 'transaction__amount')

	return render_to_response("projection.html", {'payments': payments}, context_instance=RequestContext(request))

def run_projections(request):

	error = False
	message = ""
	result = {}

	try:

		starting_cash = Decimal(request.POST.get('starting_cash'))
		minimum_balance = Decimal(request.POST.get('minimum_balance'))

		PlannedPayment.objects.all().delete()

		single_transactions = SingleTransaction.objects.all()

		for s in single_transactions:

			due_date = s.due_date()

			if due_date > datetime.now().date():
				plannedpayment = PlannedPayment(transaction=s, payment_at=due_date)
				plannedpayment.save()

		recurring_transactions = RecurringTransaction.objects.filter(is_active=True)
		
		one_year = (datetime.utcnow() + timedelta(days=365)).date()

		for e in recurring_transactions:

			payment_at = e.next_payment_date()

			while payment_at < one_year:
				plannedpayment = PlannedPayment(transaction=e, payment_at=payment_at)
				plannedpayment.save()
				payment_at = e.advance_payment_date(payment_at)

		cursor = datetime.utcnow()

		highest_interest_debt = DebtTransaction.objects.filter(transaction_type=Transaction.TRANSACTION_TYPE_DEBT).order_by('-interest_rate').first()

		while True:

			# - First, calculate the running balance for all schedule transactions
			planned_payments = PlannedPayment.objects.order_by('payment_at', 'transaction__amount')

			running_balance = starting_cash

			for planned_payment in planned_payments:			
				running_balance += planned_payment.transaction.real_amount() + planned_payment.overpayment
				planned_payment.balance = running_balance
				planned_payment.save()

			# - Next, find the transactions that align with the lowest balances
			# - These are the transactions we want to use as indicators for how much we can overpay on debts
			lowest_balance_transactions = PlannedPayment.objects.filter(payment_at__gt=cursor, payment_at__lt=one_year, balance__gt=minimum_balance).order_by('balance')

			if len(lowest_balance_transactions) == 0:
				break

			logger.info("lowest balance transactions from %s to %s: %s" %(cursor, one_year, len(lowest_balance_transactions)))

			hit = False

			for lbt in lowest_balance_transactions:

				# - find a payment for our chosen HID that occurs before this LBT to which we can apply our overpayment
				next_highest_interest_payment = PlannedPayment.objects.filter(payment_at__gt=cursor, payment_at__lte=lbt.payment_at, transaction__id=highest_interest_debt.transaction_ptr_id).order_by('payment_at').first()

				if next_highest_interest_payment:
					
					next_highest_interest_payment.overpayment = -(lbt.balance - minimum_balance)
					next_highest_interest_payment.save()

					logger.info("Applying %s from %s on %s to %s on %s" % (next_highest_interest_payment.overpayment, lbt.transaction.name, lbt.payment_at, next_highest_interest_payment.transaction.name, next_highest_interest_payment.payment_at))

					cursor = lbt.payment_at
					hit = True
				
					break

			if not hit:
				break

	except:
		error = True
		message = str(sys.exc_info()[1])
		logger.error(message)
		traceback.print_tb(sys.exc_info()[2])

	return JsonResponse({'error': error, 'message': message, 'result': result})

	# - set up start date and periods
	# - iterate through periods, figure which transactions fit
	# - write period transactions into PlannedPayment and calculated balances into Balance

def transactions(request):

	single_transactions = SingleTransaction.objects.all().order_by('-transaction_at')
	income_transactions = RecurringTransaction.objects.filter(transaction_type=Transaction.TRANSACTION_TYPE_INCOME).order_by('name')
	debt_transactions = DebtTransaction.objects.all().order_by('-interest_rate')
	utility_transactions = RecurringTransaction.objects.filter(transaction_type=Transaction.TRANSACTION_TYPE_UTILITY).order_by('name')
	creditcard_transactions = CreditCardTransaction.objects.all()

	transactions = RecurringTransaction.objects.all()
	avg_monthly_out = sum([ o.real_amount()*RecurringTransaction.period_monthly_occurrence[o.period] for o in transactions if o.transaction_type in [Transaction.TRANSACTION_TYPE_UTILITY, Transaction.TRANSACTION_TYPE_DEBT, Transaction.TRANSACTION_TYPE_CREDITCARD] ])
	avg_monthly_in = sum([ o.real_amount()*RecurringTransaction.period_monthly_occurrence[o.period] for o in transactions if o.transaction_type in [Transaction.TRANSACTION_TYPE_INCOME] ])
	avg_monthly_balance = avg_monthly_in + avg_monthly_out

	total_debt = sum([d.principal for d in debt_transactions])

	return render_to_response("transactions.html", 
		{
			'total_debt': total_debt, 
			'avg_monthly_balance': avg_monthly_balance, 
			'avg_monthly_out': avg_monthly_out, 
			'avg_monthly_in': avg_monthly_in, 
			'single_transactions': single_transactions,
			'income_transactions': income_transactions, 
			'debt_transactions': debt_transactions, 
			'utility_transactions': utility_transactions, 
			'creditcard_transactions': creditcard_transactions
		}, context_instance=RequestContext(request))

def transaction_new(request, transaction_type):
	
	if request.method == "POST":

		transaction_form = form_types[transaction_type](request.POST)

		if transaction_form.is_valid():
			t = transaction_form.save()
			return redirect('transactions')
	
	transaction_form = form_types[transaction_type](initial={'transaction_type': transaction_type})
	
	return render_to_response("transaction_edit.html", {'transaction_form': transaction_form, 'new_or_edit': 'New', 'transaction_type_or_name': [ c[1] for c in Transaction.type_choices if c[0] == transaction_type ][0]}, context_instance=RequestContext(request))

def transaction_edit(request, name_slug):

	logger.info("editing %s" % name_slug)
	name = name_slug.replace('_', ' ')
	
	transaction = Transaction.objects.filter(name=name)[0]

	transaction = transaction_types[transaction.transaction_type].objects.filter(name=name)[0]
	transaction_form = form_types[transaction.transaction_type](instance=transaction)

	if request.method == "POST":

		logger.info("got post for %s" % name_slug)
		transaction_form = form_types[transaction.transaction_type](request.POST, instance=transaction)

		if transaction_form.is_valid():
			transaction_form.save()
			return redirect('transactions')
		else:
			logger.error("not valid!")

	return render_to_response("transaction_edit.html", {'transaction_form': transaction_form, 'new_or_edit': 'Edit', 'transaction_type_or_name': "%s: %s" % ([ c[1] for c in Transaction.type_choices if c[0] == transaction.transaction_type ][0], transaction.name)}, context_instance=RequestContext(request))

def creditcardexpenses(request):

	expense_formset = CreditCardExpenseFormSet()

	if request.method == "POST":
		expense_formset = CreditCardExpenseFormSet(request.POST)
		if expense_formset.is_valid():
			logger.info(expense_formset.forms[0].instance.amount)
			expense_formset.save()

			if request.POST.get('save_and_add'):
				return redirect('creditcardexpenses')
			else:
				return redirect('transactions')

	return render_to_response("creditcardexpenses.html", {'expense_formset': expense_formset}, context_instance=RequestContext(request))




from django.shortcuts import render, render_to_response, redirect
from django.template import Context, RequestContext
from django.template.loader import get_template
from django.forms import ModelForm, BooleanField
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

# Create your views here.

class TransactionForm(ModelForm):

	class Meta:
		model = RecurringTransaction
		fields = ['name', 'amount','started_at', 'cycle_date','period', 'interest_rate', 'is_variable', 'transaction_type']

	def __init__(self, *args, **kwargs):

		is_income = False
		
		if 'instance' in kwargs:
			instance = kwargs.get('instance')
			is_income = instance.transaction_type == 'income'

		if len(args) > 0:
			post = args[0]
			is_income = post.get('transaction_type') == 'income'

		kwargs['initial'] = {'is_income': is_income}

		super(TransactionForm, self).__init__(*args, **kwargs)

	def save(self, commit=True):

		m = super(TransactionForm, self).save(commit=commit)

		if (self.cleaned_data['transaction_type'] == Transaction.TRANSACTION_TYPE_INCOME and m.amount < 0) or (self.cleaned_data['transaction_type'] != Transaction.TRANSACTION_TYPE_INCOME and m.amount > 0):
			m.amount = -m.amount
			m.save()

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

		recurring_transactions = RecurringTransaction.objects.all()
				
		PlannedPayment.objects.all().delete()
		Period.objects.all().delete()

		six_months = (datetime.now() + timedelta(days=180)).date()
		one_year = (datetime.now() + timedelta(days=365)).date()

		for e in recurring_transactions:

			if e.period in RecurringTransaction.period_week_lengths:
				payment_at = e.started_at
				while payment_at < datetime.now().date():
					payment_at += timedelta(days=RecurringTransaction.period_week_lengths[e.period])
				while payment_at < one_year:
					plannedpayment = PlannedPayment(transaction=e, payment_at=payment_at)
					plannedpayment.save()
					payment_at += timedelta(days=RecurringTransaction.period_week_lengths[e.period])

			elif e.period in RecurringTransaction.period_month_lengths:
				
				payment_at = datetime.now().date()

				if e.started_at:
					payment_at = e.started_at
					while payment_at < datetime.now().date():
						payment_at = payment_at.replace(month=next_month(payment_at, e.period))
				elif e.cycle_date > datetime.now().day:
					payment_at = datetime.now().replace(day=e.cycle_date).date()
				elif e.cycle_date < datetime.now().day:
					payment_at = datetime.now().replace(day=e.cycle_date, month=next_month(datetime.now(), e.period)).date()
				
				while payment_at <= one_year:
					plannedpayment = PlannedPayment(transaction=e, payment_at=payment_at)
					plannedpayment.save()
					new_month = next_month(payment_at, e.period)
					new_year = next_year(payment_at, e.period)
					payment_at = payment_at.replace(month=new_month, year=new_year)

		cursor = datetime.now()

		while True:

			planned_payments = PlannedPayment.objects.order_by('payment_at', 'transaction__amount')

			running_balance = starting_cash

			for planned_payment in planned_payments:			
				running_balance += planned_payment.transaction.amount + planned_payment.overpayment
				planned_payment.balance = running_balance
				planned_payment.save()

			lowest_balance_transactions = PlannedPayment.objects.filter(payment_at__gt=cursor, payment_at__lt=one_year, balance__gt=minimum_balance).order_by('balance')

			if len(lowest_balance_transactions) == 0:
				break

			for lbt in lowest_balance_transactions:

				next_highest_interest_payment = PlannedPayment.objects.filter(payment_at__gt=cursor, payment_at__lte=lbt.payment_at, transaction__transaction_type=Transaction.TRANSACTION_TYPE_DEBT).order_by('-transaction__interest_rate', 'payment_at').first()

				if next_highest_interest_payment:

					next_highest_interest_payment.overpayment = -(lbt.balance - minimum_balance)
					next_highest_interest_payment.save()

					logger.info("Applying %s from %s on %s to %s on %s" % (next_highest_interest_payment.overpayment, lbt.transaction.name, lbt.payment_at, next_highest_interest_payment.transaction.name, next_highest_interest_payment.payment_at))

					cursor = lbt.payment_at
				
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

	income_transactions = RecurringTransaction.objects.filter(transaction_type=Transaction.TRANSACTION_TYPE_INCOME)
	debt_transactions = RecurringTransaction.objects.filter(transaction_type=Transaction.TRANSACTION_TYPE_DEBT)
	utility_transactions = RecurringTransaction.objects.filter(transaction_type=Transaction.TRANSACTION_TYPE_UTILITY)
	
	transactions = RecurringTransaction.objects.all()

	avg_monthly_out = sum([ o.amount*RecurringTransaction.period_monthly_occurrence[o.period] for o in transactions if o.transaction_type in [Transaction.TRANSACTION_TYPE_UTILITY, Transaction.TRANSACTION_TYPE_DEBT] ])
	avg_monthly_in = sum([ o.amount*RecurringTransaction.period_monthly_occurrence[o.period] for o in transactions if o.transaction_type in [Transaction.TRANSACTION_TYPE_INCOME] ])
	avg_monthly_balance = avg_monthly_in + avg_monthly_out

	return render_to_response("transactions.html", {'avg_monthly_balance': avg_monthly_balance, 'avg_monthly_out': avg_monthly_out, 'avg_monthly_in': avg_monthly_in, 'income_transactions': income_transactions, 'debt_transactions': debt_transactions, 'utility_transactions': utility_transactions }, context_instance=RequestContext(request))

def transaction_new(request):
	
	transaction_form = TransactionForm()	

	if request.method == "POST":
		transaction_form = TransactionForm(request.POST)

		if transaction_form.is_valid():
			transaction_form.save()
			return redirect('transactions')

	return render_to_response("transaction_edit.html", {'transaction_form': transaction_form}, context_instance=RequestContext(request))

def transaction_edit(request, name_slug):

	name = name_slug.replace('_', ' ')
	transaction = RecurringTransaction.objects.filter(name=name)[0]

	transaction_form = TransactionForm()

	if request.method == "POST":
		transaction_form = TransactionForm(request.POST, instance=transaction)
		if transaction_form.is_valid():
			transaction_form.save()
			return redirect('transactions')
	else:	
		transaction_form = TransactionForm(instance=transaction)

	return render_to_response("transaction_edit.html", {'transaction_form': transaction_form}, context_instance=RequestContext(request))

def next_month(date, period):

	return (date.month+RecurringTransaction.period_month_lengths[period])%12 or 12

def next_year(date, period):

	if date.month + RecurringTransaction.period_month_lengths[period] > 12:
		return date.year + 1

	return date.year


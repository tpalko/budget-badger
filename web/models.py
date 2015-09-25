from django.db import models
import datetime
from django.core.validators import MinValueValidator, MaxValueValidator
import logging

logger = logging.getLogger(__name__)

class Transaction(models.Model):
	
	TRANSACTION_TYPE_INCOME = 'income'
	TRANSACTION_TYPE_UTILITY = 'utility'
	TRANSACTION_TYPE_DEBT = 'debt'
	TRANSACTION_TYPE_CREDITCARD = 'creditcard'

	type_choices = (
		(TRANSACTION_TYPE_INCOME, 'Income'),
		(TRANSACTION_TYPE_UTILITY, 'Utility'),
		(TRANSACTION_TYPE_DEBT, 'Debt'),
		(TRANSACTION_TYPE_CREDITCARD, 'Credit Card')
	)

	name = models.CharField(max_length=200, unique=True)
	amount = models.DecimalField(decimal_places=2, max_digits=20)	
	transaction_type = models.CharField(max_length=50, choices=type_choices, default=TRANSACTION_TYPE_DEBT)

	def real_amount(self):

		if self.transaction_type == Transaction.TRANSACTION_TYPE_CREDITCARD:
			return self.recurringtransaction.creditcardtransaction.expense_total()
		else:
			return self.amount

	def slug(self):
		return self.name.replace(' ', '_')

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
		PERIOD_WEEKLY: 52/12,
		PERIOD_BIWEEKLY: 26/12,
		PERIOD_MONTHLY: 1,
		PERIOD_QUARTERLY: 1/3,
		PERIOD_SEMIYEARLY: 1/6,
		PERIOD_YEARLY: 1/12
	}

	started_at = models.DateField(default=datetime.datetime.now(), blank=True, null=True)
	cycle_date = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1, blank=True, null=True)
	period = models.CharField(max_length=50, choices=period_choices, default=PERIOD_MONTHLY)	
	is_variable = models.BooleanField(null=False, default=False)

class CreditCardTransaction(RecurringTransaction):
	
	interest_rate = models.DecimalField(decimal_places=2, max_digits=5, default=0)
	closing_date = models.DateField(default=datetime.datetime.now())

	def expense_total(self):
		return sum([e.amount for e in self.creditcardexpense_set.all()])

class DebtTransaction(RecurringTransaction):

	principal = models.DecimalField(decimal_places=2, max_digits=20, default=0)
	principal_at = models.DateField()
	interest_rate = models.DecimalField(decimal_places=2, max_digits=5, default=0)

class OneTimeTransaction(Transaction):
	pass	

class CreditCardExpense(models.Model):
	creditcardtransaction = models.ForeignKey(CreditCardTransaction)
	name = models.CharField(max_length=50)
	amount = models.DecimalField(decimal_places=2, max_digits=20, default=0)

	def __unicode__(self):
		return self.name

class Period(models.Model):

	#transactions = models.ManyToManyField(Transaction, through='PlannedPayment')
	periodstart_at = models.DateField()
	period_days = models.IntegerField(default=7)
	expense_total = models.DecimalField(decimal_places=2, max_digits=20, default=0)
	income_total = models.DecimalField(decimal_places=2, max_digits=20, default=0)
	balance = models.DecimalField(decimal_places=2, max_digits=20, default=0)

class PlannedPayment(models.Model):

	transaction = models.ForeignKey(Transaction)
	#period = models.ForeignKey(Period)
	overpayment = models.DecimalField(decimal_places=2, max_digits=20, default=0)
	payment_at = models.DateField()
	balance = models.DecimalField(decimal_places=2, max_digits=20, default=0)

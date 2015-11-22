# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CreditCardExpense',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50)),
                ('amount', models.DecimalField(default=0, max_digits=20, decimal_places=2)),
            ],
        ),
        migrations.CreateModel(
            name='PlannedPayment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('overpayment', models.DecimalField(default=0, max_digits=20, decimal_places=2)),
                ('payment_at', models.DateField()),
                ('balance', models.DecimalField(default=0, max_digits=20, decimal_places=2)),
            ],
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=200)),
                ('amount', models.DecimalField(max_digits=20, decimal_places=2)),
                ('transaction_type', models.CharField(default=b'debt', max_length=50, choices=[(b'income', b'Income'), (b'utility', b'Utility'), (b'debt', b'Debt'), (b'creditcard', b'Credit Card')])),
            ],
        ),
        migrations.CreateModel(
            name='OneTimeTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='web.Transaction')),
                ('transaction_date', models.DateField()),
            ],
            bases=('web.transaction',),
        ),
        migrations.CreateModel(
            name='RecurringTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='web.Transaction')),
                ('started_at', models.DateField(default=datetime.datetime(2015, 11, 21, 6, 30, 59, 705241), null=True, blank=True)),
                ('cycle_due_date', models.IntegerField(default=1, null=True, blank=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)])),
                ('period', models.CharField(default=b'monthly', max_length=50, choices=[(b'weekly', b'Weekly'), (b'bi-weekly', b'Bi-Weekly'), (b'monthly', b'Monthly'), (b'quarterly', b'Quarterly'), (b'semi-yearly', b'Semi-Yearly'), (b'yearly', b'Yearly')])),
                ('is_variable', models.BooleanField(default=False)),
            ],
            bases=('web.transaction',),
        ),
        migrations.AddField(
            model_name='plannedpayment',
            name='transaction',
            field=models.ForeignKey(to='web.Transaction'),
        ),
        migrations.CreateModel(
            name='CreditCardTransaction',
            fields=[
                ('recurringtransaction_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='web.RecurringTransaction')),
                ('interest_rate', models.DecimalField(default=0, max_digits=5, decimal_places=2)),
                ('cycle_billing_date', models.DateField(default=datetime.datetime(2015, 11, 21, 6, 30, 59, 705782))),
            ],
            bases=('web.recurringtransaction',),
        ),
        migrations.CreateModel(
            name='DebtTransaction',
            fields=[
                ('recurringtransaction_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='web.RecurringTransaction')),
                ('principal', models.DecimalField(default=0, max_digits=20, decimal_places=2)),
                ('principal_at', models.DateField()),
                ('interest_rate', models.DecimalField(default=0, max_digits=5, decimal_places=2)),
            ],
            bases=('web.recurringtransaction',),
        ),
        migrations.AddField(
            model_name='onetimetransaction',
            name='creditcardtransaction',
            field=models.ForeignKey(to='web.CreditCardTransaction'),
        ),
        migrations.AddField(
            model_name='creditcardexpense',
            name='creditcardtransaction',
            field=models.ForeignKey(to='web.CreditCardTransaction'),
        ),
    ]

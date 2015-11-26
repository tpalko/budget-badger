# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Period',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('periodstart_at', models.DateField()),
                ('period_days', models.IntegerField(default=7)),
                ('expense_total', models.DecimalField(default=0, max_digits=20, decimal_places=2)),
                ('income_total', models.DecimalField(default=0, max_digits=20, decimal_places=2)),
            ],
        ),
        migrations.CreateModel(
            name='PlannedPayment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('overpayment', models.DecimalField(default=0, max_digits=20, decimal_places=2)),
                ('payment_at', models.DateField()),
            ],
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=200)),
                ('amount', models.DecimalField(max_digits=20, decimal_places=2)),
            ],
        ),
        migrations.CreateModel(
            name='OneTimeTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='web.Transaction')),
            ],
            bases=('web.transaction',),
        ),
        migrations.CreateModel(
            name='RecurringTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='web.Transaction')),
                ('started_at', models.DateField(default=datetime.datetime(2015, 9, 8, 4, 0, 7, 966013))),
                ('cycle_date', models.IntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)])),
                ('period', models.CharField(default=b'monthly', max_length=50, choices=[(b'weekly', b'Weekly'), (b'bi-weekly', b'Bi-Weekly'), (b'monthly', b'Monthly'), (b'quarterly', b'Quarterly'), (b'semi-yearly', b'Semi-Yearly'), (b'yearly', b'Yearly')])),
            ],
            bases=('web.transaction',),
        ),
        migrations.AddField(
            model_name='plannedpayment',
            name='transaction',
            field=models.ForeignKey(to='web.Transaction'),
        ),
    ]

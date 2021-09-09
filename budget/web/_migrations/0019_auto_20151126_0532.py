# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0018_auto_20150923_0328'),
    ]

    operations = [
        migrations.CreateModel(
            name='SingleTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='web.Transaction')),
                ('transaction_at', models.DateField()),
            ],
            bases=('web.transaction',),
        ),
        migrations.DeleteModel(
            name='Period',
        ),
        migrations.RemoveField(
            model_name='creditcardtransaction',
            name='closing_date',
        ),
        migrations.RemoveField(
            model_name='recurringtransaction',
            name='cycle_date',
        ),
        migrations.AddField(
            model_name='creditcardtransaction',
            name='cycle_billing_date',
            field=models.IntegerField(default=1, null=True, blank=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)]),
        ),
        migrations.AddField(
            model_name='recurringtransaction',
            name='cycle_due_date',
            field=models.IntegerField(default=1, null=True, blank=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)]),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 11, 26, 5, 31, 46, 539689), null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='amount',
            field=models.DecimalField(null=True, max_digits=20, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(default=b'debt', max_length=50, choices=[(b'single', b'Single'), (b'income', b'Income'), (b'utility', b'Utility'), (b'debt', b'Debt'), (b'creditcard', b'Credit Card')]),
        ),
        migrations.DeleteModel(
            name='OneTimeTransaction',
        ),
        migrations.AddField(
            model_name='singletransaction',
            name='creditcardtransaction',
            field=models.ForeignKey(to='web.CreditCardTransaction'),
        ),
    ]

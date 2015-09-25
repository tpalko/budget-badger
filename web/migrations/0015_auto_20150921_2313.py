# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0014_auto_20150917_0611'),
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
            name='CreditCardTransaction',
            fields=[
                ('recurringtransaction_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='web.RecurringTransaction')),
                ('closing_date', models.DateField(default=datetime.datetime(2015, 9, 21, 23, 13, 13, 291004))),
            ],
            bases=('web.recurringtransaction',),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 21, 23, 13, 13, 289213), null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(default=b'debt', max_length=50, choices=[(b'income', b'Income'), (b'utility', b'Utility'), (b'debt', b'Debt'), (b'creditcard', b'Credit Card')]),
        ),
        migrations.AddField(
            model_name='creditcardexpense',
            name='creditcardtransaction',
            field=models.ForeignKey(to='web.CreditCardTransaction'),
        ),
    ]

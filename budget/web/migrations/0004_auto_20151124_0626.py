# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0003_auto_20151124_0611'),
    ]

    operations = [
        migrations.CreateModel(
            name='SingleTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='web.Transaction')),
                ('transaction_date', models.DateField()),
                ('creditcardtransaction', models.ForeignKey(to='web.CreditCardTransaction')),
            ],
            bases=('web.transaction',),
        ),
        migrations.RemoveField(
            model_name='onetimetransaction',
            name='creditcardtransaction',
        ),
        migrations.RemoveField(
            model_name='onetimetransaction',
            name='transaction_ptr',
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 11, 24, 6, 26, 54, 89480), null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(default=b'debt', max_length=50, choices=[(b'single', b'Single'), (b'income', b'Income'), (b'utility', b'Utility'), (b'debt', b'Debt'), (b'creditcard', b'Credit Card')]),
        ),
        migrations.DeleteModel(
            name='OneTimeTransaction',
        ),
    ]

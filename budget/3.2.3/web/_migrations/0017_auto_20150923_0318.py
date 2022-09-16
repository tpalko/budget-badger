# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0016_auto_20150921_2321'),
    ]

    operations = [
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
        migrations.RemoveField(
            model_name='transaction',
            name='interest_rate',
        ),
        migrations.AddField(
            model_name='creditcardtransaction',
            name='interest_rate',
            field=models.DecimalField(default=0, max_digits=5, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='creditcardtransaction',
            name='closing_date',
            field=models.DateField(default=datetime.datetime(2015, 9, 23, 3, 18, 7, 714880)),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 23, 3, 18, 7, 713767), null=True, blank=True),
        ),
    ]

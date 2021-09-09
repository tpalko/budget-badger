# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0006_auto_20150910_0556'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='period',
            name='transactions',
        ),
        migrations.RemoveField(
            model_name='plannedpayment',
            name='period',
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 11, 3, 28, 1, 937547)),
        ),
    ]

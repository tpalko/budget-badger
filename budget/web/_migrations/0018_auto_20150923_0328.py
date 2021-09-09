# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0017_auto_20150923_0318'),
    ]

    operations = [
        migrations.AlterField(
            model_name='creditcardtransaction',
            name='closing_date',
            field=models.DateField(default=datetime.datetime(2015, 9, 23, 3, 28, 54, 489072)),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 23, 3, 28, 54, 488032), null=True, blank=True),
        ),
    ]

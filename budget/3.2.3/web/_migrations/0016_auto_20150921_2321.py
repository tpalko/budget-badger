# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0015_auto_20150921_2313'),
    ]

    operations = [
        migrations.AlterField(
            model_name='creditcardtransaction',
            name='closing_date',
            field=models.DateField(default=datetime.datetime(2015, 9, 21, 23, 21, 46, 712767)),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 21, 23, 21, 46, 710913), null=True, blank=True),
        ),
    ]

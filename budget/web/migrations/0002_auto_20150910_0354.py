# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='plannedpayment',
            name='period',
            field=models.ForeignKey(default=1, to='web.Period'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 10, 3, 54, 42, 70442)),
        ),
    ]

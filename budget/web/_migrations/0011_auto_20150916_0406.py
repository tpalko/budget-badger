# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0010_auto_20150916_0405'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recurringtransaction',
            name='cycle_date',
            field=models.IntegerField(default=1, null=True, blank=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)]),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 16, 4, 6, 27, 316624), null=True, blank=True),
        ),
    ]

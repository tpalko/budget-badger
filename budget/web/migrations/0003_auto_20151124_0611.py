# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0002_auto_20151124_0609'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 11, 24, 6, 11, 16, 228250), null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='amount',
            field=models.DecimalField(null=True, max_digits=20, decimal_places=2),
        ),
    ]

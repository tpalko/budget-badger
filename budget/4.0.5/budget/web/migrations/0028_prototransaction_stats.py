# Generated by Django 4.0.5 on 2022-09-28 19:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0027_utilitytransaction_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='prototransaction',
            name='stats',
            field=models.JSONField(null=True),
        ),
    ]

# Generated by Django 4.0.5 on 2023-09-13 15:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0057_merge_20230908_1847'),
    ]

    operations = [
        migrations.AddField(
            model_name='recordmeta',
            name='description',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='transactionruleset',
            name='join_operator',
            field=models.CharField(choices=[['and', 'And'], ['or', 'Or']], default='or', max_length=3),
        ),
    ]

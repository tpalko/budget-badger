# Generated by Django 4.0.5 on 2022-09-12 19:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0008_alter_uploadedfile_first_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='tag',
            field=models.CharField(max_length=50, null=True),
        ),
    ]
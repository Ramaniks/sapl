# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2018-04-06 13:00
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parlamentares', '0021_clear_thumbnails_cache'),
    ]

    operations = [
        migrations.AddField(
            model_name='partido',
            name='observacao',
            field=models.TextField(blank=True, verbose_name='Observação'),
        ),
    ]

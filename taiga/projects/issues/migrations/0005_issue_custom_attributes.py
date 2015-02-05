# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_pgjson.fields


class Migration(migrations.Migration):

    dependencies = [
        ('issues', '0004_auto_20150114_0954'),
    ]

    operations = [
        migrations.AddField(
            model_name='issue',
            name='custom_attributes',
            field=django_pgjson.fields.JsonField(default=None, verbose_name='custom attributes', blank=True, null=True),
            preserve_default=True,
        ),
    ]

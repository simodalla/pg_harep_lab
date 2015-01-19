# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import uuid


def get_random_string(prefix=None):
    prefix = '{}_'.format(prefix) if prefix else ''
    return '{}{}'.format(prefix, ''.join(str(uuid.uuid4()).split('-')[:2]))
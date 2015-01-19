# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import uuid
from functools import wraps
from inspect import getcallargs

from fabric.api import local
from fabric.decorators import _wrap_as_new

from postgresql import psql_cmd
from utils import get_random_string


def test_dec(*arg_dec, **kwargs_dec):
    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            func_args = getcallargs(func, *args, **kwargs)
            print(func_args)
            local('echo "prima..."')
            result = func(*args, **kwargs)
            local('echo "dopo..."')
            return result
        return _wrap_as_new(func, inner)
    return outer


def tmp_with_params(*arg_dec, **kwargs_dec):
    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            func_args = getcallargs(func, *args, **kwargs)
            print(arg_dec, kwargs_dec)
            print(func_args, args, kwargs)
            local('echo "prima..."')
            result = func(*args, **kwargs)
            local('echo "dopo..."')
            return result
        return _wrap_as_new(func, inner)
    return outer


def tmp_db(func):
    @wraps(func)
    def inner(*args, **kwargs):
        g = func.func_globals
        if 'env' in g.keys() and 'pg_tmp_db_name' in g['env'].keys():
            raise Exception('pg_tmp_db_name is already in env!!!')
        g['env']['pg_tmp_db_name'] = get_random_string('test')
        psql_cmd('CREATE DATABASE {}'.format(g['env']['pg_tmp_db_name']))
        print("*** TEST DATABASE NAME: {}".format(g['env']['pg_tmp_db_name']))
        result = func(*args, **kwargs)
        psql_cmd('DROP DATABASE {}'.format(g['env']['pg_tmp_db_name']))
        del g['env']['pg_tmp_db_name']
        return result
    return _wrap_as_new(func, inner)

# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import functools
import inspect

def identity(f):
    return f


@identity
def foo():
    return 'bar'


# def check_is_admin(username):
#     if username != 'admin':
#         raise Exception("This user is not allowed to get food")

def check_is_admin(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        # print(args)
        # print(kwargs)
        func_args = inspect.getcallargs(f, *args, **kwargs)
        print(func_args)
        # if kwargs.get('username') != 'admin':
        # if args[1] != 'admin':
        if func_args.get('username') != 'admin':
            raise Exception("This user is not allowed to get food")
        result = f(*args, **kwargs)
        print("AFTER...")
        return result
    return wrapper


class Store(object):

    def __init__(self):
        self.storage = dict()

    @check_is_admin
    def get_food(self, username, food):
        """Get food!"""
        return self.storage.get(food)

    @check_is_admin
    def put_food(self, username, food):
        self.storage.update({food: food})


def is_admin(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if kwargs.get(*args, **kwargs) != 'admin':
            raise Exception("This user is not allowed to get food")
        return f(*args, **kwargs)
    return wrapper


def foobar(username='someone'):
    """Do crazy stuff."""
    pass


@is_admin
def foobar_d(username='someone'):
    """Do crazy stuff."""
    pass

if __name__ == '__main__':
    store = Store()
    store.put_food(username='admin', food='apple')
    store.put_food('admin', food='apple')
    store.put_food('admin', 'apple')
    print(store.get_food(username='admin', food='apple'))
    # print(store.get_food('pippo', 'pig'))
    # print(foobar.func_doc)
    # print(foobar.__name__)
    # print("-------------")
    # print(foobar_d.func_doc)
    # print(foobar_d.__doc__)
    # print(foobar_d.__name__)



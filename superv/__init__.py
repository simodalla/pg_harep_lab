# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import os.path
import utils.config as config
from fabric.api import settings, run, task, with_settings, abort
from fabric.contrib.files import exists, append


SUPERVISOR_CONFD_PATH = '/etc/supervisor/conf.d/'


@with_settings(user='root')
@task
def install():
    # run('apt-get update && apt-get install -y supervisor')
    run('apt-get install -y supervisor')


@task
def add_program(program, command, user=None, autostart=True):
    config_path = os.path.join(SUPERVISOR_CONFD_PATH,
                               '{}.conf'.format(program))
    if not exists(config_path):
        run('touch {}'.format(config_path))
        rows = ['[program:{}]'.format(program),
                'command={}'.format(command),
                'user={}'.format(user) if user else '',
                'autostart={}'.format(str(autostart).lower()),
                'autorestart=true',
                'redirect_stderr=true']
        for row in rows:
            if row:
                append(config_path, row)
    else:
        abort('Supervisor conf for {} already exist!'.format(program))


@task
def add_postgres_program(program=config.POSTGRESQL_USERNAME,
                         datadir=config.POSTGRESQL_DATA_PATH,
                         autostart=True):
    add_program(program,
                command='{} -D {}'.format(config.POSTGRESQL_CMD_SERVER,
                                          datadir),
                user=config.POSTGRESQL_USERNAME,
                autostart=autostart)

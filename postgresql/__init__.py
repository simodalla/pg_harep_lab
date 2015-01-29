# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from fabric.api import settings, run, task, open_shell, with_settings
from fabric.contrib.files import append, contains

from utils.config import *


def psql_cmd(cmd, db=None, tuples_only=False, quiet=False):
    with settings(user=POSTGRESQL_USERNAME):
        if not cmd.endswith(';'):
            cmd += ';'
        return run("{}{}{} -c \"{}\"{}".format(
            POSTGRESQL_CMD_PSQL,
            ' -d %s' % db if db else '',
            ' -t' if tuples_only else '',
            cmd,
            ';' if not cmd.endswith(';') else ''), quiet=quiet)


@with_settings(user=POSTGRESQL_USERNAME)
@task
def print_conf(data_path=None, pg_settings=None):
    """Print important settings of postgresql.conf file"""
    pg_settings = pg_settings or sorted(
        ['shared_buffers', 'synchronous_commit',
         'wal_writer_delay', 'wal_writer_delayconfig',
         'checkpoint_segments', 'checkpoint_timeout',
         'checkpoint_completion_target',
         'checkpoint_warning', 'archive_command',
         'wal_level', 'archive_mode',
         'max_wal_senders', 'wal_keep_segments'])
    out = run("grep -E '{}' {}".format(
        '|'.join(pg_settings),
        os.path.join(POSTGRESQL_DATA_PATH, 'postgresql.conf')), quiet=True)
    print("*************\n{}\n************".format(out))


@task
def run_interactive(datapath=None):
    """Run postgres server"""
    with settings(user=POSTGRESQL_USERNAME):
        open_shell('{} -D {}'.format(POSTGRESQL_CMD_SERVER,
                                     datapath or POSTGRESQL_DATA_PATH))


@task
def add_bin_path():
    bin_path = os.path.join(POSTGRESQL_ROOT_PATH, 'bin')
    with settings(user=POSTGRESQL_USERNAME):
        if not contains('~/.profile', bin_path):
            append('~/.profile', '\n\nPATH="{}:$PATH"'.format(bin_path))
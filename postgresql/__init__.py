# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from fabric.api import settings, run

from utils.config import POSTGRESQL_CMD_PSQL, POSTGRESQL_USERNAME


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
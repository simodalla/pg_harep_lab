# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import os.path

SNAPSHOTS = {
    'POSTGRES_SOURCE_INSTALL': 'postgres_source_installation'}

POSTGRESQL_HOSTS = {
    'simple': {'192.168.59.201': 'pgsimplemaster',
               '192.168.59.202': 'pgsimpleslave'},
    'ptr': {'192.168.59.201': 'pgptrmaster',
            '192.168.59.202': 'pgptrslave'},
}
POSTGRESQL_USERNAME = 'postgres'
POSTGRESQL_ROOT_PATH = '/usr/local/pgsql'
POSTGRESQL_DATA_PATH = os.path.join(POSTGRESQL_ROOT_PATH, 'data')
POSTGRESQL_HOME_PATH = '/home/postgresql'
POSTGRESQL_STORAGE_PATH = '/opt/postgresql_storage'
POSTGRESQL_LOG_PATH = '/var/log/postgresql'
POSTGRESQL_CMD_SERVER = os.path.join(POSTGRESQL_ROOT_PATH, 'bin', 'postgres')
POSTGRESQL_CMD_PSQL = os.path.join(POSTGRESQL_ROOT_PATH, 'bin', 'psql')
POSTGRESQL_CONFIG_FILE = os.path.join(POSTGRESQL_DATA_PATH, 'postgresql.conf')
POSTGRESQL_PGHBA_FILE = os.path.join(POSTGRESQL_DATA_PATH, 'pg_hba.conf')
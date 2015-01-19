# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import os.path

VM_NETWORK = '192.168.59'
VM_TEMPLATE_IP = '.'.join([VM_NETWORK, '200'])
VM_MASTER_IP = '.'.join([VM_NETWORK, '201'])
VM_SLAVE_IP = '.'.join([VM_NETWORK, '202'])
VM_SLAVE_2_IP = '.'.join([VM_NETWORK, '231'])

SNAPSHOTS = {
    'POSTGRES_SOURCE_INSTALL': 'postgres_source_installation'}

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

POSTGRESQL_HOSTS = {
    'simple': {
        VM_MASTER_IP: {'vm_name': 'pgsimplemaster'},
        VM_SLAVE_IP: {'vm_name': 'pgsimpleslave'},
    },
    'ptr': {
        VM_MASTER_IP: {
            'vm_name': 'pgptrmaster',
            'archive_path': os.path.join(POSTGRESQL_STORAGE_PATH,
                                         'ptr_archive'),
        },
        VM_SLAVE_IP: {
            'vm_name': 'pgptrslave',
            'base_backup_path': os.path.join(POSTGRESQL_STORAGE_PATH,
                                             'base_backup_data')},
    },
    'async': {
        VM_MASTER_IP: {
            'vm_name': 'pgasynmaster',
        },
        VM_SLAVE_IP: {
            'vm_name': 'pgasynslave',
        },
        VM_SLAVE_2_IP: {
            'vm_name': 'pgasynslave2',
        }
    }
}
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import os.path

VM_IMAGE_NAME = 'ubuntu1404p93'
# VM_IMAGE_NAME = 'ubuntu1404p94'
VM_IMAGE_SNAPSHOT = 'post_installation'
VM_NETWORK = '192.168.59'
VM_TEMPLATE_IP = '.'.join([VM_NETWORK, '200'])
VM_MASTER_IP = '.'.join([VM_NETWORK, '201'])
VM_SLAVE_IP = '.'.join([VM_NETWORK, '202'])
VM_SLAVE_2_IP = '.'.join([VM_NETWORK, '203'])
VM_SLAVE_3_IP = '.'.join([VM_NETWORK, '204'])

SNAPSHOTS = {
    'POSTGRES_SOURCE_INSTALL': 'postgres_source_installation'}

POSTGRESQL_USERNAME = 'postgres'
POSTGRESQL_ROOT_PATH = '/usr/local/pgsql'
# POSTGRESQL_DATA_PATH = os.path.join(POSTGRESQL_ROOT_PATH, 'data')
POSTGRESQL_HOME_PATH = os.path.join('/home', POSTGRESQL_USERNAME)
POSTGRESQL_DATA_PATH = os.path.join(POSTGRESQL_HOME_PATH, 'db', 'pgdata')
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
            'archive_path': os.path.join(POSTGRESQL_STORAGE_PATH,
                                         'async_archive'),
        },
        VM_SLAVE_IP: {
            'vm_name': 'pgasynslave',
        },
        VM_SLAVE_2_IP: {
            'vm_name': 'pgasynslave2',
        }
    },
    'sync': {
        VM_MASTER_IP: {
            'vm_name': 'pgsyncmaster',
            'application_name': 'sync_scenario',
        },
        VM_SLAVE_IP: {
            'vm_name': 'pgsyncslave',
        },
        VM_SLAVE_2_IP: {
            'vm_name': 'pgsyncslave2',
        },
    },
    'pgbouncer': {
        VM_SLAVE_2_IP: {
            'vm_name': 'pgbouncer',
        }
    },
    'pgpool_replication': {
        VM_MASTER_IP: {
            'vm_name': 'osspc17',
        },
        VM_SLAVE_IP: {
            'vm_name': 'osspc18',
        },
        VM_SLAVE_2_IP: {
            'vm_name': 'osspc16',
        }
    },
    'pg94simple': {
        VM_MASTER_IP: {'vm_name': 'pg94simple'},
    },
    'pg94async': {
        VM_MASTER_IP: {
            'vm_name': 'pg94asynmaster',
            'archive_path': os.path.join(POSTGRESQL_STORAGE_PATH,
                                         'async_archive'),
        },
        VM_SLAVE_IP: {
            'vm_name': 'pg94asynslave',
        },
    },
    'cityware_async': {
        VM_MASTER_IP: {
            'vm_name': 'pgmaster',
            'archive_path': os.path.join(POSTGRESQL_HOME_PATH,
                                         'archive'),
        },
        VM_SLAVE_IP: {
            'vm_name': 'pgslave',
        }
    },
    'city4': {
        VM_MASTER_IP: {
            'vm_name': 'pg4master',
            'archive_path': os.path.join(POSTGRESQL_HOME_PATH,
                                         'archive'),
        },
        VM_SLAVE_IP: {
            'vm_name': 'pg4slave',
        }
    },
    'city5': {
        VM_MASTER_IP: {
            'vm_name': 'pg5master',
        },
        VM_SLAVE_IP: {
            'vm_name': 'pg5slave',
        }
    },
    'city6': {
        VM_MASTER_IP: {
            'vm_name': 'pg6master',
            'application_name': 'sync_cityware',
        },
        VM_SLAVE_IP: {
            'vm_name': 'pg6slave1',
        },
        VM_SLAVE_2_IP: {
            'vm_name': 'pg6slave2',
        },
        VM_SLAVE_3_IP: {
            'vm_name': 'pg6slave3',
        }
    },
    'city7': {
        VM_MASTER_IP: {
            'vm_name': 'pg7master',
        },
        VM_SLAVE_IP: {
            'vm_name': 'pg7slave1',
        },
        VM_SLAVE_2_IP: {
            'vm_name': 'pg7pool1',
        },
        VM_SLAVE_3_IP: {
            'vm_name': 'pg7pool2',
        }
    },
}
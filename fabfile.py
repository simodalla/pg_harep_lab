# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import datetime
import os.path
import time

from fabric.api import (run, env, task, settings, hosts, open_shell, cd, local,
                        with_settings)
from fabric import colors
from fabric.contrib.files import exists, uncomment, append, contains

import postgresql
from postgresql import psql_cmd
from utils.decorators import tmp_db
from utils.files import sed
from utils.config import *
import vbox
import ssh
import scenario
from utils import get_random_string


env.lab_vm_image_name = 'ubuntu1404'
env.lab_vm_image_snapshot = 'post_installation'
env.password = 'default'
env.host = '192.168.59.200'


def get_vm_ip(vm_name):
    print(vbox.vbox_manage('guestproperty', 'get',
          vm_name, '/VirtualBox/GuestInfo/Net/1/V4/IP'))


@hosts('192.168.59.201')
@task
def master_shell(user=env.user):
    vbox.running_up_and_wait('pgsimplemaster')
    with settings(user=user):
        open_shell()


@hosts('192.168.59.202')
@task
def slave_shell(user=env.user):
    vbox.running_up_and_wait('pgsimpleslave')
    with settings(user=user):
        open_shell()


@task
def psql_shell():
    with settings(user=POSTGRESQL_USERNAME):
        open_shell(POSTGRESQL_CMD_PSQL)


@hosts('192.168.59.201')
@task
def run_master_postgres(scenario='simple'):
    """Run simple master vm and run postgres server"""
    vbox.running_up_and_wait(POSTGRESQL_HOSTS[scenario][env.host]['vm_name'])
    postgresql.run_interactive()


@task
@hosts('192.168.59.201')
def simple_master_psql():
    """Run simple master vm and open an psql shell"""
    vbox.running_up_and_wait(POSTGRESQL_HOSTS['simple'][env.host]['vm_name'])
    psql_shell()


@hosts('192.168.59.200')
@task
def deploy_vm_image():
    vbox.running_up_and_wait(env.lab_vm_image_name)
    run('apt-get update && apt-get upgrade -y')
    if not vbox.has_snapshot(env.lab_vm_image_name,
                             SNAPSHOTS['POSTGRES_SOURCE_INSTALL']):
        run('wget https://ftp.postgresql.org/pub/source/v9.3.5/'
            'postgresql-9.3.5.tar.gz')
        run('apt-get install -y libreadline-dev zlib1g-dev flex bison '
            'libxml2-dev libxslt-dev libssl-dev python-dev python3-dev '
            'libldap-dev')
        postgres_source_dir = '/opt/postgresql_9_3_5'
        run('rm -rf ' + postgres_source_dir)
        run('mkdir {dir} && tar xvf postgresql-9.3.5.tar.gz -C {dir}'
            ' --strip-components=1'.format(dir=postgres_source_dir))

        with cd(postgres_source_dir):
            run('./configure --with-libxml --with-libxslt --with-openssl'
                ' --with-python --with-ldap')
            run('make clean')
            run('make world')
            run('make install-world')

        vbox.make_snaspshot(env.lab_vm_image_name,
                            SNAPSHOTS['POSTGRES_SOURCE_INSTALL'],
                            'snapshot post installation from source')

    if not vbox.has_snapshot(env.lab_vm_image_name, 'postgres_user_config'):
        vbox.running_up_and_wait(env.lab_vm_image_name)
        run('adduser --quiet --disabled-password --gecos "Postgres User"'
            ' {}'.format(POSTGRESQL_USERNAME))
        run('echo "{}:{}" | chpasswd'.format(POSTGRESQL_USERNAME,
                                             env.password))
        postgresql.add_bin_path()
        for path in [POSTGRESQL_DATA_PATH, POSTGRESQL_LOG_PATH,
                     POSTGRESQL_STORAGE_PATH]:
            if not exists(path):
                run('mkdir {}'.format(path))
            run('chown {postgres}:{postgres} {path}'.format(
                postgres=POSTGRESQL_USERNAME, path=path))

        vbox.make_snaspshot(env.lab_vm_image_name,
                            'postgres_user_config',
                            'snapshot post postgres user configuration')

    if not vbox.has_snapshot(env.lab_vm_image_name,
                             'postgres_server_post_config'):
        vbox.running_up_and_wait(env.lab_vm_image_name)
        with settings(user=POSTGRESQL_USERNAME):
            run('{} -D {}'.format(
                os.path.join(POSTGRESQL_ROOT_PATH, 'bin/initdb'),
                POSTGRESQL_DATA_PATH))

            pg_hba = os.path.join(POSTGRESQL_DATA_PATH, 'pg_hba.conf')
            uncomment(pg_hba, 'local   replication     {}'.format(
                POSTGRESQL_USERNAME))
            uncomment(pg_hba,
                      'host    replication     {}'
                      '        127.0.0.1\/32'.format(POSTGRESQL_USERNAME))
            for auth_conf in ['host         all  all  192.168.59.0/24  trust',
                              'host         replication  {}  192.168.59.0/24'
                              '  trust'.format(POSTGRESQL_USERNAME)]:
                append(pg_hba, auth_conf)

            postgres_conf = os.path.join(POSTGRESQL_DATA_PATH,
                                         'postgresql.conf')
            uncomment(postgres_conf, 'listen_addresses = ')
            run('sed -i.bak -r -e "s/listen_addresses = \'localhost\'/'
                'listen_addresses = \'*\'/g" {}'.format(postgres_conf))

            vbox.make_snaspshot(env.lab_vm_image_name,
                                'postgres_server_post_config',
                                'snapshot post postgres server configuration')


@hosts('192.168.59.200')
@task
def deploy_simple_scenario(master_vm_name='pgsimplemaster',
                           slave_vm_name='pgsimpleslave'):
    for vm_name in [master_vm_name, slave_vm_name]:
        if not vbox.vm_exist(vm_name):
            vbox.clone_vm(env.lab_vm_image_name, name=vm_name, options='link',
                          snapshot='postgres_server_post_config')

        if not vbox.has_snapshot(vm_name,
                                 'network_config_for_scenario'):
            success = vbox.running_up_and_wait(vm_name)
            sed('/etc/hostname', before='ubuntu1', after=vm_name)
            sed('/etc/hosts', before='ubuntu1', after=vm_name)

            append('/etc/hosts', '192.168.59.201  {}'.format(master_vm_name))
            append('/etc/hosts', '192.168.59.202  {}'.format(slave_vm_name))

            if vm_name == master_vm_name:
                sed('/etc/network/interfaces',
                    before="address 192.168.59.200",
                    after="address 192.168.59.201",)
            else:
                sed('/etc/network/interfaces',
                    before="address 192.168.59.200",
                    after="address 192.168.59.202",)
            if success:
                vbox.make_snaspshot(vm_name,
                                    'network_config_for_scenario',
                                    'network configuration for scenario')


@hosts(VM_TEMPLATE_IP)
@with_settings(user='root')
@task
def prepare_scenario(scenario):
    for ip in POSTGRESQL_HOSTS[scenario]:
        vm_name = POSTGRESQL_HOSTS[scenario][ip]['vm_name']
        if not vbox.vm_exist(vm_name):
            vbox.clone_vm(env.lab_vm_image_name, name=vm_name, options='link',
                          snapshot='postgres_server_post_config')
        if not vbox.has_snapshot(vm_name, 'network_config_for_scenario'):
            success = vbox.running_up_and_wait(vm_name)
            ssh.prepare_ssh_autologin()
            sed('/etc/hostname', before='ubuntu1', after=vm_name)
            sed('/etc/hosts', before='ubuntu1', after=vm_name)
            for other_ip in [oi for oi in POSTGRESQL_HOSTS[scenario]
                             if oi != ip]:
                append('/etc/hosts', '{ip}  {hostname}'.format(
                    ip=other_ip,
                    hostname=POSTGRESQL_HOSTS[scenario][other_ip]))
            sed('/etc/network/interfaces',
                before="address {}".format(VM_TEMPLATE_IP),
                after="address {}".format(ip))
            if success:
                vbox.make_snaspshot(vm_name,
                                    'network_config_for_scenario',
                                    'network configuration for scenario')



@hosts('192.168.59.201', '192.168.59.202')
@task
def deploy_ptr_scenario():
    vm_name = POSTGRESQL_HOSTS['ptr'][env.host]['vm_name']
    vm_parent = POSTGRESQL_HOSTS['simple'][env.host]['vm_name']
    if not vbox.vm_exist(vm_name):
        vbox.clone_vm(vm_parent, name=vm_name, options='link',
                      snapshot='network_config_for_scenario')

    if not vbox.has_snapshot(vm_name,
                             'activation_archiving_transaction_log'):
        success = vbox.running_up_and_wait(vm_name)
        with settings(user='root'):
            ssh.prepare_ssh_autologin()
            sed('/etc/hostname', before=vm_parent, after=vm_name)
            sed('/etc/hosts', before=vm_parent, after=vm_name)
        with settings(user=POSTGRESQL_USERNAME):
            postgresql.add_bin_path()
            ssh.prepare_ssh_autologin()
            if env.host.endswith('201'):
                run('mkdir {}'.format(
                    POSTGRESQL_HOSTS['ptr'][env.host]['archive_path']))
                uncomment(POSTGRESQL_CONFIG_FILE, 'wal_level =')
                sed(POSTGRESQL_CONFIG_FILE,
                    "wal_level = minimal",
                    "wal_level = archive")
                uncomment(POSTGRESQL_CONFIG_FILE, 'archive_mode =')
                sed(POSTGRESQL_CONFIG_FILE,
                    "archive_mode = off",
                    "archive_mode = on")
                uncomment(POSTGRESQL_CONFIG_FILE, 'archive_command =')
                sed(POSTGRESQL_CONFIG_FILE,
                    before="archive_command = ''",
                    after="archive_command = 'cp %p {}/%f'".format(
                        POSTGRESQL_HOSTS['ptr'][env.host]['archive_path']))
                uncomment(POSTGRESQL_CONFIG_FILE, 'max_wal_senders =')
                sed(POSTGRESQL_CONFIG_FILE,
                    "max_wal_senders = 0",
                    "max_wal_senders = 15")
            elif env.host.endswith('202'):
                run('mkdir {}'.format(
                    POSTGRESQL_HOSTS['ptr'][env.host]['base_backup_path']))
        if success:
            vbox.make_snaspshot(vm_name,
                                'activation_archiving_transaction_log',
                                'activation archiving transaction log')


@task
def list_databases():
    """List the database instances on server [pag 29]"""
    psql_cmd("SELECT oid, datname FROM pg_database")


@task
@tmp_db
def ptr_test_archive_xlog(table_name='t_test'):
    with settings(warn_only=True, user='postgres'):
        run("ls -l {}".format(
            POSTGRESQL_HOSTS['ptr'][env.host]['archive_path']))
        psql_cmd("CREATE TABLE %s AS SELECT * FROM "
                 "generate_series(1, 1000000);" % table_name,
                 db=env.pg_tmp_db_name)
        psql_cmd("SELECT * FROM %s LIMIT 3;" % table_name,
                 db=env.pg_tmp_db_name)
        run("ls -l {}".format(
            POSTGRESQL_HOSTS['ptr'][env.host]['archive_path']))


@hosts('192.168.59.202')
@with_settings(user='postgres')
@task
def ptr_slave_make_base_backup(checkpoint='fast', xlog_method=None,
                               base_backup_path=None):
    base_backup_path = base_backup_path or '{}_{}'.format(
        POSTGRESQL_HOSTS['ptr'][env.host]['base_backup_path'],
        get_random_string())
    run('mkdir {}'.format(base_backup_path))
    print(colors.green(
        '\nPath of base backup: "{}"\n'.format(base_backup_path)))
    pg_basebackup_cmd = os.path.join(
        POSTGRESQL_ROOT_PATH, 'bin', 'pg_basebackup')
    run('{cmd} -h {master} -D {data} {checkpoint} {xlog_method}'.format(
        cmd=pg_basebackup_cmd,
        master=VM_MASTER_IP,
        data=base_backup_path,
        checkpoint="--checkpoint={}".format(
            checkpoint) if checkpoint else '',
        xlog_method="--xlog-method={}".format(
            xlog_method) if xlog_method else '').strip())
    run("ls -l {}".format(base_backup_path))


@hosts('192.168.59.202')
@with_settings(user='postgres')
@task
def ptr_perform_basic_recovery():
    base_backup_path = '{}_{}'.format(
        POSTGRESQL_HOSTS['ptr'][env.host]['base_backup_path'],
        get_random_string())
    ptr_slave_make_base_backup(base_backup_path=base_backup_path)
    archive_path = POSTGRESQL_HOSTS['ptr'][VM_MASTER_IP]['archive_path']
    recovery_file = 'recovery.conf'
    with cd(base_backup_path):
        run('touch {}'.format(recovery_file))
        append(recovery_file,
               "restore_command = 'rsync -azh {}@{}:{}/%f %p'".format(
                   POSTGRESQL_USERNAME,
                   VM_MASTER_IP,
                   archive_path))
        append(recovery_file, "recovery_target_time = '{}'".format(
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    run('chmod 700 {}'.format(base_backup_path))
    if exists(archive_path):
        run('rm -rf {}/*'.format(archive_path))
    else:
        run('mkdir {}'.format(archive_path))
    open_shell('pg_ctl -D %s/ start' % base_backup_path)


@task
@tmp_db
def test_base_dir():
    """Test the "base" dir of "data" dir [pag 29]"""
    db_name = env.pg_tmp_db_name
    table_name = 't_test'
    with settings(warn_only=True):
        run('ls -l {}'.format(os.path.join(POSTGRESQL_DATA_PATH, 'base')))
        out_dbs = psql_cmd('SELECT oid, datname FROM pg_database')
        psql_cmd("CREATE TABLE %s (id int4)" % table_name, db=db_name)
        out_table = psql_cmd(
            "SELECT relfilenode, relname FROM pg_class"
            " WHERE relname = '{}'".format(table_name),
            db=db_name)
        oid_db = [row.strip().split('|')[0].strip()
                  for row in out_dbs.split('\n')
                  if row.find(db_name) != -1][0]
        oid_table = [row.strip().split('|')[0].strip()
                     for row in out_table.split('\n')
                     if row.find(table_name) != -1][0]

        run('ls -l {}*'.format(
            os.path.join(POSTGRESQL_DATA_PATH, 'base', oid_db, oid_table)))


@task
def demo_random():
    from utils import get_random_string
    print(get_random_string())
    print(get_random_string('test'))

# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import datetime
import os.path
import time

from fabric.api import (run, env, task, settings, hosts, open_shell, cd, local,
                        with_settings, abort)
from fabric import colors
from fabric.contrib.files import exists, uncomment, append, contains

import postgresql
from postgresql import psql_cmd
from utils.decorators import tmp_db
from utils.files import sed
from utils.config import *
import scenario
import vbox
import ssh
import superv


from utils import get_random_string


env.lab_vm_image_name = VM_IMAGE_NAME
env.lab_vm_image_snapshot = VM_IMAGE_SNAPSHOT
env.password = 'default'
env.host = '192.168.59.200'


@task
def set_env_lab(image_name=VM_IMAGE_NAME):
    env.lab_vm_image_name = image_name


def get_vm_ip(vm_name):
    print(vbox.vbox_manage('guestproperty', 'get',
          vm_name, '/VirtualBox/GuestInfo/Net/1/V4/IP'))


@hosts(VM_MASTER_IP)
@task
def master_shell(user=env.user):
    vbox.running_up_and_wait('pgsimplemaster')
    with settings(user=user):
        open_shell()


@hosts(VM_SLAVE_IP)
@task
def slave_shell(user=env.user):
    vbox.running_up_and_wait('pgsimpleslave')
    with settings(user=user):
        open_shell()


@task
def psql_shell():
    with settings(user=POSTGRESQL_USERNAME):
        open_shell(POSTGRESQL_CMD_PSQL)


@hosts(VM_MASTER_IP)
@task
def run_master_postgres(scenario):
    """Run simple master vm and run postgres server"""
    vbox.running_up_and_wait(POSTGRESQL_HOSTS[scenario][env.host]['vm_name'])
    postgresql.run_interactive()


@task
@hosts('192.168.59.201')
def simple_master_psql():
    """Run simple master vm and open an psql shell"""
    vbox.running_up_and_wait(POSTGRESQL_HOSTS['simple'][env.host]['vm_name'])
    psql_shell()



@hosts(VM_TEMPLATE_IP)
@with_settings(user='root')
@task
def deploy_postgres_image(version='9.3.6'):
    vbox.running_up_and_wait(env.lab_vm_image_name)
    if not vbox.has_snapshot(env.lab_vm_image_name,
                             'autologin_and_apt_update'):
        ssh.prepare_ssh_autologin()
        run('apt-get update && apt-get upgrade -y')
        vbox.make_snaspshot(env.lab_vm_image_name,
                            'autologin_and_apt_update',
                            'autologin_and_apt_update')
    vbox.running_up_and_wait(env.lab_vm_image_name)
    if not vbox.has_snapshot(env.lab_vm_image_name,
                             SNAPSHOTS['POSTGRES_SOURCE_INSTALL']):
        source_url = (
            'https://ftp.postgresql.org/pub/source/v{version}/'
            'postgresql-{version}.tar.gz'.format(version=version))
        run('wget {}'.format(source_url))
        run('apt-get install -y libreadline-dev zlib1g-dev flex bison '
            'libxml2-dev libxslt-dev libssl-dev python-dev python3-dev '
            'libldap-dev')
        postgres_source_dir = '/opt/source/{}'.format(
            source_url.split('/')[-1].split('.tar.gz')[0])
        run('rm -rf ' + postgres_source_dir)
        run('mkdir -p {dir} && tar xvf postgresql-{version}.tar.gz -C {dir}'
            ' --strip-components=1'.format(dir=postgres_source_dir,
                                           version=version))

        with cd(postgres_source_dir):
            run('./configure --with-libxml --with-libxslt --with-openssl'
                ' --with-python --with-ldap')
            run('make clean')
            run('make world')
            run('make install-world')

        with cd(os.path.join(postgres_source_dir, 'contrib')):
            run('make')
            run('make install')

        vbox.make_snaspshot(env.lab_vm_image_name,
                            SNAPSHOTS['POSTGRES_SOURCE_INSTALL'],
                            'snapshot post installation from source')

    if not vbox.has_snapshot(env.lab_vm_image_name, 'postgres_user_config'):
        vbox.running_up_and_wait(env.lab_vm_image_name)
        run('adduser --quiet --disabled-password --gecos "Postgres User"'
            ' {}'.format(POSTGRESQL_USERNAME))
        run('echo "{}:{}" | chpasswd'.format(POSTGRESQL_USERNAME,
                                             env.password))
        for path in [POSTGRESQL_DATA_PATH, POSTGRESQL_LOG_PATH,
                     POSTGRESQL_STORAGE_PATH]:
            if not exists(path):
                run('mkdir {}'.format(path))
            run('chown {postgres}:{postgres} {path}'.format(
                postgres=POSTGRESQL_USERNAME, path=path))
        postgresql.add_bin_path()
        with settings(user=POSTGRESQL_USERNAME):
            postgresql.add_bin_path()
            ssh.prepare_ssh_autologin()
        vbox.make_snaspshot(env.lab_vm_image_name,
                            'postgres_user_config',
                            'snapshot post postgres user configuration')

    if not vbox.has_snapshot(env.lab_vm_image_name,
                             'postgres_server_post_config'):
        vbox.running_up_and_wait(env.lab_vm_image_name)
        with settings(user=POSTGRESQL_USERNAME):
            run('ls -l {}'.format(POSTGRESQL_DATA_PATH))
            run('{} -D {} -E unicode'.format(
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
            for parameter in ['listen_addresses', 'checkpoint_segments',
                              'checkpoint_timeout', 'checkpoint_warning',
                              'checkpoint_completion_target',
                              'log_destination', 'logging_collector',
                              'log_directory', 'log_filename',
                              'log_file_mode', 'log_truncate_on_rotation',
                              'log_rotation_age', 'log_rotation_size',
                              'log_duration']:
                uncomment(postgres_conf, '{} = '.format(parameter))
            sed(postgres_conf,
                "listen_addresses = 'localhost'",
                "listen_addresses = '*'")
            sed(postgres_conf,
                "logging_collector = off",
                "logging_collector = on")
            sed(postgres_conf,
                "log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'",
                # "log_filename = 'postgresql.log'")
                "log_filename = '%A.log'")
            sed(postgres_conf,
                "log_statement = 'none'",
                "log_statement = 'all'")
            sed(postgres_conf,
                "log_line_prefix = ''",
                "log_line_prefix = '[%t-%d-%p-%u-%h]'")

        superv.install()
        superv.add_postgres_program(program='postgres',
                                    datadir=POSTGRESQL_DATA_PATH,
                                    autostart=True)
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


@hosts(VM_MASTER_IP)
@with_settings(user=POSTGRESQL_USERNAME)
@task
def deploy_async_master(archive=False, current_scenario='async'):
    vm_name = POSTGRESQL_HOSTS[current_scenario][env.host]['vm_name']
    vbox.running_up_and_wait(vm_name)
    if not vbox.has_snapshot(vm_name,
                             'set_aysnc_replication'):
        vbox.running_up_and_wait(vm_name)
        postgresql.add_bin_path()
        if env.host == VM_MASTER_IP:  # master
            uncomment(POSTGRESQL_CONFIG_FILE, 'wal_level =')
            sed(POSTGRESQL_CONFIG_FILE,
                "wal_level = minimal",
                "wal_level = hot_standby")
            uncomment(POSTGRESQL_CONFIG_FILE, 'max_wal_senders =')
            sed(POSTGRESQL_CONFIG_FILE,
                "max_wal_senders = 0",
                "max_wal_senders = 15")
            uncomment(POSTGRESQL_CONFIG_FILE, 'wal_keep_segments =')
            sed(POSTGRESQL_CONFIG_FILE,
                "wal_keep_segments = 0",
                "wal_keep_segments = 1000")
            uncomment(POSTGRESQL_CONFIG_FILE, 'hot_standby =')
            # making slave readable (pag. 82)
            sed(POSTGRESQL_CONFIG_FILE,
                'hot_standby = off',
                'hot_standby = on')
        vbox.make_snaspshot(vm_name,
                            'set_aysnc_replication',
                            'set aysnc replication')
    if archive:
        if not vbox.has_snapshot(vm_name,
                                 'set_archive_mode'):
            archive_path = POSTGRESQL_HOSTS[current_scenario][env.host][
                'archive_path']
            run('mkdir {}'.format(archive_path))
            uncomment(POSTGRESQL_CONFIG_FILE, 'archive_mode =')
            sed(POSTGRESQL_CONFIG_FILE,
                "archive_mode = off",
                "archive_mode = on")
            uncomment(POSTGRESQL_CONFIG_FILE, 'archive_command =')
            sed(POSTGRESQL_CONFIG_FILE,
                before="archive_command = ''",
                after="archive_command = 'cp %p {}/%f'".format(archive_path))
            vbox.make_snaspshot(vm_name,
                                'set_archive_mode',
                                'set archive mode')
    vbox.running_up_and_wait(vm_name)
    with settings(user='root'):
        run('supervisorctl stop postgres')
        time.sleep(3)
        run('supervisorctl start postgres')
    # run_master_postgres(current_scenario)


@hosts(VM_SLAVE_IP)
@with_settings(user=POSTGRESQL_USERNAME)
@task
def deploy_async_slave(target_path=None, master=None,
                       trigger_file=False, archive=False,
                       current_scenario='async',
                       autorecovery=False):
    autorecovery = bool(autorecovery)
    vm_name = POSTGRESQL_HOSTS[current_scenario][env.host]['vm_name']
    master = master or VM_MASTER_IP
    vbox.running_up_and_wait(vm_name)
    target_path = (
        os.path.join(POSTGRESQL_STORAGE_PATH, target_path) if target_path else
        '{}_{}'.format(os.path.join(POSTGRESQL_STORAGE_PATH, current_scenario),
                       get_random_string()))
    postgresql.add_bin_path()
    print(colors.green('\nPath of target dir: "{}"\n'.format(target_path)))
    if not exists(target_path):
        run('mkdir {path} && chmod 700 {path}'.format(path=target_path))
        pg_basebackup_cmd = os.path.join(
            POSTGRESQL_ROOT_PATH, 'bin', 'pg_basebackup')
        run('{cmd} -h {master} -D {data} {autorecovery} '
            '--xlog-method=stream'.format(
                cmd=pg_basebackup_cmd, master=master, data=target_path,
                autorecovery='-R' if autorecovery else ''))
        with cd(target_path):
            if not autorecovery:
                recovery_file = 'recovery.conf'
                if not exists(recovery_file):
                    run('touch {}'.format(recovery_file))
                else:
                    run('rm -f {}'.format(recovery_file))
                if archive:
                    archive_path = POSTGRESQL_HOSTS[current_scenario][
                        VM_MASTER_IP]['archive_path']
                    if exists(archive_path):
                        run('rm -rf {}/*'.format(archive_path))
                    else:
                        run('mkdir {}'.format(archive_path))
                    append(recovery_file,
                           "restore_command = 'rsync -azh {}@{}:{}/%f"
                           " %p'".format(POSTGRESQL_USERNAME,
                                         VM_MASTER_IP,
                                         archive_path))
                append(recovery_file, 'standby_mode = on')
                append(recovery_file,
                       "primary_conninfo= ' host={} port=5432 '".format(
                           master))
                # # making slave readable (pag. 82)
                # uncomment('postgresql.conf', 'hot_standby =')
                # sed('postgresql.conf', 'hot_standby = off',
                #     'hot_standby = on')
                if trigger_file:
                    if not contains(recovery_file, 'trigger_file'):
                        append(recovery_file,
                               "trigger_file = '/tmp/start_me_up.txt'")

    vbox.running_up_and_wait(vm_name)
    with settings(user='root'):
        if superv.add_postgres_program(program='postgres_async',
                                       datadir=target_path,
                                       autostart=False):
            sed('/etc/supervisor/conf.d/postgres.conf',
                before="autostart=True", after="autostart=False")
            run('supervisorctl reread')
            run('supervisorctl reload')
            run('supervisorctl stop postgres')
            time.sleep(2)
            run('supervisorctl start postgres_async')
    # postgresql.run_interactive(datapath=target_path)


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


@hosts(VM_SLAVE_IP)
@with_settings(user=POSTGRESQL_USERNAME)
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


@hosts(VM_SLAVE_IP)
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
    print(colors.green('DB_NAME: {}'.format(db_name)))
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
@tmp_db
def test_async_cluster():
    """Test the "base" dir of "data" dir [pag 29]"""
    db_name = env.pg_tmp_db_name
    table_name = 't_test'
    print(colors.green('DB_NAME: {}'.format(db_name)))
    with settings(warn_only=True, user=POSTGRESQL_USERNAME):
        run('ls -l {}'.format(os.path.join(POSTGRESQL_DATA_PATH, 'base')))
        out_dbs = psql_cmd('SELECT oid, datname FROM pg_database')
        psql_cmd("CREATE TABLE %s (id int4)" % table_name, db=db_name)
        psql_shell()


#### synchronous replication scenario ######################################

@hosts(VM_MASTER_IP)
@with_settings(user=POSTGRESQL_USERNAME)
@task
def deploy_sync_master(archive=False):
    current_scenario = 'sync'
    vm_name = POSTGRESQL_HOSTS[current_scenario][env.host]['vm_name']
    application_name = POSTGRESQL_HOSTS[current_scenario][env.host][
        'application_name']
    if not vbox.has_snapshot(vm_name,
                             'set_sync_replication'):
        vbox.running_up_and_wait(vm_name)
        postgresql.add_bin_path()
        uncomment(POSTGRESQL_CONFIG_FILE, 'wal_level =')
        sed(POSTGRESQL_CONFIG_FILE,
            "wal_level = minimal",
            "wal_level = hot_standby")
        uncomment(POSTGRESQL_CONFIG_FILE, 'max_wal_senders =')
        sed(POSTGRESQL_CONFIG_FILE,
            "max_wal_senders = 0",
            "max_wal_senders = 15")
        uncomment(POSTGRESQL_CONFIG_FILE, 'hot_standby =')
        sed(POSTGRESQL_CONFIG_FILE,
            'hot_standby = off',
            'hot_standby = on')
        uncomment(POSTGRESQL_CONFIG_FILE, 'synchronous_standby_names =')
        sed(POSTGRESQL_CONFIG_FILE,
            "synchronous_standby_names = ''",
            "synchronous_standby_names = '{}'".format(application_name))
        uncomment(POSTGRESQL_CONFIG_FILE, 'wal_keep_segments =')
        sed(POSTGRESQL_CONFIG_FILE,
            'wal_keep_segments = 0',
            'wal_keep_segments = 500')
        vbox.make_snaspshot(vm_name,
                            'set_aysnc_replication',
                            'set aysnc replication')
        vbox.running_up_and_wait(vm_name)
    run_master_postgres(current_scenario)

@hosts(VM_SLAVE_IP)
@with_settings(user=POSTGRESQL_USERNAME)
@task
def deploy_sync_slave(target_path=None, master=None,
                      trigger_file=False, archive=False):
    current_scenario = 'sync'
    vm_name = POSTGRESQL_HOSTS[current_scenario][env.host]['vm_name']
    application_name = POSTGRESQL_HOSTS[current_scenario][VM_MASTER_IP][
        'application_name']
    master = master or VM_MASTER_IP
    vbox.running_up_and_wait(vm_name)
    target_path = (
        os.path.join(POSTGRESQL_STORAGE_PATH, target_path) if target_path else
        '{}_{}'.format(os.path.join(POSTGRESQL_STORAGE_PATH, current_scenario),
                       get_random_string()))
    postgresql.add_bin_path()
    print(colors.green('\nPath of target dir: "{}"\n'.format(target_path)))
    if not exists(target_path):
        run('mkdir {path} && chmod 700 {path}'.format(path=target_path))
        pg_basebackup_cmd = os.path.join(
            POSTGRESQL_ROOT_PATH, 'bin', 'pg_basebackup')
        run('{cmd} -h {master} -D {data} --xlog-method=stream'.format(
            cmd=pg_basebackup_cmd,
            master=master,
            data=target_path))
        with cd(target_path):
            recovery_file = 'recovery.conf'
            if not exists(recovery_file):
                run('touch {}'.format(recovery_file))
            else:
                run('rm -f {}'.format(recovery_file))
            if archive:
                archive_path = POSTGRESQL_HOSTS[current_scenario][
                    VM_MASTER_IP]['archive_path']
                if exists(archive_path):
                    run('rm -rf {}/*'.format(archive_path))
                else:
                    run('mkdir {}'.format(archive_path))
                append(recovery_file,
                       "restore_command = 'rsync -azh {}@{}:{}/%f %p'".format(
                           POSTGRESQL_USERNAME,
                           VM_MASTER_IP,
                           archive_path))
            append(recovery_file, 'standby_mode = on')
            append(recovery_file,
                   "primary_conninfo= ' host={} application_name={}"
                   " port=5432 '".format(master, application_name))
            if trigger_file:
                if not contains(recovery_file, 'trigger_file'):
                    append(recovery_file,
                           "trigger_file = '/tmp/start_me_up.txt'")

    postgresql.run_interactive(datapath=target_path)


@hosts(VM_MASTER_IP)
@with_settings(user=POSTGRESQL_USERNAME)
@task
def check_sync_replication():
    local(r"""psql -h {} -U {} <<EOF
\x
SELECT * FROM pg_stat_replication;
EOF""".format(VM_MASTER_IP, POSTGRESQL_USERNAME))


@task
@tmp_db
def test_sync_cluster(table_name=None):
    """Test the "base" dir of "data" dir [pag 29]"""
    db_name = env.pg_tmp_db_name
    table_name = table_name or 't_test'
    print(colors.green('DB_NAME: {}'.format(db_name)))
    with settings(warn_only=True, user=POSTGRESQL_USERNAME):
        run('ls -l {}'.format(os.path.join(POSTGRESQL_DATA_PATH, 'base')))
        psql_cmd("CREATE TABLE %s (id serial, name VARCHAR(20))" % table_name,
                 db=db_name)
        psql_shell()


@task
def watch_query(db=None, table=None):
    table = table or 't_test'
    if not db:
        abort('Specify database name!')
    local('watch -n 1 "psql -h {} -U {} -d {} -c \'select * from {}'
          ' order by id desc\'"'.format(env.host, POSTGRESQL_USERNAME,
                                        db, table))


@task
def insert_to_test(db=None, value=None, table=None, ):
    table = table or 't_test'
    value = "'{}'".format(value) if value else "random()"
    if not db:
        abort('Specify database name!')
    psql_cmd("INSERT INTO {} (name) VALUES ({})".format(table, value),
             db=db)


@hosts(VM_MASTER_IP)
@with_settings(user=POSTGRESQL_USERNAME)
@task
def change_durability_onthefly(db=None, synchronous_commit='local'):
    """change durability onthefly (pag. 103"""
    if not db:
        abort('Specify database name!')
    local(r"""psql -h {} -U {} -d {}<<EOF
BEGIN;
INSERT INTO t_test (name) VALUES ('name_1');
INSERT INTO t_test (name) VALUES ('name_2');
SET synchronous_commit TO {};
\x
SELECT * FROM pg_stat_replication;
COMMIT;
EOF""".format(VM_MASTER_IP, POSTGRESQL_USERNAME, db, synchronous_commit))

#### end synchronous replication scenario ###################################

#### pgbouncer ################

@hosts(VM_SLAVE_2_IP)
@with_settings(user='root')
@task
def deploy_pgbouncer():
    current_scenario = 'pgbouncer'
    vm_name = POSTGRESQL_HOSTS[current_scenario][env.host]['vm_name']
    vbox.running_up_and_wait(vm_name)
    if not vbox.has_snapshot(vm_name, 'pgbouncer_installation'):
        source_url = ('http://pgfoundry.org/frs/download.php/3393/'
                      'pgbouncer-1.5.4.tar.gz')
        run('apt-get update && apt-get install -y libevent-dev')
        run('wget {}'.format(source_url))
        pgbouncer_source_dir = '/opt/pgbouncer_1_5_4'
        run('rm -rf ' + pgbouncer_source_dir)
        run('mkdir {dir} && tar xvf {source} -C {dir}'
            ' --strip-components=1'.format(dir=pgbouncer_source_dir,
                                           source=source_url.split('/')[-1]))
        with cd(pgbouncer_source_dir):
            run('./configure')
            run('make clean')
            run('make install')
        vbox.make_snaspshot(
            vm_name, 'pgbouncer_installation', 'pgbouncer installation')

#### end pgbouncer ################

#### pgpool ####################
@hosts(VM_SLAVE_2_IP)
@with_settings(user='root')
@task
def deploy_pgpool(current_scenario='pgpool_replication'):
    vm_name = POSTGRESQL_HOSTS[current_scenario][env.host]['vm_name']
    source_url = ('http://www.pgpool.net/download.php?'
                  'f=pgpool-II-3.4.1.tar.gz')
    source_file = source_url.split('=')[-1]
    source_dir = '/opt/source/{}'.format(
        source_file.replace('.tar.gz', '').replace('.', '_'))

    vbox.running_up_and_wait(vm_name)
    if not vbox.has_snapshot(vm_name, 'pgpool_installation'):
        postgresql.add_bin_path(user=env.user)
        superv.install()
        run('wget -O {} {}'.format(source_file, source_url))
        run('rm -rf ' + source_dir)
        run('mkdir -p {dir} && tar xvf {source} -C {dir}'
            ' --strip-components=1'.format(dir=source_dir,
                                           source=source_file))
        with cd(source_dir):
            run('./configure --with-pgsql={}'.format(POSTGRESQL_ROOT_PATH))
            run('make clean')
            run('make install')
        run('ldconfig /usr/local/lib/')
        run('mkdir /var/run/pgpool/')
        # with cd(os.path.join(source_dir, 'src', 'sql', 'pgpool-regclass')):
        #     run('make')
        #     run('make install')
        # with cd('/usr/local/etc/'):
        #     for pgpool_conf in ['pgpool.local_replication.conf',
        #                         'pgpool.async_replication.conf']:
        #         run('cp pgpool.conf.sample {}'.format(pgpool_conf))
        #         sed(pgpool_conf,
        #             "listen_addresses = 'localhost'",
        #             "listen_addresses = '*'")
        #         for var in ['backend_hostname1', 'backend_port1',
        #                     'backend_weight1', 'backend_data_directory1',
        #                     'backend_flag1']:
        #             uncomment(pgpool_conf, var)
        #         if 'local' in pgpool_conf:
        #             sed(pgpool_conf,
        #                 'replication_mode = off',
        #                 'replication_mode = on')
        #         elif 'async' in pgpool_conf:
        #             sed(pgpool_conf,
        #                 'master_slave_mode = off',
        #                 'master_slave_mode = on')
        #             sed(pgpool_conf,
        #                 "master_slave_sub_mode = 'slony'",
        #                 "master_slave_sub_mode = 'stream'")
        #             sed(pgpool_conf,
        #                 "backend_hostname0 = 'localhost'",
        #                 "backend_hostname0 = '{}'".format(VM_MASTER_IP))
        #             sed(pgpool_conf,
        #                 "backend_hostname1 = 'host2'",
        #                 "backend_hostname1 = '{}'".format(VM_SLAVE_IP))
        #             sed(pgpool_conf,
        #                 "backend_port1 = 5433",
        #                 "backend_port1 = 5432")
        #             sed(pgpool_conf,
        #                 "backend_data_directory1 = '/data1'",
        #                 "backend_data_directory1 = '{}'".format(
        #                     os.path.join(POSTGRESQL_STORAGE_PATH,
        #                                  'async_pgpool')))
        #             sed(pgpool_conf,
        #                 "sr_check_user = 'nobody'",
        #                 "sr_check_user = 'postgres'")
        #         sed(pgpool_conf,
        #             'load_balance_mode = off',
        #             'load_balance_mode = on')
        #     run('touch pcp.conf')
        #     for user in ['user1', 'user2', POSTGRESQL_USERNAME]:
        #         append('pcp.conf',
        #                '{}:c21f969b5f03d33d43e04f8f136e7682'.format(user))
        vbox.make_snaspshot(
            vm_name, 'pgpool_installation', 'pgpool installation')

    # vbox.running_up_and_wait(vm_name)
    # if not vbox.has_snapshot(vm_name, 'local_replication'):
    #     with settings(user=POSTGRESQL_USERNAME):
    #         for i in range(1, 3):
    #             instance_name = 'pgdb{}'.format(i)
    #             data_dir = os.path.join(POSTGRESQL_STORAGE_PATH, instance_name)
    #             port = 5432 + i
    #             run('mkdir {}'.format(data_dir))
    #             run('initdb -D {}'.format(data_dir))
    #             with cd(data_dir):
    #                 config_file = os.path.split(POSTGRESQL_CONFIG_FILE)[-1]
    #                 uncomment(config_file, 'listen_addresses = ')
    #                 sed(config_file,
    #                     "listen_addresses = 'localhost'",
    #                     "listen_addresses = '*'")
    #                 uncomment(config_file, 'port = ')
    #                 sed(config_file,
    #                     "port = 5432",
    #                     "port = {}".format(port))
    #             with settings(user='root'):
    #                 print(colors.red("current user: %s" % env.user))
    #                 run('mkdir /var/log/pgpool/ && '
    #                     'touch /var/log/pgpool/pgpool_status')
    #                 with cd('/usr/local/etc/'):
    #                     pgpool_conf = 'pgpool.local_replication.conf'
    #                     if port == 5433:
    #                         sed(pgpool_conf,
    #                             "backend_port0 = 5432",
    #                             "backend_port0 = {}".format(port))
    #                         sed(pgpool_conf,
    #                             "backend_data_directory0 = "
    #                             "'/var/lib/pgsql/data'",
    #                             "backend_data_directory0 = '{}'".format(
    #                                 data_dir))
    #                     elif port == 5434:
    #                         sed(pgpool_conf,
    #                             "backend_port1 = 5433",
    #                             "backend_port1 = {}".format(port))
    #                         sed(pgpool_conf,
    #                             "backend_data_directory1 = '/data1'",
    #                             "backend_data_directory1 = '{}'".format(
    #                                 data_dir))
    #                 superv.add_postgres_program(program=instance_name,
    #                                             datadir=data_dir,
    #                                             autostart=True)
    #                 run('supervisorctl reread')
    #                 run('supervisorctl reload')
    #             time.sleep(3)
    #             with cd(os.path.join(source_dir, 'src', 'sql')):
    #                 print(colors.red("current user: %s" % env.user))
    #                 run('psql -p {} -f insert_lock.sql template1'.format(port))
    #                 run('psql -p {} -f pgpool-regclass/pgpool-regclass.sql'
    #                     ' template1'.format(port))
    #     vbox.make_snaspshot(
    #         vm_name, 'local_replication', 'local_replication')
    vbox.running_up_and_wait(vm_name)


@hosts(VM_SLAVE_2_IP)
@with_settings(user='root')
@task
def pgpool_run(replication='async', debug=False):
    pid_dir = '/var/run/pgpool/'
    if not exists(pid_dir):
        run('mkdir {}'.format(pid_dir))
    pgpool_conf = '/usr/local/etc/pgpool.{}_replication.conf'.format(
        replication)
    run('pgpool %s-n -f %s' % (' -d' if debug else '', pgpool_conf))


@hosts(VM_SLAVE_2_IP)
@with_settings(user=POSTGRESQL_USERNAME, warn_only=True)
@task
def pgpool_status(replication='async', user=POSTGRESQL_USERNAME):
    for i in range(0, 2):
        run('pcp_node_info 5 localhost 9898 {} default {}'.format(user, i))
    run('psql -l -p 9999')


#### end pgpool ################



@task
def demo_random():
    from utils import get_random_string
    print(get_random_string())
    print(get_random_string('test'))

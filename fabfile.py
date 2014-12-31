# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import time
import os.path

from fabric.api import local, run, env, task, settings, hosts, open_shell, cd
from fabric.contrib.files import exists, uncomment, append, contains, sed


import vbox
from ssh import prepare_ssh_autologin


# env.lab = dict()
env.lab_vm_image_name = 'ubuntu1404'
env.lab_vm_image_snapshot = 'post_installation'
env.user = 'root'
env.password = 'default'
env.host = '192.168.59.200'

SNAPSHOTS = {
    'POSTGRES_SOURCE_INSTALL': 'postgres_source_installation'}
POSTGRESQL_ROOT_PATH = '/usr/local/pgsql'
POSTGRESQL_DATA_PATH = os.path.join(POSTGRESQL_ROOT_PATH, 'data')
POSTGRESQL_HOME_PATH = '/home/postgresql'
POSTGRESQL_STORAGE_PATH = '/opt/postgresql_storage'
POSTGRESQL_LOG_PATH = '/var/log/postgresql'


def get_vm_ip(vm_name):
    print(vbox.vbox_manage('guestproperty', 'get',
          vm_name, '/VirtualBox/GuestInfo/Net/1/V4/IP'))


@task
def deploy_pg_server():
    # vm_name = 'lab_pg_server'
    # vbox.clone_vm(env.lab_vm_image_name, name=vm_name,
    #               snapshot=env.lab_vm_image_snapshot)
    vbox.vbox_manage('startvm', env.lab_vm_image_name)
    up = False
    while not up:
        with settings(warn_only=True):
            get_vm_ip(env.lab_vm_image_name)
            run('ll')
            time.sleep(1)
            up = True
    vbox.vbox_manage('controlvm', env.lab_vm_image_name, 'acpipowerbutton')


@task()
def demo():
    # print(vbox.has_snapshot(env.lab_vm_image_name, 'post_installation'))
    # vbox.has_snapshot('pgsimplemaster', 'pippo')
    print(vbox.vm_exist('vm_exist'))
    print(vbox.vm_exist('pgsimplemaster'))


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
            ' postgres')
        run('echo "postgres:{}" | chpasswd'.format(env.password))
        for path in [POSTGRESQL_DATA_PATH, POSTGRESQL_LOG_PATH,
                     POSTGRESQL_STORAGE_PATH]:
            if not exists(path):
                run('mkdir {}'.format(path))
            run('chown postgres:postgres {}'.format(path))

        vbox.make_snaspshot(env.lab_vm_image_name,
                            'postgres_user_config',
                            'snapshot post postgres user configuration')

    if not vbox.has_snapshot(env.lab_vm_image_name,
                             'postgres_server_post_config'):
        vbox.running_up_and_wait(env.lab_vm_image_name)
        with settings(user='postgres'):
            run('{} -D {}'.format(
                os.path.join(POSTGRESQL_ROOT_PATH, 'bin/initdb'),
                POSTGRESQL_DATA_PATH))

            pg_hba = os.path.join(POSTGRESQL_DATA_PATH, 'pg_hba.conf')
            uncomment(pg_hba, 'local   replication     postgres')
            uncomment(pg_hba, 'host    replication     postgres'
                              '        127.0.0.1\/32')
            for auth_conf in ['host         all  all  192.168.59.0/24  trust',
                              'host         replication  postgres'
                              '  192.168.59.0/24  trust']:
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
def deploy_ptr_scenario(master_vm_name='pgsimplemaster',
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


@hosts('192.168.59.201')
@task
def master_pgsql(user=env.user):
    vbox.running_up_and_wait('pgsimplemaster')
    with settings(user=user):
        open_shell('/usr/local/pgsql/bin/psql')



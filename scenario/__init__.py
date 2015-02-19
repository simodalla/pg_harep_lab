# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from fabric.api import task, hosts, run, with_settings, settings
from fabric.contrib.files import append

from vbox import (vm_exist, clone_vm, has_snapshot, running_up_and_wait,
                  make_snapshot, power_off_and_wait, delete_vm)
from ssh import prepare_ssh_autologin
from postgresql import add_bin_path

from utils.config import *
from utils.files import sed

from fabfile import env

@hosts(VM_TEMPLATE_IP)
@with_settings(user='root')
@task
def prepare(scenario, vm_image=None, snapshot=None):
    vm_image = vm_image or env.lab_vm_image_name
    snapshot = snapshot or 'postgres_server_post_config'
    for ip in POSTGRESQL_HOSTS[scenario]:
        vm_name = POSTGRESQL_HOSTS[scenario][ip]['vm_name']
        if not vm_exist(vm_name):
            clone_vm(vm_image, name=vm_name, options='link', snapshot=snapshot)
        if not has_snapshot(vm_name, 'network_config_for_scenario'):
            success = running_up_and_wait(vm_name)
            prepare_ssh_autologin()
            with settings(user=POSTGRESQL_USERNAME):
                prepare_ssh_autologin()
                add_bin_path()
            sed('/etc/hostname', before='ubuntu1', after=vm_name)
            sed('/etc/hosts', before='ubuntu1', after=vm_name)
            for other_ip in [oi for oi in POSTGRESQL_HOSTS[scenario]
                             if oi != ip]:
                append('/etc/hosts', '{ip}  {hostname}'.format(
                    ip=other_ip,
                    hostname=POSTGRESQL_HOSTS[scenario][other_ip]['vm_name']))
            sed('/etc/network/interfaces',
                before="address {}".format(VM_TEMPLATE_IP),
                after="address {}".format(ip))
            if success:
                make_snapshot(vm_name,
                               'network_config_for_scenario',
                               'network configuration for scenario')


@task
def power_off(scenario):
    """Poweroff all virtual machines of scenario"""
    for conf in POSTGRESQL_HOSTS[scenario]:
        power_off_and_wait(POSTGRESQL_HOSTS[scenario][conf]['vm_name'])


@task
def power_on(scenario):
    print(scenario)
    """Power on all virtual machines of scenario"""
    for conf in POSTGRESQL_HOSTS[scenario]:
        running_up_and_wait(
            POSTGRESQL_HOSTS[scenario][conf]['vm_name'], wait=False)


@task
def delete(scenario):
    """Poweroff, unregister and delete all virtual machines of scenario"""
    for conf in POSTGRESQL_HOSTS[scenario]:
        delete_vm(POSTGRESQL_HOSTS[scenario][conf]['vm_name'])


@task
@hosts(VM_MASTER_IP)
@with_settings(user=POSTGRESQL_USERNAME, warn_olny=True)
def ssh_autologin(scenario):
    run('ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa')
    run('cat .ssh/id_rsa.pub >> .ssh/authorized_keys')
    for host in POSTGRESQL_HOSTS[scenario]:
        if host != VM_MASTER_IP:
            run('rsync -azvh .ssh  {}@{}:'.format(env.user, host))
            run('cat .ssh/id_rsa.pub >> .ssh/authorized_keys')

@task
@hosts(VM_MASTER_IP, VM_SLAVE_IP, VM_SLAVE_2_IP, VM_SLAVE_3_IP)
@with_settings(user='root', warn_olny=True)
def ssh_autologin_root(scenario):
    with settings(warn_only=True):
        run('rm -rf {}/ssh/*'.format(env.user))
        run('cp -R /home/{}/.ssh/* /{}/.ssh'.format(POSTGRESQL_USERNAME,
                                                    env.user))

    # for host in POSTGRESQL_HOSTS[scenario]:
    #     # with settings(warn_only=True, user='root'):
    #     # if host != VM_MASTER_IP:
    #     run('rsync -azvh .ssh  {}@{}:'.format(env.user, host))
    #     run('cat .ssh/id_rsa.pub >> .ssh/authorized_keys')
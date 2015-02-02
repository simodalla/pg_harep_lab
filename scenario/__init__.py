# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from fabric.api import task, hosts, run, with_settings, settings

import vbox
from utils.config import *


@task
def power_off(scenario):
    """Poweroff all virtual machines of scenario"""
    for conf in POSTGRESQL_HOSTS[scenario]:
        vbox.power_off_and_wait(POSTGRESQL_HOSTS[scenario][conf]['vm_name'])


@task
def power_on(scenario):
    print(scenario)
    """Power on all virtual machines of scenario"""
    for conf in POSTGRESQL_HOSTS[scenario]:
        vbox.running_up_and_wait(
            POSTGRESQL_HOSTS[scenario][conf]['vm_name'], wait=False)


@task
def delete(scenario):
    """Poweroff, unregister and delete all virtual machines of scenario"""
    for conf in POSTGRESQL_HOSTS[scenario]:
        vbox.delete_vm(POSTGRESQL_HOSTS[scenario][conf]['vm_name'])


@task
@hosts(VM_MASTER_IP)
@with_settings(user=POSTGRESQL_USERNAME, warn_olny=True)
def ssh_autologin(scenario):
    with settings(warn_only=True):
        run('ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa')
        run('cat .ssh/id_rsa.pub >> .ssh/authorized_keys')
        for host in POSTGRESQL_HOSTS[scenario]:
            if host != VM_MASTER_IP:
                run('rsync -azvh .ssh  postgres@{}:'.format(host))
                run('cat .ssh/id_rsa.pub >> .ssh/authorized_keys')
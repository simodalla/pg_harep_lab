# -*- coding: iso-8859-1 -*-

import time

from fabric import api
from fabric.exceptions import NetworkError


class VBoxManageCommand(object):

    _cmd = 'VBoxManage {} {} {}'
    dry_run = False

    def __init__(self, command, *args, **kwargs):
        self.command = command
        self.cmd_args = args
        if 'dry_run' in kwargs:
            self.dry_run = kwargs.get('dry_run')
            del kwargs['dry_run']
        self._cmd_kwargs = kwargs

    @property
    def cmd(self):
        return self._cmd.format(self.command,
                                ' '.join(self.cmd_args),
                                ' '.join(self.cmd_kwargs))

    @property
    def cmd_kwargs(self):
        return [
            '--{} {}'.format(key, value if value is not True else '').strip()
            for key, value in self._cmd_kwargs.items() if value is not None]

    def run(self, local=True):
        func = getattr(api, 'local' if local else 'run')
        if self.dry_run:
            return
        return func(self.cmd)


def has_snapshot(vm_name, snapshot_name):
    with api.settings(warn_only=True):
        out = api.local('VBoxManage snapshot {} list '
                        '--machinereadable'.format(vm_name),
                        capture=True).split('\n')
        out = [s.split('=')[1].strip('"') for s in out
               if s.startswith('SnapshotName')]
        if snapshot_name in out:
            return True
        return False


def get_vm_status(vm_name):
    status = api.local('VBoxManage showvminfo {} --machinereadable'
                       ' | grep VMState='.format(vm_name),
                       capture=True)
    return status.split('=')[1].strip().strip('\n').strip('"')


def vm_exist(vm_name):
    with api.settings(api.hide('warnings'),
                      warn_only=True):
        return True if api.local('VBoxManage list vms |'
                                 ' grep {}'.format(vm_name),
                                 capture=True).strip() else False


def wait_for_up():
    for attempt in range(0, 15):
        try:
            # run('ls', quiet=True)
            api.run('ls -l')
            return True
        except NetworkError:
            print("waiting for running up n: {}".format(attempt))
            time.sleep(2)
            continue
    return False


def wait_for_down(vm_name):
    for attempt in range(0, 15):
        status = get_vm_status(vm_name)
        print("waiting for power off n: {}".format(attempt))
        if status == 'poweroff':
            return True
        time.sleep(2)
    return False


def running_up_and_wait(vm_name):
    if get_vm_status(vm_name) == 'poweroff':
        vbox_manage('startvm', vm_name, type='headless')
        return wait_for_up()
    return False


def power_off_and_wait(vm_name):
    vbox_manage('controlvm', vm_name, 'acpipowerbutton')
    wait_for_down(vm_name)


def make_snaspshot(vm_name, snapshot_name, snapshot_description):
    power_off_and_wait(vm_name)
    vbox_manage('snapshot', vm_name, 'take',
                snapshot_name,
                description='"{}"'.format(snapshot_description))

@api.task
def vbox_manage(command, *args, **kwargs):
    return VBoxManageCommand(command, *args, **kwargs).run()


@api.task
def clone_vm(uuid_name, snapshot=None, options='link', register=True, **kwargs):
    vbox_manage('clonevm', uuid_name, snapshot=snapshot,
                options=options, register=register, **kwargs)

# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import os

from fabric import colors
from fabric.api import task, run, cd
from fabric.contrib.files import exists, contains, append


@task
def prepare_ssh_autologin(ssh_pub_key='~/.ssh/id_rsa.pub'):
    """Prepare server for ssh autologin with ssh ke."""
    ssh_dir = '~/.ssh'
    authorized_keys = 'authorized_keys'

    if not exists(ssh_dir):
        run('mkdir %s' % ssh_dir)

    with cd(ssh_dir):
        if not exists(authorized_keys):
            run('touch %s && chmod 600 %s' % (authorized_keys,
                                              authorized_keys))
        if not os.path.exists(os.path.expanduser(ssh_pub_key)):
            print(colors.red('Public key file "%s" not'
                             ' exist.' % ssh_pub_key))
            return False
        ssh_pub_key_string = open(
            os.path.expanduser(ssh_pub_key), 'r').readline()

        if not contains(authorized_keys, ssh_pub_key_string):
            append(authorized_keys, ssh_pub_key_string)
            print(colors.green('Public key successfully added'
                               ' in %s.' % authorized_keys))
        else:
            print(colors.magenta('Public key already in %s.' %
                                 authorized_keys))
    run('chmod 700 %s' % ssh_dir)
    return True
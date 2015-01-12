# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, with_statement

import hashlib

from fabric.api import *
from fabric.contrib.files import _expand_path


def sed(filename, before, after, limit='', use_sudo=False, backup='.bak',
    flags='', shell=False, not_escaping=False):
    """
    Run a search-and-replace on ``filename`` with given regex patterns.

    Equivalent to ``sed -i<backup> -r -e "/<limit>/ s/<before>/<after>/<flags>g"
    <filename>``. Setting ``backup`` to an empty string will, disable backup
    file creation.

    For convenience, ``before`` and ``after`` will automatically escape forward
    slashes, single quotes and parentheses for you, so you don't need to
    specify e.g.  ``http:\/\/foo\.com``, instead just using ``http://foo\.com``
    is fine.

    If ``use_sudo`` is True, will use `sudo` instead of `run`.

    The ``shell`` argument will be eventually passed to `run`/`sudo`. It
    defaults to False in order to avoid problems with many nested levels of
    quotes and backslashes. However, setting it to True may help when using
    ``~fabric.operations.cd`` to wrap explicit or implicit ``sudo`` calls.
    (``cd`` by it's nature is a shell built-in, not a standalone command, so it
    should be called within a shell.)

    Other options may be specified with sed-compatible regex flags -- for
    example, to make the search and replace case insensitive, specify
    ``flags="i"``. The ``g`` flag is always specified regardless, so you do not
    need to remember to include it when overriding this parameter.

    .. versionadded:: 1.1
        The ``flags`` parameter.
    .. versionadded:: 1.6
        Added the ``shell`` keyword argument.
    """
    func = use_sudo and sudo or run
    # Characters to be escaped in both
    for char in "/'":
        expr = r'\%s' % char if char != "'" else r"'\''"
        before = before.replace(char, expr)
        after = after.replace(char, expr)
    # Characters to be escaped in replacement only (they're useful in regexen
    # in the 'before' part)
    for char in "()":
        after = after.replace(char, r'\%s' % char)
    if limit:
        limit = r'/%s/ ' % limit
    context = {
        'script': r"'%ss/%s/%s/%sg'" % (limit, before, after, flags),
        'filename': _expand_path(filename),
        'backup': backup
    }
    # Test the OS because of differences between sed versions

    with hide('running', 'stdout'):
        platform = run("uname")
    if platform in ('NetBSD', 'OpenBSD', 'QNX'):
        # Attempt to protect against failures/collisions
        hasher = hashlib.sha1()
        hasher.update(env.host_string)
        hasher.update(filename)
        context['tmp'] = "/tmp/%s" % hasher.hexdigest()
        # Use temp file to work around lack of -i
        expr = r"""cp -p %(filename)s %(tmp)s \
&& sed -r -e %(script)s %(filename)s > %(tmp)s \
&& cp -p %(filename)s %(filename)s%(backup)s \
&& mv %(tmp)s %(filename)s"""
    else:
        context['extended_regex'] = '-E' if platform == 'Darwin' else '-r'
        expr = r"sed -i%(backup)s %(extended_regex)s -e %(script)s %(filename)s"
    command = expr % context
    return func(command, shell=shell)
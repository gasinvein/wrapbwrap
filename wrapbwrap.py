#!/usr/bin/env python3
import subprocess
import os
import sys
import argparse
import glob


def is_kinda_safe_path(path):
    """
    Check if given path is not one of the "sensitive" paths or its parents
    """
    sensitive_paths = [os.environ['HOME'], '/home', '/var/lib', '/tmp', '/run', '/run/user']
    given_path = os.path.realpath(path)
    for sp in sensitive_paths:
        if os.path.commonpath([given_path, sp]) == given_path:
            return False
    return True


class BWrapper(object):
    """
    Object handling arguments for bwrap instance to be executed
    """
    _bwrap = 'bwrap'
    _default_args = [
        '--unshare-pid',
        '--unshare-user-try',
        '--ro-bind', '/usr', '/usr',
        '--symlink', 'usr/lib', '/lib',
        '--symlink', 'usr/lib64', '/lib64',
        '--symlink', 'usr/bin', '/bin',
        '--symlink', 'usr/sbin', '/sbin',
        # TODO replace with something secure
        '--ro-bind', '/etc', '/etc',
        '--proc', '/proc',
        '--dev', '/dev',
        '--tmpfs', '/var',
        '--symlink', '../run', '/var/run',
#        '--new-session',
    ]

    def __init__(self, add_essentials=True):
        self._args = self._default_args.copy()
        if add_essentials:
            self.add_mount('/tmp/.X11-unix')
            self.add_mount(os.environ['XAUTHORITY'], False)
            self.add_mount(os.path.join(os.environ['XDG_RUNTIME_DIR'], 'pulse', 'native'))
            self.add_dir(os.environ['HOME'])

    def add_mount(self, path, writable=True, dev=False):
        if dev:
            a = '--dev-bind'
        elif writable:
            a = '--bind'
        else:
            a = '--ro-bind'
        p = os.path.abspath(path)
        self._args += [a, p, p]

    def add_dir(self, path, tmpfs=True):
        a = '--tmpfs' if tmpfs else '--dir'
        self._args += [a, path]

    def add_symlink(self, target, name):
        self._args += ['--symlink', target, name]

    def get_bwrap_cmdline(self, cmdline, workdir=None):
        if workdir is None:
            workdir = os.getcwd()
        return [self._bwrap] + self._args + ['--chdir', workdir] + ['--'] + cmdline

    def run(self, cmdline, workdir=None, stdin=None):
        if stdin is None:
            stdin = sys.stdin
        c = self.get_bwrap_cmdline(cmdline, workdir)
        # TODO pass stadin to subprocess, don't let python handle it for itself
        return subprocess.run(c, shell=False, stdin=stdin)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run command in bwrap sandbox')
    parser.add_argument('-m', '--mount', action='append', type=str, help='Mount directory')
    parser.add_argument('--system-bus', action='store_true', help='Allow D-Bus system bus access (warning: insecure)')
    parser.add_argument('--session-bus', action='store_true', help='Allow D-Bus session bus access (warning: insecure)')
    parser.add_argument('-n', '--no-network', dest='network', action='store_false', help='Disallow network')
    parser.add_argument('-i', '--input', action='store_true', help='Allow access to input devices')
    parser.add_argument('--no-gpu', dest='gpu', action='store_false', help='Disallow access to GPU')
    parser.add_argument('cmd', type=str, nargs='+', help='Command to run')
    args = parser.parse_args()

    wrapper = BWrapper(add_essentials=True)

#    if args.cmd[0].startswith('-'):
#        raise ValueError('First argument must be command name')

    if args.mount:
        for m in args.mount:
            wrapper.add_mount(os.path.abspath(m))

    if args.network:
        rc = '/etc/resolv.conf'
        if os.path.islink(rc):
            wrapper.add_mount(os.path.realpath(rc))
    else:
        wrapper._args.append('--unshare-net')

    if args.system_bus:
        wrapper.add_mount('/run/dbus/system_bus_socket')

    if args.session_bus:
        wrapper.add_mount(os.environ['DBUS_SESSION_BUS_ADDRESS'].split('=')[1])

    if args.input:
        wrapper.add_mount('/dev/uinput', dev=True)
        wrapper.add_mount('/dev/input', dev=True)
        for h in glob.glob('/dev/hidraw*', dev=True):
            wrapper.add_mount(h, dev=True)

    if args.gpu:
        wrapper.add_mount('/dev/dri', dev=True)
        for n in glob.glob('/dev/nvidia*'):
            wrapper.add_mount(n, dev=True)

    cwd = os.getcwd()

    if is_kinda_safe_path(cwd):
        wrapper.add_mount(cwd)
    else:
        wrapper.add_dir(cwd, tmpfs=False)
        print('Working directory {} includes sensitive directories, not mounting'.format(cwd), file=sys.stderr)

    # TODO if command is a file and it's not inside cwd, mount it

    proc = wrapper.run(args.cmd, workdir=cwd)
    sys.exit(proc.returncode)

#!/usr/bin/env python3
import subprocess
import os
import sys
import argparse


bwrap_args = [
    '--unshare-pid',
    '--unshare-user-try',
    '--ro-bind', '/usr', '/usr',
    '--symlink', 'usr/lib', '/lib',
    '--symlink', 'usr/lib64', '/lib64',
    '--symlink', 'usr/bin', '/bin',
    # TODO replace with something secure
    '--ro-bind', '/etc', '/etc',
    '--proc', '/proc',
    '--dev-bind', '/dev', '/dev',
    '--bind', '/tmp/.X11-unix', '/tmp/.X11-unix',
    '--bind', os.environ['XAUTHORITY'], os.environ['XAUTHORITY'],
    '--bind', os.path.join(os.environ['XDG_RUNTIME_DIR'], 'pulse', 'native'), os.path.join(os.environ['XDG_RUNTIME_DIR'], 'pulse', 'native'),
    '--tmpfs', '/var',
    '--symlink', '../run', '/var/run',
    '--tmpfs', os.environ['HOME']
]


def is_kinda_safe_path(path):
    """
    Check if given path is not one of the "sensitive" paths or its parents
    """
    sensitive_paths = [os.environ['HOME'], '/home', '/var/lib', '/tmp']
    given_path = os.path.realpath(path)
    for sp in sensitive_paths:
        if os.path.commonpath([given_path, sp]) == given_path:
            return False
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run command in bwrap sandbox')
    parser.add_argument('-m', '--mount', action='append', type=str, help='Mount directory')
    parser.add_argument('--system-bus', action='store_true', help='Allow D-Bus system bus access (warning: insecure)')
    parser.add_argument('--session-bus', action='store_true', help='Allow D-Bus session bus access (warning: insecure)')
    parser.add_argument('cmd', type=str, nargs='+', help='Command to run')
    args = parser.parse_args()

    if args.cmd[0].startswith('-'):
        raise ValueError('First argument must be command name')

    if args.mount:
        for m in args.mount:
            mpath = os.path.abspath(m)
            bwrap_args += ['--bind', mpath, mpath]

    if args.system_bus:
        dbus_system_socket = '/run/dbus/system_bus_socket'
        bwrap_args += [
            '--bind', dbus_system_socket, dbus_system_socket,
        ]

    if args.session_bus:
        dbus_session_socket = os.environ['DBUS_SESSION_BUS_ADDRESS'].split('=')[1]
        bwrap_args += [
            '--bind', dbus_session_socket, dbus_session_socket
        ]

    cwd = os.getcwd()
    if is_kinda_safe_path(cwd):
        bwrap_args += ['--bind', cwd, cwd]
    else:
        print('Working directory {} includes sensitive directories, not mounting'.format(cwd), file=sys.stderr)

    proc = subprocess.run(['bwrap'] + bwrap_args + ['--'] + args.cmd, shell=False, stdin=sys.stdin)
    sys.exit(proc.returncode)

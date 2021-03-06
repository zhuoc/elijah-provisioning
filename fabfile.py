from __future__ import with_statement

from fabric.api import env
from fabric.api import hide
from fabric.api import run
from fabric.api import local
from fabric.api import sudo
from fabric.api import task
from fabric.api import abort
from fabric.context_managers import cd

import os
import sys


def check_support():
    if run("egrep '^flags.*(vmx|svm)' /proc/cpuinfo > /dev/null").failed:
        abort("Need hardware VM support (vmx)")


def disable_EPT():
    if run("egrep '^flags.*(ept)' /proc/cpuinfo > /dev/null").failed:
        return
    else:
        # disable EPT
        sudo('modprobe -r kvm_intel')
        sudo('modprobe kvm_intel "ept=0"')


@task
def localhost():
    env.run = local
    env.warn_only = True
    env.hosts = ['localhost']


@task
def install():
    check_support()

    # install dependent package
    with hide('stdout'):
        sudo("apt-get update")
    if sudo("apt-get install -y qemu-kvm libvirt-bin gvncviewer " +
            "python-libvirt python-xdelta3 python-dev openjdk-6-jre  " +
            "liblzma-dev apparmor-utils libc6-i386 python-pip libxml2-dev " +
            "libxslt1-dev").failed:
        abort("Failed to install libraries")
    if sudo("pip install msgpack-python==0.1.13 pyliblzma==0.5.3 " + 
            "psutil==0.6.1 SQLAlchemy==0.8.2 python-dateutil==1.5 " +
            "requests==1.1.0 lxml==2.3.5").failed:
        # Use old-version of msgpack library due to OpenStack compatibility
        # See at https://bugs.launchpad.net/devstack/+bug/1134575
        abort("Failed to install python libraries")

    # disable libvirtd from appArmor to enable custom KVM
    if sudo("aa-complain /usr/sbin/libvirtd").failed:
        abort("Failed to disable AppArmor for custom KVM")

    # add current user to groups (optional)
    username = env.get('user')
    if sudo("adduser %s kvm" % username).failed:
        abort("Cannot add user to kvm group")
    if sudo("adduser %s libvirtd" % username).failed:
        abort("Cannot add user to libvirtd group")
    if sudo("adduser %s fuse" % username).failed:
        abort("Cannot add user to fuse group")

    # Make sure to have fuse support
    # qemu-kvm changes the permission of /dev/fuse, so we revert back the
    # permission. This bug is fixed from udev-175-0ubuntu26
    # Please see https://bugs.launchpad.net/ubuntu/+source/udev/+bug/1152718
    if sudo("chmod 1666 /dev/fuse").failed:
        abort("Failed to enable fuse for the user")
    if sudo("chmod 644 /etc/fuse.conf").failed:
        abort("Failed to change permission of fuse configuration")
    if sudo("sed -i 's/#user_allow_other/user_allow_other/g' /etc/fuse.conf"):
        abort("Failed to allow other user to access FUSE file")

    # (Optional) disable EPT support
    # When you use EPT support with FUSE+mmap, it randomly causes kernel panic.
    # We're investigating it whether it's Linux kernel bug or not.
    disable_EPT()

    # install cloudlet package
    current_dir = os.path.abspath(os.curdir)
    with cd(current_dir):
        if sudo("python setup.py install").failed:
            abort("cannot install cloudlet library")

    sys.stdout.write("[SUCCESS] VM synthesis code is installed\n")


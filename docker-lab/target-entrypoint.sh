#!/bin/sh
set -eu
# Remount only this container's private cgroup namespace, never the host tree.
mount -o remount,rw /sys/fs/cgroup
install -d -m 755 /run/sshd
install -m 600 -o ansible -g ansible /run/lab-public/authorized_keys /home/ansible/.ssh/authorized_keys
ssh-keygen -A
exec /sbin/init

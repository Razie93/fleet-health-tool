#!/bin/sh
set -eu
install -d -m 700 /root/.ssh
if [ ! -s /root/.ssh/id_ed25519 ]; then
    ssh-keygen -q -t ed25519 -N "" -C fleet-compliance-lab -f /root/.ssh/id_ed25519
fi
install -m 644 /root/.ssh/id_ed25519.pub /lab-public/authorized_keys
exec sleep infinity

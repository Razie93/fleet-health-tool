# Fleet Health Tool Operations Manual and Troubleshooting Runbook

## 1. Purpose and Scope

The Fleet Health Tool provides:

- CPU, memory, and disk utilization checks through `src/monitor.py`.
- Ubuntu/Debian baseline hardening through `ansible/compliance.yml`.
- Automated tests for monitor behavior in `tests/test_monitor.py`.

`src/log_cleaner.py` and `src/notifier.py` currently contain module
documentation only. They do not yet expose callable functions or command-line
interfaces. Do not schedule either module in production until implementations
and tests are added. SMTP troubleshooting in this runbook applies to a future
notifier or an external SMTP integration.

## 2. Prerequisites and Installation

### Controller requirements

- Python 3
- A Python virtual environment
- `psutil` for host metrics
- `pytest` for tests
- Ansible for compliance automation
- WSL or a Linux host for running Ansible
- SSH key access and sudo privileges on each managed server

> Ansible cannot be used as a native Windows control node. On Windows, run
> Ansible inside WSL or the project's Linux controller container.

### Python setup

From the repository root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install psutil pytest ansible
```

On Linux or WSL:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install psutil pytest ansible
ansible-galaxy collection install community.general
```

The current `requirements.txt` is a placeholder and does not install these
dependencies. Use the commands above until dependency versions are recorded in
that file.

### Managed-server requirements

Each target must:

1. Run Ubuntu or Debian.
2. Have Python 3 and OpenSSH Server installed.
3. Be reachable from the Ansible controller over SSH.
4. Provide a non-root account with sudo privileges.
5. Contain the controller's public key in the account's
   `~/.ssh/authorized_keys`.

Before disabling root login, verify non-root access in a separate terminal:

```bash
ssh -i /root/.ssh/id_ed25519 -p 22 ansible@172.28.93.11
sudo -n true
```

### Inventory

Targets are defined in `ansible/inventory.ini`. A private Docker lab inventory
can use entries such as:

```ini
[linux_servers]
node1 ansible_host=172.28.93.11
node2 ansible_host=172.28.93.12
```

Update `ansible_host`, `ansible_user`, `ansible_port`, and
`ansible_ssh_private_key_file` for the deployment environment. Never commit a
private SSH key.

Verify connectivity before applying compliance changes:

```bash
ansible -i ansible/inventory.ini linux_servers -m ping
```

## 3. CLI Usage Examples

### Monitor with the default 80% threshold

Windows:

```powershell
.\venv\Scripts\python.exe src\monitor.py
```

Linux or WSL:

```bash
./venv/bin/python src/monitor.py
```

The command prints a JSON object. An empty object means all readings are within
the configured threshold:

```json
{}
```

Alerts are keyed by `cpu`, `memory`, or `disk`:

```json
{
  "cpu": {
    "threshold": 80.0,
    "unit": "percent",
    "value": 95.0
  }
}
```

### Set one threshold for all resources

```bash
./venv/bin/python src/monitor.py \
  --threshold 75 \
  --log-file fleet-health.log
```

### Check a specific filesystem

```bash
./venv/bin/python src/monitor.py \
  --threshold 85 \
  --disk-path /var \
  --log-file fleet-health.log
```

### Change the CPU sampling interval

```bash
./venv/bin/python src/monitor.py \
  --cpu-sample-interval 1.0 \
  --log-file fleet-health.log
```

### Force an alert for a smoke test

```bash
./venv/bin/python src/monitor.py \
  --threshold 1 \
  --log-file health-monitor.log
```

The monitor exits with:

- `0` when no threshold is exceeded.
- `1` when one or more alerts are present.

An exit code of `1` is therefore an operational alert, not an application
crash.

### Run tests

```bash
./venv/bin/python -m pytest tests/test_monitor.py -q
```

The tests mock `psutil` readings and do not place load on the host.

### Validate and apply the compliance playbook

Run these commands from WSL or Linux:

```bash
ansible-playbook \
  -i ansible/inventory.ini \
  ansible/compliance.yml \
  --syntax-check

ansible-playbook \
  -i ansible/inventory.ini \
  ansible/compliance.yml \
  --check \
  --diff

ansible-playbook \
  -i ansible/inventory.ini \
  ansible/compliance.yml
```

The playbook:

1. Refuses non-Debian-family targets.
2. Installs `ufw` and `fail2ban`.
3. Allows the inventory's `ansible_port` through UFW before enabling it.
4. Enables and starts UFW and fail2ban.
5. Enforces `PermitRootLogin no`.
6. Validates `sshd_config` with `sshd -t` before saving it.
7. Restarts the `ssh` service only when `sshd_config` changes.

Re-run the playbook to verify idempotence. A compliant system should report no
changed tasks:

```bash
ansible-playbook -i ansible/inventory.ini ansible/compliance.yml
```

## 4. Configuration Thresholds

### CLI threshold

`--threshold` applies the same percentage to CPU, memory, and disk. Its default
is `80.0`. The accepted range is `0` through `100`, inclusive, and the value
must be finite.

An alert is generated only when a reading is strictly greater than the
threshold. A reading of exactly `80.0` does not breach a threshold of `80.0`.

| Option | Default | Purpose |
| --- | ---: | --- |
| `--threshold` | `80.0` | CPU, memory, and disk alert percentage |
| `--disk-path` | `/` | Filesystem passed to `psutil.disk_usage` |
| `--cpu-sample-interval` | `0.1` seconds | CPU measurement interval |
| `--log-file` | `monitor.log` | Warning and informational log destination |

The log file's parent directory must already exist and be writable by the
process account.

### Independent programmatic thresholds

Python callers can configure each resource separately:

```python
from src.monitor import check_system_health

alerts = check_system_health(
    cpu_threshold=85.0,
    memory_threshold=80.0,
    disk_threshold=90.0,
    disk_path="/var",
    cpu_sample_interval=1.0,
)
```

Each returned alert has this structure:

```python
{
    "value": 95.0,
    "threshold": 85.0,
    "unit": "percent",
}
```

## 5. Routine Operations

### Daily health check

```bash
./venv/bin/python src/monitor.py --log-file fleet-health.log
echo $?
tail -n 50 fleet-health.log
```

Investigate sustained alerts rather than reacting to a single short CPU spike.
Disk and memory alerts generally warrant immediate capacity or process review.

### Compliance verification

```bash
ansible -i ansible/inventory.ini linux_servers -m ping
ansible -i ansible/inventory.ini linux_servers -b -m command \
  -a "systemctl is-active ufw fail2ban ssh"
ansible -i ansible/inventory.ini linux_servers -b -m command \
  -a "sshd -T"
```

To inspect only the effective root-login setting:

```bash
ansible -i ansible/inventory.ini linux_servers -b -m shell \
  -a "sshd -T | grep '^permitrootlogin '"
```

Expected output:

```text
permitrootlogin no
```

## 6. Troubleshooting

Treat passwords, private keys, SMTP credentials, and diagnostic output as
sensitive. Do not paste secrets into tickets or commit them to Git.

| Failure | Diagnostic commands | Likely cause | Fix |
| --- | --- | --- | --- |
| **SSH timeout** | From the controller: `ansible -i ansible/inventory.ini linux_servers -m ping -vvvv`; `nc -vz 172.28.93.11 22`; `ssh -vvv -i /root/.ssh/id_ed25519 -p 22 ansible@172.28.93.11`. From server console: `sudo ss -lntp \| grep ':22'`; `sudo systemctl status ssh --no-pager`; `sudo ufw status verbose`. On a Windows network path: `Test-NetConnection 172.28.93.11 -Port 22`. | Incorrect host/port, routing failure, SSH stopped, or UFW/security-group rule blocking the connection. | Correct `ansible_host` and `ansible_port`; start SSH with `sudo systemctl enable --now ssh`; allow the actual port with `sudo ufw allow 22/tcp`; repair network/security-group routing. Confirm a working session before closing console access. |
| **SSH `Permission denied (publickey)` or Ansible permission denied** | `ssh -vvv -i /root/.ssh/id_ed25519 -p 22 ansible@172.28.93.11`; `ls -l /root/.ssh/id_ed25519`; server console: `sudo journalctl -u ssh -n 100 --no-pager`; `sudo ls -ld /home/ansible/.ssh`; `sudo ls -l /home/ansible/.ssh/authorized_keys`; privilege test: `ansible -i ansible/inventory.ini linux_servers -b -m command -a 'id' -vvvv`. | Wrong user or key, permissive key-file modes, missing public key, incorrect ownership, or missing sudo rights. | Set the private key to `chmod 600 /root/.ssh/id_ed25519`; set server ownership with `sudo chown -R ansible:ansible /home/ansible/.ssh`; apply `chmod 700 /home/ansible/.ssh` and `chmod 600 /home/ansible/.ssh/authorized_keys`; install the matching public key; correct inventory variables; grant only the required sudo privileges. |
| **SMTP authentication failure (`535`, `5.7.8`, or similar)** | Confirm the endpoint: `openssl s_client -starttls smtp -connect smtp.example.com:587 -crlf -servername smtp.example.com`. Test authentication without putting secrets on the command line: `SMTP_HOST=smtp.example.com SMTP_PORT=587 SMTP_USER='user@example.com' SMTP_PASSWORD='app-password' python -c "import os,smtplib; s=smtplib.SMTP(os.environ['SMTP_HOST'],int(os.environ['SMTP_PORT']),timeout=10); s.ehlo(); s.starttls(); s.ehlo(); s.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']); print('SMTP authentication succeeded'); s.quit()"`. | Wrong credentials, SMTP AUTH disabled, provider requires an app password, account lockout, or TLS mode/port mismatch. | Verify host and port with the provider; enable SMTP AUTH if policy permits; use an app password when MFA is enabled; rotate expired credentials; use STARTTLS on port 587 or implicit TLS with `smtplib.SMTP_SSL` on port 465. Store credentials in a secret manager or environment variables and never log them. The current `notifier.py` does not yet implement SMTP. |

### Monitor cannot write its log

Example error:

```text
PermissionError: [Errno 13] Permission denied: 'monitor.log'
```

Diagnose:

```bash
pwd
ls -ld .
ls -l monitor.log
touch monitor-write-test.log
```

Fix the destination ownership or select a writable path:

```bash
mkdir -p "$HOME/.local/state/fleet-health"
./venv/bin/python src/monitor.py \
  --log-file "$HOME/.local/state/fleet-health/monitor.log"
```

Do not solve the issue by making the directory world-writable.

### Invalid SSH configuration

The playbook validates the candidate file before applying it. If validation
fails:

```bash
sudo /usr/sbin/sshd -t -f /etc/ssh/sshd_config
sudo journalctl -u ssh -n 100 --no-pager
sudo grep -nE '^[[:space:]]*PermitRootLogin' /etc/ssh/sshd_config
```

Correct the reported syntax error, validate again, and only then restart SSH:

```bash
sudo /usr/sbin/sshd -t -f /etc/ssh/sshd_config
sudo systemctl restart ssh
```

### UFW or fail2ban is not running

```bash
sudo systemctl status ufw fail2ban --no-pager
sudo journalctl -u ufw -u fail2ban -n 100 --no-pager
sudo ufw status verbose
sudo fail2ban-client status
```

Reapply the playbook after correcting package, repository, or configuration
errors:

```bash
ansible-playbook -i ansible/inventory.ini ansible/compliance.yml
```

## 7. Escalation Data

Collect the following before escalating:

```bash
python --version
python -m pip show psutil pytest ansible ansible-core
ansible --version
ansible-inventory -i ansible/inventory.ini --graph
git rev-parse --short HEAD
```

For monitor incidents, include the JSON output, threshold, disk path, exit code,
and relevant log lines. For Ansible incidents, include the failed task name and
redacted `-vvvv` output. Never include private keys, passwords, SMTP secrets, or
authentication tokens.

# Fleet Health Tool

A Python and Ansible toolkit for monitoring host resources, rotating logs, and
enforcing baseline security settings on Ubuntu and Debian servers.

## Features

- Monitors CPU, memory, and disk utilization with `psutil`
- Returns structured JSON alerts when thresholds are exceeded
- Writes health-check results to a configurable log file
- Finds `ERROR` and `CRITICAL` log entries
- Compresses oversized logs into timestamped gzip archives
- Installs and enables UFW and fail2ban with Ansible
- Disables SSH root login and validates the SSH configuration before restart
- Includes pytest unit tests with mocked system metrics
- Includes an isolated Docker Compose lab for compliance testing

> `src/notifier.py` is currently a placeholder and does not send alerts yet.

## Project Structure

```text
fleet-health-tool/
├── src/
│   ├── __init__.py
│   ├── monitor.py
│   ├── log_cleaner.py
│   └── notifier.py
├── ansible/
│   ├── inventory.ini
│   └── compliance.yml
├── tests/
│   ├── test_monitor.py
│   └── test_log_cleaner.py
├── docs/
│   └── RUNBOOK.md
├── docker-lab/
│   ├── compose.yml
│   ├── Dockerfile.controller
│   └── Dockerfile.target
├── LICENSE
├── README.md
└── requirements.txt
```

## Prerequisites

- Python 3
- `psutil`
- `pytest`
- Ansible, when applying server compliance
- WSL or Linux for using Ansible as a control node

Ansible does not support native Windows control nodes. Windows users should run
Ansible through WSL or a Linux controller.

## Installation

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Linux or WSL

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
ansible-galaxy collection install community.general
```

## Resource Monitoring

Run with the default 80% threshold:

```bash
python src/monitor.py
```

Set one threshold for CPU, memory, and disk:

```bash
python src/monitor.py --threshold 75 --log-file fleet_health.log
```

Check a specific filesystem:

```bash
python src/monitor.py \
  --threshold 85 \
  --disk-path /var \
  --cpu-sample-interval 1.0 \
  --log-file fleet_health.log
```

Force an alert for a smoke test:

```bash
python src/monitor.py --threshold 1 --log-file fleet_health.log
```

The command prints alerts as JSON and exits with:

- `0` when all readings are within the threshold
- `1` when one or more thresholds are exceeded

Example alert:

```json
{
  "cpu": {
    "threshold": 80.0,
    "unit": "percent",
    "value": 95.0
  }
}
```

## Log Inspection and Rotation

Inspect `fleet_health.log` and rotate it when it exceeds the default 5 MiB:

```bash
python src/log_cleaner.py
```

Inspect another log:

```bash
python src/log_cleaner.py /var/log/fleet_health.log
```

Force rotation during a smoke test:

```bash
python src/log_cleaner.py --max-size-mb 0.0001
```

The cleaner prints a JSON summary containing matching error entries and the
created archive path. Rotation completes the gzip archive before truncating the
source log.

## Running Tests

```bash
python -m pytest -v
```

The tests mock CPU, memory, and disk values, so they do not stress the host.

## Ansible Compliance

Update `ansible/inventory.ini` with the target hosts, SSH user, port, Python
interpreter, and private-key path. Do not commit private keys.

Verify connectivity:

```bash
ansible -i ansible/inventory.ini linux_servers -m ping
```

Preview the playbook:

```bash
ansible-playbook \
  -i ansible/inventory.ini \
  ansible/compliance.yml \
  --check \
  --diff
```

Apply compliance:

```bash
ansible-playbook -i ansible/inventory.ini ansible/compliance.yml
```

The playbook:

- Supports Ubuntu and Debian targets
- Installs UFW and fail2ban
- Allows the configured SSH port before enabling UFW
- Enables and starts both services
- Enforces `PermitRootLogin no`
- Restarts SSH only when `sshd_config` changes

Verify non-root SSH and sudo access before applying the playbook.

### Local Docker compliance lab

The committed inventory targets an isolated Docker network. On Windows with
Docker Desktop, start the lab from PowerShell:

> The lab grants its target containers elevated Linux capabilities and gives
> the disposable `ansible` user passwordless sudo. Run it only on a trusted
> local development machine; do not deploy this Compose configuration to
> production or a shared host.

```powershell
.\docker-lab\Start-Lab.ps1
```

Open a shell in the Linux controller:

```powershell
docker compose -f docker-lab/compose.yml exec controller bash
```

Then run Ansible from inside that controller:

```bash
ansible-playbook -i ansible/inventory.ini ansible/compliance.yml
```

The lab generates SSH keys inside Docker volumes. No private key is written to
or committed from the repository.

## Operations and Troubleshooting

See [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for:

- Installation and configuration details
- Routine operational commands
- Threshold behavior
- SSH timeout and permission troubleshooting
- SMTP authentication diagnostics
- UFW, fail2ban, and SSH configuration recovery

## License

This project is available under the [MIT License](LICENSE).

## Git Workflow

Development takes place on short-lived feature branches:

```bash
git checkout -b feature/your-feature
```

Run the test suite before committing:

```bash
python -m pytest -v
git status
```

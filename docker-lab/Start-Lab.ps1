[CmdletBinding()]
param([switch]$NoBuild)

$ErrorActionPreference = 'Stop'
$Compose = Join-Path $PSScriptRoot 'compose.yml'
$DockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
if ($DockerCommand) {
    $script:Docker = $DockerCommand.Source
} else {
    $script:Docker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
}
if (-not (Test-Path $script:Docker)) {
    throw 'Docker CLI not found. Open a new PowerShell after installing Docker Desktop.'
}
# Process-local PATH makes Docker credential helpers available in old terminals.
$env:PATH = (Split-Path $script:Docker) + ';' + $env:PATH

function Invoke-LabDocker {
    & $script:Docker @args
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed (exit $LASTEXITCODE): $args"
    }
}

Invoke-LabDocker info --format '{{.ServerVersion}}'
if (-not $NoBuild) {
    $ExistingImages = @(Invoke-LabDocker image ls --format '{{.Repository}}:{{.Tag}}')
    if (($ExistingImages -notcontains 'fleet-compliance-controller:local') -or
        ($ExistingImages -notcontains 'fleet-compliance-target:local')) {
        # Build only on first setup. Rebuilding can replace containers and their
        # writable state; normal startup must preserve the configured targets.
        Invoke-LabDocker compose --parallel 1 --progress plain -f $Compose build controller node1
    }
}
Invoke-LabDocker compose -f $Compose up -d --no-build --wait --wait-timeout 150

# Fetch PUBLIC host keys directly from our Docker containers, not from an
# unauthenticated network scan. The private client key never leaves its volume.
$KnownHosts = @()
$Targets = [ordered]@{node1 = '172.28.93.11'; node2 = '172.28.93.12'}
foreach ($Node in $Targets.Keys) {
    $Address = (Invoke-LabDocker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "fleet-lab-$Node").Trim()
    if ($Address -ne $Targets[$Node]) {
        throw "Unexpected IP for ${Node}: $Address. Check Compose and inventory before proceeding."
    }
    $PublicKey = (Invoke-LabDocker compose -f $Compose exec -T $Node cat /etc/ssh/ssh_host_ed25519_key.pub).Trim()
    if ($PublicKey -notmatch '^ssh-ed25519 [A-Za-z0-9+/=]+(?: .*)?$') {
        throw "Invalid public SSH host key for $Node"
    }
    $KnownHosts += "$Address,$Node $PublicKey"
}
(($KnownHosts -join "`n") + "`n") | & $script:Docker compose -f $Compose exec -T controller sh -c 'umask 077; cat > /root/.ssh/known_hosts'
if ($LASTEXITCODE -ne 0) { throw 'Could not register lab SSH host keys.' }

Invoke-LabDocker compose -f $Compose exec -T controller ansible all -i ansible/inventory.ini -m ping
Write-Host "Lab ready. Open Bash with: docker compose -f docker-lab/compose.yml exec controller bash"

# Windows Service Setup (NSSM)

## Prerequisites
- Python 3.11+ installed (e.g. `C:\Python311\python.exe`)
- NSSM downloaded from https://nssm.cc/download
- Agent files in `C:\sentinel-agent\`

## Install Agent Service

```cmd
nssm install SentinelAgent "C:\Python311\python.exe" "C:\sentinel-agent\agent.py"
nssm set SentinelAgent AppDirectory "C:\sentinel-agent"
nssm set SentinelAgent AppStdout "C:\sentinel-agent\agent.log"
nssm set SentinelAgent AppStderr "C:\sentinel-agent\agent-error.log"
nssm start SentinelAgent
```

## Install Simulator Service

```cmd
nssm install SentinelSimulator "C:\Python311\python.exe" "C:\sentinel-agent\simulator.py --output-dir C:\sentinel-agent\sim_logs"
nssm set SentinelSimulator AppDirectory "C:\sentinel-agent"
nssm set SentinelSimulator AppStdout "C:\sentinel-agent\simulator.log"
nssm set SentinelSimulator AppStderr "C:\sentinel-agent\simulator-error.log"
nssm start SentinelSimulator
```

## Manage Services

```cmd
nssm status SentinelAgent
nssm stop SentinelAgent
nssm restart SentinelAgent
nssm remove SentinelAgent confirm
```

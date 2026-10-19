# Contributing

Keep changes focused on the current-status monitor. Explain the problem, the
resulting behavior and any operational limits in each pull request.

## Local verification

Use Windows with Python 3.11 or newer:

```powershell
python -m unittest discover -s . -v
python netmon.py --once
```

The smoke test uses the supplied loopback-only configuration. Do not commit real
target inventories, generated status files, credentials or operational logs.

## Review and merge

Create a short-lived branch and open a pull request. Include meaningful tests for
behavior changes, update affected documentation, and inspect the CI results.
Review subprocess bounds, configuration validation, publication behavior and
stale-data handling when those paths change. Merge after review and passing CI.

CI checks Windows unit tests and loopback reachability. Remote devices, unattended
startup and authenticated server hosting need separate environment acceptance.
Deployment automation and desired-state reconciliation are not implemented.

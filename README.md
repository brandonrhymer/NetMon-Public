# NetMon Lite

A small Windows IPv4 reachability monitor written in Python, with a static browser
dashboard. It focuses on current status, bounded probes,
and making measurement failures visible. Python 3.11+; standard library only.

## Try it on Windows

The supplied configuration probes only your own machine (`127.0.0.1`).

```powershell
python netmon.py --once
python -m unittest discover -s . -v
```

To monitor continuously, run `python netmon.py`. In a second terminal, run:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

Open http://127.0.0.1:8765/. Stop both processes with Ctrl+C. This development
server is for local preview. It has no authentication.

For your own targets, copy `devices.example.json` to ignored `devices.json`, edit
it, and run `python netmon.py --config devices.json`. Use only networks you are
authorized to monitor. Generated results in `published/` are ignored by Git.

## Code tour and design choices

- `load_config`: validates target addresses, duplicate names/addresses and timing.
- `probe`: calls Windows ping with an argument list and a process deadline. An
  echo reply means `up`; timeout/unreachable means `down`; measurement failures
  or unrecognized responses mean `error`.
- `collect`: overlaps waiting on up to 16 probes using a thread pool. Rounds do
  not overlap. The last successful reply is retained in memory during one run.
- `publish`: writes a temporary JSON document and replaces the published file,
  so readers do not receive a partially written document.
- `index.html`: fetches current JSON, renders names as text and marks readings
  stale after an elapsed deadline or a failed fetch.

There is no database, history store or application framework. These choices
keep the collection path small enough to understand, test and maintain.
The tests mock ping responses to cover failure cases without contacting targets.

## Boundaries and honest limits

This is an early prototype. A successful ping establishes only
that the selected device answered this collector. It does not prove application
health or complete network health. ICMP filtering can prevent a reply.

The collector requires Windows. Failure-message parsing currently recognizes
English Windows output; other output becomes `error`. RTT reported as `<1ms`
is represented as 1ms. Last-success state resets when the process restarts.
Only one collector may write a given output file. Remote targets, localized
Windows, unattended startup and secured server deployment require further
acceptance testing. No production-readiness or deployment claim is made here.

For a server deployment, serve only the dashboard and published data through a
separately configured authenticated HTTPS server. Keep configurations and source
outside its document root. This repository does not provision that environment.

## Development workflow

Changes use short-lived branches and pull requests. The Windows CI workflow runs
unit tests on Python 3.11 and 3.13 and performs a real loopback probe. Review the
diff and CI results before merging. Branch protection is not yet configured.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the local checks and review criteria.
Automated tests do not establish production deployment acceptance.

## License

MIT; see [LICENSE](LICENSE).

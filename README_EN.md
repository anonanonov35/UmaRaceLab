# Uma Race Lab 0.4.1

[Русская версия](README.md)

Unofficial, AI-assisted desktop race simulator for Umamusume: Pretty Derby Global. **Exact agreement with the native game has not yet been established.** The simulation uses a community engine with local amendments and data read from your own installation.

## Windows release

Extract the entire `UmaRaceLab-0.4.1-windows-x64.zip` archive and run `UmaRaceLab.exe`. Keep the `_internal` folder beside the executable. Python and Node.js are included. Select your installed game's `master.mdb` with **Select database**. Necessary course resources must already have been downloaded by the game.

Settings and builds are saved in `%LOCALAPPDATA%/UmaRaceLab`. Existing source-version builds can be imported from `local/autosave-builds.json`. No game binaries, databases, assets, account information or player builds are shipped.

## Features

- Shared field of 1–18 runners, lane positions, blocking, overtaking, stamina and last spurt.
- Manual stats, all ten aptitude grades, specific outfit variants and their own unique skills linked from local master data.
- Skill library with inherited, gold and unique entries, levels and explicit simulation-support status.
- Real course layout and elevation views with corners, slopes and phase markers.
- Replay controls, finish results, approximate race margins and JSON telemetry export.
- RU/EN, light/dark themes and local build storage.

## Source and build

Source: Python 3.11+ with Tk, Node.js and `pip install -r requirements.txt`; run `python tools/prepare_release_deps.py` once, then `python -m uma_lab`. Windows binary builds use Python 3.12 x64, `requirements-build.txt` and `python tools/build_windows.py`. See [release/build instructions](docs/GITHUB_RELEASE.md) and the included GitHub Actions workflow.

The application is GPL-3.0; the compiled honse-sim component has corresponding Rust source in `vendor/honse-sim/source`. See [third-party credits](THIRD_PARTY.md), [accuracy limits](docs/ACCURACY.md) and [research notes](docs/RESEARCH_V2.md). No affiliation with Cygames. Built with assistance from OpenAI Codex.

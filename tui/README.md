# ANME-CLI TUI

Working build of the richer terminal interface. It provides real search, a full
anime-details view, terminal-rendered posters, episode-level Sub/Dub indicators,
live trending content, continue-watching, watchlist/history storage, and launches
the existing `anme-cli` streaming backend.
The TUI performs the conditional Sub/Dub choice and controls MPV over IPC.

## Requirements

- Python 3.10+
- MPV
- the parent `anme-cli` script and its normal dependencies
- a true-colour terminal; Kitty or WezTerm gives the best poster output

## Install

```sh
./install.sh
anme-cli
```

On Windows PowerShell, run `./install.ps1` instead.

Lifecycle commands:

```sh
anme-cli --update
anme-cli --version
anme-cli --uninstall
```

The installer creates an isolated environment under
`~/.local/share/anme-cli` and links the command into `~/.local/bin`.

## Run from source

```sh
cd tui
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Use `/` to search, arrow keys to move, `Enter` to open, and `q` to quit.

Library controls:

- `Enter` opens a Watchlist or History title
- `R` resumes the selected History episode
- `X` removes the selected Watchlist/History entry
- `Ctrl+X` clears History
- playback automatically updates Watchlist progress and History

Player controls:

- `Space` pauses or resumes playback
- `Left` and `Right` seek backward or forward 10 seconds
- `F` toggles fullscreen
- `Q` or `Escape` closes MPV and returns to the library
- elapsed time, duration, state and percentage update live through MPV IPC

Discover:

- fetches the current live trending list from the provider
- opens any trending title directly into its details and episode screen
- shows recent History entries as Continue Watching
- switches from two columns to a stacked layout on narrow terminals
- caches poster downloads and renders a portable true-colour terminal version

Search:

- displays title, type and Sub/Dub episode counts
- updates a poster, duration and synopsis preview while navigating
- uses a side-by-side layout on wide terminals and stacked layout when narrow

## Implemented screens

- Discover and Continue Watching
- Search with live preview
- Anime details and episodes
- Sub/Dub selection
- MPV player controller
- Watchlist
- History and resume

## Tests

```sh
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

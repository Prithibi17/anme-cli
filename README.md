# anme-cli

`anme-cli` is a keyboard-first anime browser and player for the terminal. It
combines a modern Textual interface with the lightweight streaming backend from
the original `ani-cli` project.

## Features

- Live Discover and trending anime
- Search with poster, synopsis, type, score, genres and Sub/Dub counts
- Anime details and per-episode Sub/Dub availability
- Conditional Sub/Dub selection
- Watchlist, history, progress and resume
- MPV playback controls through IPC
- Pause, seek, fullscreen and live playback progress
- True-colour terminal posters with local caching
- Responsive wide and narrow terminal layouts

## Install with one command

### Linux and macOS

```bash
curl -fsSL https://raw.githubusercontent.com/Prithibi17/anme-cli/main/install.sh | sh
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/Prithibi17/anme-cli/main/install.ps1 | iex
```

Windows requires Python, Git for Windows (including Git Bash), and MPV. The
installer adds `%USERPROFILE%\bin` to your user PATH and makes the command
available immediately in the PowerShell window used for installation.

Then run it anytime:

```bash
anme-cli
```

If the command is not found, add the local binary directory to your shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add that line to `~/.bashrc` or `~/.zshrc` to keep it permanent.

## Update, repair or uninstall

These commands work from any supported terminal after installation:

```bash
anme-cli --update
anme-cli --version
anme-cli --uninstall
```

Running the installer again is safe and upgrades or repairs the existing
installation.

## Requirements

- Linux, macOS, or Windows terminal
- Python 3.10+
- Git
- MPV
- `curl`, `sed` and `grep`
- `fzf` only when using the legacy backend interactively (the TUI player does
  not require it)

Ubuntu/Debian example:

```bash
sudo apt install python3 python3-venv git mpv curl sed grep fzf
```

## Controls

| Key | Action |
|---|---|
| `/` | Search |
| `1–4` | Discover, Search, Watchlist, History |
| `Tab / Shift+Tab` | Next or previous section |
| `?` | Keyboard help |
| `Enter` | Open selected anime or episode |
| `W` | Add/remove the Details title from Watchlist |
| `R` | Resume selected history entry |
| `X` | Remove selected entry |
| `Space` | Pause/resume playback |
| `Left/Right` | Seek 10 seconds |
| `Up/Down` | Player volume |
| `M` | Mute |
| `N/P` | Next/previous episode |
| `A/V` | Audio/quality controls |
| `F` | Toggle video-only/fullscreen view |
| `Esc` | Go back to Anime Details or previous screen |
| `Q` | Exit player/application |

## Development

```bash
git clone https://github.com/Prithibi17/anme-cli.git
cd anme-cli/tui
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
anme-cli
```

Run tests:

```bash
cd tui
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

## Credits and license

The streaming backend is derived from
[pystardust/ani-cli](https://github.com/pystardust/ani-cli). The project remains
licensed under GPL-3.0; see [LICENSE](LICENSE).

Streaming availability depends on third-party providers. Use the software only
where permitted by applicable law and the provider's terms.

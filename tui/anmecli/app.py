from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import uuid
import sys
from io import BytesIO
from urllib.request import Request, urlopen

from PIL import Image
from rich.style import Style
from rich.text import Text
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, LoadingIndicator, Static, TabbedContent, TabPane
from textual_image.widget import Image as TerminalImage

from .provider import Anime, AnimeDetails, details, episodes, search, trending
from .store import Store
from .maintenance import uninstall, update
from . import __version__


def poster_cache_path(url: str) -> Path:
    """Download a poster once and return the cached image path."""
    if not url:
        raise ValueError("Poster URL is empty")
    cache_dir = Path.home() / ".cache" / "anme-cli" / "posters"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.img"
    if not cache_file.exists():
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=12) as response:
            cache_file.write_bytes(response.read())
    return cache_file


def poster_renderable(url: str, width: int = 28, height: int = 18) -> Text:
    """Render a Unicode fallback for terminals without an image protocol."""
    if not url:
        return Text("Poster unavailable", style="dim")
    raw = poster_cache_path(url).read_bytes()
    image = Image.open(BytesIO(raw)).convert("RGB")
    image.thumbnail((width, height * 2))
    canvas = Image.new("RGB", (width, height * 2), (7, 18, 25))
    x = (width - image.width) // 2
    y = (height * 2 - image.height) // 2
    canvas.paste(image, (x, y))
    output = Text()
    for row in range(0, height * 2, 2):
        for column in range(width):
            top = canvas.getpixel((column, row))
            bottom = canvas.getpixel((column, row + 1))
            output.append("▀", Style(color=f"rgb{top}", bgcolor=f"rgb{bottom}"))
        if row < height * 2 - 2:
            output.append("\n")
    return output


class AnimeCard(Vertical):
    can_focus = True
    BINDINGS = [("enter", "open", "Open")]

    class Selected(Message):
        def __init__(self, anime: Anime) -> None:
            super().__init__()
            self.anime = anime

    def __init__(self, index: int) -> None:
        super().__init__(id=f"trend-card-{index}", classes="anime-card")
        self.anime: Anime | None = None

    def compose(self) -> ComposeResult:
        yield TerminalImage(id=f"{self.id}-image", classes="card-image")
        yield Static("Loading…", id=f"{self.id}-caption", classes="card-caption")

    def set_anime(self, anime: Anime, artwork: Path | None, info: AnimeDetails | None) -> None:
        self.anime = anime
        if artwork:
            self.query_one(".card-image", TerminalImage).image = artwork
        content = Text()
        content.append(anime.title.upper(), style="bold white")
        if info:
            content.append(f"   ★ {info.score}", style="cyan")
            content.append(
                f"\nSUB {info.sub_episodes or '–'}   DUB {info.dub_episodes or '–'}",
                style="black on #62d9f5",
            )
        self.query_one(".card-caption", Static).update(content)

    def action_open(self) -> None:
        if self.anime:
            self.post_message(self.Selected(self.anime))

    def on_click(self, _event: events.Click) -> None:
        self.action_open()


class AnimeDetailsScreen(ModalScreen[None]):
    CSS = """
    AnimeDetailsScreen { align: center middle; background: $background 90%; }
    #dialog { width: 96%; height: 96%; border: solid $accent; background: $surface; }
    #details-header { height: 3; border-bottom: solid #31505d; padding: 0 1; }
    #details-heading { width: 1fr; color: $accent; content-align: left middle; }
    #summary { height: 20; }
    #poster { width: 30; height: 19; margin: 1; }
    #metadata { width: 1fr; height: 19; padding: 1; border-left: solid #31505d; }
    #episode-area { height: 1fr; border-top: solid #31505d; }
    #episodes { width: 2fr; height: 1fr; }
    #selected-episode { width: 1fr; height: 1fr; padding: 1 2; border-left: solid #31505d; }
    #actions { height: 4; align-horizontal: right; border-top: solid #31505d; padding: 0 1; }
    #actions Button { margin: 0 1; }
    """
    BINDINGS = [("escape", "back", "Back")]

    def __init__(
        self,
        info: AnimeDetails,
        episode_rows: list[tuple[str, str]],
        poster: Path | None,
        initial_episode: str | None = None,
    ) -> None:
        super().__init__()
        self.info = info
        self.episode_rows = episode_rows
        self.poster = poster
        self.initial_episode = initial_episode

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            with Horizontal(id="details-header"):
                yield Static("ANME-CLI / ANIME DETAILS", id="details-heading")
                yield Button("← Back", id="back")
            with Horizontal(id="summary"):
                if self.poster:
                    yield TerminalImage(self.poster, id="poster")
                else:
                    yield Static("Poster unavailable", id="poster")
                yield Static(self.metadata_markup(), id="metadata")
            with Horizontal(id="episode-area"):
                yield DataTable(id="episodes", cursor_type="row")
                yield Static("Select an episode", id="selected-episode")
            with Horizontal(id="actions"):
                yield Button("← Back", id="footer-back")
                yield Button("+ Watchlist", id="watchlist")
                yield Button("Play episode", id="play", variant="primary")

    def metadata_markup(self) -> str:
        genres = ", ".join(self.info.genres) or "N/A"
        return (
            f"[b cyan]{self.info.anime.title.upper()}[/b cyan]\n"
            f"[dim]Aired:[/dim] {self.info.aired}\n"
            f"[dim]Status:[/dim] {self.info.status}    [dim]Score:[/dim] {self.info.score}\n"
            f"[dim]Duration:[/dim] {self.info.duration}\n"
            f"[dim]Audio:[/dim] SUB {self.info.sub_episodes}  •  DUB {self.info.dub_episodes}\n"
            f"[dim]Genres:[/dim] {genres}\n\n"
            f"[b cyan]SYNOPSIS[/b cyan]\n{self.info.synopsis}"
        )

    def on_mount(self) -> None:
        table = self.query_one("#episodes", DataTable)
        table.add_columns("#", "Duration", "SUB", "DUB")
        selected_row = 0
        for index, (number, _episode_id) in enumerate(self.episode_rows):
            integer = int(float(number))
            table.add_row(
                number,
                self.info.duration,
                "✓" if integer <= self.info.sub_episodes else "–",
                "✓" if integer <= self.info.dub_episodes else "–",
                key=number,
            )
            if number == self.initial_episode:
                selected_row = index
        if self.episode_rows:
            table.move_cursor(row=selected_row)
            table.focus()
            self.update_selected_episode(str(self.episode_rows[selected_row][0]))

    def action_back(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#back, #footer-back")
    def back(self) -> None:
        self.action_back()

    @on(Button.Pressed, "#watchlist")
    def add_watchlist(self) -> None:
        callback = getattr(self.app, "add_details_watchlist", None)
        if callback:
            callback(self.info)

    @on(Button.Pressed, "#play")
    def play(self) -> None:
        table = self.query_one("#episodes", DataTable)
        self.request_play(str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value))

    @on(DataTable.RowSelected, "#episodes")
    def select_row(self, event: DataTable.RowSelected) -> None:
        self.request_play(str(event.row_key.value))

    @on(DataTable.RowHighlighted, "#episodes")
    def highlight_row(self, event: DataTable.RowHighlighted) -> None:
        self.update_selected_episode(str(event.row_key.value))

    def request_play(self, episode: str) -> None:
        callback = getattr(self.app, "play_from_details", None)
        if callback:
            callback(self.info, episode)

    def update_selected_episode(self, episode: str) -> None:
        number = int(float(episode))
        has_sub = number <= self.info.sub_episodes
        has_dub = number <= self.info.dub_episodes
        audio = "SUB + DUB" if has_sub and has_dub else "DUB" if has_dub else "SUB"
        self.query_one("#selected-episode", Static).update(
            "[b cyan]SELECTED EPISODE[/b cyan]\n\n"
            f"[b]Episode {episode}[/b]\n"
            f"Duration: {self.info.duration}\n"
            f"Audio: {audio}\n"
            "Quality: Auto (best)\n\n"
            "[Enter] Play episode\n"
            "[Esc] Back"
        )


class AudioPicker(ModalScreen[str | None]):
    CSS = """
    AudioPicker { align: center middle; background: $background 70%; }
    #audio-dialog { width: 48; height: 11; border: solid $accent; padding: 1 2; background: $surface; }
    #audio-actions { height: 3; margin-top: 1; align-horizontal: center; }
    #audio-actions Button { margin: 0 1; }
    """
    BINDINGS = [("escape", "back", "Back")]

    def compose(self) -> ComposeResult:
        with Vertical(id="audio-dialog"):
            yield Label("[b]Choose audio[/b]\nBoth versions are available for this episode.")
            with Horizontal(id="audio-actions"):
                yield Button("SUB", id="sub", variant="primary")
                yield Button("DUB", id="dub")
                yield Button("← Back", id="cancel")

    def action_back(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed)
    def choose(self, event: Button.Pressed) -> None:
        self.dismiss(None if event.button.id == "cancel" else event.button.id)


class PlayerScreen(ModalScreen[None]):
    CSS = """
    PlayerScreen { align: center middle; background: $background 95%; }
    #player-dialog { width: 97%; height: 96%; border: solid $accent; background: $surface; }
    #player-header { height: 3; border-bottom: solid #31505d; padding: 0 1; }
    #player-brand { width: 1fr; color: $accent; content-align: left middle; }
    #player-title { width: 2fr; text-align: center; content-align: center middle; }
    #player-mode { width: 1fr; text-align: right; content-align: right middle; }
    #player-grid { height: 1fr; }
    #video-column { width: 3fr; height: 1fr; }
    #video-frame { height: 1fr; content-align: center middle; border-bottom: solid #31505d; }
    #now-playing { height: 4; padding: 1; }
    #player-sidebar { width: 1fr; height: 1fr; border-left: solid #31505d; }
    #episode-queue { height: 2fr; padding: 1; overflow-y: auto; }
    #playback-info { height: 1fr; border-top: solid #31505d; padding: 1; }
    #player-status { height: 3; content-align: center middle; }
    #progress { height: 3; border: solid #31505d; content-align: center middle; }
    #player-actions { height: 4; align-horizontal: center; content-align: center middle; }
    #player-actions Button { margin: 0 1; }
    #player-hint { height: 3; color: #79aab8; text-align: center; content-align: center middle; border-top: solid #31505d; }
    """
    BINDINGS = [
        ("space", "pause", "Pause"),
        ("left", "seek(-10)", "Back 10s"),
        ("right", "seek(10)", "Forward 10s"),
        ("f", "fullscreen", "Fullscreen"),
        ("q", "close_player", "Exit player"),
        ("escape", "back_to_anime", "Back to anime"),
    ]

    def __init__(
        self,
        anime: Anime,
        episode: str,
        mode: str,
        socket_path: Path,
        process: asyncio.subprocess.Process | None,
        poster: Path | None,
        episode_rows: list[tuple[str, str]],
        error_log: Path,
        inline_video: bool,
        player_wrapper: Path | None,
    ) -> None:
        super().__init__()
        self.anime = anime
        self.episode = episode
        self.mode = mode
        self.socket_path = socket_path
        self.process = process
        self.poster = poster
        self.episode_rows = episode_rows
        self.error_log = error_log
        self.inline_video = inline_video
        self.player_wrapper = player_wrapper

    def compose(self) -> ComposeResult:
        with Vertical(id="player-dialog"):
            with Horizontal(id="player-header"):
                yield Static("ANME-CLI / PLAYER", id="player-brand")
                yield Static(f"{self.anime.title.upper()} — EPISODE {self.episode}", id="player-title")
                yield Static(f"AUTO • {self.mode.upper()}", id="player-mode")
            with Horizontal(id="player-grid"):
                with Vertical(id="video-column"):
                    if self.inline_video:
                        yield Static("Starting inline video…", id="video-frame")
                    elif self.poster:
                        yield TerminalImage(self.poster, id="video-frame")
                    else:
                        yield Static("Video is playing in the MPV window", id="video-frame")
                    yield Static(
                        f"[b cyan]{self.anime.title.upper()}[/b cyan]\n"
                        f"Episode {self.episode}  •  Playing in MPV",
                        id="now-playing",
                    )
                with Vertical(id="player-sidebar"):
                    yield Static(self.queue_markup(), id="episode-queue")
                    yield Static(
                        "[b cyan]PLAYBACK[/b cyan]\n\n"
                        f"Audio: [b]{self.mode.upper()}[/b]\n"
                        "Quality: Auto (best)\n"
                        "Speed: 1.0×\n"
                        "Autoplay: ON",
                        id="playback-info",
                    )
            yield Static("Connecting to MPV…", id="player-status")
            yield Static("░" * 60, id="progress")
            with Horizontal(id="player-actions"):
                yield Button("← Back to anime", id="back-anime")
                yield Button("⏪ 10s", id="seek-back")
                yield Button("⏯ Pause", id="pause", variant="primary")
                yield Button("10s ⏩", id="forward")
                yield Button("Fullscreen", id="fullscreen")
                yield Button("Exit", id="exit", variant="error")
            yield Static(
                "[Esc] Back to anime   [Space] Pause   [←/→] Seek   [F] Fullscreen   [Q] Exit player",
                id="player-hint",
            )

    def queue_markup(self) -> str:
        current = float(self.episode)
        rows = [number for number, _episode_id in self.episode_rows]
        try:
            index = rows.index(self.episode)
        except ValueError:
            index = 0
        visible = rows[max(0, index - 3) : index + 5]
        lines = ["[b cyan]UP NEXT / EPISODES[/b cyan]", ""]
        for number in visible:
            marker = ">" if float(number) == current else " "
            style = "bold green" if marker == ">" else "white"
            lines.append(f"[{style}]{marker} {number:>4}  Episode {number}[/{style}]")
        return "\n".join(lines)

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_status)

    def ipc(self, command: list[object]) -> object | None:
        if not self.socket_path.exists():
            return None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.3)
                client.connect(str(self.socket_path))
                client.sendall((json.dumps({"command": command}) + "\n").encode())
                data = b""
                while b"\n" not in data:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            response = json.loads(data.split(b"\n", 1)[0] or b"{}")
            return response.get("data")
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def refresh_status(self) -> None:
        if self.process is None:
            return
        if self.process.returncode is not None:
            if self.player_wrapper:
                self.player_wrapper.unlink(missing_ok=True)
                self.player_wrapper = None
            if self.process.returncode == 0:
                message = "Playback finished"
            else:
                detail = ""
                try:
                    lines = [line.strip() for line in self.error_log.read_text(errors="replace").splitlines() if line.strip()]
                    detail = lines[-1] if lines else "The backend exited without an error message"
                except OSError:
                    detail = "Could not read the playback error log"
                message = f"Playback failed (exit {self.process.returncode}): {detail}"
            self.query_one("#player-status", Static).update(message)
            return
        position = self.ipc(["get_property", "time-pos"])
        duration = self.ipc(["get_property", "duration"])
        paused = self.ipc(["get_property", "pause"])
        if not isinstance(position, (int, float)) or not isinstance(duration, (int, float)):
            return
        percent = min(100, max(0, int(position / duration * 100))) if duration else 0
        filled = percent * 60 // 100
        bar = "█" * filled + "░" * (60 - filled)
        state = "PAUSED" if paused else "PLAYING"
        self.query_one("#player-status", Static).update(
            f"{state}   {self.format_time(position)} / {self.format_time(duration)}   {percent}%"
        )
        self.query_one("#progress", Static).update(f"[green]{bar[:filled]}[/green]{bar[filled:]}")

    @staticmethod
    def format_time(seconds: float) -> str:
        total = max(0, int(seconds))
        return f"{total // 60:02d}:{total % 60:02d}"

    def action_pause(self) -> None:
        self.ipc(["cycle", "pause"])

    def action_seek(self, seconds: int) -> None:
        self.ipc(["seek", seconds, "relative"])

    def action_fullscreen(self) -> None:
        self.ipc(["cycle", "fullscreen"])

    def action_close_player(self) -> None:
        self.ipc(["quit"])
        self.dismiss()

    def action_back_to_anime(self) -> None:
        self.ipc(["quit"])
        self.dismiss()

    @on(Button.Pressed)
    def player_button(self, event: Button.Pressed) -> None:
        actions = {
            "back-anime": self.action_back_to_anime,
            "seek-back": lambda: self.action_seek(-10),
            "pause": self.action_pause,
            "forward": lambda: self.action_seek(10),
            "fullscreen": self.action_fullscreen,
            "exit": self.action_close_player,
        }
        action = actions.get(event.button.id or "")
        if action:
            action()


class AnmeCLIApp(App[None]):
    TITLE = "ANME-CLI / WATCH"
    SUB_TITLE = "Terminal anime browser"
    CSS_PATH = "theme.tcss"
    BINDINGS = [
        ("/", "focus_search", "Search"),
        ("a", "add_watchlist", "Add to watchlist"),
        ("r", "resume", "Resume"),
        ("x", "remove_entry", "Remove"),
        ("ctrl+x", "clear_history", "Clear history"),
        ("d", "open_tab('discover')", "Discover"),
        ("w", "open_tab('watchlist')", "Watchlist"),
        ("h", "open_tab('history')", "History"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.store = Store()
        self.search_results: dict[str, Anime] = {}
        self.trending_results: dict[str, Anime] = {}
        self.details_cache: dict[str, AnimeDetails] = {}
        self.episode_cache: dict[str, list[tuple[str, str]]] = {}
        self.watchlist_entries: dict[str, Anime] = {}
        self.history_entries: dict[str, tuple[Anime, str, str]] = {}
        # Do not resolve the venv Python symlink: resolving it points at the
        # system Python directory instead of this installation's Scripts/bin.
        bundled_backend = Path(os.sys.executable).parent / "anme-cli-backend"
        repository_backend = Path(__file__).resolve().parents[2] / "anme-cli"
        configured_backend = os.environ.get("ANME_CLI_BIN") or os.environ.get("ANI_CLI_BIN")
        self.ani_cli = next(
            (
                candidate
                for candidate in (
                    Path(configured_backend).expanduser() if configured_backend else None,
                    bundled_backend,
                    repository_backend,
                )
                if candidate is not None and candidate.exists()
            ),
            repository_backend,
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="discover", id="tabs"):
            with TabPane("Discover", id="discover"):
                yield Input(placeholder="/  Search anime…", id="home-query")
                yield Label("[b cyan]01 / TRENDING ANIME[/b cyan]", classes="section-title")
                yield LoadingIndicator(id="discover-loading")
                with Horizontal(id="trending-cards"):
                    for index in range(5):
                        yield AnimeCard(index)
                with Horizontal(id="home-lower"):
                    with Vertical(classes="home-panel"):
                        yield Label("[b cyan]02 / RECENTLY RELEASED EPISODES[/b cyan]", classes="section-title")
                        yield DataTable(id="discover-releases", cursor_type="row")
                    with Vertical(classes="home-panel"):
                        yield Label("[b cyan]03 / CONTINUE WATCHING[/b cyan]", classes="section-title")
                        yield DataTable(id="discover-recent", cursor_type="row")
                yield Static(
                    Text("[↑↓←→] Navigate   [Enter] Open   [/] Search   [D] Refresh   [Q] Quit"),
                    classes="hint",
                )
            with TabPane("Search", id="search"):
                yield Input(placeholder="Search anime by title…", id="query")
                yield LoadingIndicator(id="loading")
                with Horizontal(id="search-grid"):
                    yield DataTable(id="results", cursor_type="row")
                    yield Static("Search for an anime to see its preview.", id="search-preview")
                yield Static("Enter: episodes  •  A: add to watchlist", classes="hint")
            with TabPane("Watchlist", id="watchlist"):
                yield DataTable(id="watchlist-table", cursor_type="row")
                yield Static("Enter: details  •  X: remove", classes="hint")
            with TabPane("History", id="history"):
                yield DataTable(id="history-table", cursor_type="row")
                yield Static("Enter: details  •  R: resume  •  X: remove  •  Ctrl+X: clear", classes="hint")
        yield Footer()

    def on_mount(self) -> None:
        results = self.query_one("#results", DataTable)
        results.add_columns("#", "Title", "Type", "SUB", "DUB")
        watchlist = self.query_one("#watchlist-table", DataTable)
        watchlist.add_columns("Title", "Progress")
        history = self.query_one("#history-table", DataTable)
        history.add_columns("Title", "Episode", "Last watched")
        releases = self.query_one("#discover-releases", DataTable)
        releases.add_columns("Anime", "Episode", "Audio")
        recent = self.query_one("#discover-recent", DataTable)
        recent.add_columns("Title", "Episode", "Audio")
        self.query_one("#loading").display = False
        self.query_one("#discover-loading").display = False
        self.refresh_library_tables()
        self.load_discover()

    def on_resize(self, event: events.Resize) -> None:
        self.set_class(event.size.width < 92, "narrow")

    def action_focus_search(self) -> None:
        self.query_one("#tabs", TabbedContent).active = "search"
        self.query_one("#query", Input).focus()

    def action_open_tab(self, tab: str) -> None:
        self.query_one("#tabs", TabbedContent).active = tab
        self.refresh_library_tables()
        if tab == "discover":
            self.load_discover()

    def action_add_watchlist(self) -> None:
        if self.query_one("#tabs", TabbedContent).active != "search":
            return
        table = self.query_one("#results", DataTable)
        if not table.row_count:
            return
        row_key = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        anime = self.search_results.get(row_key)
        if anime:
            self.store.add_watchlist(anime.anime_id, anime.title)
            self.refresh_library_tables()
            self.notify(f"Added {anime.title} to watchlist")

    def action_resume(self) -> None:
        if self.query_one("#tabs", TabbedContent).active != "history":
            return
        table = self.query_one("#history-table", DataTable)
        if not table.row_count:
            return
        anime_id = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        entry = self.history_entries.get(anime_id)
        if entry:
            anime, episode, mode = entry
            self.play(anime, episode, mode)

    def action_remove_entry(self) -> None:
        active = self.query_one("#tabs", TabbedContent).active
        if active == "watchlist":
            table = self.query_one("#watchlist-table", DataTable)
            if table.row_count:
                anime_id = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
                self.store.remove_watchlist(anime_id)
                self.notify("Removed from watchlist")
        elif active == "history":
            table = self.query_one("#history-table", DataTable)
            if table.row_count:
                anime_id = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
                self.store.remove_history(anime_id)
                self.notify("Removed from history")
        else:
            return
        self.refresh_library_tables()

    def action_clear_history(self) -> None:
        if self.query_one("#tabs", TabbedContent).active == "history":
            self.store.clear_history()
            self.refresh_library_tables()
            self.notify("History cleared")

    @on(Input.Submitted, "#query")
    def submit_search(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.load_search(event.value.strip())

    @on(Input.Submitted, "#home-query")
    def submit_home_search(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.query_one("#tabs", TabbedContent).active = "search"
            query = self.query_one("#query", Input)
            query.value = event.value.strip()
            self.load_search(event.value.strip())

    @work(exclusive=True)
    async def load_search(self, query: str) -> None:
        loading = self.query_one("#loading")
        table = self.query_one("#results", DataTable)
        loading.display = True
        table.clear()
        try:
            found = await asyncio.to_thread(search, query)
            self.search_results = {anime.anime_id: anime for anime in found}
            for index, anime in enumerate(found, 1):
                table.add_row(
                    str(index).zfill(2),
                    anime.title,
                    anime.media_type,
                    str(anime.sub_episodes) if anime.sub_episodes else "–",
                    str(anime.dub_episodes) if anime.dub_episodes else "–",
                    key=anime.anime_id,
                )
            if not found:
                self.notify("No results found", severity="warning")
            else:
                self.show_search_preview(found[0])
        except Exception as error:
            self.notify(f"Search failed: {error}", severity="error", timeout=6)
        finally:
            loading.display = False

    @on(DataTable.RowSelected, "#results")
    def result_selected(self, event: DataTable.RowSelected) -> None:
        anime = self.search_results.get(str(event.row_key.value))
        if anime:
            self.load_episodes(anime)

    @on(DataTable.RowHighlighted, "#results")
    def result_highlighted(self, event: DataTable.RowHighlighted) -> None:
        anime = self.search_results.get(str(event.row_key.value))
        if anime:
            self.show_search_preview(anime)

    @work(exclusive=True, group="preview")
    async def show_search_preview(self, anime: Anime) -> None:
        preview = self.query_one("#search-preview", Static)
        full_info = self.details_cache.get(anime.anime_id)
        if full_info is None:
            try:
                full_info = await asyncio.to_thread(details, anime)
                self.details_cache[anime.anime_id] = full_info
            except Exception:
                full_info = None
        text = Text()
        if anime.poster_url:
            try:
                text = await asyncio.to_thread(poster_renderable, anime.poster_url, 22, 13)
                text.append("\n")
            except Exception:
                pass
        text.append(anime.title + "\n", style="bold cyan")
        text.append(
            f"{anime.media_type}  •  {anime.duration}\n"
            f"SUB {anime.sub_episodes or '–'}  •  DUB {anime.dub_episodes or '–'}\n\n",
            style="white",
        )
        if full_info:
            text.append(
                f"Aired: {full_info.aired}\n"
                f"Status: {full_info.status}  •  Score: {full_info.score}\n"
                f"Genres: {', '.join(full_info.genres) or 'N/A'}\n\n",
                style="white",
            )
        text.append(anime.synopsis or "Open the title for complete details.", style="dim")
        preview.update(text)

    @on(AnimeCard.Selected)
    def trending_card_selected(self, event: AnimeCard.Selected) -> None:
        self.load_episodes(event.anime)

    @on(DataTable.RowSelected, "#discover-releases")
    def release_selected(self, event: DataTable.RowSelected) -> None:
        anime = self.trending_results.get(str(event.row_key.value))
        if anime:
            self.load_episodes(anime)

    @on(DataTable.RowSelected, "#discover-recent")
    def recent_selected(self, event: DataTable.RowSelected) -> None:
        entry = self.history_entries.get(str(event.row_key.value))
        if entry:
            anime, episode, _mode = entry
            self.load_episodes(anime, episode)

    @work(exclusive=True, group="discover")
    async def load_discover(self) -> None:
        loading = self.query_one("#discover-loading")
        releases = self.query_one("#discover-releases", DataTable)
        loading.display = True
        releases.clear()
        try:
            found = await asyncio.to_thread(trending)
            self.trending_results = {anime.anime_id: anime for anime in found}
            featured = found[:5]
            info_results = await asyncio.gather(
                *(asyncio.to_thread(details, anime) for anime in featured),
                return_exceptions=True,
            )
            art_results = await asyncio.gather(
                *(
                    asyncio.to_thread(poster_cache_path, anime.poster_url)
                    for anime in featured
                ),
                return_exceptions=True,
            )
            for index, anime in enumerate(featured):
                info = info_results[index] if isinstance(info_results[index], AnimeDetails) else None
                if info:
                    self.details_cache[anime.anime_id] = info
                art = art_results[index] if isinstance(art_results[index], Path) else None
                self.query_one(f"#trend-card-{index}", AnimeCard).set_anime(anime, art, info)
                releases.add_row(
                    anime.title,
                    str(info.sub_episodes if info else "–"),
                    "SUB + DUB" if info and info.dub_episodes else "SUB",
                    key=anime.anime_id,
                )
            if not found:
                self.notify("Trending content is currently unavailable", severity="warning")
        except Exception as error:
            self.notify(f"Discover failed: {error}", severity="error")
        finally:
            loading.display = False

    @on(DataTable.RowSelected, "#watchlist-table")
    def watchlist_selected(self, event: DataTable.RowSelected) -> None:
        anime = self.watchlist_entries.get(str(event.row_key.value))
        if anime:
            self.load_episodes(anime)

    @on(DataTable.RowSelected, "#history-table")
    def history_selected(self, event: DataTable.RowSelected) -> None:
        entry = self.history_entries.get(str(event.row_key.value))
        if entry:
            anime, episode, _mode = entry
            self.load_episodes(anime, episode)

    @work
    async def load_episodes(self, anime: Anime, initial_episode: str | None = None) -> None:
        self.notify("Loading anime details and episodes…")
        try:
            cached_info = self.details_cache.get(anime.anime_id)
            if cached_info is None:
                info, rows = await asyncio.gather(
                    asyncio.to_thread(details, anime),
                    asyncio.to_thread(episodes, anime.anime_id),
                )
                self.details_cache[anime.anime_id] = info
            else:
                info = cached_info
                rows = await asyncio.to_thread(episodes, anime.anime_id)
            try:
                poster = await asyncio.to_thread(poster_cache_path, info.poster_url)
            except Exception:
                poster = None
        except Exception as error:
            self.notify(f"Could not load anime details: {error}", severity="error")
            return
        if not rows:
            self.notify("No released episodes found", severity="warning")
            return
        self.episode_cache[anime.anime_id] = rows
        self.push_screen(AnimeDetailsScreen(info, rows, poster, initial_episode))

    def add_details_watchlist(self, info: AnimeDetails) -> None:
        self.store.add_watchlist(info.anime.anime_id, info.anime.title)
        self.refresh_library_tables()
        self.notify(f"Added {info.anime.title} to watchlist")

    def play_from_details(self, info: AnimeDetails, episode: str) -> None:
        number = int(float(episode))
        has_sub = number <= info.sub_episodes
        has_dub = number <= info.dub_episodes
        if has_sub and has_dub:
            self.push_screen(
                AudioPicker(),
                lambda mode: self.play(info.anime, episode, mode) if mode else None,
            )
        elif has_dub:
            self.play(info.anime, episode, "dub")
        else:
            self.play(info.anime, episode, "sub")

    def play(self, anime: Anime, episode: str, mode: str = "sub") -> None:
        self.store.add_history(anime.anime_id, anime.title, episode, mode)
        self.store.update_progress(anime.anime_id, episode)
        self.refresh_library_tables()
        self.launch_player(anime, episode, mode)

    @staticmethod
    def kitty_video_player() -> str | None:
        """Return an MPV executable when this Kitty session supports MPV's Kitty VO."""
        preference = os.environ.get("ANME_CLI_INLINE_VIDEO", "auto").lower()
        if preference in {"0", "false", "no", "off"}:
            return None
        detected_renderer = getattr(TerminalImage, "_Renderable", None)
        renderer_module = getattr(detected_renderer, "__module__", "")
        terminal_identity = " ".join(
            os.environ.get(name, "").lower()
            for name in ("TERM", "TERM_PROGRAM", "LC_TERMINAL", "TERMINAL")
        )
        known_tgp_terminal = any(
            name in terminal_identity
            for name in ("kitty", "ghostty", "konsole", "wezterm")
        )
        tgp_detected = renderer_module.endswith(".tgp")
        if preference not in {"1", "true", "yes", "on", "force"} and not (
            tgp_detected or known_tgp_terminal or os.environ.get("KITTY_WINDOW_ID")
        ):
            return None
        configured = os.environ.get("ANI_CLI_PLAYER")
        player = configured if configured and "mpv" in configured.lower() else shutil.which("mpv")
        if not player:
            return None
        try:
            result = subprocess.run(
                [player, "--vo=help"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return player if "kitty" in result.stdout.split() else None

    @work
    async def launch_player(self, anime: Anime, episode: str, mode: str) -> None:
        if not self.ani_cli.exists():
            self.notify(
                "anme-cli backend was not found. Set ANME_CLI_BIN or reinstall the app.",
                severity="error",
                timeout=8,
            )
            return
        state_dir = Path.home() / ".local" / "state" / "anme-cli"
        state_dir.mkdir(parents=True, exist_ok=True)
        socket_path = state_dir / f"mpv-{uuid.uuid4().hex}.sock"
        error_log = state_dir / f"playback-{uuid.uuid4().hex}.log"
        env = os.environ.copy()
        env["ANI_CLI_EXACT"] = "1"
        inline_player = await asyncio.to_thread(self.kitty_video_player)
        inline_video = inline_player is not None
        player_wrapper: Path | None = None
        if inline_player:
            # Keep ani-cli's informational output away from Textual, while
            # allowing MPV's Kitty graphics escape sequences to reach the TTY.
            player_wrapper = state_dir / f"mpv-inline-{uuid.uuid4().hex}"
            player_wrapper.write_text(
                f"#!/bin/sh\nexec {shlex.quote(inline_player)} \"$@\" >/dev/tty\n"
            )
            player_wrapper.chmod(0o700)
            env["ANI_CLI_PLAYER"] = str(player_wrapper)
        else:
            self.notify(
                "Inline video is unavailable in this terminal/MPV build; opening an external MPV window. "
                "Set ANME_CLI_INLINE_VIDEO=force after confirming `mpv --vo=help` lists kitty.",
                severity="warning",
                timeout=10,
            )
        command = [
            *(
                [shutil.which("bash") or "bash", str(self.ani_cli)]
                if os.name == "nt"
                else [str(self.ani_cli)]
            ),
            "-S", "1",
            "-e", episode,
            f"--{mode}",
            "--no-detach",
            "--exit-after-play",
            anime.title,
        ]
        self.notify(f"Opening {anime.title} episode {episode} ({mode.upper()})")
        info = self.details_cache.get(anime.anime_id)
        try:
            player_art = await asyncio.to_thread(
                poster_cache_path, info.poster_url if info else anime.poster_url
            )
        except Exception:
            player_art = None
        player_screen = PlayerScreen(
            anime,
            episode,
            mode,
            socket_path,
            None,
            player_art,
            self.episode_cache.get(anime.anime_id, []),
            error_log,
            inline_video,
            player_wrapper,
        )
        await self.push_screen(player_screen)

        previous_flags = env.get("ANI_CLI_PLAYER_FLAGS", "")
        flags = [previous_flags, f"--input-ipc-server={socket_path}"]
        if inline_video:
            frame = player_screen.query_one("#video-frame").region
            flags.extend(
                [
                    "--vo=kitty",
                    "--profile=sw-fast",
                    "--really-quiet",
                    "--vo-kitty-alt-screen=no",
                    "--vo-kitty-config-clear=no",
                    f"--vo-kitty-left={frame.x + 1}",
                    f"--vo-kitty-top={frame.y + 1}",
                    f"--vo-kitty-cols={max(1, frame.width)}",
                    f"--vo-kitty-rows={max(1, frame.height)}",
                ]
            )
        env["ANI_CLI_PLAYER_FLAGS"] = " ".join(part for part in flags if part).strip()
        with error_log.open("wb") as error_stream:
            process = await asyncio.create_subprocess_exec(
                *command,
                env=env,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=error_stream,
            )
        player_screen.process = process

    def refresh_library_tables(self) -> None:
        # App.query_one() searches only the active modal screen. Playback is
        # started from the details modal, while these tables live on the root
        # screen underneath it.
        root_screen = self.screen_stack[0]
        watchlist = root_screen.query_one("#watchlist-table", DataTable)
        watchlist.clear()
        watchlist_rows = self.store.watchlist()
        self.watchlist_entries = {
            anime_id: Anime(anime_id, title) for anime_id, title, _progress in watchlist_rows
        }
        for anime_id, title, progress in watchlist_rows:
            watchlist.add_row(title, progress, key=anime_id)
        history = root_screen.query_one("#history-table", DataTable)
        history.clear()
        history_rows = self.store.history()
        self.history_entries = {
            anime_id: (Anime(anime_id, title), episode, mode)
            for anime_id, title, episode, mode, _watched_at in history_rows
        }
        for anime_id, title, episode, mode, watched_at in history_rows:
            history.add_row(title, f"{episode} ({mode.upper()})", watched_at, key=anime_id)
        recent = root_screen.query_one("#discover-recent", DataTable)
        recent.clear()
        for anime_id, title, episode, mode, _watched_at in history_rows[:8]:
            recent.add_row(title, episode, mode.upper(), key=anime_id)


def main() -> None:
    if "--version" in sys.argv or "-V" in sys.argv:
        print(__version__)
        return
    if "--update" in sys.argv:
        raise SystemExit(update())
    if "--uninstall" in sys.argv:
        raise SystemExit(uninstall())
    AnmeCLIApp().run()

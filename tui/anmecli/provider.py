from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


BASE_URL = "https://hianime.at"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class Anime:
    anime_id: str
    title: str
    poster_url: str = ""
    media_type: str = "N/A"
    duration: str = "N/A"
    sub_episodes: int = 0
    dub_episodes: int = 0
    synopsis: str = ""


@dataclass(frozen=True)
class AnimeDetails:
    anime: Anime
    poster_url: str
    synopsis: str
    aired: str
    duration: str
    status: str
    score: str
    genres: tuple[str, ...]
    sub_episodes: int
    dub_episodes: int


def _get(path: str) -> str:
    request = Request(f"{BASE_URL}{path}", headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", "replace")


def search(query: str) -> list[Anime]:
    page = _get(f"/search?keyword={quote_plus(query)}")
    page = page.split('id="main-sidebar"', 1)[0]
    seen: set[str] = set()
    results: list[Anime] = []
    chunks = re.split(r'<div class="flw-item[^>]*>', page)[1:]
    for chunk in chunks:
        chunk = chunk.split('<div class="clearfix"></div>', 1)[0]
        identity = re.search(
            r'<h3 class="film-name">\s*<a href="[^"]*/([^"/]+)"\s*title="([^"]+)"',
            chunk,
            re.S,
        )
        if not identity:
            continue
        anime_id, title = identity.groups()
        if anime_id not in seen:
            seen.add(anime_id)
            poster = re.search(r'<img src="([^"]+)"[^>]*class="film-poster-img"', chunk, re.S)
            sub = re.search(r'tick-sub[^>]*>.*?</i>\s*([0-9]+)', chunk, re.S)
            dub = re.search(r'tick-dub[^>]*>.*?</i>\s*([0-9]+)', chunk, re.S)
            description = re.search(r'<div class="description">(.*?)</div>', chunk, re.S)
            info = re.findall(r'<span class="fdi-item[^>]*">\s*([^<]+)', chunk, re.S)
            results.append(
                Anime(
                    anime_id=anime_id,
                    title=unescape(title),
                    poster_url=poster.group(1) if poster else "",
                    media_type=" ".join(info[0].split()) if info else "N/A",
                    duration=" ".join(info[1].split()) if len(info) > 1 else "N/A",
                    sub_episodes=int(sub.group(1)) if sub else 0,
                    dub_episodes=int(dub.group(1)) if dub else 0,
                    synopsis=(
                        " ".join(unescape(re.sub(r"<[^>]+>", "", description.group(1))).split())
                        if description
                        else ""
                    ),
                )
            )
    return results


def trending(limit: int = 12) -> list[Anime]:
    page = _get("/home")
    start = page.find('id="anime-trending"')
    if start < 0:
        return []
    section = page[start : page.find('<div id="anime-featured"', start)]
    pattern = re.compile(
        r'<div class="film-title[^>]*>(.*?)</div>.*?'
        r'<a href="https?://[^/]+/([^"/]+)"[^>]*>\s*'
        r'<img src="([^"]+)"',
        re.S,
    )
    found: list[Anime] = []
    seen: set[str] = set()
    for title_html, anime_id, poster_url in pattern.findall(section):
        title = " ".join(unescape(re.sub(r"<[^>]+>", "", title_html)).split())
        if anime_id not in seen:
            seen.add(anime_id)
            found.append(Anime(anime_id, title, poster_url))
        if len(found) >= limit:
            break
    return found


def episodes(anime_id: str) -> list[tuple[str, str]]:
    numeric_id = anime_id.rsplit("-", 1)[-1]
    page = (
        _get(f"/api/theme/episode/list/{numeric_id}")
        .replace(r'\"', '"')
        .replace(r'\/','/')
    )
    pattern = re.compile(
        rf'data-number="([^"]+)".*?data-id="([0-9]+)".*?/watch/{re.escape(anime_id)}\?ep=',
        re.S,
    )
    return [(episode, episode_id) for episode, episode_id in pattern.findall(page)]


def details(anime: Anime) -> AnimeDetails:
    page = _get(f"/{anime.anime_id}")

    def first(pattern: str, default: str = "N/A") -> str:
        match = re.search(pattern, page, re.S | re.I)
        if not match:
            return default
        value = re.sub(r"<[^>]+>", " ", match.group(1))
        return " ".join(unescape(value).split())

    poster = first(r'<img src="([^"]+)" class="film-poster-img"', "")
    synopsis = first(r'<div class="film-description m-hide">.*?<div class="text">(.*?)</div>')
    aired = first(r'<span class="item-head">Aired:</span>\s*<span class="name">(.*?)</span>')
    duration = first(r'<span class="item-head">Duration:</span>\s*<span class="name">(.*?)</span>')
    status = first(r'<span class="item-head">Status:</span>\s*<span class="name">(.*?)</span>')
    score = first(r'<span class="item-head">MAL Score:</span>\s*<span class="name">(.*?)</span>')
    genre_match = re.search(
        r'<span class="item-head">Genres:</span>(.*?)</div>', page, re.S | re.I
    )
    genres = tuple(
        unescape(value)
        for value in re.findall(r'title="([^"]+)"', genre_match.group(1) if genre_match else "")
    )

    def count(kind: str) -> int:
        value = first(rf'<div class="tick-item tick-{kind}">.*?</i>\s*([0-9]+)', "0")
        return int(value) if value.isdigit() else 0

    return AnimeDetails(
        anime=anime,
        poster_url=poster,
        synopsis=synopsis,
        aired=aired,
        duration=duration,
        status=status,
        score=score,
        genres=genres,
        sub_episodes=count("sub"),
        dub_episodes=count("dub"),
    )

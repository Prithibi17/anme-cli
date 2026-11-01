import unittest
from unittest.mock import patch

from anmecli.provider import Anime, details, episodes, search, trending


SEARCH_HTML = '''
<div class="flw-item flw-item-big"><div class="film-poster">
<div class="tick-item tick-sub"><i></i>12</div><div class="tick-item tick-dub"><i></i>8</div>
<img src="poster.jpg" class="film-poster-img"><div class="film-detail">
<h3 class="film-name"><a href="https://hianime.at/test-show-7" title="Test Show">Test Show</a></h3>
<div class="description">A test &amp; story.</div><div class="fd-infor">
<span class="fdi-item">TV</span><span class="fdi-item fdi-duration">24m</span>
</div></div><div class="clearfix"></div><div id="main-sidebar"></div>
'''

DETAIL_HTML = '''
<img src="poster.jpg" class="film-poster-img"><div class="tick-item tick-sub"><i></i>12</div>
<div class="tick-item tick-dub"><i></i>8</div><div class="film-description m-hide"><div class="text">Story</div></div>
<span class="item-head">Aired:</span><span class="name">2026</span>
<span class="item-head">Duration:</span><span class="name">24m</span>
<span class="item-head">Status:</span><span class="name">Airing</span>
<span class="item-head">MAL Score:</span><span class="name">8.2</span>
<span class="item-head">Genres:</span><a title="Action">Action</a></div>
'''


class ProviderTests(unittest.TestCase):
    @patch("anmecli.provider._get", return_value=SEARCH_HTML)
    def test_search_metadata(self, _get) -> None:
        result = search("test")[0]
        self.assertEqual(result.title, "Test Show")
        self.assertEqual((result.sub_episodes, result.dub_episodes), (12, 8))
        self.assertEqual((result.media_type, result.duration), ("TV", "24m"))

    @patch("anmecli.provider._get", return_value=DETAIL_HTML)
    def test_details_metadata(self, _get) -> None:
        result = details(Anime("test-show-7", "Test Show"))
        self.assertEqual(result.genres, ("Action",))
        self.assertEqual(result.dub_episodes, 8)

    @patch(
        "anmecli.provider._get",
        return_value=r'data-number="1" data-id="99" href="https:\/\/hianime.at\/watch\/test-show-7?ep=99"',
    )
    def test_episode_parser(self, _get) -> None:
        self.assertEqual(episodes("test-show-7"), [("1", "99")])

    @patch(
        "anmecli.provider._get",
        return_value='<div id="anime-trending"><div class="film-title">Test Show</div><a href="https://hianime.at/test-show-7"><img src="poster.jpg"></a><div id="anime-featured">',
    )
    def test_trending_parser(self, _get) -> None:
        self.assertEqual(trending(1)[0].anime_id, "test-show-7")


if __name__ == "__main__":
    unittest.main()

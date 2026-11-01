import os
import tempfile
import unittest
from unittest.mock import patch

from anmecli.store import Store


class StoreTests(unittest.TestCase):
    def test_watchlist_history_and_audio_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"HOME": directory}
        ):
            with patch("pathlib.Path.home", return_value=__import__("pathlib").Path(directory)):
                store = Store()
                store.add_watchlist("show-1", "Show")
                store.update_progress("show-1", "3")
                store.add_history("show-1", "Show", "3", "dub")
                self.assertEqual(store.watchlist()[0][2], "3")
                self.assertEqual(store.history()[0][2:4], ("3", "dub"))
                store.remove_watchlist("show-1")
                store.clear_history()
                self.assertEqual(store.watchlist(), [])
                self.assertEqual(store.history(), [])


if __name__ == "__main__":
    unittest.main()

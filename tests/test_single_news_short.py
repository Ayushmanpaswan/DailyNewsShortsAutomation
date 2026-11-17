import unittest

import fetch_news
import make_video


class SingleNewsShortTests(unittest.TestCase):
    def test_pipeline_selects_only_one_news_story(self):
        self.assertEqual(fetch_news.MAX_NEWS, 1)

    def test_single_poster_video_is_four_seconds(self):
        self.assertEqual(make_video.SECONDS_PER_NEWS, 4)

    def test_video_is_not_configured_for_transitions(self):
        self.assertEqual(make_video.TRANSITION_SECONDS, 0.5)
        # With one poster, make_video bypasses xfade entirely.


if __name__ == "__main__":
    unittest.main()

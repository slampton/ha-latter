"""Browsing the Music Assistant library: the browse handle, album track order and artist albums.

ma_browse.py is standard-library only and loaded by file path; browse_engine.py is checked as source text.
"""

from __future__ import annotations

from pathlib import Path
import unittest

from custom_components.latter.media import browse as ma_browse

LATTER_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "latter"

# A live browse_media answer for library://album/67 (Music Assistant, 2026.11), trimmed.
DIRT_CHILDREN = [
    {"title": "Alice In Chains - Them Bones", "media_class": "track", "media_content_type": "music", "media_content_id": "library://track/831"},
    {"title": "Alice In Chains - Dam That River", "media_class": "track", "media_content_type": "music", "media_content_id": "library://track/832"},
    {"title": "Alice In Chains - Rain When I Die", "media_class": "track", "media_content_type": "music", "media_content_id": "library://track/833"},
    {"title": "Alice In Chains - Would?", "media_class": "track", "media_content_type": "music", "media_content_id": "library://track/843"},
]
ARTIST_CHILDREN = [
    {"title": "Alice In Chains - Dirt", "media_class": "album", "media_content_type": "music", "media_content_id": "library://album/67"},
    {"title": "Alice In Chains - Facelift", "media_class": "album", "media_content_type": "music", "media_content_id": "library://album/89"},
    {"title": "Alice In Chains - Jar Of Flies", "media_class": "album", "media_content_type": "music", "media_content_id": "library://album/144"},
    {"title": "Alice In Chains - Alice In Chains", "media_class": "album", "media_content_type": "music", "media_content_id": "library://album/359"},
]


class _BrowseMedia:
    """Stands in for homeassistant.components.media_player.BrowseMedia: an object with as_dict(), not a dict."""

    def __init__(self, title: str, children: list[dict]) -> None:
        self.title = title
        self.children = children

    def as_dict(self) -> dict:
        return {"title": self.title, "media_class": "album", "children": [dict(c) for c in self.children]}


class TestDeskRegression(unittest.TestCase):
    """Desk Assistant, 2026-11-08: Albums > Dirt showed "No items found".

    Desk's active speaker is its own media_player.desk_assistant_music, linked to the available Music
    Assistant player media_player.desk_assistant (ma_player_entity), so the browse handle was right.
    The in-process browse_media response is {entity_id: BrowseMedia}; the code read it only as a dict
    and returned no children.
    """

    def test_in_process_response_object_is_read(self) -> None:
        resp = {"media_player.desk_assistant": _BrowseMedia("Dirt", DIRT_CHILDREN)}
        node = ma_browse.browse_node_dict(resp["media_player.desk_assistant"])
        self.assertIsNotNone(node)
        self.assertEqual(
            [s["name"] for s in ma_browse.album_track_slots(node["children"])],
            ["1. Them Bones", "2. Dam That River", "3. Rain When I Die", "4. Would?"],
        )
        # Over the websocket API the same response arrives as JSON (a dict); both read the same.
        self.assertEqual(ma_browse.browse_node_dict(_BrowseMedia("Dirt", DIRT_CHILDREN).as_dict()), node)
        self.assertIsNone(ma_browse.browse_node_dict(None))
        self.assertIsNone(ma_browse.browse_node_dict("Dirt"))

    def test_desk_browses_on_its_own_ma_player(self) -> None:
        available = ["media_player.desk_assistant", "media_player.garage_hifi", "media_player.kitchen_speaker"]
        # Preferred: the counterpart of Desk's own speaker (desk_assistant_music -> desk_assistant).
        self.assertEqual(
            ma_browse.choose_browse_entity(["media_player.desk_assistant", None, None], available),
            "media_player.desk_assistant",
        )

    def test_browse_engine_reads_the_object(self) -> None:
        src = (LATTER_DIR / "media" / "browse.py").read_text(encoding="utf-8")
        self.assertIn("browse_node_dict(resp.get(browse_entity))", src)


class TestBrowseEntity(unittest.TestCase):
    def test_prefers_the_devices_own_player_then_a_stable_first(self) -> None:
        players = ["media_player.office_amp", "media_player.kitchen_speaker", "media_player.desk_assistant"]
        self.assertEqual(ma_browse.choose_browse_entity(["media_player.desk_assistant"], players), "media_player.desk_assistant")
        # No MA player of its own (e.g. a pocket Device): the default speaker's, else the first by entity_id.
        self.assertEqual(ma_browse.choose_browse_entity([None, "media_player.office_amp"], players), "media_player.office_amp")
        self.assertEqual(ma_browse.choose_browse_entity([None, None], players), "media_player.desk_assistant")
        self.assertEqual(ma_browse.choose_browse_entity(["media_player.gone"], list(reversed(players))), "media_player.desk_assistant")

    def test_no_player(self) -> None:
        self.assertIsNone(ma_browse.choose_browse_entity(["media_player.x"], []))
        self.assertEqual(ma_browse.text_slot("No Music Assistant player to browse with")[0]["type"], "text")


class TestAlbumTracks(unittest.TestCase):
    def test_album_order_numbering_and_prefix(self) -> None:
        slots = ma_browse.album_track_slots(DIRT_CHILDREN, current_title="Would?")
        self.assertEqual(
            [s["name"] for s in slots],
            ["1. Them Bones", "2. Dam That River", "3. Rain When I Die", "4. Would?"],
        )
        self.assertEqual([s["id"] for s in slots], [c["media_content_id"] for c in DIRT_CHILDREN])
        self.assertEqual([s["active"] for s in slots], [False, False, False, True])
        self.assertTrue(all(s["type"] == "track" for s in slots))

    def test_compilation_keeps_artists(self) -> None:
        mixed = [
            {"title": "Massive Attack - Teardrop", "media_content_id": "library://track/1"},
            {"title": "Portishead - Roads", "media_content_id": "library://track/2"},
        ]
        self.assertEqual(
            [s["name"] for s in ma_browse.album_track_slots(mixed)],
            ["1. Massive Attack - Teardrop", "2. Portishead - Roads"],
        )

    def test_title_equal_to_prefix_and_bad_children(self) -> None:
        self.assertEqual(ma_browse.strip_artist_prefix("Alice In Chains - ", "Alice In Chains"), "Alice In Chains - ")
        rows = [{"title": "A - One", "media_content_id": ""}, {"title": "", "media_content_id": "x"}, {"title": "A - Two", "media_content_id": "u"}]
        self.assertEqual([s["name"] for s in ma_browse.album_track_slots(rows)], ["1. Two"])


class TestArtistAlbums(unittest.TestCase):
    def test_names_and_orders(self) -> None:
        by_name = ma_browse.artist_album_slots(ARTIST_CHILDREN, "Alice In Chains", "name")
        self.assertEqual([s["name"] for s in by_name], ["Alice In Chains", "Dirt", "Facelift", "Jar Of Flies"])
        year = ["library://album/89", "library://album/67", "library://album/144"]
        by_year = ma_browse.artist_album_slots(ARTIST_CHILDREN, "Alice In Chains", "year", year)
        # Albums missing from Music Assistant's year order keep the browse order, last.
        self.assertEqual([s["name"] for s in by_year], ["Facelift", "Dirt", "Jar Of Flies", "Alice In Chains"])
        unranked = ma_browse.artist_album_slots(ARTIST_CHILDREN, "Alice In Chains", "year_desc")
        self.assertEqual([s["id"] for s in unranked], [c["media_content_id"] for c in ARTIST_CHILDREN])
        self.assertTrue(all(s["type"] == "album" for s in by_year))


class TestOnePath(unittest.TestCase):
    def test_browse_engine_has_no_track_title_search_or_speaker_bound_browse(self) -> None:
        src = (LATTER_DIR / "media" / "browse.py").read_text(encoding="utf-8")
        self.assertNotIn("_browse_ma_media_children", src)
        self.assertNotIn('media_type="track",\n            search=album_ref', src)
        self.assertNotIn('not ("library://" in album_ref)', src)
        self.assertIn("choose_browse_entity(preferred, ma_players)", src)

    def test_bounded_64_entry_lru_cache(self) -> None:
        self.assertEqual(ma_browse.MAX_BROWSE_CACHE_ENTRIES, 64)
        ma_browse.clear_browse_cache()
        for i in range(80):
            ma_browse._cache_put(f"key_{i}", {"slots": [f"line_{i}"]})
        self.assertEqual(len(ma_browse._BROWSE_LYRICS_BIO_CACHE), 64)
        self.assertIsNone(ma_browse._cache_get("key_0"))
        self.assertIsNotNone(ma_browse._cache_get("key_16"))
        # Touching key_16 moves it to MRU so adding key_80 evicts key_17 instead of key_16
        ma_browse._cache_put("key_80", {"slots": ["line_80"]})
        self.assertIsNotNone(ma_browse._cache_get("key_16"))
        self.assertIsNone(ma_browse._cache_get("key_17"))
        ma_browse.clear_browse_cache()
        self.assertEqual(len(ma_browse._BROWSE_LYRICS_BIO_CACHE), 0)


if __name__ == "__main__":
    unittest.main()

"""A project's small stores: the dock's pinned filters and its own tags (filters.py), folder colours (foldercolors.py), the app's
settings (server.settings_read/write, lang, tr) and the agents' notifications (server.notify)."""
import json
import re

import pytest

import config
import filters
import foldercolors
import server
from unit_env import PROJECT, SETTINGS


@pytest.fixture
def pins(tmp_path, monkeypatch):
    f = tmp_path / "state" / "filters.json"
    monkeypatch.setattr(filters, "FILE", str(f))
    return f


@pytest.fixture
def rules(tmp_path, monkeypatch):
    f = tmp_path / "support" / "library-rules.json"
    monkeypatch.setattr(config, "RULES_FILE", str(f))
    return f


class TestPins:
    def test_a_project_that_never_chose_has_no_pins(self, pins):
        assert filters.read() == {"pins": None}

    def test_pins_keep_their_order_and_drop_copies(self, pins):
        assert filters.write(["fav", "tag:Bird", "fav", "no"]) == {"pins": ["fav", "tag:Bird", "no"]}
        assert filters.read() == {"pins": ["fav", "tag:Bird", "no"]}
        assert json.loads(pins.read_text()) == {"pins": ["fav", "tag:Bird", "no"]}

    def test_an_empty_list_is_a_choice_too(self, pins):
        filters.write([])
        assert filters.read() == {"pins": []}

    @pytest.mark.parametrize("bad", [None, "fav", {"pins": []}, ["ok", 3], ["ok", ""], ["x" * 201], ["a\nb"], ["tab\t"]])
    def test_anything_but_a_list_of_short_printable_ids_is_refused_and_nothing_is_written(self, pins, bad):
        with pytest.raises(ValueError):
            filters.write(bad)
        assert not pins.exists()

    def test_at_most_300_pins_are_kept(self, pins):
        assert len(filters.write([f"p{n}" for n in range(400)])["pins"]) == 300

    @pytest.mark.parametrize("text", ["{nope", "[]", '{"pins": "fav"}', '{"other": 1}'])
    def test_a_broken_or_odd_file_reads_as_not_chosen(self, pins, text):
        pins.parent.mkdir(parents=True); pins.write_text(text)
        assert filters.read() == {"pins": None}

    def test_bad_ids_in_the_file_are_dropped_when_read(self, pins):
        pins.parent.mkdir(parents=True); pins.write_text(json.dumps({"pins": ["a", 1, "", "a", "b\x00"]}))
        assert filters.read() == {"pins": ["a"]}


class TestOwnTags:
    def test_words_become_one_regex_that_finds_each_word_where_a_word_starts(self):
        rx = re.compile(filters.words_regex(["bird", " c++ ", ""]), re.I)
        assert rx.search("Birdcage") and rx.search("in c++ code") and not rx.search("songbird") and not rx.search("c")

    @pytest.mark.parametrize("words", [[], ["", "  "], ["w"] * 41, ["x" * 61], [3]])
    def test_no_words_too_many_or_too_long_are_refused(self, words):
        with pytest.raises(ValueError):
            filters.words_regex(words)

    def test_a_new_tag_is_appended_to_this_boards_rules_and_nothing_else_changes(self, rules):
        rules.parent.mkdir(parents=True)
        rules.write_text(json.dumps({"*": {"tags": [["T", "Shared", "s"]]}, "other": {"skip": ["x"]}, PROJECT: {"skip": ["y"]}}))
        entry = filters.add_tag(" Who ", " Bird ", "bird, birds;feather\n")
        assert entry == ["Who", "Bird", "(?<!\\w)bird|(?<!\\w)birds|(?<!\\w)feather"]
        doc = json.loads(rules.read_text())
        assert doc[PROJECT] == {"skip": ["y"], "tags": [entry]} and doc["other"] == {"skip": ["x"]} and doc["*"]["tags"] == [["T", "Shared", "s"]]

    def test_without_a_rules_file_one_is_made_with_the_board_key(self, rules):
        filters.add_tag("G", "T", ["w"])
        assert list(json.loads(rules.read_text())) == [config.PROJECT_ID]

    def test_the_boards_key_is_found_whatever_its_case(self, rules):
        rules.parent.mkdir(parents=True); rules.write_text(json.dumps({PROJECT.upper(): {"tags": []}}))
        filters.add_tag("G", "T", ["w"])
        assert list(json.loads(rules.read_text())) == [PROJECT.upper()]

    @pytest.mark.parametrize("existing", ["*", PROJECT])
    def test_a_tag_the_board_already_gets_is_refused_with_key_error(self, rules, existing):
        rules.parent.mkdir(parents=True); rules.write_text(json.dumps({existing: {"tags": [["G", "Bird", "b"]]}}))
        with pytest.raises(KeyError):
            filters.add_tag("Other", "Bird", ["x"])

    @pytest.mark.parametrize("group,tag", [("", "T"), ("G", ""), ("G" * 41, "T"), ("G", "T" * 61), (None, "T"), ("G", None)])
    def test_a_missing_or_too_long_name_or_group_is_refused(self, rules, group, tag):
        with pytest.raises(ValueError):
            filters.add_tag(group, tag, ["w"])
        assert not rules.exists()

    @pytest.mark.parametrize("text", ["[1]", "{nope"])
    def test_a_rules_file_that_is_not_an_object_is_started_again(self, rules, text):
        rules.parent.mkdir(parents=True); rules.write_text(text)
        filters.add_tag("G", "T", ["w"])
        assert json.loads(rules.read_text()) == {config.PROJECT_ID: {"tags": [["G", "T", "(?<!\\w)w"]]}}

    def test_a_board_entry_that_is_not_an_object_is_replaced(self, rules):
        rules.parent.mkdir(parents=True); rules.write_text(json.dumps({PROJECT: "x"}))
        filters.add_tag("G", "T", ["w"])
        assert json.loads(rules.read_text())[PROJECT]["tags"][0][1] == "T"

    def test_reload_rules_reads_the_rules_file_as_it_stands(self, rules):
        filters.add_tag("G", "Fresh", ["w"])
        assert filters.reload_rules()["tags"] == [["G", "Fresh", "(?<!\\w)w"]]


@pytest.fixture
def colours(tmp_path, monkeypatch):
    f = tmp_path / "state" / "folders.json"
    monkeypatch.setattr(foldercolors, "FILE", str(f))
    return f


class TestFolderColours:
    def test_no_file_means_no_colours(self, colours):
        assert foldercolors.read() == {"colors": {}}

    def test_a_colour_is_set_changed_and_taken_off(self, colours):
        foldercolors.write("renders", "blue")
        foldercolors.write("renders/261006-grain", "pink")
        assert foldercolors.write("renders", "green") == {"colors": {"renders": "green", "renders/261006-grain": "pink"}}
        assert foldercolors.write("renders", None) == {"colors": {"renders/261006-grain": "pink"}}
        assert foldercolors.write("renders/261006-grain", "") == {"colors": {}}
        assert json.loads(colours.read_text()) == {"colors": {}}

    def test_taking_off_a_colour_that_is_not_there_is_fine(self, colours):
        assert foldercolors.write("none", None) == {"colors": {}}

    @pytest.mark.parametrize("path", ["", "/abs", "../up", "a/../b", "a\nb", "x" * 1001, None, 5])
    def test_a_bad_folder_path_is_refused(self, colours, path):
        with pytest.raises(ValueError):
            foldercolors.write(path, "blue")
        assert not colours.exists()

    @pytest.mark.parametrize("colour", ["Blue", "#00f", "magenta", 3])
    def test_a_colour_outside_the_boards_note_colours_is_refused(self, colours, colour):
        with pytest.raises(ValueError):
            foldercolors.write("a", colour)

    def test_folder_names_with_dots_that_are_not_a_parent_step_are_fine(self, colours):
        assert foldercolors.write("v1..v2/a.b", "red") == {"colors": {"v1..v2/a.b": "red"}}

    def test_bad_entries_in_the_file_are_dropped_when_read(self, colours):
        colours.parent.mkdir(parents=True)
        colours.write_text(json.dumps({"colors": {"ok": "red", "/abs": "red", "x": "teal", "../y": "blue"}}))
        assert foldercolors.read() == {"colors": {"ok": "red"}}

    @pytest.mark.parametrize("text", ["{nope", "[]", '{"colors": []}'])
    def test_a_broken_file_reads_as_no_colours(self, colours, text):
        colours.parent.mkdir(parents=True); colours.write_text(text)
        assert foldercolors.read() == {"colors": {}}

    def test_more_than_the_limit_is_refused(self, colours, monkeypatch):
        monkeypatch.setattr(foldercolors, "MAX", 2)
        foldercolors.write("a", "red"); foldercolors.write("b", "red")
        with pytest.raises(ValueError):
            foldercolors.write("c", "red")
        assert foldercolors.read() == {"colors": {"a": "red", "b": "red"}}


class TestSettings:
    def test_only_the_apps_own_keys_are_kept_and_values_are_text(self, lib):
        out = server.settings_write({"cv.lang": "ru", "cv.m3.grid": 1, "view": "panel", "evil": "x", "cv.langx": "y", 3: "z"})
        assert out == {"cv.lang": "ru", "cv.m3.grid": "1", "view": "panel"}
        assert server.settings_read() == out

    def test_a_null_takes_a_setting_off(self, lib):
        server.settings_write({"cv.lang": "ru", "view": "panel"})
        assert server.settings_write({"cv.lang": None}) == {"view": "panel"}

    def test_a_change_with_no_known_key_writes_nothing(self, lib):
        assert server.settings_write({"evil": 1}) == {} and not SETTINGS.exists()

    def test_a_long_value_is_cut_to_2000_characters(self, lib):
        assert len(server.settings_write({"cv.ui": "x" * 5000})["cv.ui"]) == 2000

    @pytest.mark.parametrize("text", ["{nope", "[1]"])
    def test_a_broken_settings_file_reads_as_no_settings(self, lib, text):
        SETTINGS.write_text(text)
        assert server.settings_read() == {}

    def test_the_language_is_english_unless_russian_is_chosen(self, lib):
        assert server.lang() == "en" and server.tr("Yes", "Да") == "Yes"
        server.settings_write({"cv.lang": "ru"})
        assert server.lang() == "ru" and server.tr("Yes", "Да") == "Да"
        server.settings_write({"cv.lang": "de"})
        assert server.lang() == "en"

    def test_the_librarys_own_collection_names_follow_the_language(self, lib):
        items = [{"title": "В корне доски"}, {"title": "Mine"}]
        assert [i["title"] for i in server.ui_items(items)] == ["Board root", "Mine"]
        server.settings_write({"cv.lang": "ru"})
        assert server.ui_items([{"title": "В корне доски"}])[0]["title"] == "В корне доски"


class TestNotifications:
    def test_a_notification_needs_a_title(self, lib):
        with pytest.raises(ValueError):
            server.notify({"title": "  "})

    def test_a_notification_is_stored_trimmed_and_unread(self, lib):
        n = server.notify({"title": " Batch ", "text": "t" * 3000, "ids": list(range(600)), "previews": ["a"] * 9,
                           "area": {"x": 1, "y": 2, "w": 3, "h": 4.5, "z": 9}})
        assert n["title"] == "Batch" and len(n["text"]) == 2000 and len(n["ids"]) == 500 and n["ids"][0] == "0"
        assert len(n["previews"]) == 8 and n["area"] == {"x": 1, "y": 2, "w": 3, "h": 4.5} and n["read"] is False
        assert n["who"] == "agent" and server.notifications() == [n]

    def test_an_area_with_a_missing_or_non_number_side_is_left_out(self, lib):
        assert "area" not in server.notify({"title": "t", "area": {"x": 1, "y": 2, "w": "3", "h": 4}})

    def test_reading_marks_the_named_ones_or_all_and_counts_the_rest(self, lib):
        a, b, c = (server.notify({"title": t}) for t in "abc")
        assert server.read_notifications([a["id"]]) == 2
        assert server.read_notifications() == 0
        assert all(n["read"] for n in server.notifications())

    def test_only_the_last_500_are_kept(self, lib):
        server._write_json(server.NOTIFS, [{"id": str(n), "read": True} for n in range(500)])
        server.notify({"title": "new"})
        stored = server.notifications()
        assert len(stored) == 500 and stored[-1]["title"] == "new" and stored[0]["id"] == "1"

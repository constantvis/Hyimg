"""The board's settings from the environment and its library rules (config.py), and the theme tags made from them (tags.py)."""
import json
import os
import subprocess
import sys

import pytest

import config
import tags
from unit_env import MOUNT, PROJECT, REVIEW, RULES_FILE


class TestEnvironment:
    def test_an_absolute_setting_is_returned_as_its_real_path(self, tmp_path, monkeypatch):
        (tmp_path / "real").mkdir(); os.symlink(tmp_path / "real", tmp_path / "link")
        monkeypatch.setenv("HY_UNIT_X", str(tmp_path / "link"))
        assert config.absolute_setting("HY_UNIT_X") == str((tmp_path / "real").resolve())

    @pytest.mark.parametrize("value", ["", "relative/path", "./x"])
    def test_a_missing_or_relative_setting_stops_the_server(self, monkeypatch, value):
        monkeypatch.setenv("HY_UNIT_X", value)
        with pytest.raises(SystemExit, match="HY_UNIT_X must be an absolute path"):
            config.absolute_setting("HY_UNIT_X")

    def test_a_setting_falls_back_to_its_default(self, monkeypatch):
        monkeypatch.delenv("HY_UNIT_X", raising=False)
        assert config.absolute_setting("HY_UNIT_X", "/") == "/"

    def test_the_state_folder_defaults_to_review_inside_the_library(self):
        assert config.HERE == os.path.join(config.W, "_review") and config.BOARDS == os.path.join(config.HERE, "boards")

    @pytest.mark.parametrize("change,message", [
        ({"HYIMG_PROJECT_ID": "not-a-uuid"}, "HYIMG_PROJECT_ID must be a UUID"),
        ({"HYIMG_PROJECT_ID": ""}, "HYIMG_PROJECT_ID must be a UUID"),
        ({"HYIMG_LIBRARY_ROOT": "/no/such/folder/hyimg-unit"}, "HYIMG_LIBRARY_ROOT must be an existing directory"),
        ({"HYIMG_LIBRARY_ROOT": "lib"}, "HYIMG_LIBRARY_ROOT must be an absolute path"),
    ])
    def test_a_bad_environment_stops_the_import_with_a_clear_message(self, tmp_path, change, message):
        env = {"PATH": os.environ.get("PATH", ""), "HYIMG_LIBRARY_ROOT": str(tmp_path), "HYIMG_PROJECT_ID": PROJECT,
               "HYIMG_LIBRARY_RULES": str(tmp_path / "none.json"), "PYTHONDONTWRITEBYTECODE": "1", **change}
        r = subprocess.run([sys.executable, "-c", "import config"], cwd=REVIEW, env=env, capture_output=True, text=True, timeout=20)
        assert r.returncode != 0 and message in r.stderr


class TestRules:
    def test_the_boards_rules_merge_the_shared_ones_with_its_own_whatever_the_case_of_its_id(self):
        r = config._rules()
        assert r["skip"] == ["_skipme"] and r["tags"][0][1] == "Bird"   # the board's own "tags" replace the shared ones

    @pytest.mark.parametrize("text", ["{nope", "[1, 2]", '"x"'])
    def test_a_rules_file_that_is_broken_or_not_an_object_gives_no_rules(self, tmp_path, monkeypatch, text):
        f = tmp_path / "rules.json"; f.write_text(text)
        monkeypatch.setattr(config, "RULES_FILE", str(f))
        assert config._rules() == {}

    def test_no_rules_file_gives_no_rules(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RULES_FILE", str(tmp_path / "none.json"))
        assert config._rules() == {}

    def test_a_mount_needs_an_ext_prefix_and_a_path(self):
        assert config.MOUNTS == {"ext/refs": (str(MOUNT), "Refs", "pinterest")}

    def test_a_relative_mount_path_is_inside_the_reference_folder(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "STYLE_REFS", str(tmp_path))
        monkeypatch.setattr(config, "RULES", {"mounts": [{"prefix": "ext/a", "path": "sub/dir"}]})
        assert config._mounts() == {"ext/a": (str(tmp_path / "sub/dir"), "a", "")}

    def test_without_mount_rules_each_folder_of_the_reference_folder_is_a_collection(self, tmp_path, monkeypatch):
        for d in ("one", "two.v2", ".hidden", "-dash"):
            (tmp_path / d).mkdir()
        (tmp_path / "file.txt").write_text("")
        monkeypatch.setattr(config, "STYLE_REFS", str(tmp_path))
        monkeypatch.setattr(config, "RULES", {})
        assert config._mounts() == {"ext/one": (str(tmp_path / "one"), "one", ""), "ext/two.v2": (str(tmp_path / "two.v2"), "two.v2", "")}

    def test_an_empty_mount_list_shows_no_reference_folders(self, tmp_path, monkeypatch):
        (tmp_path / "one").mkdir()
        monkeypatch.setattr(config, "STYLE_REFS", str(tmp_path))
        monkeypatch.setattr(config, "RULES", {"mounts": []})
        assert config._mounts() == {}


@pytest.fixture
def tag_rules():
    def use(rules):
        tags.configure(rules); tags.BOILER.clear()
    yield use
    tags.configure(config.RULES); tags.BOILER.clear()


class TestTags:
    def test_a_rule_with_a_broken_regex_or_a_wrong_shape_is_left_out(self, tag_rules):
        tag_rules({"tags": [["G", "Ok", "ok"], ["G", "Bad", "("], ["G", "Short"], ["G", 1, "x"], "text"]})
        assert tags.RULES == [("G", "Ok", "ok")]

    def test_the_boards_rules_were_configured_at_import_without_the_broken_one(self):
        assert [r[1] for r in tags.RULES] == ["Bird"]

    def test_a_rule_finds_its_words_in_the_prompt_name_and_folder(self, tag_rules):
        tag_rules({"tags": [["Who", "Bird", r"\bbirds?\b"]]})
        assert "Bird" in tags.tags({"prompt": "Two birds on a wire"})
        assert "Bird" in tags.tags({"name": "bird_01"})
        assert "Bird" in tags.tags({"folder": "shoot/bird"})
        assert "Bird" not in tags.tags({"prompt": "a birdcage"})

    @pytest.mark.parametrize("prompt", ["no birds anywhere", "Never a bird, please", "without bird.", "avoid birds; sky", "nothing like a bird"])
    def test_a_negated_phrase_never_gives_its_tag(self, tag_rules, prompt):
        tag_rules({"tags": [["Who", "Bird", r"\bbirds?\b"]]})
        assert "Bird" not in tags.tags({"prompt": prompt})

    def test_negation_ends_at_the_punctuation(self, tag_rules):
        tag_rules({"tags": [["Who", "Bird", r"\bbirds?\b"]]})
        assert "Bird" in tags.tags({"prompt": "no people, a bird on a rail"})

    def test_a_code_in_the_name_gives_its_tag_once(self, tag_rules):
        tag_rules({"tags": [["T", "Crash test", "crash"]], "tagCodes": {"cr": "Crash test", "bad": 3}})
        out = tags.tags({"name": "261006-cr-crash_01"})
        assert out.count("Crash test") == 1 and tags._CODES == {"cr": "Crash test"}

    @pytest.mark.parametrize("model,folder,engine", [
        ("higgsfield nano", "", "Nano Banana Pro · Higgsfield"), ("Magnific", "", "Nano Banana Pro · Magnific"),
        ("midjourney v7", "", "Midjourney"), ("", "b-mj-1", "Midjourney"), ("gpt-image", "b-mj-1", "GPT Image"),
        ("gemini-2.5-flash-image", "", "Nano Banana 2"), ("gemini-3-pro", "", "Nano Banana Pro · Gemini"),
        ("codex", "", "GPT Image"), ("blender", "", "3D и перекраска"), ("", "", "Движок не указан"), (None, "", "Движок не указан"),
    ])
    def test_the_engine_tag_comes_from_the_model_and_only_without_one_from_the_folder(self, model, folder, engine):
        assert tags.engine(model, folder) == engine

    def test_the_engine_tag_is_always_last_before_the_owners_own_tags(self, tag_rules):
        tag_rules({})
        assert tags.tags({"model": "gpt", "owner_tags": ["Mine", "GPT Image"]}) == ["GPT Image", "Mine"]

    def test_a_sentence_in_many_prompts_is_boilerplate_and_gives_no_tag(self, tag_rules):
        tag_rules({"tags": [["S", "Studio", "studio"]]})
        style = "A campaign style block shot in a white studio with soft light."
        items = [{"prompt": f"{style} Scene {n} of a street."} for n in range(8)]
        tags.learn(items)
        assert "Studio" not in tags.tags(items[0])
        tags.learn(items[:7])
        assert "Studio" in tags.tags(items[0])

    def test_tags_are_returned_as_a_fresh_list_each_time(self, tag_rules):
        tag_rules({})
        a = tags.tags({"model": "gpt"}); a.append("x")
        assert tags.tags({"model": "gpt"}) == ["GPT Image"]

    def test_the_groups_list_pinned_tags_first_then_each_other_rule_once(self, tag_rules):
        tag_rules({"tags": [["A", "x", "x"], ["A", "x", "y"], ["B", "z", "z"]], "pinnedTags": [["B", "z"], ["bad"], [["B"], "z"]]})
        assert tags.groups() == [["B", "z"], ["A", "x"]]

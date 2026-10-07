"""Unit tests for the library page's small helpers (review/v2.html): the folder tree's order, labels and colours, the arrows that step
through the folders, and the filter chips' cycle and look.

Why the page and not node: these functions live in the page's one big inline <script>, next to code that reaches for the DOM, fetch,
localStorage and the other inline scripts' globals (T, HY_CHEV, hyPaper) at its top level. Cutting a function out of the HTML and
evaluating it in node would mean a fake DOM and copies of those globals, and the cut would break whenever another agent moves a line
around it. So the page is loaded once per module in Chromium against a temporary server, and its own functions are called with crafted
inputs through page.evaluate. The page is not changed: global let variables (GF, TF, vfilter, REJ, ASKN, FCOL) are set and put back
inside the same evaluate call."""
import pytest

# the filters' state back to nothing chosen (the reset button's own line, #tfClear), the questions' count to 0, All folders chosen
RESET = "() => { TF = {}; GF = {}; vfilter = ''; setRej(''); ASKN = 0; chooseFolder(''); }"


@pytest.fixture
def lib(lib_page):
    lib_page.evaluate(RESET)
    yield lib_page
    lib_page.evaluate(RESET)
    assert not lib_page.errors, lib_page.errors


# ---------- fsortCmp and fLabel: the folders A–Z by what the tree shows ----------

NODE = "(n) => ({ path: n.path, seg: n.seg || n.path.split('/').pop(), title: n.title ?? n.path, kids: new Map((n.kids || []).map(k => [k, {}])) })"


def sort_labels(page, nodes):
    return page.evaluate(f"""ns => {{ const node = {NODE};
        return ns.map(node).sort(fsortCmp(fLabel)).map(n => fLabel(n)); }}""", nodes)


def label(page, node):
    return page.evaluate(f"n => fLabel(({NODE})(n))", node)


def test_folders_sort_a_to_z_whatever_their_case(lib):
    assert sort_labels(lib, [{"path": "beta"}, {"path": "Alpha"}, {"path": "gamma"}, {"path": "Delta"}]) == ["Alpha", "beta", "Delta", "gamma"]


def test_numbers_in_folder_names_sort_in_their_order(lib):
    assert sort_labels(lib, [{"path": "img 10"}, {"path": "img 2"}, {"path": "img 1"}]) == ["img 1", "img 2", "img 10"]


def test_folders_with_the_same_label_fall_back_to_their_names_in_number_order(lib):
    nodes = [{"path": "p/s10", "title": "Same"}, {"path": "p/s2", "title": "Same"}]
    order = lib.evaluate(f"ns => ns.map({NODE}).sort(fsortCmp(fLabel)).map(n => n.seg)", nodes)
    assert order == ["s2", "s10"]


def test_a_plain_folder_is_labelled_by_its_name_not_its_whole_path(lib):
    assert label(lib, {"path": "a/x"}) == "x"


def test_a_folder_with_its_own_title_shows_the_title_without_the_research_prefix(lib):
    assert label(lib, {"path": "r/cats", "title": "Research · Cats"}) == "Cats"
    assert label(lib, {"path": "r/dogs", "title": "Dogs at noon"}) == "Dogs at noon"


def test_the_apps_own_folders_have_their_words(lib):
    assert label(lib, {"path": "added"}) == "Added by hand"
    assert label(lib, {"path": "ext"}) == "External"
    assert label(lib, {"path": "."}) == "Board root"


def test_a_folder_with_subfolders_keeps_its_title_but_the_apps_word_wins(lib):
    assert label(lib, {"path": "p", "title": "Project P", "kids": ["x"]}) == "Project P"
    assert label(lib, {"path": "research", "title": "Research · All", "kids": ["x"]}) == "Research"


# ---------- fcolOf: a folder's colour, its own or its nearest coloured ancestor's ----------

def colour(page, colours, path):
    return page.evaluate("([c, p]) => { const keep = FCOL; FCOL = c; try { return fcolOf(p); } finally { FCOL = keep; } }", [colours, path])


def test_a_folder_with_its_own_colour_keeps_it(lib):
    assert colour(lib, {"a": "red", "a/b": "blue"}, "a/b") == "blue"


def test_a_subfolder_without_its_own_colour_takes_its_parents(lib):
    assert colour(lib, {"a": "red"}, "a/b") == "red"


def test_a_deep_subfolder_takes_the_nearest_coloured_ancestor_not_the_top(lib):
    assert colour(lib, {"a": "red", "a/b": "blue"}, "a/b/c/d") == "blue"


def test_a_folder_under_no_coloured_folder_has_no_colour(lib):
    assert colour(lib, {"a": "red"}, "b/c") == ""
    assert colour(lib, {"a": "red"}, "ab/c") == ""   # «ab» only starts like «a»: not under it
    assert colour(lib, {"a/b": "red"}, "a") == ""    # a colour does not climb up to the parent


# ---------- stepCollection: ↑ ↓ through the folders in the tree's order ----------
# the library of the temporary server: a, a/x, a/y, b, c/d (c holds no picture of its own), img 10, img 2, Zed

STEPS = "steps => { chooseFolder(''); return steps.map(d => { stepCollection(d); return document.getElementById('coll').value; }); }"


def test_arrow_down_walks_the_folders_a_to_z_with_a_parent_before_its_subfolders(lib):
    assert lib.evaluate(STEPS, [1] * 8) == ["a", "a/x", "a/y", "b", "c/d", "img 2", "img 10", "Zed"]


def test_arrow_down_at_the_last_folder_stays_there(lib):
    assert lib.evaluate(STEPS, [1] * 10)[-2:] == ["Zed", "Zed"]


def test_arrow_up_from_the_first_folder_goes_back_to_all_folders(lib):
    assert lib.evaluate(STEPS, [1, -1, -1]) == ["a", "", ""]


def test_a_parent_without_pictures_of_its_own_is_passed_over(lib):
    walked = lib.evaluate(STEPS, [1] * 8)
    assert "c" not in walked and "c/d" in walked   # tests/test_shortcuts.py expects the same of its own c, c/x, c/y


def test_the_arrows_skip_folders_the_filters_leave_empty(lib):
    walked = lib.evaluate("""() => {
        const liked = new Set(['a/x', 'img 10']), was = items.map(i => i.feedback);
        items.forEach(i => { i.feedback = liked.has(i.folder) ? { ...(i.feedback || {}), fav: true } : i.feedback; });
        GF = { fav: 'inc' };
        try { chooseFolder(''); const out = []; for (let n = 0; n < 4; n++) { stepCollection(1); out.push(document.getElementById('coll').value); } return out; }
        finally { items.forEach((i, n) => { i.feedback = was[n]; }); GF = {}; }
    }""")
    assert walked == ["a", "a/x", "img 10", "img 10"]   # «a» holds a/x's liked frame, so it is not empty


# ---------- fcycle: off → shown (+) → excluded (−) → off ----------

def cycle(page, fid, alts):
    return page.evaluate("([id, alts]) => alts.map(a => { fcycle(id, a); return fstate(fdef(id)); })", [fid, alts])


def test_a_filter_cycles_shown_then_excluded_then_off(lib):
    assert cycle(lib, "fav", [False, False, False]) == ["inc", "exc", ""]


def test_alt_click_excludes_at_once_and_alt_again_clears(lib):
    assert cycle(lib, "fav", [True, True]) == ["exc", ""]
    assert cycle(lib, "fav", [False, True]) == ["inc", "exc"]   # a shown filter, Alt: excluded


def test_a_tag_filter_cycles_the_same_way(lib):
    assert cycle(lib, "tag:Birds", [False, False, False]) == ["inc", "exc", ""]
    assert lib.evaluate("() => (fcycle('tag:Birds', false), TF)") == {"Birds": "inc"}


def test_a_rating_is_one_choice_and_a_second_click_takes_it_off(lib):
    seen = lib.evaluate("""() => {
        const at = () => [vfilter, fstate(fdef('take')), fstate(fdef('idea'))], out = [];
        fcycle('take'); out.push(at()); fcycle('idea'); out.push(at()); fcycle('idea'); out.push(at()); return out; }""")
    assert seen == [["take", "inc", ""], ["idea", "", "inc"], ["", "", ""]]


def test_rejected_frames_show_with_the_rest_then_alone_then_hide(lib):
    seen = lib.evaluate("() => [1, 2, 3].map(() => { fcycle('rej'); return [REJ, document.getElementById('showRej').checked]; })")
    assert seen == [["with", True], ["only", True], ["", False]]


def test_a_filter_on_frames_takes_the_3d_mode_off(lib):
    assert lib.evaluate("() => { vfilter = '3d'; fcycle('fav'); return [vfilter, GF.fav]; }") == ["", "inc"]


def test_all_takes_the_rating_and_the_frame_filters_off(lib):
    seen = lib.evaluate("() => { fcycle('take'); fcycle('fav'); fcycle('kind:image'); fcycle('all'); return [vfilter, GF, fstate(fdef('all'))]; }")
    assert seen == ["", {}, "inc"]


# «All» ignored the tag filters until 2026-10-06 (found by this test): it read chosen beside an active tag chip and left it on
def test_all_is_not_chosen_while_a_tag_filter_is_on_and_takes_it_off(lib):
    seen = lib.evaluate("() => { fcycle('tag:Birds'); const before = fstate(fdef('all')); fcycle('all'); return [before, TF]; }")
    assert seen == ["", {}]


# ---------- chipSpec: how a chip in the capsule reads ----------

def chip(page, fid, st, x=False, setup=""):
    return page.evaluate(f"([id, st, x]) => {{ {setup}; return chipSpec(fdef(id), st, x); }}", [fid, st, x])


def test_a_shown_chip_reads_plus_and_is_pressed(lib):
    c = chip(lib, "fav", "inc")
    assert c["html"].startswith("+ ") and c["pressed"] is True and "inc" in c["cls"].split()


def test_an_excluded_chip_reads_minus_and_is_not_pressed(lib):
    c = chip(lib, "fav", "exc")
    assert c["html"].startswith("− ") and c["pressed"] is False and "exc" in c["cls"].split()


def test_an_off_chip_has_no_sign(lib):
    c = chip(lib, "fav", "")
    assert c["html"] == "♥" and c["pressed"] is False


def test_a_rating_chip_has_no_plus_and_all_points_at_no_filter(lib):
    assert chip(lib, "take", "inc")["html"] == "Take"
    a = chip(lib, "all", "inc")
    assert a["html"] == "All" and a["f"] == "" and a["k"] == "all"


def test_an_active_chip_that_is_not_pinned_carries_a_cross_to_remove_it(lib):
    c = chip(lib, "tag:Birds", "inc", True)
    assert c["html"] == "+ Birds <i>✕</i>" and c["title"] == "Remove" and c["x"] is True


def test_the_rejected_chip_says_whether_they_show_with_the_rest_or_alone(lib):
    assert chip(lib, "rej", "inc", setup="setRej('with')")["html"] == "+ Rejected"
    assert chip(lib, "rej", "inc", setup="setRej('only')")["html"] == "Only rejected"
    assert chip(lib, "rej", "", setup="setRej('')")["html"] == "Rejected"


def test_the_question_chip_is_lit_while_questions_wait(lib):
    waiting = chip(lib, "ask", "", setup="ASKN = 3")
    assert "has" in waiting["cls"].split() and "3" in waiting["title"] and '<span class="qi">?</span>' in waiting["html"]
    done = chip(lib, "ask", "", setup="ASKN = 0")
    assert "has" not in done["cls"].split() and done["title"] == "All questions answered"


def test_a_tags_name_is_shown_as_text_not_markup(lib):
    assert chip(lib, "tag:<img src=x>", "")["html"] == "&lt;img src=x&gt;"


# ---------- other helpers beside them ----------

def test_a_folder_holds_its_subfolders_but_not_a_sibling_with_a_longer_name(lib):
    got = lib.evaluate("() => [inFolder('a', 'a'), inFolder('a/x/y', 'a'), inFolder('ab', 'a'), inFolder('ab/x', 'a'), inFolder('a', 'a/x')]")
    assert got == [True, True, False, False, False]


def test_the_cards_kind_badge(lib):
    got = lib.evaluate("""() => [kindBadge({}), kindBadge({ kind: 'doc', ext: 'PSD' }), kindBadge({ kind: 'video', duration: 65.4 }),
        kindBadge({ kind: 'video', duration: 9.6 }), kindBadge({ kind: 'video' })]""")
    assert got == ["", "PSD", "▶ 1:05", "▶ 0:10", "▶"]


def test_a_frame_is_new_until_reviewed_and_again_when_its_file_changes_later(lib):
    got = lib.evaluate("""() => {
        const at = Date.parse('2026-10-01T12:00:00') / 1000, f = { verdict: 'take', updated: '2026-10-01 12:00:00' };
        return [isNew({ mtime: at }), isNew({ mtime: at, feedback: f }), isNew({ mtime: at + 60, feedback: f }),
                isNew({ mtime: at + 61, feedback: f }), isNew({ mtime: at, empty: true })]; }""")
    assert got == [True, False, False, True, False]   # within a minute of the review it still counts as reviewed


def test_the_note_markdown_makes_bold_italic_and_lists_and_escapes_markup(lib):
    html = lib.evaluate("() => mdHtml('**b** *i* <script>\\n- one\\n- two\\n1. first')")
    assert html == ("<div><b>b</b> <i>i</i> &lt;script&gt;</div><ul><li>one</li><li>two</li></ul><ol><li>first</li></ol>")
    assert lib.evaluate("() => mdHtml('')") == ""

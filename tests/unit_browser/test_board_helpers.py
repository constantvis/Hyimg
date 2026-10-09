"""Unit tests for the board page's small helpers (review/canvas.html): the size law of the cards' marks (mkFit, mkApply, the --vbs
factor), the selection bar kept inside the board (clampBars), the slack around a playing video (vidNear), the stuck group titles'
placement (stickTitles) and the geometry and text helpers beside them.

Why the page and not node: these functions live in the page's one big inline <script>, whose top level builds the board's DOM, starts
observers and timers and reads globals of the other scripts (T, hyVideo, the plugins). Cutting a function out of the HTML and
evaluating it in node would need a fake DOM and copies of those globals, and the cut would break whenever another agent moves a line
around it. So the page is loaded once per module in Chromium against a temporary server, and its own functions are called with crafted
inputs through page.evaluate. The page is not changed: whatever a test puts in (a camera, a group, a test element in EL) it takes out
again in the same evaluate call."""
import pytest


@pytest.fixture
def cv(board_page):
    yield board_page
    assert not board_page.errors, board_page.errors


# ---------- mkFit and mkApply: one size law for the marks on a card ----------

def fit(page, sw, sh, **f):
    return page.evaluate("([sw, sh, f]) => mkFit(sw, sh, f)", [sw, sh, f])


# the owner's lab, 2026-10-06: a plate 26 px at most, 14 at least, k = the short side × .25 / 26; inset 8.5 (16 by the corner squares)
# times k, 3.5 px between marks; none under a 24 px short side; a pill folds under 104 px wide
KMIN = 14 / 26


def test_marks_are_full_size_from_a_104_px_short_side(cv):
    assert fit(cv, 104, 200, fav=True, kind=True)["k"] == 1
    assert fit(cv, 400, 300, fav=True, note=True, crop=True, dup=True, kind=True, grade=True) == {"k": 1, "off": False, "x": "", "fold": False}


def test_the_factor_is_a_quarter_of_the_short_side_over_26(cv):
    assert fit(cv, 200, 78, fav=True)["k"] == 0.75        # 78 × .25 / 26
    assert fit(cv, 80, 200, fav=True)["k"] == 0.76        # .769 floored to the hundredth
    assert abs(fit(cv, 40, 200, fav=True)["k"] - KMIN) < 1e-9   # never under 14 px while the marks fit
    assert abs(fit(cv, 30, 30, fav=True)["k"] - KMIN) < 1e-9


def test_a_card_under_24_px_on_either_side_shows_no_marks(cv):
    assert fit(cv, 23, 200, fav=True)["off"] is True
    assert fit(cv, 200, 23, fav=True)["off"] is True
    assert fit(cv, 24, 24, fav=True)["off"] is False


def test_marks_that_do_not_fit_leave_the_least_needed_first(cv):
    # grade, copy, crop, note, ♥; the kind pill stays to the last
    assert fit(cv, 30, 30, fav=True, note=True, crop=True, dup=True, kind=True, grade=True)["x"] == "grade dup crop note fav"
    assert fit(cv, 60, 45, fav=True, note=True, crop=True, dup=True, kind=True, grade=True)["x"] == "grade"
    assert fit(cv, 50, 45, fav=True, note=True, crop=True, dup=True, kind=True, grade=True)["x"] == "grade dup crop"
    assert fit(cv, 24, 24, kind=True, frame=True, fav=True)["x"] == "fav kind frame"   # a frame's # leaves with the kind, last
    assert fit(cv, 50, 60, kind=True, frame=True, dup=True)["x"] == "dup"   # the copy goes first from a frame card's bottom row


def test_both_rows_are_counted_with_the_grade(cv):
    # top: the note's 12 px dot, ♥, grade, crop; 2·8.5k + 3·26k + 3·3.5 + 12 must fit the width: k ≤ (w − 22.5) / 95
    f = fit(cv, 100, 200, fav=True, note=True, crop=True, grade=True)
    assert f["x"] == "" and abs(f["k"] - 0.81) < 1e-9, f
    # bottom: the copy mark and the folded pill, 2·8.5k + 2·26k + 3.5 ≤ the width
    assert fit(cv, 60, 200, dup=True, kind=True)["x"] == ""
    # two rows on a flat card: 2·8.5k + 2·26k + 3.5 ≤ the height
    flat = fit(cv, 300, 40, fav=True, dup=True)
    assert flat["x"] == "dup" and abs(flat["k"] - KMIN) < 1e-9, flat


def test_a_card_with_its_corner_squares_has_less_room_for_its_marks(cv):
    assert fit(cv, 62, 62, fav=True, note=True, crop=True)["x"] == ""
    assert fit(cv, 62, 62, fav=True, note=True, crop=True, hs=True)["x"] == "crop"   # 16 px × k beside the squares


APPLY = """([sw, sh, f]) => { const el = document.createElement('div'); mkApply(el, sw, sh, f);
  return { vbs: el.style.getPropertyValue('--vbs'), cls: [...el.classList].sort(), mkx: el.dataset.mkx || '' }; }"""


def test_the_law_lands_on_the_card_as_its_vbs_factor(cv):
    assert cv.evaluate(APPLY, [200, 78, {"fav": True}]) == {"vbs": "0.75", "cls": [], "mkx": ""}
    assert cv.evaluate(APPLY, [300, 200, {"fav": True}]) == {"vbs": "1", "cls": [], "mkx": ""}


def test_a_pill_folds_under_104_px_and_earlier_when_its_row_cannot_hold_it_open(cv):
    assert "vnarrow" not in cv.evaluate(APPLY, [104, 200, {"kind": True, "kindW": 58}])["cls"]
    assert "vnarrow" in cv.evaluate(APPLY, [103, 200, {"kind": True, "kindW": 58}])["cls"]
    # 104 square with the copy mark and the corner squares: 2·16 + 26 + 3.5 + 58 > 104, so it folds
    assert cv.evaluate(APPLY, [104, 104, {"kind": True, "kindW": 58, "dup": True, "hs": True}])["cls"] == ["mkh", "vnarrow"]
    assert "vnarrow" not in cv.evaluate(APPLY, [200, 200, {"kind": True, "kindW": 58, "dup": True, "hs": True}])["cls"]


def test_a_tiny_card_is_marked_off_and_dropped_marks_are_listed(cv):
    assert cv.evaluate(APPLY, [20, 20, {"fav": True}])["cls"] == ["mkoff", "vnarrow"]
    assert cv.evaluate(APPLY, [24, 24, {"fav": True, "dup": True, "kind": True}])["mkx"] == "dup fav"


def test_the_corner_squares_show_from_62_px_wide(cv):
    assert cv.evaluate("() => [handlesOn(61, 100), handlesOn(62, 100), handlesOn(62, 29), HANDLE_PX]") == [False, True, False, 30]


def bezier(p, x1=.32, y1=.72, x2=0., y2=1.):   # cubic-bezier(.32,.72,0,1), solved for x by bisection
    bx = lambda t: 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3
    by = lambda t: 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3
    lo, hi = 0., 1.
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if bx(mid) < p else (lo, mid)
    return by((lo + hi) / 2)


def test_the_far_views_mark_curve_is_the_apps_curve(cv):
    ps = [-1, 0, .1, .25, .5, .75, .9, 1, 2]
    got = cv.evaluate("ps => ps.map(mkEase)", ps)
    assert got[0] == 0 and got[1] == 0 and got[-2] == 1 and got[-1] == 1
    for p, v in zip(ps[2:-2], got[2:-2]):
        assert abs(v - bezier(p)) < 1e-4, (p, v, bezier(p))
    assert got == sorted(got)


# ---------- clampBars: the selection bar stays inside the board's visible part ----------

CLAMP = """([z, inset, centre, width]) => {
  const keep = { ...cam }, keepI = INSET; INSET = inset; cam.z = z; renderCam();
  const st = stage.getBoundingClientRect(), t = document.createElement('div');
  t.className = 'tidy'; Object.assign(t.style, { width: width + 'px', height: '30px', left: cam.x + (centre - st.left) / z + 'px', top: cam.y + 400 / z + 'px' });
  document.getElementById('handles').appendChild(t);
  const before = t.getBoundingClientRect(); clampBars(); const after = t.getBoundingClientRect(), tr = t.style.translate;
  t.remove(); INSET = keepI; Object.assign(cam, keep); renderCam();
  return { before: [before.left, before.right], after: [after.left, after.right], minL: st.left + inset + 8, maxR: st.right - 8, tr };
}"""
ZOOMS = [0.5, 1, 2]


@pytest.mark.parametrize("z", ZOOMS)
def test_a_bar_under_the_library_slides_right_to_8_px_past_its_edge(cv, z):
    r = cv.evaluate(CLAMP, [z, 300, 320, 240])   # centred 20 px past the library's edge: it would start 100 px under it
    assert r["before"][0] < r["minL"]
    assert abs(r["after"][0] - r["minL"]) < 0.6, r
    assert abs((r["after"][1] - r["after"][0]) - 240) < 0.6, r   # it slides, it does not shrink


@pytest.mark.parametrize("z", ZOOMS)
def test_a_bar_past_the_right_edge_slides_left_to_8_px_inside(cv, z):
    r = cv.evaluate(CLAMP, [z, 0, 1190, 240])
    assert abs(r["after"][1] - r["maxR"]) < 0.6, r


@pytest.mark.parametrize("z", ZOOMS)
def test_a_bar_wider_than_the_board_starts_8_px_after_the_library(cv, z):
    r = cv.evaluate(CLAMP, [z, 300, 700, 1000])
    assert abs(r["after"][0] - r["minL"]) < 0.6, r


def test_a_bar_with_room_on_both_sides_stays_centred(cv):
    r = cv.evaluate(CLAMP, [1, 300, 700, 240])
    assert r["tr"] == "" and r["after"] == r["before"]


# ---------- vidNear: the slack around a playing video card ----------

NEAR = """([w, h, pts, hidden]) => {
  const el = document.createElement('div'); Object.assign(el.style, { position: 'fixed', left: '100px', top: '100px', width: w + 'px', height: h + 'px' });
  el.hidden = !!hidden; document.body.appendChild(el); EL.set('__unit_vid', el);
  try { return pts.map(([x, y]) => vidNear('__unit_vid', { clientX: x, clientY: y })); } finally { EL.delete('__unit_vid'); el.remove(); }
}"""


def near(page, w, h, pts, hidden=False):
    return page.evaluate(NEAR, [w, h, pts, hidden])


def test_a_small_video_card_keeps_8_px_of_slack(cv):
    # 100 × 100: 4 % is 4 px, the slack is at least 8
    assert near(cv, 100, 100, [[93, 150], [91, 150], [207, 150], [209, 150], [150, 93], [150, 207], [93, 93]]) == [True, False, True, False, True, True, True]


def test_the_slack_is_4_percent_of_the_shorter_side(cv):
    # 1000 × 500: 20 px
    assert near(cv, 1000, 500, [[81, 300], [79, 300], [500, 619], [500, 621]]) == [True, False, True, False]


def test_the_slack_stops_at_24_px(cv):
    # 1000 × 1000: 4 % would be 40
    assert near(cv, 1000, 1000, [[77, 500], [75, 500], [500, 1123], [500, 1125]]) == [True, False, True, False]


def test_a_hidden_or_unknown_card_has_no_slack(cv):
    assert near(cv, 200, 200, [[150, 150]], hidden=True) == [False]
    assert cv.evaluate("() => vidNear('no such card', { clientX: 0, clientY: 0 })") is False


# ---------- stickTitles: a long group's title sticks as a plate after the breadcrumb ----------

STICK = """(o) => {
  const keep = { ...cam }; cam.x = 0; cam.y = 0; cam.z = 1;
  if (o.hide) document.documentElement.classList.add('hy-hideui');
  board.groups.__unit_g = { x: o.x, y: o.y, w: o.w, h: o.h, title: o.title || 'Unit group', members: [] };
  try {
    render();
    const b = document.querySelector('#gsticky .gst[data-gid="__unit_g"]'), st = stage.getBoundingClientRect(), c = document.getElementById('crumb').getBoundingClientRect();
    return { plate: b && !b._out ? { x: b._x, y: b._y, w: b.offsetWidth, text: b.textContent } : null,
             crumbRight: c.right - st.left, crumbMid: c.top - st.top + c.height / 2, inset: INSET };
  } finally { delete board.groups.__unit_g; document.documentElement.classList.remove('hy-hideui'); Object.assign(cam, keep); render(); }
}"""
PH = 26   # the plate's height in stickTitles


def stick(page, **o):
    return page.evaluate(STICK, o)


def test_a_group_whose_title_went_above_the_screen_gets_a_plate_right_after_the_breadcrumb(cv):
    r = stick(cv, x=-200, y=-100, w=900, h=700, title="Long group\nsecond line")
    p = r["plate"]
    assert p is not None and p["text"] == "Long group"   # its first line only
    assert p["x"] == round(r["crumbRight"] + 8)
    assert abs(p["y"] + PH / 2 - r["crumbMid"]) <= 1   # on the breadcrumb's middle line


def test_a_plate_starts_where_the_titles_text_was_when_the_group_starts_right_of_the_breadcrumb(cv):
    r = stick(cv, x=500, y=-100, w=500, h=700)
    assert r["plate"]["x"] == 490   # 10 px before the group's edge, as the title's text sits


def test_a_narrow_groups_plate_ends_6_px_inside_its_right_edge(cv):
    gl = 400
    r = stick(cv, x=gl, y=-100, w=40, h=700, title="A long title for a narrow group")
    p = r["plate"]
    assert p is not None and p["w"] == 60   # the plate's smallest width
    assert p["x"] + p["w"] == gl + 40 - 6


def test_no_plate_while_the_title_is_on_screen(cv):
    assert stick(cv, x=400, y=200, w=500, h=400)["plate"] is None


def test_no_plate_when_the_group_ends_just_under_the_line(cv):
    r = stick(cv, x=400, y=-400, w=500, h=400 + 40)   # its bottom 40 px down the screen: no room under the line for the plate
    assert r["plate"] is None


def test_with_the_interface_hidden_the_plate_rides_the_top_edge(cv):
    r = stick(cv, x=-200, y=-100, w=900, h=700, hide=True)
    assert r["plate"]["y"] == 12 and r["plate"]["x"] == r["inset"] + 12


# ---------- other helpers beside them ----------

def test_a_big_group_pauses_only_while_it_covers_the_screen_up_to_150_px_from_each_side(cv):
    got = cv.evaluate("""() => {
      const keep = { ...cam }, r = stageBox(); cam.x = 0; cam.y = 0;
      const out = [1, 2].flatMap(z => { cam.z = z; const W = r.width / z, H = r.height / z, m = 150 / z;
        return [bigOnScreen({ x: 0, y: 0, w: W, h: H }), bigOnScreen({ x: m - 1 / z, y: 0, w: W - m, h: H }), bigOnScreen({ x: m + 2 / z, y: 0, w: W, h: H }), bigOnScreen(null)]; });
      Object.assign(cam, keep); return out; }""")
    assert got == [True, True, False, False] * 2


def test_live_merge_keeps_edits_made_here_and_takes_the_rest_from_the_other_side(cv):
    out = cv.evaluate("""() => mergeMap(
      { same: 1, mine: 1, theirs: 1, delMine: 1, delTheirs: 1, both: 1, mineVsDel: 1 },
      { same: 1, mine: 2, theirs: 1, delTheirs: 1, both: 2, mineVsDel: 2, addMine: 1 },
      { same: 1, mine: 1, theirs: 3, delMine: 1, both: 3, addTheirs: 1 })""")
    assert out == {"same": 1, "mine": 2, "theirs": 3, "both": 2, "mineVsDel": 2, "addMine": 1, "addTheirs": 1}


def test_an_arrow_leaves_a_box_on_its_edge_towards_the_target(cv):
    got = cv.evaluate("""() => { const r = { x: 0, y: 0, w: 100, h: 50 };
      return [edgePt(r, { x: 500, y: 25 }), edgePt(r, { x: 50, y: -300 }), edgePt(r, { x: 90, y: 75 }), edgePt(r, { x: 150, y: 75 }), edgePt(r, { x: 50, y: 25 })]
        .map(p => [p.x, p.y]); }""")
    want = [(100, 25), (50, 0), (70, 50), (100, 50), (50, 25)]   # right side, top, bottom (steeper than the diagonal), the corner, the centre
    assert [pytest.approx(w) for w in want] == got


def test_a_cards_height_follows_its_width_aspect_and_crop(cv):
    got = cv.evaluate("""() => [itemH({ w: 300, ar: 1.5 }), itemH({ w: 300, ar: 1.5, crop: [0, 0, .5, 1] }), itemH({ w: 300, ar: 1.5, crop: [0, 0, 1, .5] }),
      itemH({ type: 'note', h: 80, fs: 20 }), itemH({ type: 'text', fs: 20 })]""")
    assert got == pytest.approx([200, 400, 100, 80, 24])


def test_a_notes_size_is_its_own_or_the_nearest_by_its_text_to_width_ratio(cv):
    assert cv.evaluate("() => [noteSize({ size: 4, fs: 1, w: 999 }), noteSize({ fs: 10, w: 320 }), noteSize({ fs: 10, w: 90 }), noteSize({ size: 9, fs: 10, w: 240 })]") == [4, 0, 4, 1]


def test_a_page_named_only_with_dashes_or_underscores_is_a_divider(cv):   # 3 of them at least, mixed, spaces aside (owner 2026-10-09)
    got = cv.evaluate("() => ['---', '___', '--------', '-_-_-', '- - -', '— — —', '--', '- -', '-', 'a---', '', null, '  ---  '].map(isDivider)")
    assert got == [True, True, True, True, True, True, False, False, False, False, False, False, True]


def test_file_sizes_read_in_kb_under_a_megabyte_and_mb_from_it(cv):
    assert cv.evaluate("() => [fmtSize(2048), fmtSize(1048576 * 2.5)]") == ["2 KB", "2.5 MB"]


def test_the_trim_clock_reads_minutes_and_tenths(cv):
    assert cv.evaluate("() => [trimClock(0), trimClock(5.24), trimClock(65.24), trimClock(600)]") == ["0:00.0", "0:05.2", "1:05.2", "10:00.0"]


# 59.96 s read «0:60.0» until the clock rounded to tenths before splitting off the minutes (found by this test 2026-10-06)
def test_the_trim_clock_carries_a_rounded_up_minute(cv):
    assert cv.evaluate("() => [trimClock(59.96), trimClock(119.97)]") == ["1:00.0", "2:00.0"]

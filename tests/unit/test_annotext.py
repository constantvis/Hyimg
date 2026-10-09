"""Drawings and comment areas in words (review/annotext.py, owner 2026-10-07: «чтобы они всё понимали, не смотря на картинки»): the kind,
colour and author, the object, where in words, in shares and in the picture's own pixels (its crop applied) or an HTML page's css px; a
pen loop, a line, an arrow between two objects, a text label, a drawing on the empty board; a drawing and a comment linked both ways."""
import time

import unit_env  # noqa: F401
import annotext

ME = "11111111-1111-4111-8111-111111111111"
PEOPLE = {ME: {"name": "Ann Lee", "color": "green"}}
B = {"items": {"i1": {"path": "a/sky.png", "x": 0, "y": 0, "w": 400, "ar": 2000 / 1400, "crop": None},
               "i2": {"path": "a/sea.png", "x": 500, "y": 0, "w": 400, "ar": 2000 / 1400, "crop": [.5, 0, 1, 1]},
               "h1": {"type": "html", "src": "site/index.html", "vw": 1280, "x": 0, "y": 400, "w": 640, "h": 400}}}
SIZE = lambda rel: (2000, 1400)
NOW = time.strftime("%Y-%m-%dT%H:%M:%S")


def ann(kind, pts, obj="i1", **k):
    return {"id": "a" + kind, "kind": kind, "color": "red", "w": .01, "pts": pts, "by": {"person": ME, "via": k.pop("via", "app")}, "created": NOW,
            "anchor": {"obj": obj, "kind": "picture", "file": B["items"].get(obj, {}).get("path", "")} if obj else None, **k}


def test_an_ellipse_in_words_and_pixels():
    d = annotext.describe(ann("ellipse", [[.62, .10], [.85, .40]]), B, PEOPLE, SIZE)
    assert d["text"] == "красный овал вокруг области вверху справа: x 62–85 %, y 10–40 % = px 1240–1700 × 140–560 из 2000×1400, на кадре a/sky.png, Ann Lee"
    assert d["region"]["px"] == [1240, 1700, 140, 560] and d["region"]["words"] == "вверху справа"


def test_a_rectangle_on_a_cropped_picture_counts_the_crop_and_an_agent_signs():
    d = annotext.describe(ann("rect", [[0, .5], [.5, 1]], obj="i2", via="claude"), B, PEOPLE, SIZE)
    assert "внизу слева" in d["text"] and "px 1000–1500 × 700–1400 из 2000×1400" in d["text"] and d["text"].endswith("Claude · Ann Lee")


def test_pen_loop_and_lines():
    import math
    loop = [[.5 + .2 * math.cos(t / 10 * math.pi), .5 + .2 * math.sin(t / 10 * math.pi)] for t in range(21)]
    d = annotext.describe(ann("pen", loop), B, PEOPLE, SIZE)
    assert d["shape"] == "loop" and d["text"].startswith("красная обводка: выделяет область в центре")
    d = annotext.describe(ann("pen", [[.1, .8], [.3, .81], [.5, .79], [.7, .8]]), B, PEOPLE, SIZE)
    assert d["shape"] == "hline" and "горизонтальная черта (подчеркивание или зачеркивание)" in d["text"] and "внизу" in d["text"]
    d = annotext.describe(ann("pen", [[.5, .1], [.51, .5], [.49, .9]]), B, PEOPLE, SIZE)
    assert d["shape"] == "vline"


def test_an_arrow_from_one_object_to_another_and_a_label_and_a_free_shape():
    # from i1 (u .9, v .5) to i2: the head in board units, i2 at x 500..900 and twice as tall (its crop)
    d = annotext.describe(ann("arrow", [[.9, .5], [1.75, .5]]), B, PEOPLE, SIZE)
    assert d["to"] == "i2" and d["text"].startswith("красная стрелка от кадра a/sky.png (x 90 %, y 50 % (1800, 700 px)) к кадру a/sea.png (x 50 %, y 25 % (1500, 350 px))")
    d = annotext.describe(ann("text", [[.2, .3]], text="too dark"), B, PEOPLE, SIZE)
    assert d["text"].startswith("красная надпись «too dark» вверху слева")
    d = annotext.describe(ann("rect", [[1000, 1000], [1200, 1100]], obj=None), B, PEOPLE, SIZE)
    assert "доска x 1000–1200, y 1000–1100" in d["text"] and "на пустом месте доски" in d["text"]


def test_an_html_card_in_css_px_and_a_gone_object():
    d = annotext.describe(ann("rect", [[.5, 0], [1, .5]], obj="h1"), B, PEOPLE, SIZE)
    assert "css px страницы 640–1280 × 0–400 из 1280×800" in d["text"] and "на HTML-странице site/index.html" in d["text"]
    gone = ann("rect", [[0, 0], [1, 1]], obj="zz")
    assert "которого больше нет" in annotext.describe(gone, B, PEOPLE, SIZE)["text"]


def test_a_drawing_and_a_comment_on_it_are_linked_both_ways():
    t = {"id": "c1", "anchor": {"obj": "i1"}, "at": [.86, .1], "area": [.62, .1, .23, .3], "created": NOW, "messages": [{"text": "небо темнее"}]}
    far = {"id": "c2", "anchor": {"obj": "i1"}, "at": [.1, .9], "created": "2020-01-01T00:00:00", "messages": [{"text": "другое"}]}
    d = annotext.describe(ann("ellipse", [[.62, .10], [.85, .40]]), B, PEOPLE, SIZE, [t, far])
    assert d["about"] == ["c1"] and d["text"].endswith("→ комментарий c1: «небо темнее»")
    dt = annotext.describe_thread(t, B, PEOPLE, SIZE, [{"id": "aellipse", "about": d["about"]}])
    assert dt["marks"] == ["aellipse"] and dt["text"].startswith("область вверху справа: x 62–85 %, y 10–40 % = px 1240–1700 × 140–560")
    assert dt["text"].endswith("; рисунки: aellipse")
    pin = annotext.describe_thread(far, B, PEOPLE, SIZE, [])
    assert pin["text"] == "булавка x 10 %, y 90 % (200, 1260 px) на кадре a/sky.png"


def test_the_library_preview_marks_read_the_same_way():
    m = annotext.library_marks("a/sea.png", [{"kind": "box", "pts": [[.1, .1], [.3, .2]], "text": "пятно"}], B["items"]["i2"], "i2", SIZE)
    assert m[0]["text"] == "область 1 из просмотра библиотеки, вверху слева: x 10–30 %, y 10–20 % = px 200–600 × 140–280 из 2000×1400: «пятно»"


def test_an_element_comment_names_the_element_and_where_its_pin_stands():
    """a comment from Dev Studio's tree (owner 2026-10-08): the element, and its pin's place when not on the element's own box"""
    import comments
    t = {"id": "c1", "anchor": {"obj": "h1", "kind": "html", "file": "site/index.html"}, "at": [.25, .1], "by": {"person": ME},
         "element": comments.clean_element({"key": "html>body:1>main:1>div:1", "css": "#wrap", "tag": "div", "text": "One Two", "page": [320, 80], "pin": "kids"})}
    assert t["element"]["pin"] == "kids" and t["element"]["page"] == [320, 80]
    assert "элемент #wrap (булавка на его содержимом, своей рамки нет)" in annotext.describe_thread(t, B, PEOPLE, SIZE)["text"]
    t["element"] = comments.clean_element({**t["element"], "pin": "somewhere"})   # a word it doesn't know is dropped
    assert "pin" not in t["element"] and annotext.describe_thread(t, B, PEOPLE, SIZE)["text"].endswith("элемент #wrap")


def test_an_element_further_down_the_page_says_where_it_is():
    """a comment on an element below the page's first screen (Dev Studio's tree scrolls to it, owner 2026-10-08): the card's picture holds
    its pin at the bottom edge (at y 0.98), the words give the element's own point in the page and say the pin waits at that edge"""
    import comments
    el = comments.clean_element({"key": "html>body:1>section:4", "css": "#s", "tag": "section", "text": "Tall section", "page": [36, 1917]})
    t = {"id": "c2", "anchor": {"obj": "h1", "kind": "html", "file": "site/index.html"}, "at": [.028, .98], "by": {"person": ME}, "element": el}
    d = annotext.describe_thread(t, B, PEOPLE, SIZE)["text"]
    assert "булавка x 3 %, y 98 % (36, 1917 css px страницы, ниже первого экрана: на картинке карточки она у нижнего края)" in d, d
    t["element"] = {**el, "page": [1400, 1917]}
    assert "ниже и правее первого экрана: на картинке карточки она у края)" in annotext.describe_thread(t, B, PEOPLE, SIZE)["text"]
    t["element"] = {**el, "page": [36, 432]}; t["at"] = [.028, .54]   # on the first screen: its point, nothing more
    assert "булавка x 3 %, y 54 % (36, 432 css px страницы) на HTML-странице" in annotext.describe_thread(t, B, PEOPLE, SIZE)["text"]

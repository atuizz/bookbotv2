from types import SimpleNamespace

from app.handlers.book_detail import build_booklist_keyboard, build_user_book_keyboard


def _flatten_callback_data(keyboard):
    return [btn.callback_data for row in keyboard.inline_keyboard for btn in row]


def test_build_user_book_keyboard_structure():
    kb = build_user_book_keyboard(book_id=1, is_fav=False)
    assert len(kb.inline_keyboard) == 3
    row = kb.inline_keyboard[0]
    assert len(row) == 3
    assert row[0].callback_data == "book:fav:1"
    assert row[1].callback_data == "book:booklist:1"
    assert row[2].callback_data == "book:review:1"
    assert kb.inline_keyboard[1][0].callback_data == "book:tagadd:1"
    assert kb.inline_keyboard[1][1].callback_data == "book:similar:1:1"
    assert kb.inline_keyboard[1][2].callback_data == "book:more:1"
    assert kb.inline_keyboard[2][0].callback_data == "book:download:1"


def test_build_user_book_keyboard_favorited_text_changes():
    kb_unfav = build_user_book_keyboard(book_id=1, is_fav=False)
    kb_fav = build_user_book_keyboard(book_id=1, is_fav=True)
    assert kb_unfav.inline_keyboard[0][0].text != kb_fav.inline_keyboard[0][0].text


def test_build_booklist_keyboard_selected():
    booklists = [SimpleNamespace(id=7, name="默认", is_default=True, items=[1, 2])]
    kb = build_booklist_keyboard(book_id=9, booklists=booklists, selected_ids={7})
    assert len(kb.inline_keyboard) == 3
    assert kb.inline_keyboard[0][0].callback_data == "book:booklist_toggle:9:7"
    assert kb.inline_keyboard[1][0].callback_data == "book:booklist_new:9"
    assert kb.inline_keyboard[1][1].callback_data == "book:booklist_overview:9"
    assert kb.inline_keyboard[2][0].callback_data == "book:restore:9"


def test_build_booklist_keyboard_unselected():
    booklists = [SimpleNamespace(id=5, name="稍后阅读", is_default=False, items=[])]
    kb = build_booklist_keyboard(book_id=9, booklists=booklists, selected_ids=set())
    all_cb = _flatten_callback_data(kb)
    assert "book:booklist_new:9" in all_cb
    assert "book:booklist_overview:9" in all_cb
    assert "book:booklist_toggle:9:5" in all_cb

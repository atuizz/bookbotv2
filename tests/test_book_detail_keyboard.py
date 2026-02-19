from app.handlers.book_detail import build_booklist_keyboard, build_user_book_keyboard


def test_build_user_book_keyboard_not_favorited():
    kb = build_user_book_keyboard(book_id=1, is_fav=False)
    assert len(kb.inline_keyboard) == 2
    assert [b.text for b in kb.inline_keyboard[0]] == ["🤍收藏", "+书单", "💬评价"]
    assert [b.text for b in kb.inline_keyboard[1]] == ["+加标签", "💡我相似", "...更多"]


def test_build_user_book_keyboard_favorited():
    kb = build_user_book_keyboard(book_id=1, is_fav=True)
    assert kb.inline_keyboard[0][0].text == "💚收藏"


def test_build_booklist_keyboard_selected():
    kb = build_booklist_keyboard(book_id=9, count=2, selected=True)
    assert len(kb.inline_keyboard) == 2
    assert [b.text for b in kb.inline_keyboard[0]] == ["++新建", "<返回"]
    assert kb.inline_keyboard[1][0].text == "✅[2本] 我喜欢的书籍"


def test_build_booklist_keyboard_unselected():
    kb = build_booklist_keyboard(book_id=9, count=0, selected=False)
    assert kb.inline_keyboard[1][0].text == "[0本] 我喜欢的书籍"


from app.handlers.book_detail import (
    build_admin_tag_queue_keyboard,
    build_more_keyboard,
    build_review_list_keyboard,
    build_review_rating_keyboard,
)
from app.services.book_ops import generate_booklist_share_token


def _all_callbacks(keyboard):
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def test_generate_booklist_share_token_shape():
    token = generate_booklist_share_token()
    assert 8 <= len(token) <= 20
    assert token.isalnum()


def test_build_more_keyboard_contains_expected_actions():
    keyboard = build_more_keyboard(book_id=12, is_admin=True)
    callbacks = _all_callbacks(keyboard)
    assert "book:booklist_overview:12" in callbacks
    assert "book:review_list:12:1" in callbacks
    assert "book:share:12" in callbacks
    assert "book:admin_edit:12" in callbacks
    assert "book:admin_tag_queue:12" in callbacks


def test_build_review_keyboards_include_navigation_and_rating():
    rating_keyboard = build_review_rating_keyboard(book_id=4, current_rating=3)
    assert rating_keyboard.inline_keyboard[0][2].callback_data == "book:review_rate:4:3"

    list_keyboard = build_review_list_keyboard(book_id=4, page=2, total=12, per_page=5)
    callbacks = _all_callbacks(list_keyboard)
    assert "book:review_list:4:1" in callbacks
    assert "book:review_list:4:3" in callbacks
    assert "book:review:4" in callbacks


def test_build_admin_tag_queue_keyboard_supports_pending_and_remove():
    pending = [type("TagApp", (), {"tag_name": "仙侠", "id": 3})()]
    keyboard = build_admin_tag_queue_keyboard(
        book_id=8,
        items=pending,
        current_tags=[(6, "科幻")],
    )
    callbacks = _all_callbacks(keyboard)
    assert "book:admin_tag_remove:8:6" in callbacks
    assert "book:admin_tag_approve:8:3" in callbacks
    assert "book:admin_tag_reject:8:3" in callbacks

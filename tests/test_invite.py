from app.handlers.invite import build_invite_main, generate_invite_link, parse_invite_code


class DummyUser:
    def __init__(self, user_id: int, username: str | None, full_name: str | None):
        self.id = user_id
        self.username = username
        self.full_name = full_name


def test_build_invite_main_escapes_and_encodes(monkeypatch):
    class DummySettings:
        bot_username = "@bookbot"

    monkeypatch.setattr("app.handlers.invite.get_settings", lambda: DummySettings())

    user = DummyUser(123, "<b>u</b>", "<i>n</i>")
    text, keyboard = build_invite_main(user)
    assert "<b>u</b>" not in text
    assert "&lt;b&gt;u&lt;/b&gt;" in text
    assert "<i>n</i>" not in text
    assert "&lt;i&gt;n&lt;/i&gt;" in text
    assert keyboard.inline_keyboard[0][0].url is not None
    assert "url=" in keyboard.inline_keyboard[0][0].url
    assert "%3A%2F%2F" in keyboard.inline_keyboard[0][0].url


def test_parse_invite_code_valid(monkeypatch):
    class DummySettings:
        bot_username = "@bookbot"

    monkeypatch.setattr("app.handlers.invite.get_settings", lambda: DummySettings())
    link = generate_invite_link(123456)
    code = link.split("start=", 1)[1]
    assert parse_invite_code(code) == 123456


def test_parse_invite_code_invalid(monkeypatch):
    class DummySettings:
        bot_username = "@bookbot"

    monkeypatch.setattr("app.handlers.invite.get_settings", lambda: DummySettings())
    assert parse_invite_code("INV123456ABCDEFGH") is None

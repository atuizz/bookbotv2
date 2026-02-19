# -*- coding: utf-8 -*-

from app.core.deeplink import encode_payload, decode_payload
from app.handlers.book_detail import build_book_caption
from app.core.models import Book, File, FileFormat, BookStatus


def test_encode_decode_payload_roundtrip():
    value = "烽火戏诸侯"
    token = encode_payload(value)
    assert token
    assert decode_payload(token) == value


def test_build_book_caption_has_clickable_title_and_author():
    book = Book(
        title="梦莉小说合集",
        author="mirr",
        file_hash="a" * 64,
        uploader_id=1,
        status=BookStatus.ACTIVE,
    )
    book.id = 123
    book.file = File(
        sha256_hash="a" * 64,
        size=1024,
        extension="txt",
        format=FileFormat.TXT,
        word_count=100,
    )
    book.book_tags = []

    text = build_book_caption(book, bot_username="novel_bot")
    assert "https://t.me/novel_bot?start=book_123" in text
    assert "start=au_" in text


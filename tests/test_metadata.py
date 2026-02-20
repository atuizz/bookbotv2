# -*- coding: utf-8 -*-

from app.services.metadata import extract_upload_metadata, parse_title_author_from_filename


def test_parse_title_author_from_filename_dash():
    title, author = parse_title_author_from_filename("剑来 - 烽火戏诸侯.txt")
    assert title == "剑来"
    assert author == "烽火戏诸侯"


def test_extract_upload_metadata_txt_front_matter():
    raw = (
        "书名: 梦莉小说合集\n"
        "作者: mirr\n"
        "标签: 校园, 纯爱 #甜文\n"
        "简介: 这是简介\n"
        "\n"
        "正文开始\n"
        "第一章 ...\n"
    ).encode("utf-8")
    meta = extract_upload_metadata(file_name="梦莉小说合集.txt", file_ext="txt", file_bytes=raw)
    assert meta.title == "梦莉小说合集"
    assert meta.author == "mirr"
    assert "校园" in meta.tags
    assert "纯爱" in meta.tags
    assert "甜文" in meta.tags
    assert meta.word_count > 0
    assert meta.description == "这是简介"


def test_extract_upload_metadata_supports_character_and_keywords_fields():
    raw = (
        "书名: 我不是戏神\n"
        "作者: 二六直蚁\n"
        "主角: 陈伶\n"
        "关键词: 诡异, 推理\n"
        "\n"
        "正文...\n"
    ).encode("utf-8")
    meta = extract_upload_metadata(file_name="我不是戏神.txt", file_ext="txt", file_bytes=raw)
    assert meta.title == "我不是戏神"
    assert meta.author == "二六直蚁"
    assert "陈伶" in meta.tags
    assert "诡异" in meta.tags
    assert "推理" in meta.tags


def test_extract_upload_metadata_supports_bracketed_and_bulleted_fields():
    raw = (
        "【书名】：武道无穷，吾身无拘\n"
        "- 【作者】：猴子\n"
        "• 标签：玄幻、热血\n"
        "正文...\n"
    ).encode("utf-8")
    meta = extract_upload_metadata(file_name="武道无穷.txt", file_ext="txt", file_bytes=raw)
    assert meta.title == "武道无穷，吾身无拘"
    assert meta.author == "猴子"
    assert "玄幻" in meta.tags
    assert "热血" in meta.tags

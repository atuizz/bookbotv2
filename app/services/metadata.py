import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UploadMetadata:
    title: str
    author: str
    tags: list[str]
    word_count: int
    description: Optional[str]


_RE_SEP = re.compile(r"[|/、,，;；\t ]+")
_RE_TITLE_AUTHOR_1 = re.compile(r"^(?P<title>.+?)\s*[-_—–]\s*(?P<author>.+?)$")
_RE_TITLE_AUTHOR_2 = re.compile(r"^《(?P<title>.+?)》\s*(?P<author>.+?)$")
_RE_FIELD_KEYS = (
    "书名|作者|标签|分类|主角|人物|角色|关键字|关键词|题材|类型|简介|"
    "title|author|tag|tags|category|description"
)
_RE_FIELD = re.compile(
    rf"^\s*(?:[-*•]+)?\s*(?:【|\[)?(?P<k>{_RE_FIELD_KEYS})(?:】|\])?\s*[:：]\s*(?P<v>.*?)\s*$",
    flags=re.IGNORECASE,
)


def _clean_value(v: str) -> str:
    v = (v or "").strip()
    v = v.replace("\u200b", "").replace("\ufeff", "").strip()
    return v


def _clean_title(v: str) -> str:
    v = _clean_value(v)
    v = re.sub(r"[\[\(（【].*?[\]\)）】]\s*$", "", v).strip()
    return v or "未知"


def _clean_author(v: str) -> str:
    v = _clean_value(v)
    if not v:
        return "Unknown"
    v = re.sub(r"^作者[:：]\s*", "", v).strip()
    return v or "Unknown"


def _normalize_tag(v: str) -> str:
    v = _clean_value(v).lstrip("#").strip()
    v = re.sub(r"\s+", "", v)
    return v


def _split_tags(raw: str) -> list[str]:
    raw = _clean_value(raw)
    if not raw:
        return []
    parts = [p for p in _RE_SEP.split(raw) if p]
    tags = []
    for p in parts:
        t = _normalize_tag(p)
        if not t:
            continue
        tags.append(t)
    deduped = list(dict.fromkeys(tags))
    return deduped[:30]


def parse_title_author_from_filename(file_name: str) -> tuple[str, str]:
    base = _clean_value(file_name)
    if "." in base:
        base = base.rsplit(".", 1)[0]
    base = _clean_value(base)

    m = _RE_TITLE_AUTHOR_2.match(base)
    if m:
        return _clean_title(m.group("title")), _clean_author(m.group("author"))
    m = _RE_TITLE_AUTHOR_1.match(base)
    if m:
        return _clean_title(m.group("title")), _clean_author(m.group("author"))
    return _clean_title(base), "Unknown"


def _count_word_like(text: str) -> int:
    n = 0
    for ch in text:
        if ch.isspace():
            continue
        if ch.isalnum() or ("\u4e00" <= ch <= "\u9fff"):
            n += 1
    return n


def _extract_txt_front_matter(text: str) -> dict:
    lines = [ln.strip() for ln in (text or "").splitlines()[:1200] if ln.strip()]
    lines = lines[:400]
    out: dict = {"tags": []}
    for ln in lines:
        m = _RE_FIELD.match(ln)
        if not m:
            continue
        k = (m.group("k") or "").strip().lower()
        v = _clean_value(m.group("v"))
        if k in {"书名", "title"} and "title" not in out:
            out["title"] = _clean_title(v)
        elif k in {"作者", "author"} and "author" not in out:
            out["author"] = _clean_author(v)
        elif k in {"标签", "分类", "主角", "人物", "角色", "关键字", "关键词", "题材", "类型", "tag", "tags", "category"}:
            out["tags"].extend(_split_tags(v))
        elif k in {"简介", "description"} and "description" not in out:
            out["description"] = v[:800]
    out["tags"] = list(dict.fromkeys([t for t in out.get("tags", []) if t]))[:30]
    return out


def extract_upload_metadata(*, file_name: str, file_ext: str, file_bytes: bytes) -> UploadMetadata:
    title, author = parse_title_author_from_filename(file_name)
    tags: list[str] = []
    description: Optional[str] = None
    word_count = 0

    if file_ext.lower() == "txt" and file_bytes:
        text = None
        for enc in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk"):
            try:
                text = file_bytes.decode(enc)
                break
            except Exception:
                continue
        if text is None:
            text = file_bytes.decode("latin1", errors="replace")
        fm = _extract_txt_front_matter(text)
        title = fm.get("title") or title
        author = fm.get("author") or author
        tags = fm.get("tags") or tags
        description = fm.get("description") or description
        word_count = _count_word_like(text)

    title = _clean_title(title)
    author = _clean_author(author)
    tags = [t for t in (_normalize_tag(x) for x in tags) if t]
    tags = list(dict.fromkeys(tags))[:30]

    return UploadMetadata(
        title=title,
        author=author,
        tags=tags,
        word_count=int(word_count or 0),
        description=description,
    )

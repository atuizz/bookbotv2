import re
from collections import Counter


_RE_CJK = re.compile(r"[\u4e00-\u9fff]{2,6}")
_RE_EN = re.compile(r"[A-Za-z]{4,20}")
_RE_CJK_1 = re.compile(r"[\u4e00-\u9fff]{1,4}")


_STOPWORDS_CJK = {
    "我们",
    "你们",
    "他们",
    "她们",
    "它们",
    "自己",
    "这个",
    "那个",
    "这些",
    "那些",
    "什么",
    "怎么",
    "为什么",
    "不是",
    "所以",
    "因为",
    "但是",
    "然后",
    "如果",
    "这样",
    "那样",
    "还有",
    "已经",
    "可以",
    "不会",
    "不要",
    "没有",
    "时候",
    "现在",
    "刚才",
    "一下",
    "一个",
    "两个",
    "三个",
    "一些",
    "这里",
    "那里",
    "如何",
    "而且",
    "而是",
    "于是",
    "而后",
    "之后",
    "之前",
    "之中",
    "之内",
    "之上",
    "之下",
    "一种",
    "一样",
    "一般",
    "一直",
    "还是",
    "只是",
    "其实",
    "终于",
    "同时",
    "不过",
    "当然",
    "毕竟",
    "从而",
    "因为",
    "所以",
    "第章",
    "第一章",
    "第二章",
    "第三章",
    "第四章",
    "第五章",
    "第六章",
    "第七章",
    "第八章",
    "第九章",
    "第十章",
    "正文",
    "目录",
    "作者",
    "书名",
    "简介",
    "标签",
    "分类",
    "主角",
    "人物",
    "角色",
    "关键字",
    "关键词",
    "小说",
    "章节",
    "更新",
    "发布",
    "阅读",
    "完结",
    "开始",
    "结束",
    "说道",
    "问道",
    "笑道",
    "看着",
    "看了",
    "看见",
    "感觉",
    "突然",
    "继续",
    "同时",
    "之后",
    "之前",
    "发现",
    "时候",
    "看到",
    "知道",
    "听到",
    "看向",
    "说道",
    "什么",
    "怎么",
    "如果",
    "然后",
    "无关",
    "内容",
}


_GENRE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("玄幻", ("玄幻", "异界", "斗气", "武魂", "魂环", "神域", "圣域", "神兽")),
    ("奇幻", ("奇幻", "魔法", "法师", "巫师", "龙族", "精灵", "魔王", "魔兽")),
    ("仙侠", ("仙侠", "修仙", "修真", "金丹", "元婴", "飞升", "渡劫", "灵根", "丹药")),
    ("武侠", ("武侠", "江湖", "门派", "掌门", "剑客", "武林", "内力", "轻功")),
    ("都市", ("都市", "商业", "职场", "总裁", "白领", "豪门", "地产", "公司")),
    ("言情", ("言情", "甜宠", "虐恋", "先婚后爱", "追妻", "恋爱", "相亲", "告白")),
    ("悬疑", ("悬疑", "推理", "案件", "凶手", "密室", "侦探", "线索", "尸体")),
    ("科幻", ("科幻", "星际", "机甲", "外星", "宇宙", "飞船", "虫族", "量子")),
    ("末日", ("末日", "丧尸", "废土", "灾变", "求生", "围城", "避难所")),
    ("历史", ("历史", "朝堂", "皇帝", "王朝", "权谋", "宰相", "科举", "边关")),
    ("军事", ("军事", "战争", "战场", "军团", "将军", "炮火", "阵地", "营地")),
    ("游戏", ("游戏", "网游", "副本", "玩家", "升级", "装备", "技能", "公会")),
    ("灵异", ("灵异", "鬼怪", "诡异", "阴阳", "驱魔", "道士", "冥界", "厉鬼")),
    ("二次元", ("二次元", "同人", "轻小说", "动漫", "宅", "cos", "社团")),
]


_ADULT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("后宫", ("后宫", "全收", "全推", "开后宫", "收后宫")),
    ("校花", ("校花", "班花", "女神", "学姐", "学妹", "女老师")),
    ("人妻", ("人妻", "少妇", "熟妇", "寡妇")),
    ("淫荡", ("淫荡", "放荡", "骚", "骚气", "浪")),
    ("肉欲", ("肉棒", "阴茎", "龟头", "阴蒂", "乳房", "乳头", "内裤", "胸罩", "屁股")),
    ("高潮", ("高潮", "射精", "插入", "抽插", "内射", "深喉", "舔", "口交")),
]

_SINGLE_CHAR_WHITELIST = {"爽", "虐", "燃"}


def _normalize_tag(t: str) -> str:
    t = (t or "").strip().lstrip("#")
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[\"'“”‘’]", "", t)
    return t[:20]


def _tokenize_cjk(text: str) -> list[str]:
    return _RE_CJK.findall(text or "")

def _tokenize_cjk_1(text: str) -> list[str]:
    return _RE_CJK_1.findall(text or "")


def _tokenize_en(text: str) -> list[str]:
    return [w.lower() for w in _RE_EN.findall(text or "")]


def sample_segments(*, text: str, segment_len: int, segments: int = 5) -> list[str]:
    text = (text or "")
    if segment_len <= 0 or not text:
        return []
    n = len(text)
    if n <= segment_len:
        return [text]

    positions: list[int] = []
    if segments <= 1:
        positions = [0]
    else:
        for i in range(segments):
            pos = int((n - segment_len) * (i / (segments - 1)))
            positions.append(max(0, min(n - segment_len, pos)))

    out: list[str] = []
    seen: set[int] = set()
    for pos in positions:
        if pos in seen:
            continue
        seen.add(pos)
        out.append(text[pos : pos + segment_len])
    return out


def sample_text(*, title: str, text: str, budget: int = 200_000, segments: int = 5) -> str:
    title = (title or "").strip()
    text = (text or "")
    if budget <= 0:
        return title
    if not text:
        return title

    overhead = (len(title) + 1) if title else 0
    available = max(0, budget - overhead)
    if len(text) <= available:
        return (title + "\n" + text) if title else text

    seg_len = max(10_000, available // max(1, segments))
    segs = sample_segments(text=text, segment_len=seg_len, segments=segments)
    if title:
        return title + "\n" + "\n".join(segs)
    return "\n".join(segs)


def _keyword_hits(text: str, keys: tuple[str, ...]) -> tuple[int, int]:
    distinct = 0
    total = 0
    for k in keys:
        c = (text or "").count(k)
        if c > 0:
            distinct += 1
            total += c
    return distinct, total


def _title_keywords(title: str, text: str) -> list[str]:
    title = (title or "").strip()
    if not title:
        return []
    text = text or ""
    toks = [_normalize_tag(x) for x in _tokenize_cjk(title)]
    out: list[str] = []

    def add(t: str) -> None:
        if _is_noise_token(t):
            return
        if t not in out:
            out.append(t)

    for t in toks:
        if not t:
            continue
        if len(t) <= 4:
            add(t)
            continue
        for k in (4, 3, 2):
            for i in range(0, len(t) - k + 1):
                sub = t[i : i + k]
                if len(sub) < 2:
                    continue
                if text and sub not in text:
                    continue
                add(sub)

    return out[:10]


def _is_noise_token(t: str) -> bool:
    if not t:
        return True
    if any(ch.isdigit() for ch in t):
        return True
    if len(set(t)) == 1:
        return True
    if t in _STOPWORDS_CJK:
        return True
    if t.startswith("第") and t.endswith("章"):
        return True
    if t.startswith("第") and t.endswith("节"):
        return True
    if len(t) == 1 and t not in _SINGLE_CHAR_WHITELIST:
        return True
    return False


def generate_tags(*, title: str, text: str, limit: int = 10) -> list[str]:
    title = (title or "").strip()
    text = (text or "")
    src = sample_text(title=title, text=text, budget=200_000, segments=5)
    overhead = (len(title) + 1) if title else 0
    available = max(0, 200_000 - overhead)
    seg_len = max(10_000, available // 5) if available else 10_000
    segments = sample_segments(text=text, segment_len=seg_len, segments=5)
    low_src = src.lower()

    title_tags = _title_keywords(title, src)

    genre_scored: list[tuple[int, str]] = []
    for tag, keys in _GENRE_RULES:
        distinct, total = _keyword_hits(src, keys)
        if distinct >= 3 or total >= 6:
            score = distinct * 3 + min(total, 10)
            genre_scored.append((score, tag))
    genre_scored.sort(reverse=True)
    genre_tags = [t for _, t in genre_scored[:2]]

    adult_scored: list[tuple[int, str]] = []
    for tag, keys in _ADULT_RULES:
        distinct, total = _keyword_hits(src, keys)
        if distinct >= 2 or total >= 6:
            score = distinct * 4 + min(total, 10)
            adult_scored.append((score, tag))
    adult_scored.sort(reverse=True)
    adult_tags = [t for _, t in adult_scored[:4]]

    seg_token_sets: list[set[str]] = []
    seg_tokens_all: list[str] = []
    for seg in segments if segments else [src]:
        toks = [_normalize_tag(x) for x in _tokenize_cjk(seg)]
        toks = [t for t in toks if not _is_noise_token(t)]
        seg_token_sets.append(set(toks))
        seg_tokens_all.extend(toks)

    seg_counter = Counter(seg_tokens_all)
    seg_presence: dict[str, int] = {}
    for s in seg_token_sets:
        for t in s:
            seg_presence[t] = seg_presence.get(t, 0) + 1

    buckets = 6
    name_counter: Counter[str] = Counter()
    name_mask: dict[str, int] = {}
    n = len(text) or 1
    for m in _RE_CJK_1.finditer(text):
        t = _normalize_tag(m.group(0))
        if len(t) not in (2, 3):
            continue
        if _is_noise_token(t):
            continue
        if title and t in title:
            continue
        name_counter[t] += 1
        b = int(m.start() / n * buckets)
        if b >= buckets:
            b = buckets - 1
        name_mask[t] = name_mask.get(t, 0) | (1 << b)

    name_candidates: list[tuple[int, str]] = []
    for t, c in name_counter.items():
        mask = name_mask.get(t, 0)
        bc = mask.bit_count() if hasattr(int, "bit_count") else bin(mask).count("1")
        if bc >= 2 and c >= 6:
            name_candidates.append((bc * 100000 + c, t))
    name_candidates.sort(reverse=True)
    name_tags = [t for _, t in name_candidates[:8]]

    keyword_candidates: list[tuple[int, str]] = []
    for t, c in seg_counter.items():
        if len(t) < 2 or len(t) > 6:
            continue
        if t in genre_tags or t in adult_tags or t in name_tags or t in title_tags:
            continue
        if title and t in title:
            continue
        sp = seg_presence.get(t, 0)
        if sp <= 0:
            continue
        if c < 6 and sp < 2:
            continue
        score = sp * 1000 + c
        keyword_candidates.append((score, t))
    keyword_candidates.sort(reverse=True)

    en_tokens = _tokenize_en(src)
    en_tokens = [t for t in en_tokens if t not in {"http", "https", "www"}]
    en_counter = Counter(en_tokens)

    tags: list[str] = []
    tags.extend(title_tags)
    tags.extend(adult_tags)
    tags.extend(genre_tags)
    tags.extend(name_tags)

    for _, t in keyword_candidates:
        if len(tags) >= limit:
            break
        if t in tags:
            continue
        tags.append(t)

    if len(tags) < limit and en_counter:
        for t, _ in en_counter.most_common(40):
            if len(tags) >= limit:
                break
            nt = _normalize_tag(t)
            if not nt or nt in tags:
                continue
            tags.append(nt)

    tags = [t for t in (_normalize_tag(x) for x in tags) if t]
    tags = list(dict.fromkeys(tags))[:limit]
    return tags

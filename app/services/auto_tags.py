import re
from collections import Counter


_RE_CJK = re.compile(r"[\u4e00-\u9fff]{2,6}")
_RE_EN = re.compile(r"[A-Za-z]{4,20}")


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
}


_GENRE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("玄幻", ("玄幻", "异界", "斗气", "武魂", "魂环", "神域")),
    ("奇幻", ("奇幻", "魔法", "法师", "巫师", "龙族", "精灵")),
    ("仙侠", ("仙侠", "修仙", "修真", "金丹", "元婴", "飞升", "渡劫")),
    ("武侠", ("武侠", "江湖", "门派", "掌门", "剑客", "武林")),
    ("都市", ("都市", "商业", "职场", "总裁", "白领", "豪门")),
    ("言情", ("言情", "甜宠", "虐恋", "先婚后爱", "追妻", "恋爱")),
    ("悬疑", ("悬疑", "推理", "案件", "凶手", "密室", "侦探")),
    ("科幻", ("科幻", "星际", "机甲", "外星", "穿越星", "宇宙")),
    ("末日", ("末日", "丧尸", "废土", "灾变", "求生")),
    ("历史", ("历史", "朝堂", "皇帝", "王朝", "权谋", "宰相")),
    ("军事", ("军事", "战争", "战场", "军团", "将军")),
    ("游戏", ("游戏", "网游", "副本", "玩家", "升级", "装备")),
    ("灵异", ("灵异", "鬼怪", "诡异", "阴阳", "驱魔", "道士")),
    ("二次元", ("二次元", "同人", "轻小说", "动漫", "宅")),
]


def _normalize_tag(t: str) -> str:
    t = (t or "").strip().lstrip("#")
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[\"'“”‘’]", "", t)
    return t[:20]


def _tokenize_cjk(text: str) -> list[str]:
    return _RE_CJK.findall(text or "")


def _tokenize_en(text: str) -> list[str]:
    return [w.lower() for w in _RE_EN.findall(text or "")]


def generate_tags(*, title: str, text: str, limit: int = 10) -> list[str]:
    title = (title or "").strip()
    text = (text or "")
    src = (title + "\n" + text)[:200_000]

    tags: list[str] = []
    low_src = src.lower()
    for tag, keys in _GENRE_RULES:
        if any(k.lower() in low_src for k in keys):
            tags.append(tag)

    cjk_tokens = _tokenize_cjk(src)
    cjk_tokens = [
        t for t in cjk_tokens
        if t not in _STOPWORDS_CJK and not t.startswith("第") and not t.endswith("章")
    ]
    en_tokens = _tokenize_en(src)
    en_tokens = [t for t in en_tokens if t not in {"http", "https", "www"}]

    counter = Counter(cjk_tokens)
    for t, _ in counter.most_common(80):
        nt = _normalize_tag(t)
        if not nt or nt in tags:
            continue
        if title and nt in title:
            continue
        tags.append(nt)
        if len(tags) >= limit:
            break

    if len(tags) < limit and en_tokens:
        ec = Counter(en_tokens)
        for t, _ in ec.most_common(40):
            nt = _normalize_tag(t)
            if not nt or nt in tags:
                continue
            tags.append(nt)
            if len(tags) >= limit:
                break

    tags = [t for t in (_normalize_tag(x) for x in tags) if t]
    tags = list(dict.fromkeys(tags))[:limit]
    return tags


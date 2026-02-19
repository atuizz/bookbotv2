# Bug 修复与截图对齐报告

## 1. 概览

- 审查范围：`app/` 全部模块 + `tests/` + `docs/screenshots/`
- 关键结论：修复了多处运行时错误、安全风险与交互缺失点；并将 /start、/help、/settings、搜索结果、上传状态、书籍详情卡（含管理员视图）对齐到截图展示。
- 回归结果：`python -m pytest -q`：30 passed, 1 skipped（本地环境 Python 3.10）。

## 2. Bug 修复明细

### 2.1 HTML 注入/渲染破坏（高）

**问题**
- Bot 全局使用 HTML ParseMode 时，用户输入、书名、作者等若包含 `<` `>` `&` 会破坏消息渲染，形成 Telegram HTML 注入风险。

**修复**
- 新增统一转义函数 [text.py](file:///d:/CODE/book_bot_v2/app/core/text.py)。
- 在搜索、标签搜索、上传提示、邀请页、排行榜、用户中心、书籍详情卡等动态字段输出处统一转义。

**涉及代码**
- [search.py](file:///d:/CODE/book_bot_v2/app/handlers/search.py)
- [tag_search.py](file:///d:/CODE/book_bot_v2/app/handlers/tag_search.py)
- [upload.py](file:///d:/CODE/book_bot_v2/app/handlers/upload.py)
- [invite.py](file:///d:/CODE/book_bot_v2/app/handlers/invite.py)
- [rankings.py](file:///d:/CODE/book_bot_v2/app/handlers/rankings.py)
- [user.py](file:///d:/CODE/book_bot_v2/app/handlers/user.py)
- 书籍详情卡输出与按钮：[build_book_caption/send_book_card](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py#L106-L258)

**测试**
- 新增搜索结果 HTML 转义断言：[test_search.py](file:///d:/CODE/book_bot_v2/tests/test_search.py)
- 新增邀请页 HTML 转义与分享链接编码断言：[test_invite.py](file:///d:/CODE/book_bot_v2/tests/test_invite.py)

---

### 2.2 `/help` 运行时 NameError（高）

**问题**
- `/help` 构建键盘使用 `InlineKeyboardMarkup/InlineKeyboardButton`，但未导入，运行时触发 NameError。

**修复**
- 补齐 import：[common.py](file:///d:/CODE/book_bot_v2/app/handlers/common.py)

---

### 2.3 `/ss` 标签搜索结果构建参数错误（高）

**问题**
- `build_search_result_text(response, filters)` 把 `filters` 误当作 `bot_username` 传入，导致结果链接构建异常/不可预期。

**修复**
- 改为 `build_search_result_text(response, get_settings().bot_username, filters)` 并补齐 query 转义：[tag_search.py](file:///d:/CODE/book_bot_v2/app/handlers/tag_search.py)

---

### 2.4 邀请页“返回”逻辑错误 + 分享链接未 URL 编码（中）

**问题**
- `invite:back` 通过 `cmd_my(callback.message)` 复用命令，但 `callback.message.from_user` 为 Bot 自身，导致“返回后展示错误用户信息”。
- 分享 URL 未编码，包含特殊字符时会破坏链接参数。

**修复**
- 抽出 `build_invite_main()` 并在回调中使用 `callback.from_user`；分享 URL 使用 `urllib.parse.quote` 编码：[invite.py](file:///d:/CODE/book_bot_v2/app/handlers/invite.py)

---

### 2.5 举报流程回调缺失 + 对文件消息 edit_text 失败（中）

**问题**
- “举报原因”按钮 callback_data 为 `report:{book_id}:{reason}`，原先无对应 handler，点击无效。
- 在文件消息上调用 `edit_text` 可能失败（文件消息通常应 edit_caption 或发送新消息）。

**修复**
- 增加 `report:` 回调处理，并将举报原因选择改为发送新消息，不编辑原文件消息：
  - 举报入口与原因回调：[book_detail.py](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py#L308-L532)

---

### 2.6 收藏并发安全与计数一致性（中）

**问题**
- 收藏表有唯一约束，但收藏逻辑为“先查再插 + 手动计数”，并发点击可能触发 IntegrityError 或导致收藏计数不一致。

**修复**
- 对插入捕获 `IntegrityError` 并回滚；收藏计数改为数据库原子 `UPDATE favorite_count = favorite_count ± 1`，避免并发下的脏计数：
  - [handle_favorite](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py#L334-L442)

---

### 2.7 管理员命令缺少权限校验（中）

**问题**
- `/code_status` 标注为管理员命令但未做校验，存在信息泄露风险。

**修复**
- 查询 DB `User.is_admin` 并拒绝非管理员：
  - [group_verify.py](file:///d:/CODE/book_bot_v2/app/handlers/group_verify.py)

---

## 3. 截图 1:1 对齐验证矩阵

> 说明：以下逐张截图列出对应入口、关键 UI/交互点与代码位置（以“消息文本 + InlineKeyboard 布局”为准）。

### 3.1 7fbf4ae9-e9bb-4865-aab2-0ace91f16d76.jpg（Bot 起始说明）

- 截图内容：Telegram “Bot 介绍卡片（What can this bot do?）”样式说明 + 命令列表。
- 代码对齐：将 `/start` 文案对齐到截图说明（但 BotFather 里的“介绍卡片文本/命令列表”本质属于 Telegram 配置项，不完全由代码控制）：
  - [/start](file:///d:/CODE/book_bot_v2/app/handlers/common.py)

### 3.2 3ad222ad-23b7-47ee-ad24-78153cddb941.jpg（/help 与 /settings）

- /help 文案 + 两按钮：
  - 入口：`/help`
  - 文案与按钮：[/help](file:///d:/CODE/book_bot_v2/app/handlers/common.py)
- /settings 面板：
  - 入口：`/settings`
  - 文案与按钮：[/settings](file:///d:/CODE/book_bot_v2/app/handlers/settings.py)

### 3.3 ae8454be-2a72-43d4-b52e-f126bec3fc8e.jpg、54e930f7-a2e1-4ef5-a65e-f02562572443.jpg（搜索结果 + 筛选键盘）

- 入口：`/s 关键词` 或直接发送文本
- 对齐点：
  - 头部 Results 统计行、序号 01-10、格式 Emoji、评分/质量、捐赠提示
  - 分页行 `1∨ 2 3 4 5 6 ...N`、筛选行（分级/格式/体积/字数）、排序行（最热/最新/最大）、序号按钮 1-10
- 代码位置：
  - 结果文本：[build_search_result_text](file:///d:/CODE/book_bot_v2/app/handlers/search.py)
  - 键盘构建：[build_search_keyboard](file:///d:/CODE/book_bot_v2/app/handlers/search.py)

### 3.4 image_a446bd.jpg、54e930f7-a2e1-4ef5-a65e-f02562572443.jpg（上传状态）

- 入口：直接发送文档
- 对齐点：
  - “加入队列/正在收录/收录成功/文件已存在”状态文案
  - `/info` 引导与排队/成功/失败统计行
- 代码位置：
  - [upload.py](file:///d:/CODE/book_bot_v2/app/handlers/upload.py)
  - [/info](file:///d:/CODE/book_bot_v2/app/handlers/common.py)

### 3.5 image_a3e500.jpg、image_a3e524.jpg（书籍详情卡：管理员视图）

- 入口：搜索结果点击序号按钮/链接（`book:detail:{id}` / `book:download:{id}`）
- 对齐点：
  - 详情卡字段（书名/作者/文库/统计/评分/质量/标签/创建/更新/上传）与分隔符 `|`、`R`、`笔`
  - 按钮布局：`频道/群组/反馈/捐赠` + `删除标签/举报书籍/编辑书籍` + `编辑历史/关闭/返回`
- 代码位置：
  - 详情卡输出与键盘：[book_detail.py:L106-L258](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py#L106-L258)
  - 举报原因回调处理：[book_detail.py](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py)

## 4. 仍需你补充截图/确认的缺口

为完成“所有状态 1:1 对齐”，仍建议补充以下原型截图（目前 screenshots 目录未覆盖或覆盖不足）：

- 搜索无结果态（包含建议文案与是否出现键盘）
- 搜索/翻页加载中态（是否要保留“🔍 加载中...”临时文本）
- 举报原因选择后的最终反馈态（点击原因后页面/提示应如何呈现）
- 权限相关：封禁用户、VIP 专属书籍、成人内容分级切换后的差异展示
- 上传失败态（备份频道不可用、Meilisearch 不可用、DB 超时等）对应的用户提示稿


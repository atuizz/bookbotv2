# Telegram UI 规范（消息文本与内联键盘）

本项目 UI 运行在 Telegram 客户端内，视觉与交互由「消息文本 + InlineKeyboard」决定。本规范用于把 `docs/screenshots/` 与 `docs/原型截图/` 的截图状态落到可实现、可测试的输出基线。

## 1. 搜索（/s）

### 1.1 搜索中提示

- 文本：
  - `🔍 正在搜索: <b>{关键词}</b>...`
- 位置：
  - [perform_search](file:///d:/CODE/book_bot_v2/app/handlers/search.py)

### 1.2 搜索结果卡片

- 文本输出位置：
  - [build_search_result_text](file:///d:/CODE/book_bot_v2/app/handlers/search.py)
- 结果项输出规则（每条 2 行）：
  - 第 1 行：`{序号两位}. {可选:❓ }{书名}{可选: ⭐/🔞}`
  - 第 2 行：`{格式emoji}·{格式}·{体积}·{字数}字·{评分/质量}`
  - 底部推广行：`💎 捐赠会员：提升等级获得书币，等级权限翻倍，优先体验新功能`

### 1.3 搜索无结果态

- 参考截图：`docs/原型截图/搜索无结果态.png`
- 文本（两行）：
  - `没有检索到结果，请尝试其他关键词或调整筛选条件`
  - `内容分级:{全部|安全|成人|未知}`
- 输出位置：
  - [build_no_result_text](file:///d:/CODE/book_bot_v2/app/handlers/search.py)

### 1.4 翻页加载中态

- 参考截图：`docs/原型截图/翻页加载中态.png`
- 行为：
  - 翻页/筛选/排序时不插入“加载中/应用中”占位文本，直接用 edit 更新结果卡片。

### 1.5 搜索键盘：分页 + 筛选 + 排序 + 序号下载

- 输出位置：
  - [build_search_keyboard](file:///d:/CODE/book_bot_v2/app/handlers/search.py)

#### 分页行（第 1 行）

- 当前页按钮显示：`{页码}∨`
- 末页按钮显示：`...{total_pages}`

#### 主筛选行（第 2 行）

- `分级{▲/▼}`、`格式{▲/▼}`、`体积{▲/▼}`、`字数{▲/▼}`
- 点击仅展开/收起子面板，不触发重新搜索：
  - `search:filter:rating`
  - `search:filter:format`
  - `search:filter:size`
  - `search:filter:words`

#### 子面板行（可选插入）

- 分级子面板（1 行 4 按钮）：
  - `✅全部 | 安全🛟 | 成人🔞 | 未知❓`
  - callback：`search:filter:rating:{all|safe|adult|unknown}`
- 格式子面板（2 行 4 按钮）：
  - 行1：`✅全部 | TXT | PDF | EPUB`
  - 行2：`AZW3 | MOBI | DOCX | RTF`
  - callback：`search:filter:format:{all|txt|pdf|epub|azw3|mobi|docx|rtf}`
- 体积子面板（第 1 行 3 按钮；第 2 行 4 按钮）：
  - 行1：`✅全部 | 300KB以下 | 300KB-1MB`
  - 行2：`1MB-3MB | 3MB-8MB | 8MB-20MB | 20MB以上`
  - callback：`search:filter:size:{all|lt300k|300k_1m|1m_3m|3m_8m|8m_20m|20m_plus}`
- 字数子面板（2 行，每行 3 按钮）：
  - 行1：`✅全部 | 30万字以下 | 30-50万字`
  - 行2：`50-100万字 | 100-200万字 | 200万字以上`
  - callback：`search:filter:words:{all|lt30w|30w_50w|50w_100w|100w_200w|200w_plus}`

#### 排序行

- `最热↓/最热`、`最新↓/最新`、`最大↓/最大`
- callback：`search:sort:{popular|newest|largest}`

#### 序号下载行（两行）

- 行1：`1 2 3 4 5`
- 行2：`6 7 8 9 10`
- callback：`search:dl:{1..10}`

## 2. 书籍详情卡（点击搜索结果后）

### 2.1 普通用户按钮布局

- 参考截图：
  - `docs/原型截图/收藏后.png`
  - `docs/原型截图/添加书单.png`
- 键盘输出位置：
  - [build_user_book_keyboard](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py)
- 布局（2 行 × 3 列）：
  - 行1：`🤍收藏/💚收藏`、`+书单`、`💬评价`
  - 行2：`+加标签`、`💡我相似`、`...更多`

### 2.2 收藏反馈（toast）

- 收藏成功：`已添加到我喜欢的书籍`
- 取消收藏：`已取消收藏`
- 位置：
  - [handle_favorite](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py)

### 2.3 书单选择模式

- 键盘输出位置：
  - [build_booklist_keyboard](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py)
- 布局：
  - 行1：`++新建`、`<返回`
  - 行2：`✅[{N}本] 我喜欢的书籍`（当前实现将“我喜欢的书籍”映射为收藏列表）

## 3. 新手帮助（/help）

- 参考截图：`docs/原型截图/新手帮助.png`
- 输出位置：
  - [/help](file:///d:/CODE/book_bot_v2/app/handlers/common.py)
- 按钮：
  - `邀请书友使用`、`捐赠会员计划`

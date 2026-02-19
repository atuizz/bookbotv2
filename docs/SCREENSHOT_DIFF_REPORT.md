# 截图对比报告（基线与实现映射）

本报告用于将截图文件逐一映射到代码输出位置，并作为后续“视觉回归 / 人工验收”的检查清单。由于 Telegram UI 最终由客户端渲染，本项目的可控面为「消息文本 + InlineKeyboard 结构」。

## 1. 对比原则

- 以截图为准：按钮文本、顺序、换行、分隔符、符号（✅/▼/▲/∨/...）应一致。
- 像素级差异（≤1px）属于 Telegram 客户端渲染层面验证项：需使用 `scripts/compare_screenshots.py` 对“Telegram 客户端实际截图”进行离线比对。

## 2. 原型截图（docs/原型截图）

### 2.1 搜索无结果态.png

- 基线内容：
  - `没有检索到结果，请尝试其他关键词或调整筛选条件`
  - `内容分级:全部`
- 对应实现：
  - [build_no_result_text](file:///d:/CODE/book_bot_v2/app/handlers/search.py)
- 现状：
  - 已按两行文案输出，并将“内容分级”与当前筛选联动。

### 2.2 翻页加载中态.png

- 基线特征：
  - 翻页后直接展示新页内容，不出现“加载中/应用中”占位文本。
- 对应实现：
  - [on_search_callback](file:///d:/CODE/book_bot_v2/app/handlers/search.py)
- 现状：
  - 翻页/排序/筛选均不再插入占位文本，直接 edit 更新。

### 2.3 分级筛选.png / 格式筛选.png / 体积筛选.png / 字数筛选.png

- 基线特征：
  - 点击筛选按钮展开子面板；子面板中选中项以 `✅` 前缀标记；
  - 体积/字数为区间筛选。
- 对应实现：
  - [build_search_keyboard](file:///d:/CODE/book_bot_v2/app/handlers/search.py)
  - 区间筛选支持（服务层）：[SearchFilters](file:///d:/CODE/book_bot_v2/app/services/search.py)
- 现状：
  - 已实现子面板展开与区间筛选（min/max）。

### 2.4 收藏后.png

- 基线特征：
  - “收藏”按钮状态切换；
  - toast：`已添加到我喜欢的书籍`
- 对应实现：
  - [handle_favorite](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py)
  - [build_user_book_keyboard](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py)
- 现状：
  - 已实现按钮切换与 toast 文案。

### 2.5 添加书单.png

- 基线特征：
  - 进入书单模式后，底部键盘替换为：`++新建`、`<返回`、`[{N}本] 我喜欢的书籍`
- 对应实现：
  - [build_booklist_keyboard](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py)
  - [show_booklist_menu](file:///d:/CODE/book_bot_v2/app/handlers/book_detail.py)
- 现状：
  - 已实现书单模式键盘；当前“我喜欢的书籍”映射为收藏列表（无需新增数据模型）。

### 2.6 新手帮助.png

- 基线内容：
  - 需要从截图逐行抄取并与 `/help` 输出对齐（该图片在当前环境上传预览失败，但不影响后续逐行对齐实现）。
- 对应实现：
  - [/help](file:///d:/CODE/book_bot_v2/app/handlers/common.py)
- 现状：
  - 已逐行对齐截图文案与按钮（“邀请书友使用 / 捐赠会员计划”）。

## 3. 现有截图（docs/screenshots）

- 搜索列表、上传状态、详情卡管理员视图等仍以此前对齐版本为准；若与 `docs/原型截图` 出现冲突，以你确认的最新原型为准并在实现中统一。

## 4. 离线 PixelMatch 回归（待接入）

- 期望目录约定：
  - 基线：`docs/原型截图`、`docs/screenshots`
  - 实际：`artifacts/screenshots_actual`
- 输出：
  - `artifacts/screenshot_diff`（差异热力图与 summary）
- 阈值：
  - PixelMatch ≤ 0.1

脚本将在实现完成后提供：`scripts/compare_screenshots.py`。

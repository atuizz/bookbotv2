# AGENTS 规则 - bookbot

本文件是本仓库的长期规则与记忆文件，已整合 `CLAUDE.md` 的核心约束与项目特性。

## 1）最高准则
- 允许且鼓励在有更优工程方案时，对现有文档/设计提出质疑并优化。
- 如果发现依赖过时、架构隐患、可维护性陷阱，不要盲目执行，应先暂停并给出更优方案供选择。
- 在具体技术实现上优先采用业界最佳实践，而非机械照搬文档字面描述。

## 2）项目定位
- 项目名：`bookbot`
- 项目类型：Telegram 电子书搜索与上传机器人
- 运行环境：Python 3.11+
- 主框架：`aiogram 3.x`

## 3）核心技术栈
- Bot 框架：`aiogram 3.x`（Router 模式）
- Web 框架：`FastAPI`（预留/可选）
- 数据库：`PostgreSQL 15+`
- ORM：`SQLAlchemy 2.x`（异步）
- 缓存/队列：`Redis 7+`
- 搜索引擎：`Meilisearch 1.x`
- 后台任务：`arq`
- 迁移工具：`Alembic`
- 部署方式：`systemd`

## 4）架构说明
- 启动入口：`run_bot.py` -> `app/bot.py`
- 分层结构：
  - `app/core`：配置、数据库、模型、日志、通用工具
  - `app/handlers`：Telegram 命令与回调处理器
  - `app/services`：搜索、元数据、备份、自动标签等服务
  - `app/worker.py`：后台任务 Worker 与队列封装

## 5）功能快照
- 上传链路：多格式支持、SHA256 去重、元数据提取、奖励计算。
- 搜索链路：关键词 + 筛选 + 排序 + 分页，内联键盘交互，Meilisearch 驱动。
- 详情链路：书籍详情卡片发送/复制、文件引用兜底、收藏/书单交互。
- 用户链路：`/me`、`/coins`、`/fav`、`/history`。
- 排行链路：`/top`。
- 邀请链路：`/my`。

## 6）数据模型重点
- 核心实体：`User`、`Book`、`File`、`FileRef`、`Tag`、`BookTag`、`Favorite`。
- 日志实体：`DownloadLog`、`SearchLog`。
- 关键行为：
  - 基于 SHA256 的文件级去重。
  - 基于 `file_hash` 的书籍与文件解耦。
  - 通过 `app/services/search.py` 做搜索索引同步。

## 7）编码规范
- 按 `CLAUDE.md` 约束：代码注释与文档优先使用中文。
- 新增/修改代码应使用 Python 类型提示（Type Hints）。
- Bot 用户路径要做好异常兜底，避免因异常导致崩溃。
- 关键操作（上传、扣费、队列状态变化等）必须有日志记录。
- 路径处理优先使用 `pathlib`。

## 8）业务红线
- 上传前必须进行 SHA256 校验与去重判断。
- 必须保留文件自动转发到备份频道的恢复逻辑。
- 搜索性能应保持低延迟（文档目标约 100ms，依赖 Meilisearch 优化）。

## 9）项目状态（整合 CLAUDE.md 与当前代码扫描）
- 基础设施：已完成。
- 数据层：已完成。
- 搜索处理器：已完成。
- 上传处理器：已完成。
- 用户中心处理器：已完成。
- 测试基线：`53 passed, 1 skipped`（最近一次本地验证）。
- 整体结论：可部署，但仍有下述风险项需持续改进。

## 10）已知缺口与风险
- `app/worker.py` 的上传任务处理主体仍以占位逻辑为主（`TODO`）。
- `app/handlers/invite.py` 的邀请统计为内存态，非持久化。
- `manage.sh migrate` 每次执行都会尝试自动生成迁移，存在迁移治理风险。
- 配置中包含 webhook 字段，但运行主路径目前以 polling 为主。

## 11）核心命令
- 安装环境：`./manage.sh install`
- 启动 Bot：`./manage.sh start-bot`
- 启动 Worker：`./manage.sh start-worker`
- 执行迁移：`./manage.sh migrate`
- 运行测试：`python -m pytest -q`（或环境可用时 `pytest`）

## 12）Agent 执行规则
- 新功能开发保持现有 `core/handlers/services` 分层，不随意打破结构。
- 优先在现有 handlers/services 上扩展，尽量避免引入无必要新子系统。
- 搜索相关改动需兼容当前 Meilisearch 的筛选/排序 schema。
- 非明确需求下，不替换 SHA256 去重主流程。
- 若修改用户可见命令行为或键盘交互，需同步更新 `tests/` 下相关测试。

## 13）后续可选路线（来自 CLAUDE.md）
- 管理员面板（FastAPI 后台管理）。
- 统计报表与数据分析可视化。
- CI/CD 自动化（如 GitHub Actions）。
- Docker 化部署支持。
- 多语言支持。

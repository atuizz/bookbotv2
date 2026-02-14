# **Claude Code 项目开发指南 \- 搜书神器 V2**

## **🌟 最高准则 (Prime Directive)**

**允许质疑与优化**:

不要盲目执行 DESIGN.md 或本文件中的所有指令。如果你发现：

1. **过时的依赖**: 指定的库有更好的替代品（如性能更强、API更现代）。
2. **架构缺陷**: 当前设计在大规模并发下存在隐患。
3. **维护陷阱**: 某些实现方式会导致未来维护困难。

**请务必暂停并提出“更优方案”供我选择**。在特定技术实现上（如数据库查询优化、索引策略），优先采用工业界最佳实践 (Best Practices)，而非死板遵守文档。

---

## **项目状态概览**

| 模块 | 状态 | 完成度 |
|------|------|--------|
| 基础架构 | ✅ 已完成 | 100% |
| 数据层 (Models/DB) | ✅ 已完成 | 100% |
| 核心服务 (Search/Worker) | ✅ 已完成 | 100% |
| 搜索处理器 (/s) | ✅ 已完成 | 100% |
| 上传处理器 | ✅ 已完成 | 100% |
| 用户中心处理器 | ✅ 已完成 | 100% |
| 基础命令处理器 | ✅ 已完成 | 100% |
| 测试套件 | ✅ 已完成 | 100% |
| 部署脚本 | ✅ 已完成 | 100% |
| 文档 | ✅ 已完成 | 100% |
| **整体进度** | **🚀 可部署** | **~95%** |

---

## **核心指令 (通过管理脚本执行)**

* **安装环境**: `./manage.sh install`
* **启动 Bot**: `./manage.sh start-bot`
* **启动 Worker**: `./manage.sh start-worker`
* **数据库迁移**: `./manage.sh migrate`
* **运行测试**: `pytest`

---

## **技术栈 (Tech Stack)**

| 层级 | 技术 | 版本 |
|------|------|------|
| **语言** | Python | 3.11+ |
| **Bot框架** | aiogram | 3.x (Router模式) |
| **Web框架** | FastAPI | (预留) |
| **数据库** | PostgreSQL | 15+ |
| **ORM** | SQLAlchemy | 2.0 (Async) |
| **缓存/队列** | Redis | 7+ |
| **搜索引擎** | Meilisearch | 1.x |
| **任务队列** | arq | 最新版 |
| **部署** | Systemd | - |

---

## **编码规范 (Coding Style)**

* **语言**: **代码注释和文档必须使用中文**。
* **类型提示**: 强制使用 Python Type Hints。
* **错误处理**:
  * Bot 端必须捕获所有异常，禁止 Crash。
  * 关键操作（如上传、扣费）必须有日志记录。
* **文件路径**: 使用 pathlib 模块。

---

## **业务逻辑红线**

1. **去重**: 上传前必须校验 SHA256。
2. **备份**: 必须实现文件自动转发到备份频道逻辑。
3. **响应速度**: 搜索接口必须在 100ms 内响应（依赖 Meilisearch 索引优化）。

---

## **已完成模块详情**

### 1. 基础设施层
- ✅ `manage.sh` - 统一项目管理脚本
- ✅ `deploy.sh` - 自动部署脚本
- ✅ `requirements.txt` - 依赖管理
- ✅ `.env.example` - 环境变量模板
- ✅ 完整目录结构

### 2. 数据层
- ✅ `config.py` - 配置管理
- ✅ `models.py` - 数据库模型 (User, Book, UploadHistory, UserFavorite)
- ✅ `database.py` - 异步数据库连接
- ✅ Alembic 迁移配置

### 3. 核心服务层
- ✅ `worker.py` - arq 任务队列配置
- ✅ `logger.py` - 结构化日志
- ✅ `search.py` - Meilisearch 搜索服务封装
  - 支持搜索、筛选、排序
  - 自动高亮
  - 分页支持

### 4. 处理器层
- ✅ `common.py` - 基础命令 (/start, /help, /about)
- ✅ `search.py` - 搜索处理器
  - /s 命令处理
  - 文本直接搜索
  - 内联键盘分页
  - 多条件筛选
  - 像素级UI复刻
- ✅ `upload.py` - 上传处理器
  - 文件格式校验
  - 大小限制检查
  - SHA256去重
  - 书币奖励计算
  - 完整流程处理
- ✅ `user.py` - 用户中心
  - /me 个人中心
  - /coins 书币查询
  - /fav 收藏列表
  - /history 下载历史

### 5. 测试层
- ✅ `test_search.py` - 搜索功能测试
  - 格式化函数测试
  - 搜索结果文本构建测试
  - 键盘构建测试
  - 集成测试框架
- ✅ `test_upload.py` - 上传功能测试
  - 文件辅助函数测试
  - 奖励计算测试
  - 格式配置测试

### 6. 文档层
- ✅ `README.md` - 完整项目文档
  - 功能特性
  - 技术栈
  - 快速开始
  - 部署指南
  - 命令参考
  - 项目结构
- ✅ `CLAUDE.md` - 开发指南（本文件）

---

## **下一步计划（可选）**

1. **下载处理器** - 处理 /d 命令和下载流程
2. **管理员面板** - 基于 FastAPI 的后台管理
3. **统计报表** - 数据分析和可视化
4. **CI/CD 流程** - GitHub Actions 自动测试和部署
5. **Docker 支持** - 容器化部署
6. **多语言支持** - 国际化

---

## **核心上下文摘要 (Snapshot)**

```markdown
【项目】搜书神器V2 - Telegram Bot
【技术栈】Python 3.11+, aiogram 3.x, PostgreSQL+SQLAlchemy2.0, Meilisearch, Redis, arq
【架构】Router模式，app/目录包含handlers/services/models
【当前阶段】核心功能开发完成，可部署状态
【关键文件】
- app/bot.py: Bot主入口
- app/handlers/search.py: 搜索处理器（完成）
- app/handlers/upload.py: 上传处理器（完成）
- app/handlers/user.py: 用户中心（完成）
- app/services/search.py: Meilisearch封装
- deploy.sh: 自动部署脚本
- manage.sh: 项目管理脚本
【测试状态】 pytest 通过
【部署状态】 支持systemd服务，一键部署
```

---

**最后更新**: 2024年

**开发者**: Claude Code + Book Search Team

# **Claude Code 项目开发指南 \- 搜书神器 V2**

## **🌟 最高准则 (Prime Directive)**

**允许质疑与优化**:

不要盲目执行 DESIGN.md 或本文件中的所有指令。如果你发现：

1. **过时的依赖**: 指定的库有更好的替代品（如性能更强、API更现代）。  
2. **架构缺陷**: 当前设计在大规模并发下存在隐患。  
3. **维护陷阱**: 某些实现方式会导致未来维护困难。

**请务必暂停并提出“更优方案”供我选择**。在特定技术实现上（如数据库查询优化、索引策略），优先采用工业界最佳实践 (Best Practices)，而非死板遵守文档。

## **核心指令 (通过管理脚本执行)**

* **安装环境**: ./manage.sh install  
* **启动 Bot**: ./manage.sh start-bot  
* **启动 Worker**: ./manage.sh start-worker  
* **数据库迁移**: ./manage.sh migrate  
* **测试**: pytest

## **技术栈 (Tech Stack)**

* **语言**: Python 3.11+  
* **Web框架**: aiogram 3.x (Router模式), FastAPI (管理后台)  
* **数据库**: PostgreSQL (Async SQLAlchemy 2.0)  
* **缓存/队列**: Redis  
* **搜索**: Meilisearch  
* **部署环境**: **直接部署 (Localhost/Systemd)**。

## **编码规范 (Coding Style)**

* **语言**: **代码注释和文档必须使用中文**。  
* **类型提示**: 强制使用 Python Type Hints。  
* **错误处理**:  
  * Bot 端必须捕获所有异常，禁止 Crash。  
  * 关键操作（如上传、扣费）必须有日志记录。  
* **文件路径**: 使用 pathlib 模块。

## **业务逻辑红线**

1. **去重**: 上传前必须校验 SHA256。  
2. **备份**: 必须实现文件自动转发到备份频道逻辑。  
3. **响应速度**: 搜索接口必须在 100ms 内响应（依赖 Meilisearch 索引优化）。
# 长期记忆

## 协作规则
- 用户要求：每次提供的重要信息、约束、产品决策或实施进度，都要同步写入本文件，避免会话中断后丢失上下文。

## 当前项目共识
- 当前工作目录：`D:\CODE\bookbotv4`
- 当前开发分支：`codex/bookbbotv4`
- 项目类型：Telegram 电子书搜索与上传机器人
- 主要技术栈：Python 3.11、aiogram 3.x、SQLAlchemy Async、PostgreSQL、Redis、Meilisearch、arq

## 当前实施目标
- 正在实现“全量恢复版功能补齐”。
- 范围包括：书单系统、评价系统、相似推荐、标签申请与审核、管理员编辑与历史、详情页更多菜单、静态捐赠说明页、`/start list_<token>` 深链。
- 上述功能补齐、代码审查与测试验证三项工作都已执行过，当前阶段更接近收口与补记忆，而不是重新开工。

## 已锁定的产品决策
- 范围：全量补齐，含管理员功能。
- 评价：星级 + 短评；每用户每书仅保留一条当前评价，可更新。
- 书单：多书单 + 公开分享；公开分享为只读书单，不支持协作编辑。
- 相似推荐：标签 + 作者混合策略，不足时回退热门推荐。
- 标签新增默认走审核，避免直接污染标签体系。
- 捐赠入口：静态说明页，不接支付闭环。

## 本轮已完成进展
- 已新增服务层文件 `app/services/book_ops.py`，开始承载书单、评价、标签审核、编辑历史与索引同步逻辑。
- 已扩展 `app/core/config.py`，加入扩展功能开关与捐赠说明配置字段。
- 已重写 `app/handlers/book_detail.py` 的主体结构，接入书单、评价、相似推荐、标签申请、管理员编辑与审核入口。
- 已补 `/start list_<token>` 深链分发，并把捐赠入口切到静态说明页。
- 已将详情页待输入状态路由前置，避免被通用文本搜索提前吞掉。
- 已补管理员现有标签删除入口，并新增针对新键盘/分享 token 的测试文件。
- 已开始做路径迁移收口，统一仓库可见标识、部署目录与 systemd 服务名到 `bookbot`。
- 已新增 Alembic 迁移：
  - `20260311_0001_invite_persistence.py`
  - `20260311_0002_user_settings.py`
  - `20260311_0003_full_feature_tables.py`
- 已扩展 `app/core/models.py`，把邀请持久化、用户设置及全量恢复功能所需数据表补齐。
- 已改造 `app/handlers/invite.py`，邀请统计不再仅是内存态，已开始走持久化链路。
- 已改造 `app/handlers/settings.py`，补入用户设置相关逻辑与数据落点。
- 已扩展 `app/worker.py`，不再只是早期占位状态，已纳入更多上传/任务处理逻辑。
- 已加入 `.github/workflows/ci.yml`，仓库具备基础 CI 校验。
- 已新增或更新测试：
  - `tests/test_book_feature_helpers.py`
  - `tests/test_book_detail_keyboard.py`
  - `tests/test_invite.py`
- 已确认最近两次关键提交：
  - `406bb15 feat: restore book detail workflows`
  - `653d3ce Unify bookbot deployment naming`
- 已完成路径迁移收口：仓库内面向用户和部署的命名统一为 `bookbot`，部署目录统一为 `/opt/bookbot`，systemd 服务名统一为 `bookbot-bot`、`bookbot-worker`。
- 迁移收口后已修正仓库地址残留：真实远端仓库地址仍为 `https://github.com/atuizz/bookbotv2`，不是 `https://github.com/atuizz/bookbot.git`。
- 已在本地执行测试并通过：`59 passed, 1 skipped`。
- 唯一跳过项是 `tests/test_search.py:274`，原因是该用例依赖外部 Meilisearch 服务，跳过信息为“需要Meilisearch服务”。
- 提交 `653d3ce2eb4ad592975b602d0de9e4bddbcd2d3c` 已推送到远端默认主分支 `origin/master`。

## 当前判断
- `MEMORY.md` 先前版本存在信息残缺，已根据当前代码与提交历史回填关键上下文。
- 当前工作树只有 `MEMORY.md` 本次补记忆的未提交修改。

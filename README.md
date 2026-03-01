# 📚 搜书神器 V2

一款功能强大的 Telegram 电子书搜索 Bot，支持多种格式书籍的上传、搜索和下载。

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-blue.svg)](https://docs.aiogram.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7+-blue.svg)](https://redis.io/)
[![Meilisearch](https://img.shields.io/badge/Meilisearch-1.x-blue.svg)](https://www.meilisearch.com/)

---

## ✨ 功能特性

### 🔍 智能搜索
- 支持书名、作者、标签、主角等多维度搜索
- 基于 Meilisearch 的高性能全文检索
- 智能排序（热度、最新、文件大小）
- 多条件筛选（格式、分级、体积、字数）

### 📤 便捷上传
- 支持多种格式：TXT、PDF、EPUB、MOBI、AZW3、DOC、DOCX
- 自动 SHA256 去重校验
- 自动转发到备份频道
- 上传奖励书币系统

### 💰 书币系统
- 上传获得书币奖励
- 下载消耗书币
- 多种获取渠道（上传、签到、邀请）

### 👤 用户中心
- 个人信息管理
- 书币余额查询
- 收藏书籍列表
- 下载历史记录

---

## 🛠️ 技术栈

| 组件 | 技术选型 | 用途 |
|------|---------|------|
| Bot 框架 | aiogram 3.x | Telegram Bot 开发 |
| Web 框架 | FastAPI | 管理后台 API |
| 数据库 | PostgreSQL 15+ | 主数据存储 |
| ORM | SQLAlchemy 2.0 | 数据库操作 |
| 缓存/队列 | Redis 7+ | 缓存、任务队列 |
| 搜索引擎 | Meilisearch 1.x | 全文检索 |
| 任务队列 | arq | 异步任务处理 |
| 部署 | Systemd | 进程管理 |

---

## 📦 快速开始

### 方式一：一键部署（推荐）

使用以下命令即可自动完成环境安装、代码下载和配置：

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/atuizz/bookbotv2/master/install.sh)"
```

该脚本会自动：
1. 检查并安装系统依赖 (Python 3.11, Redis, PostgreSQL, Meilisearch)
2. 自动从 GitHub 克隆/更新代码
3. 创建虚拟环境并安装项目依赖
4. 自动配置数据库和搜索引擎
5. 配置 systemd 服务实现开机自启
6. 引导设置 Bot Token

### 方式二：手动部署

1. 克隆项目
```bash
git clone https://github.com/atuizz/bookbotv2.git
cd bookbotv2
```

2. 运行管理脚本
```bash
./manage.sh install
```

# 4. 初始化数据库
sudo systemctl start postgresql
sudo -u postgres psql -c "CREATE DATABASE bookbot_v2;"
sudo -u postgres psql -c "CREATE USER bookbot WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE bookbot_v2 TO bookbot;"

# 5. 运行数据库迁移
cd /opt/book_bot_v2
./manage.sh migrate

# 6. 启动服务
sudo systemctl start book_bot_v2
sudo systemctl start book_bot_v2-worker

# 7. 查看状态
sudo systemctl status book_bot_v2
sudo journalctl -u book_bot_v2 -f
```

### 方式三：手动安装

#### 1. 系统要求

- Ubuntu 22.04 LTS 或 Debian 12
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Meilisearch 1.x

#### 2. 安装系统依赖

```bash
# 更新系统
sudo apt update
sudo apt upgrade -y

# 安装依赖
sudo apt install -y \
    python3.11 python3.11-venv python3-pip python3.11-dev \
    build-essential libpq-dev git wget curl \
    postgresql postgresql-contrib redis-server

# 安装 Meilisearch
curl -L https://install.meilisearch.com | sh
sudo mv meilisearch /usr/local/bin/
```

#### 3. 配置数据库

```bash
# 启动PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 创建数据库和用户
sudo -u postgres psql << EOF
CREATE DATABASE bookbot_v2;
CREATE USER bookbot WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE bookbot_v2 TO bookbot;
\q
EOF
```

#### 4. 配置Redis

```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

#### 5. 配置Meilisearch

```bash
# 创建Meilisearch服务
sudo tee /etc/systemd/system/meilisearch.service > /dev/null << EOF
[Unit]
Description=Meilisearch
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/meilisearch --master-key your_meili_master_key
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable meilisearch
sudo systemctl start meilisearch
```

#### 6. 部署项目

```bash
# 克隆项目
git clone https://github.com/yourusername/book_bot_v2.git /opt/book_bot_v2
cd /opt/book_bot_v2

# 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 创建环境配置文件
cp .env.example .env
# 编辑 .env 文件
nano .env
```

#### 7. 运行数据库迁移

```bash
# 使用alembic运行迁移
cd /opt/book_bot_v2
alembic upgrade head
```

#### 8. 配置Systemd服务

```bash
# Bot服务
sudo tee /etc/systemd/system/book_bot_v2.service > /dev/null << EOF
[Unit]
Description=搜书神器 V2 - Telegram Bot
After=network.target postgresql.service redis.service meilisearch.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/book_bot_v2
Environment=PATH=/opt/book_bot_v2/.venv/bin
ExecStart=/opt/book_bot_v2/.venv/bin/python run_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/book_bot_v2/logs/bot.log
StandardError=append:/opt/book_bot_v2/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

# Worker服务
sudo tee /etc/systemd/system/book_bot_v2-worker.service > /dev/null << EOF
[Unit]
Description=搜书神器 V2 - Background Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/book_bot_v2
Environment=PATH=/opt/book_bot_v2/.venv/bin
ExecStart=/opt/book_bot_v2/.venv/bin/arq app.worker.WorkerSettings
Restart=always
RestartSec=10
StandardOutput=append:/opt/book_bot_v2/logs/worker.log
StandardError=append:/opt/book_bot_v2/logs/worker_error.log

[Install]
WantedBy=multi-user.target
EOF

# 重载systemd并启用服务
sudo systemctl daemon-reload
sudo systemctl enable book_bot_v2
sudo systemctl enable book_bot_v2-worker

# 启动服务
sudo systemctl start book_bot_v2
sudo systemctl start book_bot_v2-worker

# 查看状态
sudo systemctl status book_bot_v2
```

---

## 📁 项目结构

```
book_bot_v2/
├── app/                      # 主应用包
│   ├── __init__.py
│   ├── bot.py               # Bot 主入口
│   ├── worker.py            # 后台 Worker
│   ├── core/                # 核心模块
│   │   ├── config.py        # 配置管理
│   │   ├── database.py      # 数据库连接
│   │   ├── logger.py        # 日志配置
│   │   └── models.py        # 数据模型
│   ├── handlers/            # 处理器
│   │   ├── __init__.py
│   │   ├── common.py        # 通用命令
│   │   ├── search.py        # 搜索功能
│   │   ├── upload.py        # 文件上传
│   │   └── user.py          # 用户中心
│   └── services/            # 服务层
│       ├── __init__.py
│       └── search.py        # 搜索服务
├── alembic/                 # 数据库迁移
│   ├── versions/
│   ├── env.py
│   └── alembic.ini
├── tests/                   # 测试
│   ├── __init__.py
│   ├── test_search.py
│   └── test_upload.py
├── logs/                    # 日志目录
├── data/                    # 数据目录
├── .venv/                   # 虚拟环境
├── .env                     # 环境变量
├── .env.example             # 环境变量示例
├── requirements.txt         # 依赖列表
├── run_bot.py               # 启动脚本
├── manage.sh                # 管理脚本
├── deploy.sh                # 部署脚本
└── README.md                # 项目说明
```

---

## 📝 环境变量说明

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `BOT_TOKEN` | Telegram Bot Token | `123456:ABC-DEF1234...` |
| `BOT_NAME` | Bot 名称 | `搜书神器 V2` |
| `DATABASE_URL` | PostgreSQL 连接URL | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis 连接URL | `redis://localhost:6379/0` |
| `MEILI_HOST` | Meilisearch 地址 | `http://localhost:7700` |
| `MEILI_API_KEY` | Meilisearch API密钥 | `your_master_key` |
| `BACKUP_CHANNEL_ID` | 备份频道ID | `-1001234567890` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `DEBUG` | 调试模式 | `false` |

---

## 🔧 常用命令

### 管理脚本 (manage.sh)

```bash
# 安装依赖
./manage.sh install

# 启动 Bot
./manage.sh start-bot

# 启动 Worker
./manage.sh start-worker

# 启动所有服务
./manage.sh start

# 停止服务
./manage.sh stop

# 重启服务
./manage.sh restart

# 运行测试
./manage.sh test

# 数据库迁移
./manage.sh migrate

# 创建迁移
./manage.sh makemigrations

# 降级数据库
./manage.sh downgrade

# 查看日志
./manage.sh logs

# 查看状态
./manage.sh status

# 备份数据
./manage.sh backup

# 恢复数据
./manage.sh restore

# 清理日志
./manage.sh clean

# 更新项目
./manage.sh update
```

### Systemd 命令

```bash
# 查看Bot状态
sudo systemctl status book_bot_v2

# 查看Worker状态
sudo systemctl status book_bot_v2-worker

# 启动Bot
sudo systemctl start book_bot_v2

# 停止Bot
sudo systemctl stop book_bot_v2

# 重启Bot
sudo systemctl restart book_bot_v2

# 查看Bot日志
sudo journalctl -u book_bot_v2 -f

# 查看Worker日志
sudo journalctl -u book_bot_v2-worker -f
```

---

## 🧪 测试

运行测试套件:

```bash
# 安装测试依赖
pip install -r requirements-dev.txt

# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_search.py
pytest tests/test_upload.py

# 带覆盖率报告
pytest --cov=app --cov-report=html

# 运行并生成JUnit XML报告
pytest --junitxml=test-results.xml
```

---

## 📊 项目状态

- [x] 基础架构搭建
- [x] 数据库模型设计
- [x] 搜索服务 (Meilisearch)
- [x] 搜索处理器 (/s 命令)
- [x] 上传处理器
- [x] 用户中心处理器
- [ ] 下载处理器
- [ ] 管理员面板
- [ ] 统计报表
- [x] 部署脚本
- [ ] CI/CD 流程

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

1. Fork 项目
2. 创建分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

## 🙏 致谢

- [aiogram](https://docs.aiogram.dev/) - 强大的异步 Telegram Bot 框架
- [Meilisearch](https://www.meilisearch.com/) - 极速开源搜索引擎
- [PostgreSQL](https://www.postgresql.org/) - 世界上最先进的开源关系型数据库
- [Redis](https://redis.io/) - 高性能键值存储
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL 工具包和 ORM

---

## 📞 联系我们

- Telegram 频道: [@book_search_channel](https://t.me/book_search_channel)
- 交流群组: [@book_search_group](https://t.me/book_search_group)
- 开发者: [@developer](https://t.me/developer)

---

<p align="center">
  <b>搜书神器 V2</b> - 让找书变得简单
  <br>
  Made with ❤️ by the Book Search Team
</p>

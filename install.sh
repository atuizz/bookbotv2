#!/bin/bash
#
# 搜书神器 V2 - 中文一键部署脚本
# 使用方法: sudo bash install.sh
#

set -e

# 颜色输出
red='\033[0;31m'
green='\033[0;32m'
yellow='\033[1;33m'
blue='\033[0;34m'
cyan='\033[0;36m'
reset='\033[0m'

# 打印函数
info() { echo -e "${blue}[信息]${reset} $1"; }
success() { echo -e "${green}[成功]${reset} $1"; }
warn() { echo -e "${yellow}[警告]${reset} $1"; }
error() { echo -e "${red}[错误]${reset} $1"; exit 1; }
step() { echo -e "\n${cyan}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${reset}"; echo -e "${cyan}  $1${reset}"; echo -e "${cyan}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${reset}\n"; }

# 项目配置
PROJECT_NAME="搜书神器 V2"
PROJECT_DIR="/opt/book_bot_v2"
SERVICE_NAME="book-bot-v2"

# 欢迎界面
clear
echo -e "${cyan}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║        📚 ${PROJECT_NAME} 一键部署脚本 📚          ║"
echo "║                                                          ║"
echo "║         让每个人都能自由获取知识                          ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${reset}"
echo ""

# 检查root权限
if [[ $EUID -ne 0 ]]; then
    error "此脚本需要 root 权限运行\n请使用: sudo bash install.sh"
fi

# 步骤1: 检查系统环境
step "步骤 1/7: 检查系统环境"

info "检查操作系统..."
if [[ -f /etc/os-release ]]; then
    source /etc/os-release
    info "操作系统: $PRETTY_NAME"
else
    warn "无法确定操作系统类型"
fi

info "检查 Python 版本..."
if command -v python3.11 &> /dev/null; then
    PYTHON_VERSION=$(python3.11 --version 2>&1)
    success "Python 版本: $PYTHON_VERSION"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    success "Python 版本: $PYTHON_VERSION"
    warn "建议安装 Python 3.11 以获得最佳性能"
else
    error "未找到 Python，请先安装 Python 3.11+"
fi

success "环境检查完成"

# 步骤2: 安装系统依赖
step "步骤 2/7: 安装系统依赖"

info "更新软件包列表..."
apt-get update -qq || warn "更新软件包列表失败"

info "安装系统依赖..."
apt-get install -y -qq \
    software-properties-common \
    build-essential \
    libpq-dev \
    python3-dev \
    python3-venv \
    python3-pip \
    git \
    curl \
    wget \
    nano \
    htop \
    tree \
    redis-tools \
    postgresql-client \
    redis-server \
    postgresql \
    postgresql-contrib \
    2>&1 | while read -r line; do
        # 静默安装
        :
    done

# 安装 Python 3.11 (如果系统没有)
if ! command -v python3.11 &> /dev/null; then
    info "安装 Python 3.11..."
    add-apt-repository -y ppa:deadsnakes/ppa 2>&1 > /dev/null
    apt-get update -qq
    apt-get install -y -qq python3.11 python3.11-venv python3.11-dev
fi

success "系统依赖安装完成"

# 步骤2.5: 安装和配置服务
step "步骤 2.5: 安装和配置服务"

# 1. 配置 Meilisearch
if ! command -v meilisearch &> /dev/null; then
    info "安装 Meilisearch..."
    curl -L https://install.meilisearch.com | sh
    mv meilisearch /usr/local/bin/
    chmod +x /usr/local/bin/meilisearch
    success "Meilisearch 安装完成"
fi

# 配置 Meilisearch Systemd
if [[ ! -f /etc/systemd/system/meilisearch.service ]]; then
    info "配置 Meilisearch 服务..."
    cat > /etc/systemd/system/meilisearch.service << EOF
[Unit]
Description=Meilisearch
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/meilisearch --master-key=masterKey --env=production --db-path=/var/lib/meilisearch/data
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    mkdir -p /var/lib/meilisearch/data
    systemctl daemon-reload
    systemctl enable meilisearch
    systemctl start meilisearch
    success "Meilisearch 服务已启动 (Master Key: masterKey)"
fi

# 1.5 配置 Redis
info "检查 Redis 配置..."

# 预防性修复：强制 Redis 仅监听 IPv4 (解决 IPv6 缺失导致的启动失败)
if [[ -f /etc/redis/redis.conf ]]; then
    # 只要没有明确只绑定 127.0.0.1，就强制改写，防止 bind 127.0.0.1 ::1 引发问题
    if ! grep -q "^bind 127.0.0.1$" /etc/redis/redis.conf; then
        info "优化 Redis 网络配置 (强制 IPv4)..."
        cp /etc/redis/redis.conf /etc/redis/redis.conf.bak
        sed -i "s/^bind .*/bind 127.0.0.1/" /etc/redis/redis.conf
    fi
    
    # 修复权限：无论是否修改过，都强制修复权限，防止因权限问题导致启动失败
    if id "redis" &>/dev/null; then
        info "修复 Redis 配置文件权限..."
        chown redis:redis /etc/redis/redis.conf
        chmod 640 /etc/redis/redis.conf
        # 确保日志目录权限
        if [[ -d /var/log/redis ]]; then
            chown -R redis:redis /var/log/redis
        fi
        
        # 关键修复：确保数据目录存在且权限正确（解决 FATAL CONFIG FILE ERROR: No such file or directory）
        if [[ ! -d /var/lib/redis ]]; then
            info "创建 Redis 数据目录..."
            mkdir -p /var/lib/redis
        fi
        chown -R redis:redis /var/lib/redis
        chmod 750 /var/lib/redis
    fi
fi

if systemctl is-active --quiet redis-server; then
    success "Redis 服务运行正常"
else
    info "启动 Redis 服务..."
    # 先尝试停止可能存在的僵尸进程
    systemctl stop redis-server || true
    systemctl enable redis-server || true
    
    # 尝试启动
    if ! systemctl start redis-server; then
        warn "Redis 服务启动失败，尝试重启..."
        systemctl restart redis-server || true
    fi
    
    # 再次检查状态
    if systemctl is-active --quiet redis-server; then
        success "Redis 服务启动成功"
    else
        warn "Redis 服务启动失败，正在收集错误日志..."
        echo -e "${red}=== Redis 错误日志 (最后 20 行) ===${reset}"
        journalctl -xeu redis-server.service --no-pager | tail -n 20
        echo -e "${red}=====================================${reset}"
        
        # 尝试最后的挽救：如果是因为 protected-mode 导致的（虽然这里只绑了 127.0.0.1）
        # 或者尝试直接前台运行测试配置是否正确
        # redis-server /etc/redis/redis.conf --test-memory 2
        
        error "Redis 服务无法启动，请根据上方日志排查问题。"
    fi
fi

# 等待 Redis 就绪
info "等待 Redis 服务就绪..."
for i in {1..10}; do
    if redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; then
        success "Redis 连接成功"
        break
    fi
    if [ $i -eq 10 ]; then
        warn "无法连接到 Redis (127.0.0.1)，后续步骤可能会失败"
    fi
    sleep 1
done

# 2. 配置 PostgreSQL
info "检查 PostgreSQL 配置..."
if systemctl is-active --quiet postgresql; then
    # 等待 PG 启动
    sleep 2
    
    # 创建用户
    if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='bookbot'" | grep -q 1; then
        info "创建数据库用户 bookbot..."
        sudo -u postgres psql -c "CREATE USER bookbot WITH PASSWORD 'password';"
    fi
    
    # 创建数据库
    if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='bookbot_v2'" | grep -q 1; then
        info "创建数据库 bookbot_v2..."
        sudo -u postgres psql -c "CREATE DATABASE bookbot_v2 OWNER bookbot;"
    fi
    
    success "PostgreSQL 配置完成"
else
    warn "PostgreSQL 未运行，跳过自动配置"
fi

# 步骤3: 创建项目结构
step "步骤 3/7: 创建项目结构"

info "创建项目目录: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"/{app/{handlers,services,core,models},tests,logs,data,docs,temp}

# 检查本地项目文件
if [[ -f "run_bot.py" ]]; then
    info "发现本地项目文件，正在复制..."
    cp -r app tests *.py *.txt *.sh "$PROJECT_DIR/" 2>/dev/null || true
    cp -r docs "$PROJECT_DIR/" 2>/dev/null || true
    success "项目文件复制完成"
else
    info "未找到本地项目文件，尝试从 GitHub 下载..."
    
    # 检查是否已安装 git
    if ! command -v git &> /dev/null; then
        info "安装 git..."
        apt-get install -y -qq git
    fi

    if [ -d "$PROJECT_DIR/.git" ]; then
        info "项目目录已存在 Git 仓库，执行 git pull..."
        cd "$PROJECT_DIR"
        git pull || warn "Git pull 失败，可能存在冲突或网络问题"
    else
        info "正在克隆 Git 仓库..."
        # 尝试清理目标目录（如果存在但不是git仓库）
        if [ -d "$PROJECT_DIR" ]; then
            warn "目标目录 $PROJECT_DIR 已存在但不是 Git 仓库，正在备份..."
            mv "$PROJECT_DIR" "${PROJECT_DIR}_backup_$(date +%Y%m%d%H%M%S)"
        fi
        
        git clone https://github.com/atuizz/bookbotv2.git "$PROJECT_DIR"
    fi
    
    if [[ -f "$PROJECT_DIR/run_bot.py" ]]; then
        success "项目文件下载完成"
    else
        error "项目文件下载失败，请检查网络连接或手动上传文件"
    fi
fi

success "项目结构创建完成"

# 步骤4: 创建Python虚拟环境
step "步骤 4/7: 创建Python虚拟环境"

cd "$PROJECT_DIR"

info "创建 Python 虚拟环境..."
python3.11 -m venv .venv

info "激活虚拟环境并安装依赖..."
source .venv/bin/activate

# 升级pip
pip install --upgrade pip setuptools wheel -q

# 安装依赖
if [[ -f "requirements.txt" ]]; then
    info "安装项目依赖..."
    pip install -r requirements.txt -q
else
    warn "未找到 requirements.txt"
    info "安装基础依赖..."
    pip install aiogram python-telegram-bot sqlalchemy asyncpg redis meilisearch python-dotenv -q
fi

success "虚拟环境创建完成"

# 步骤5: 配置环境变量
step "步骤 5/7: 配置环境变量"

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    info "创建环境配置文件..."
    
    # 获取用户输入
    echo -e "${yellow}"
    read -p "请输入您的 Telegram Bot Token (直接回车使用默认值): " USER_BOT_TOKEN
    echo -e "${reset}"
    if [[ -z "$USER_BOT_TOKEN" ]]; then
        USER_BOT_TOKEN="your_bot_token_here"
    fi

    cat > "$PROJECT_DIR/.env" << EOF
# =====================================
# 搜书神器 V2 - 环境配置
# =====================================

# Bot 配置
BOT_TOKEN=$USER_BOT_TOKEN
BOT_NAME=搜书神器 V2
BOT_VERSION=2.0.0

# 数据库配置
DATABASE_URL=postgresql+asyncpg://bookbot:password@127.0.0.1:5432/bookbot_v2
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=bookbot_v2
DB_USER=bookbot
DB_PASSWORD=password

# Redis 配置
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0

# Meilisearch 配置
MEILI_HOST=http://localhost:7700
MEILI_API_KEY=masterKey
MEILI_INDEX_NAME=books

# 备份频道配置
BACKUP_CHANNEL_ID=-1001234567890

# 日志配置
LOG_LEVEL=INFO

# 开发配置
DEBUG=false
ENVIRONMENT=production
EOF

    chmod 600 "$PROJECT_DIR/.env"
    success "环境配置文件创建完成"
    warn "请编辑 .env 文件并填写正确的配置值"
else
    info "环境配置文件已存在，跳过创建"
fi

# 步骤6: 设置systemd服务
step "步骤 6/7: 设置systemd服务"

info "创建systemd服务文件..."

# Bot服务
cat > /etc/systemd/system/book-bot-v2.service << EOF
[Unit]
Description=搜书神器 V2 - Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/.venv/bin
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/run_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Worker服务
cat > /etc/systemd/system/book-bot-v2-worker.service << EOF
[Unit]
Description=搜书神器 V2 - Background Worker
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/.venv/bin
ExecStart=$PROJECT_DIR/.venv/bin/arq app.worker.WorkerSettings
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重新加载systemd
systemctl daemon-reload

# 启用服务
systemctl enable book-bot-v2.service
systemctl enable book-bot-v2-worker.service

success "systemd服务配置完成"

# 步骤7: 自动执行后续步骤
step "步骤 7/8: 自动初始化与启动"

info "设置文件权限..."
chmod +x "$PROJECT_DIR/manage.sh"

info "初始化数据库..."
cd "$PROJECT_DIR"
if ./manage.sh migrate; then
    success "数据库初始化成功"
else
    error "数据库初始化失败，请检查配置"
fi

info "启动服务..."
systemctl start book-bot-v2
systemctl start book-bot-v2-worker

# 检查服务状态
sleep 3
if systemctl is-active --quiet book-bot-v2; then
    success "Bot 服务启动成功"
else
    warn "Bot 服务启动失败，请使用 systemctl status book-bot-v2 查看日志"
fi

if systemctl is-active --quiet book-bot-v2-worker; then
    success "Worker 服务启动成功"
else
    warn "Worker 服务启动失败，请使用 systemctl status book-bot-v2-worker 查看日志"
fi

# 步骤8: 显示完成信息
step "步骤 8/8: 部署完成"

clear
echo ""
echo -e "${green}╔══════════════════════════════════════════════════════════╗${reset}"
echo -e "${green}║                                                          ║${reset}"
echo -e "${green}║        🎉 ${PROJECT_NAME} 部署完成! 🎉          ║${reset}"
echo -e "${green}║                                                          ║${reset}"
echo -e "${green}╚══════════════════════════════════════════════════════════╝${reset}"
echo ""

echo -e "${green}项目目录:${reset} $PROJECT_DIR"
echo -e "${green}虚拟环境:${reset} $PROJECT_DIR/.venv"
echo -e "${green}日志目录:${reset} $PROJECT_DIR/logs"
echo ""
echo -e "${green}服务状态:${reset}"
systemctl status book-bot-v2 --no-pager | grep "Active:" || true
systemctl status book-bot-v2-worker --no-pager | grep "Active:" || true
echo ""

success "所有服务已启动，您可以开始使用了！"

# 清理
rm -f $0

exit 0

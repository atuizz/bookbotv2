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
    warn "未找到本地项目文件"
    info "请手动上传项目文件到: $PROJECT_DIR"
fi

success "项目结构创建完成"

# 步骤4: 创建Python虚拟环境
step "步骤 4/7: 创建Python虚拟环境"

cd "$PROJECT_DIR"

info "创建 Python 虚拟环境..."
python3.11 -m venv venv

info "激活虚拟环境并安装依赖..."
source venv/bin/activate

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

    cat > "$PROJECT_DIR/.env" << 'EOF'
# =====================================
# 搜书神器 V2 - 环境配置
# =====================================

# Bot 配置
BOT_TOKEN=your_bot_token_here
BOT_NAME=搜书神器 V2
BOT_VERSION=2.0.0

# 数据库配置
DATABASE_URL=postgresql+asyncpg://bookbot:password@localhost:5432/bookbot_v2
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bookbot_v2
DB_USER=bookbot
DB_PASSWORD=your_secure_password

# Redis 配置
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Meilisearch 配置
MEILI_HOST=http://localhost:7700
MEILI_API_KEY=your_meili_master_key
MEILI_INDEX_NAME=books

# 备份频道配置
BACKUP_CHANNEL_ID=-1001234567890

# 日志配置
LOG_LEVEL=INFO

# 开发配置
DEBUG=false
ENVIRONMENT=production
EOF

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
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/run_bot.py
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
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python -m app.worker
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

# 步骤7: 显示完成信息
step "步骤 7/7: 部署完成"

clear
echo ""
echo -e "${green}╔══════════════════════════════════════════════════════════╗${reset}"
echo -e "${green}║                                                          ║${reset}"
echo -e "${green}║        🎉 ${PROJECT_NAME} 部署完成! 🎉          ║${reset}"
echo -e "${green}║                                                          ║${reset}"
echo -e "${green}╚══════════════════════════════════════════════════════════╝${reset}"
echo ""

echo -e "${green}项目目录:${reset} $PROJECT_DIR"
echo -e "${green}虚拟环境:${reset} $PROJECT_DIR/venv"
echo -e "${green}日志目录:${reset} $PROJECT_DIR/logs"
echo ""

echo -e "${yellow}接下来请完成以下步骤:${reset}"
echo ""
echo -e "${cyan}1. 编辑环境配置文件:${reset}"
echo "   nano $PROJECT_DIR/.env"
echo ""
echo -e "${cyan}2. 初始化数据库:${reset}"
echo "   cd $PROJECT_DIR && ./manage.sh migrate"
echo ""
echo -e "${cyan}3. 启动服务:${reset}"
echo "   systemctl start book-bot-v2"
echo "   systemctl start book-bot-v2-worker"
echo ""
echo -e "${cyan}4. 查看状态:${reset}"
echo "   systemctl status book-bot-v2"
echo "   journalctl -u book-bot-v2 -f"
echo ""
echo -e "${cyan}5. 查看日志:${reset}"
echo "   tail -f $PROJECT_DIR/logs/bot.log"
echo ""

success "部署完成!"
log "部署完成"

# 清理
rm -f $0

exit 0

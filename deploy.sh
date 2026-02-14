#!/bin/bash
# -*- coding: utf-8 -*-
# 搜书神器 V2 - 部署脚本
# 用于在服务器上自动部署和配置

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
PROJECT_NAME="book_bot_v2"
PROJECT_DIR="/opt/${PROJECT_NAME}"
BACKUP_DIR="/opt/backups/${PROJECT_NAME}"
SERVICE_NAME="${PROJECT_NAME}"
WORKER_SERVICE_NAME="${PROJECT_NAME}-worker"

# 函数: 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 函数: 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "此脚本需要root权限运行"
        print_info "请使用: sudo $0"
        exit 1
    fi
}

# 函数: 检查系统要求
check_requirements() {
    print_info "检查系统要求..."

    # 检查操作系统
    if [[ ! -f /etc/os-release ]]; then
        print_error "无法确定操作系统类型"
        exit 1
    fi

    source /etc/os-release
    if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
        print_warning "此脚本主要为 Ubuntu/Debian 设计"
        print_warning "当前系统: $PRETTY_NAME"
        read -p "是否继续? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    print_success "系统检查通过"
}

# 函数: 安装系统依赖
install_system_deps() {
    print_info "安装系统依赖..."

    apt-get update
    apt-get install -y \
        python3.11 \
        python3.11-venv \
        python3-pip \
        python3.11-dev \
        build-essential \
        libpq-dev \
        git \
        wget \
        curl \
        redis-tools \
        postgresql-client

    print_success "系统依赖安装完成"
}

# 函数: 创建项目目录
setup_project_dir() {
    print_info "设置项目目录..."

    # 创建项目目录
    mkdir -p "$PROJECT_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "${PROJECT_DIR}/logs"
    mkdir -p "${PROJECT_DIR}/data"

    print_success "项目目录创建完成: $PROJECT_DIR"
}

# 函数: 部署项目文件
deploy_project() {
    print_info "部署项目文件..."

    # 检查当前目录是否有项目文件
    if [[ ! -f "run_bot.py" ]]; then
        print_error "未找到项目文件 (run_bot.py)"
        print_info "请确保在项目根目录运行此脚本"
        exit 1
    fi

    # 备份旧版本
    if [[ -d "${PROJECT_DIR}/app" ]]; then
        backup_timestamp=$(date +%Y%m%d_%H%M%S)
        backup_path="${BACKUP_DIR}/backup_${backup_timestamp}"
        print_info "备份旧版本到: $backup_path"
        mkdir -p "$backup_path"
        cp -r "${PROJECT_DIR}"/* "$backup_path/" 2>/dev/null || true
    fi

    # 复制项目文件
    print_info "复制项目文件到: $PROJECT_DIR"

    # 使用rsync或cp复制文件
    rsync -av --exclude='.git' --exclude='__pycache__' --exclude='venv' --exclude='.venv' \
        . "$PROJECT_DIR/" 2>/dev/null || {
        # 如果rsync失败，使用cp
        cp -r app "$PROJECT_DIR/"
        cp -r tests "$PROJECT_DIR/"
        cp *.py "$PROJECT_DIR/"
        cp *.txt "$PROJECT_DIR/"
        cp *.sh "$PROJECT_DIR/" 2>/dev/null || true
    }

    print_success "项目文件部署完成"
}

# 函数: 创建Python虚拟环境
setup_venv() {
    print_info "创建Python虚拟环境..."

    cd "$PROJECT_DIR"

    # 创建虚拟环境
    python3.11 -m venv .venv

    # 激活虚拟环境并安装依赖
    source .venv/bin/activate

    # 升级pip
    pip install --upgrade pip setuptools wheel

    # 安装依赖
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
    fi

    print_success "虚拟环境创建完成"
}

# 函数: 配置systemd服务
setup_systemd_services() {
    print_info "配置systemd服务..."

    # Bot服务
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=搜书神器 V2 - Telegram Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
Environment=PATH=${PROJECT_DIR}/.venv/bin
ExecStart=${PROJECT_DIR}/.venv/bin/python run_bot.py
Restart=always
RestartSec=10
StandardOutput=append:${PROJECT_DIR}/logs/bot.log
StandardError=append:${PROJECT_DIR}/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

    # Worker服务
    cat > "/etc/systemd/system/${WORKER_SERVICE_NAME}.service" << EOF
[Unit]
Description=搜书神器 V2 - Background Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
Environment=PATH=${PROJECT_DIR}/.venv/bin
ExecStart=${PROJECT_DIR}/.venv/bin/arq app.worker.WorkerSettings
Restart=always
RestartSec=10
StandardOutput=append:${PROJECT_DIR}/logs/worker.log
StandardError=append:${PROJECT_DIR}/logs/worker_error.log

[Install]
WantedBy=multi-user.target
EOF

    # 重新加载systemd
    systemctl daemon-reload

    # 启用服务
    systemctl enable "${SERVICE_NAME}.service"
    systemctl enable "${WORKER_SERVICE_NAME}.service"

    print_success "systemd服务配置完成"
    print_info "服务名称:"
    print_info "  - Bot: ${SERVICE_NAME}"
    print_info "  - Worker: ${WORKER_SERVICE_NAME}"
}

# 函数: 创建环境配置文件
create_env_file() {
    print_info "创建环境配置文件..."

    if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
        cat > "${PROJECT_DIR}/.env" << 'EOF'
# 搜书神器 V2 环境配置
# 请修改以下配置并重启服务

# ===================================
# Bot 配置
# ===================================
BOT_TOKEN=your_bot_token_here
BOT_NAME=搜书神器 V2
BOT_VERSION=2.0.0

# ===================================
# 数据库配置 (PostgreSQL)
# ===================================
DATABASE_URL=postgresql+asyncpg://bookbot:password@localhost:5432/bookbot_v2
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bookbot_v2
DB_USER=bookbot
DB_PASSWORD=your_secure_password

# ===================================
# Redis 配置
# ===================================
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# ===================================
# Meilisearch 配置
# ===================================
MEILI_HOST=http://localhost:7700
MEILI_API_KEY=your_meili_master_key
MEILI_INDEX_NAME=books

# ===================================
# 备份频道配置 (Telegram)
# ===================================
BACKUP_CHANNEL_ID=-1001234567890
UPLOAD_REWARD_ENABLED=true

# ===================================
# 日志配置
# ===================================
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log

# ===================================
# 开发配置
# ===================================
DEBUG=false
ENVIRONMENT=production
EOF

        print_success "环境配置文件创建完成: ${PROJECT_DIR}/.env"
        print_warning "请编辑 .env 文件并填写正确的配置值"
    else
        print_warning "环境配置文件已存在，跳过创建"
    fi
}

# 函数: 显示部署完成信息
show_completion_info() {
    echo
    echo "=========================================="
    echo -e "${GREEN}搜书神器 V2 部署完成!${NC}"
    echo "=========================================="
    echo
    echo "项目目录: $PROJECT_DIR"
    echo "备份目录: $BACKUP_DIR"
    echo "日志目录: ${PROJECT_DIR}/logs"
    echo
    echo -e "${YELLOW}接下来请完成以下步骤:${NC}"
    echo
    echo "1. 编辑环境配置文件:"
    echo "   nano ${PROJECT_DIR}/.env"
    echo
    echo "2. 初始化数据库:"
    echo "   cd $PROJECT_DIR && ./manage.sh migrate"
    echo
    echo "3. 启动服务:"
    echo "   systemctl start ${SERVICE_NAME}"
    echo "   systemctl start ${WORKER_SERVICE_NAME}"
    echo
    echo "4. 查看服务状态:"
    echo "   systemctl status ${SERVICE_NAME}"
    echo "   journalctl -u ${SERVICE_NAME} -f"
    echo
    echo "5. 查看日志:"
    echo "   tail -f ${PROJECT_DIR}/logs/bot.log"
    echo
    echo "常用命令:"
    echo "  ./manage.sh start-bot      # 启动Bot"
    echo "  ./manage.sh start-worker   # 启动Worker"
    echo "  ./manage.sh stop           # 停止服务"
    echo "  ./manage.sh test           # 运行测试"
    echo "=========================================="
}

# ============================================================================
# 主函数
# ============================================================================

main() {
    print_info "搜书神器 V2 部署脚本"
    print_info "===================="

    # 检查root权限
    check_root

    # 检查系统要求
    check_requirements

    # 安装系统依赖
    install_system_deps

    # 创建项目目录
    setup_project_dir

    # 部署项目文件
    deploy_project

    # 创建虚拟环境
    setup_venv

    # 创建环境配置文件
    create_env_file

    # 配置systemd服务
    setup_systemd_services

    # 显示完成信息
    show_completion_info
}

# 运行主函数
main "$@"

#!/bin/bash
# ============================================
# 搜书神器 V2 - 管理脚本
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目配置
PROJECT_NAME="bookbot"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$PROJECT_DIR/.venv" ]]; then
    VENV_DIR="$PROJECT_DIR/.venv"
elif [[ -d "$PROJECT_DIR/venv" ]]; then
    VENV_DIR="$PROJECT_DIR/venv"
else
    VENV_DIR="$PROJECT_DIR/.venv"
fi
PYTHON="$VENV_DIR/bin/python"
SYSTEMD_DIR="/etc/systemd/system"

# 检查 .env 文件
if [[ -f "$PROJECT_DIR/.env" ]]; then
    sed -i 's/\r$//' "$PROJECT_DIR/.env"
    sed -i 's/[[:space:]]*$//' "$PROJECT_DIR/.env"
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# ============================================
# 工具函数
# ============================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 未安装"
        exit 1
    fi

    local version=$(python3 --version | grep -oP '\d+\.\d+')
    local major=$(echo $version | cut -d. -f1)
    local minor=$(echo $version | cut -d. -f2)

    if [[ $major -lt 3 ]] || [[ $major -eq 3 && $minor -lt 11 ]]; then
        log_error "需要 Python 3.11+，当前版本: $version"
        exit 1
    fi

    log_success "Python 版本检查通过: $version"
}

check_services() {
    log_info "检查依赖服务状态..."

    local all_ok=true

    # 检查 PostgreSQL
    if pg_isready -h ${DB_HOST:-localhost} -p ${DB_PORT:-5432} &>/dev/null; then
        log_success "PostgreSQL 运行正常"
    else
        log_error "PostgreSQL 未启动"
        all_ok=false
    fi

    # 检查 Redis
    if redis-cli -h ${REDIS_HOST:-127.0.0.1} -p ${REDIS_PORT:-6379} ping >/dev/null 2>&1; then
        log_success "Redis 运行正常"
    else
        # 尝试输出错误信息
        log_error "Redis 未启动或无法连接:"
        redis-cli -h ${REDIS_HOST:-127.0.0.1} -p ${REDIS_PORT:-6379} ping || true
        all_ok=false
    fi

    # 检查 Meilisearch
    if curl -s "${MEILI_HOST:-http://localhost:7700}/health" 2>/dev/null | grep -q "available"; then
        log_success "Meilisearch 运行正常"
    else
        log_error "Meilisearch 未启动"
        all_ok=false
    fi

    if [[ "$all_ok" == false ]]; then
        log_warning "部分依赖服务未就绪，请先启动服务"
        return 1
    fi

    return 0
}

check_db_connection() {
    local host=${DB_HOST:-127.0.0.1}
    local port=${DB_PORT:-5432}
    local user=${DB_USER:-bookbot}
    local name=${DB_NAME:-bookbot_v2}
    local pass=${DB_PASSWORD:-}
    if [[ -z "$pass" ]]; then
        log_error "DB_PASSWORD 未设置"
        return 1
    fi
    if PGPASSWORD="$pass" psql -h "$host" -p "$port" -U "$user" -d "$name" -c "select 1" >/dev/null 2>&1; then
        return 0
    fi
    if [[ $EUID -ne 0 ]]; then
        log_error "数据库密码验证失败，请使用 sudo ./manage.sh migrate 或重新运行 install.sh"
        return 1
    fi
    local pass_sql=${pass//\'/\'\'}
    sudo -u postgres psql -c "ALTER USER ${user} WITH PASSWORD '${pass_sql}';" >/dev/null 2>&1 || true
    if PGPASSWORD="$pass" psql -h "$host" -p "$port" -U "$user" -d "$name" -c "select 1" >/dev/null 2>&1; then
        return 0
    fi
    log_error "数据库密码验证失败，请检查 .env 中的 DB_PASSWORD 与 DATABASE_URL"
    return 1
}
# ============================================
# 命令实现
# ============================================

cmd_install() {
    log_info "开始安装环境..."

    check_python

    # 创建虚拟环境
    if [[ ! -d "$VENV_DIR" ]]; then
        log_info "创建虚拟环境..."
        python3 -m venv "$VENV_DIR"
    else
        log_warning "虚拟环境已存在"
    fi

    # 升级 pip
    log_info "升级 pip..."
    "$VENV_DIR/bin/pip" install --upgrade pip wheel

    # 安装依赖
    log_info "安装项目依赖..."
    "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

    # 创建目录结构
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/data"
    mkdir -p "$PROJECT_DIR/temp"

    # 复制 .env.example
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        log_warning "请编辑 .env 文件配置你的环境变量"
    fi

    log_success "安装完成！"
    log_info "下一步: 编辑 .env 文件，然后运行 ./manage.sh migrate"
}

cmd_migrate() {
    log_info "执行数据库迁移..."

    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "虚拟环境不存在，请先运行 ./manage.sh install"
        exit 1
    fi

    check_services || exit 1
    check_db_connection || exit 1

    # 初始化 Alembic（如果不存在）
    if [[ ! -d "$PROJECT_DIR/alembic" ]]; then
        log_info "初始化 Alembic..."
        cd "$PROJECT_DIR" && "$PYTHON" -m alembic init alembic
    fi

    # 生成迁移
    log_info "生成迁移文件..."
    cd "$PROJECT_DIR" && "$PYTHON" -m alembic revision --autogenerate -m "Initial migration"

    # 执行迁移
    log_info "执行数据库迁移..."
    cd "$PROJECT_DIR" && "$PYTHON" -m alembic upgrade head

    # 初始化 Meilisearch 索引
    log_info "初始化搜索索引..."
    "$PYTHON" "$PROJECT_DIR/scripts/init_search.py" 2>/dev/null || log_warning "搜索索引初始化脚本未找到，跳过"

    log_success "迁移完成！"
}

cmd_start_bot() {
    log_info "启动 Telegram Bot..."

    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "虚拟环境不存在，请先运行 ./manage.sh install"
        exit 1
    fi

    check_services || exit 1

    log_info "Bot 正在启动... (按 Ctrl+C 停止)"
    cd "$PROJECT_DIR" && exec "$PYTHON" -m app.bot
}

cmd_start_worker() {
    log_info "启动 Worker..."

    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "虚拟环境不存在，请先运行 ./manage.sh install"
        exit 1
    fi

    check_services || exit 1

    log_info "Worker 正在启动... (按 Ctrl+C 停止)"
    cd "$PROJECT_DIR" && exec "$VENV_DIR/bin/arq" app.worker.WorkerSettings
}

cmd_gen_service() {
    log_info "生成 Systemd 服务文件..."

    # Bot 服务
    cat > "$PROJECT_DIR/bookbot-bot.service" << EOF
[Unit]
Description=BookBot Telegram Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PYTHON -m app.bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Worker 服务
    cat > "$PROJECT_DIR/bookbot-worker.service" << EOF
[Unit]
Description=BookBot Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$VENV_DIR/bin/arq app.worker.WorkerSettings
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    log_success "服务文件已生成:"
    echo "  - bookbot-bot.service"
    echo "  - bookbot-worker.service"
    log_info "安装命令:"
    echo "  sudo cp bookbot-*.service $SYSTEMD_DIR/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable --now bookbot-bot bookbot-worker"
}

cmd_health() {
    log_info "健康检查..."

    check_services

    # 检查虚拟环境
    if [[ -d "$VENV_DIR" ]]; then
        log_success "虚拟环境已就绪: $VENV_DIR"
    else
        log_error "虚拟环境不存在"
    fi

    # 检查 .env
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        log_success ".env 文件已存在"
    else
        log_warning ".env 文件不存在，请从 .env.example 复制"
    fi
}

cmd_doctor() {
    log_info "开始全面诊断..."
    
    # 1. 检查 Python 环境
    check_python
    if [[ -d "$VENV_DIR" ]]; then
        log_success "虚拟环境正常: $VENV_DIR"
    else
        log_error "虚拟环境丢失!"
    fi
    
    # 2. 检查 .env 配置
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        log_success ".env 配置文件存在"
        # 检查关键变量
        if grep -q "BOT_TOKEN=your_bot_token_here" "$PROJECT_DIR/.env"; then
            log_error "BOT_TOKEN 未配置! 请编辑 .env 文件"
        elif grep -q "BOT_TOKEN=" "$PROJECT_DIR/.env"; then
            log_success "BOT_TOKEN 已配置"
        else
            log_error "BOT_TOKEN 缺失!"
        fi
    else
        log_error ".env 配置文件丢失!"
    fi
    
    # 3. 检查依赖服务
    check_services
    
    # 4. 检查 Bot 服务日志
    if command -v systemctl &>/dev/null; then
        log_info "检查 Systemd 服务状态..."
        if systemctl is-active --quiet book-bot-v2; then
            log_success "Bot 服务正在运行"
        else
            log_error "Bot 服务未运行!"
        fi
        
        log_info "Bot 服务最近日志 (最后 20 行):"
        echo -e "${YELLOW}--------------------------------------------------${NC}"
        sudo journalctl -u book-bot-v2 -n 20 --no-pager
        echo -e "${YELLOW}--------------------------------------------------${NC}"
        
        if systemctl is-active --quiet book-bot-v2-worker; then
            log_success "Worker 服务正在运行"
        else
            log_error "Worker 服务未运行!"
        fi
    fi
}


# ============================================
# 主入口
# ============================================

cmd_help() {
    cat << EOF
搜书神器 V2 管理脚本

用法: ./manage.sh <命令> [参数]

命令:
  install          安装环境（创建虚拟环境、安装依赖）
  migrate          执行数据库迁移和索引初始化
  start-bot        启动 Telegram Bot
  start-worker     启动任务队列 Worker
  gen-service      生成 systemd 服务配置文件
  health           检查依赖服务健康状态
  doctor           自动诊断常见问题 (Bot不响应、服务异常等)
  test             运行测试套件
  help             显示此帮助信息

示例:
  ./manage.sh install
  ./manage.sh migrate
  ./manage.sh start-bot

Systemd 部署:
  ./manage.sh gen-service
  sudo cp bookbot-*.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now bookbot-bot bookbot-worker

EOF
}

# 主逻辑
main() {
    # 如果没有参数，显示帮助
    if [[ $# -eq 0 ]]; then
        cmd_help
        exit 0
    fi

    command="$1"
    shift

    case "$command" in
        install)
            cmd_install
            ;;
        migrate)
            cmd_migrate
            ;;
        start-bot)
            cmd_start_bot
            ;;
        start-worker)
            cmd_start_worker
            ;;
        gen-service)
            cmd_gen_service
            ;;
        health)
            cmd_health
            ;;
        doctor)
            cmd_doctor
            ;;
        test)
            # 兼容性保留，虽然已被 doctor 覆盖
            cmd_doctor
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            log_error "未知命令: $command"
            cmd_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"

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
version_ge() { [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]; }
print_deploy_info() {
    local old_commit="$1"
    local new_commit="$2"
    local old_desc="$3"
    local new_desc="$4"
    local remote_short="$5"

    echo ""
    if [[ -n "$remote_short" ]]; then
        echo -e "${green}远端 master:${reset} ${remote_short}"
    fi
    echo -e "${green}当前代码版本:${reset} ${new_commit:-unknown} ${new_desc:+(${new_desc})}"
    if [[ -n "$old_commit" && -n "$new_commit" && "$old_commit" != "$new_commit" ]]; then
        echo -e "${green}上一版本:${reset} ${old_commit:-unknown} ${old_desc:+(${old_desc})}"
        echo -e "${green}更新内容:${reset}"
        git --no-pager log --oneline --decorate "${old_commit}..${new_commit}" | head -n 20 || true
    elif [[ -n "$new_commit" ]]; then
        echo -e "${green}更新内容:${reset}"
        git --no-pager log --oneline --decorate -n 10 || true
    fi
    echo ""
}
HAS_SYSTEMD=0
if command -v systemctl &> /dev/null && [ -d /run/systemd/system ]; then
    HAS_SYSTEMD=1
fi

# 项目配置
PROJECT_NAME="搜书神器 V2"
PROJECT_DIR="/opt/bookbot"
SERVICE_NAME="bookbot-bot"
WORKER_SERVICE_NAME="bookbot-worker"
REPO_URL="https://github.com/atuizz/bookbotv2.git"
REDIS_PORT_SELECTED=6379
DB_DEFAULT_HOST="127.0.0.1"
DB_DEFAULT_PORT="5432"
DB_DEFAULT_NAME="bookbot_v2"
DB_DEFAULT_USER="bookbot"
DB_DEFAULT_PASSWORD="password"
DEPLOY_OLD_COMMIT=""
DEPLOY_OLD_DESC=""
DEPLOY_NEW_COMMIT=""
DEPLOY_NEW_DESC=""

env_get() {
    local key="$1"
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        local value
        value=$(grep -E "^${key}=" "$PROJECT_DIR/.env" | tail -n 1 | cut -d= -f2-)
        value=${value//$'\r'/}
        value=$(echo "$value" | sed -e 's/[[:space:]]*$//')
        if [[ "${value:0:1}" == "\"" && "${value: -1}" == "\"" ]]; then
            value="${value:1:-1}"
        elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
            value="${value:1:-1}"
        fi
        echo "$value"
    fi
}

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
    OS_ID="${ID:-unknown}"
    OS_VERSION_ID="${VERSION_ID:-unknown}"
    info "操作系统: $PRETTY_NAME"
else
    OS_ID="unknown"
    OS_VERSION_ID="unknown"
    warn "无法确定操作系统类型"
fi

info "检查 Python 版本..."
PYTHON_BIN=""
PYTHON_VERSION=""
if command -v python3.11 &> /dev/null; then
    PYTHON_BIN="python3.11"
elif command -v python3 &> /dev/null; then
    PYTHON_BIN="python3"
else
    error "未找到 Python，请先安装 Python 3.11+"
fi
PYTHON_VERSION=$($PYTHON_BIN --version 2>&1 | awk '{print $2}')
success "Python 版本: Python $PYTHON_VERSION"
if ! version_ge "$PYTHON_VERSION" "3.11"; then
    warn "建议安装 Python 3.11 以获得最佳性能"
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
if ! version_ge "$PYTHON_VERSION" "3.11"; then
    info "尝试安装 Python 3.11..."
    python_candidate=$(apt-cache policy python3.11 2>/dev/null | awk '/Candidate:/ {print $2}')
    if [[ -n "$python_candidate" && "$python_candidate" != "(none)" ]]; then
        apt-get install -y -qq python3.11 python3.11-venv python3.11-dev || true
    else
        if [[ "$OS_ID" == "ubuntu" ]]; then
            if ! command -v add-apt-repository &> /dev/null; then
                apt-get install -y -qq software-properties-common
            fi
            add-apt-repository -y ppa:deadsnakes/ppa 2>&1 > /dev/null || true
            apt-get update -qq
            apt-get install -y -qq python3.11 python3.11-venv python3.11-dev || true
        fi
    fi
    if command -v python3.11 &> /dev/null; then
        PYTHON_BIN="python3.11"
        PYTHON_VERSION=$(python3.11 --version 2>&1 | awk '{print $2}')
        success "Python 版本: Python $PYTHON_VERSION"
    else
        warn "未能安装 Python 3.11，将继续使用当前 Python: $PYTHON_VERSION"
    fi
fi

success "系统依赖安装完成"

# 步骤2.5: 安装和配置服务
step "步骤 2.5: 安装和配置服务"

# 1. 配置 Meilisearch
MEILI_MASTER_KEY="masterKey_$(date +%s)_${RANDOM}"
if ! command -v meilisearch &> /dev/null; then
    info "安装 Meilisearch..."
    curl -L https://install.meilisearch.com | sh
    mv meilisearch /usr/local/bin/
    chmod +x /usr/local/bin/meilisearch
    success "Meilisearch 安装完成"
fi

# 验证 Meilisearch 二进制文件是否可用
if ! /usr/local/bin/meilisearch --version &> /dev/null; then
    error "Meilisearch 二进制文件无法执行，可能是架构不匹配或缺少依赖库。\n请尝试手动下载适合您系统的版本: https://github.com/meilisearch/meilisearch/releases"
else
    MEILI_VERSION=$(/usr/local/bin/meilisearch --version | head -n 1)
    success "Meilisearch 版本验证通过: $MEILI_VERSION"
fi

# 配置 Meilisearch Systemd
if [[ $HAS_SYSTEMD -eq 1 ]]; then
    info "配置 Meilisearch 服务..."
    
    # 强制删除旧的服务文件，确保更新生效
    if [[ -f /etc/systemd/system/meilisearch.service ]]; then
        info "检测到旧的 Meilisearch 服务配置，正在更新..."
        # 停止服务以防止占用
        systemctl stop meilisearch 2>/dev/null || true
        rm -f /etc/systemd/system/meilisearch.service
    fi

    # 确保数据目录存在
    mkdir -p /var/lib/meilisearch/data
    chmod 755 /var/lib/meilisearch/data

    cat > /etc/systemd/system/meilisearch.service << EOF
[Unit]
Description=Meilisearch
After=network.target

[Service]
Type=simple
User=root
Environment=MEILI_NO_ANALYTICS=true
# 确保使用新生成的 Master Key，避免硬编码
ExecStart=/usr/local/bin/meilisearch --master-key=${MEILI_MASTER_KEY} --env=production --db-path=/var/lib/meilisearch/data
Restart=always
RestartSec=10
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF
    
    # 重新加载 systemd 配置，确保更改立即生效
    systemctl daemon-reload
    systemctl enable meilisearch
    info "Meilisearch 服务配置完成 (Master Key 已更新为安全随机值)"
fi

# 始终尝试启动 Meilisearch (确保服务运行)
if [[ $HAS_SYSTEMD -eq 1 ]]; then
    info "启动 Meilisearch..."
    if systemctl restart meilisearch; then
        # 等待 Meilisearch 启动
        info "等待 Meilisearch 启动..."
        for i in {1..30}; do
            if curl -s "http://localhost:7700/health" | grep -q "available"; then
                success "Meilisearch 服务已就绪"
                break
            fi
            if [ $i -eq 30 ]; then
                warn "Meilisearch 启动超时，正在检查日志..."
                echo -e "${red}=== Meilisearch Systemd 日志 ===${reset}"
                journalctl -u meilisearch.service -n 50 --no-pager
                echo -e "${red}================================${reset}"
            fi
            sleep 1
        done
    else
        warn "Meilisearch 服务启动失败，正在尝试诊断..."
        echo -e "${red}=== Meilisearch Systemd 日志 ===${reset}"
        journalctl -u meilisearch.service -n 50 --no-pager
        echo -e "${red}================================${reset}"
        
        info "尝试前台直接运行以捕获错误..."
        # 尝试使用 strace 跟踪系统调用 (如果已安装)
        if command -v strace &> /dev/null; then
             warn "使用 strace 跟踪启动过程..."
             strace -f -o /tmp/meili_trace.log /usr/local/bin/meilisearch --master-key=${MEILI_MASTER_KEY} --env=production --db-path=/var/lib/meilisearch/data &
        else
             /usr/local/bin/meilisearch --master-key=${MEILI_MASTER_KEY} --env=production --db-path=/var/lib/meilisearch/data &
        fi
        
        MEILI_PID=$!
        sleep 5
        if ps -p $MEILI_PID > /dev/null; then
            success "Meilisearch 前台运行成功，可能是 Systemd 配置问题"
            kill $MEILI_PID
        else
            error "Meilisearch 无法运行，请检查上方输出错误信息"
        fi
    fi
elif [[ $HAS_SYSTEMD -eq 0 ]]; then
    warn "检测到非 systemd 环境，跳过 Meilisearch 服务配置"
    # 尝试直接启动
    info "尝试直接启动 Meilisearch..."
    nohup /usr/local/bin/meilisearch --master-key=${MEILI_MASTER_KEY} --env=production --db-path=/var/lib/meilisearch/data > /var/log/meilisearch.log 2>&1 &
    sleep 5
    if curl -s "http://localhost:7700/health" | grep -q "available"; then
        success "Meilisearch 已在后台启动"
    else
        error "Meilisearch 启动失败，请检查 /var/log/meilisearch.log"
    fi
fi

# 1.5 配置 Redis
info "检查 Redis 配置..."

REDIS_ALREADY_RUNNING=0
for candidate in 6379 6380 6381; do
    if redis-cli -h 127.0.0.1 -p ${candidate} ping >/dev/null 2>&1; then
        REDIS_PORT_SELECTED=$candidate
        REDIS_ALREADY_RUNNING=1
        break
    fi
    if ss -lnt 2>/dev/null | awk '{print $4}' | grep -q ":${candidate}$"; then
        continue
    fi
    REDIS_PORT_SELECTED=$candidate
    break
done
if ss -lnt 2>/dev/null | awk '{print $4}' | grep -q ":${REDIS_PORT_SELECTED}$"; then
    if [[ $REDIS_ALREADY_RUNNING -eq 0 ]]; then
        error "Redis 端口 ${REDIS_PORT_SELECTED} 已被占用，请先释放端口"
    fi
fi

# 预防性修复：强制 Redis 仅监听 IPv4 (解决 IPv6 缺失导致的启动失败)
if [[ -f /etc/redis/redis.conf ]]; then
    # 只要没有明确只绑定 127.0.0.1，就强制改写，防止 bind 127.0.0.1 ::1 引发问题
    if ! grep -q "^bind 127.0.0.1$" /etc/redis/redis.conf; then
        info "优化 Redis 网络配置 (强制 IPv4)..."
        cp /etc/redis/redis.conf /etc/redis/redis.conf.bak
        sed -i "s/^bind .*/bind 127.0.0.1/" /etc/redis/redis.conf
    fi
    if ! grep -q "^port ${REDIS_PORT_SELECTED}$" /etc/redis/redis.conf; then
        sed -i "s/^port .*/port ${REDIS_PORT_SELECTED}/" /etc/redis/redis.conf
    fi
    
    # 修复权限：无论是否修改过，都强制修复权限，防止因权限问题导致启动失败
    if id "redis" &>/dev/null; then
        info "修复 Redis 配置文件权限..."
        chown redis:redis /etc/redis/redis.conf
        chmod 640 /etc/redis/redis.conf
        if [[ -d /var/log/redis ]]; then
            chown -R redis:redis /var/log/redis
        fi
        
        if [[ ! -d /var/lib/redis ]]; then
            info "创建 Redis 数据目录..."
            mkdir -p /var/lib/redis
        fi
        chown -R redis:redis /var/lib/redis
        chmod 750 /var/lib/redis
        
        if [[ ! -d /run/redis ]]; then
            mkdir -p /run/redis
        fi
        chown -R redis:redis /run/redis
        chmod 755 /run/redis
    fi
fi

if [[ $REDIS_ALREADY_RUNNING -eq 1 ]]; then
    success "Redis 已在端口 ${REDIS_PORT_SELECTED} 运行"
elif [[ $HAS_SYSTEMD -eq 1 ]] && systemctl is-active --quiet redis-server; then
    success "Redis 服务运行正常"
else
    if [[ $HAS_SYSTEMD -eq 1 ]]; then
        info "启动 Redis 服务..."
        systemctl stop redis-server || true
        systemctl enable redis-server || true
        if ! systemctl start redis-server; then
            warn "Redis 服务启动失败，尝试重启..."
            systemctl restart redis-server || true
        fi
        if redis-cli -h 127.0.0.1 -p ${REDIS_PORT_SELECTED} ping >/dev/null 2>&1; then
            success "Redis 服务启动成功"
        else
            warn "Redis 服务启动失败，尝试直接启动 Redis 进程..."
            redis-server /etc/redis/redis.conf --daemonize yes || true
            sleep 1
            if redis-cli -h 127.0.0.1 -p ${REDIS_PORT_SELECTED} ping >/dev/null 2>&1; then
                warn "Redis 已通过直接进程启动，但 systemd 服务未就绪"
            else
                warn "Redis 服务启动失败，正在收集错误日志..."
                echo -e "${red}=== Redis 错误日志 (最后 20 行) ===${reset}"
                journalctl -xeu redis-server.service --no-pager | tail -n 20
                echo -e "${red}=====================================${reset}"
                error "Redis 服务无法启动，请根据上方日志排查问题。"
            fi
        fi
    else
        warn "检测到非 systemd 环境，尝试直接启动 Redis 进程"
        redis-server /etc/redis/redis.conf --daemonize yes || true
        sleep 1
        if redis-cli -h 127.0.0.1 -p ${REDIS_PORT_SELECTED} ping >/dev/null 2>&1; then
            success "Redis 服务启动成功"
        else
            error "Redis 服务无法启动，请检查 redis.conf 配置"
        fi
    fi
fi

# 等待 Redis 就绪
info "等待 Redis 服务就绪..."
for i in {1..10}; do
    if redis-cli -h 127.0.0.1 -p ${REDIS_PORT_SELECTED} ping >/dev/null 2>&1; then
        success "Redis 连接成功"
        break
    fi
    if [ $i -eq 10 ]; then
        warn "无法连接到 Redis (127.0.0.1:${REDIS_PORT_SELECTED})，后续步骤可能会失败"
    fi
    sleep 1
done

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
        info "项目目录已存在 Git 仓库，正在强制更新..."
        
        # 修复 git safe.directory 问题 (解决 dubious ownership 错误)
        if ! git config --global --get-all safe.directory | grep -q "^$PROJECT_DIR$"; then
            git config --global --add safe.directory "$PROJECT_DIR"
        fi
        
        cd "$PROJECT_DIR"
        DEPLOY_OLD_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || true)
        DEPLOY_OLD_DESC=$(git show -s --format="%ci %s" HEAD 2>/dev/null || true)
        # 强制更新到最新代码
        info "正在更新代码..."
        REMOTE_MASTER=$(git ls-remote "$REPO_URL" refs/heads/master 2>/dev/null | awk '{print $1}' | head -n 1 || true)
        REMOTE_MASTER_SHORT="${REMOTE_MASTER:0:7}"
        git fetch --all
        git reset --hard origin/master
        DEPLOY_NEW_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || true)
        DEPLOY_NEW_DESC=$(git show -s --format="%ci %s" HEAD 2>/dev/null || true)
    else
        info "正在克隆 Git 仓库..."
        # 尝试清理目标目录（如果存在但不是git仓库）
        if [ -d "$PROJECT_DIR" ]; then
            warn "目标目录 $PROJECT_DIR 已存在但不是 Git 仓库，正在备份..."
            mv "$PROJECT_DIR" "${PROJECT_DIR}_backup_$(date +%Y%m%d%H%M%S)"
        fi
        
        REMOTE_MASTER=$(git ls-remote "$REPO_URL" refs/heads/master 2>/dev/null | awk '{print $1}' | head -n 1 || true)
        REMOTE_MASTER_SHORT="${REMOTE_MASTER:0:7}"
        git clone "$REPO_URL" "$PROJECT_DIR"
        cd "$PROJECT_DIR"
        DEPLOY_NEW_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || true)
        DEPLOY_NEW_DESC=$(git show -s --format="%ci %s" HEAD 2>/dev/null || true)
    fi
    
    if [[ -f "$PROJECT_DIR/run_bot.py" ]]; then
        success "项目文件下载完成"
    else
        error "项目文件下载失败，请检查网络连接或手动上传文件"
    fi
fi

success "项目结构创建完成"
if [[ -d "$PROJECT_DIR/.git" ]]; then
    cd "$PROJECT_DIR"
    print_deploy_info "$DEPLOY_OLD_COMMIT" "$DEPLOY_NEW_COMMIT" "$DEPLOY_OLD_DESC" "$DEPLOY_NEW_DESC" "$REMOTE_MASTER_SHORT"
    echo "$DEPLOY_NEW_COMMIT" > "$PROJECT_DIR/.deploy_last_commit" || true
fi

# 步骤4: 创建Python虚拟环境
step "步骤 4/7: 创建Python虚拟环境"

cd "$PROJECT_DIR"

info "创建 Python 虚拟环境..."
$PYTHON_BIN -m venv .venv

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
    echo -e "${yellow}"
    read -p "请输入您的 Telegram Bot 用户名 (不含@，直接回车使用默认值): " USER_BOT_USERNAME
    echo -e "${reset}"
    if [[ -z "$USER_BOT_USERNAME" ]]; then
        USER_BOT_USERNAME="your_bot_username"
    fi

    cat > "$PROJECT_DIR/.env" << EOF
# =====================================
# 搜书神器 V2 - 环境配置
# =====================================

# Bot 配置
BOT_TOKEN=$USER_BOT_TOKEN
BOT_USERNAME=$USER_BOT_USERNAME
BOT_NAME=搜书神器 V2
BOT_VERSION=2.0.0

# 数据库配置
DATABASE_URL=postgresql+asyncpg://${DB_DEFAULT_USER}:${DB_DEFAULT_PASSWORD}@${DB_DEFAULT_HOST}:${DB_DEFAULT_PORT}/${DB_DEFAULT_NAME}
DB_HOST=${DB_DEFAULT_HOST}
DB_PORT=${DB_DEFAULT_PORT}
DB_NAME=${DB_DEFAULT_NAME}
DB_USER=${DB_DEFAULT_USER}
DB_PASSWORD=${DB_DEFAULT_PASSWORD}

# Redis 配置
REDIS_URL=redis://127.0.0.1:${REDIS_PORT_SELECTED}/0
REDIS_HOST=127.0.0.1
REDIS_PORT=${REDIS_PORT_SELECTED}
REDIS_DB=0

# Meilisearch 配置
MEILI_HOST=http://localhost:7700
MEILI_API_KEY=${MEILI_MASTER_KEY}
MEILI_INDEX_NAME=books

# 备份频道配置
BACKUP_CHANNEL_ID=-1001234567890

# 日志配置
LOG_LEVEL=INFO

# 开发配置
DEBUG=false
ENVIRONMENT=production
EOF

    chmod 640 "$PROJECT_DIR/.env"
    if [[ -n "$SUDO_USER" ]]; then
        chown "$SUDO_USER":"$SUDO_USER" "$PROJECT_DIR/.env"
    fi
    success "环境配置文件创建完成"
    warn "请编辑 .env 文件并填写正确的配置值"
else
    info "环境配置文件已存在，跳过创建"
    sed -i 's/\r$//' "$PROJECT_DIR/.env"
    sed -i 's/[[:space:]]*$//' "$PROJECT_DIR/.env"
    if [[ -n "$SUDO_USER" ]]; then
        chown "$SUDO_USER":"$SUDO_USER" "$PROJECT_DIR/.env"
        chmod 640 "$PROJECT_DIR/.env"
    fi
    if ! grep -q "^BOT_TOKEN=" "$PROJECT_DIR/.env"; then
        echo -e "${yellow}"
        read -p "请输入您的 Telegram Bot Token: " USER_BOT_TOKEN
        echo -e "${reset}"
        if [[ -z "$USER_BOT_TOKEN" ]]; then
            error "BOT_TOKEN 不能为空，请补充后重试"
        fi
        echo "BOT_TOKEN=$USER_BOT_TOKEN" >> "$PROJECT_DIR/.env"
    fi
    if ! grep -q "^BOT_USERNAME=" "$PROJECT_DIR/.env"; then
        echo -e "${yellow}"
        read -p "请输入您的 Telegram Bot 用户名 (不含@): " USER_BOT_USERNAME
        echo -e "${reset}"
        if [[ -z "$USER_BOT_USERNAME" ]]; then
            error "BOT_USERNAME 不能为空，请补充后重试"
        fi
        echo "BOT_USERNAME=$USER_BOT_USERNAME" >> "$PROJECT_DIR/.env"
    fi
    if ! grep -q "^DB_PASSWORD=" "$PROJECT_DIR/.env"; then
        echo "DB_PASSWORD=${DB_DEFAULT_PASSWORD}" >> "$PROJECT_DIR/.env"
    fi
    if ! grep -q "^DB_USER=" "$PROJECT_DIR/.env"; then
        echo "DB_USER=${DB_DEFAULT_USER}" >> "$PROJECT_DIR/.env"
    fi
    if ! grep -q "^DB_NAME=" "$PROJECT_DIR/.env"; then
        echo "DB_NAME=${DB_DEFAULT_NAME}" >> "$PROJECT_DIR/.env"
    fi
    if ! grep -q "^DB_HOST=" "$PROJECT_DIR/.env"; then
        echo "DB_HOST=${DB_DEFAULT_HOST}" >> "$PROJECT_DIR/.env"
    fi
    if ! grep -q "^DB_PORT=" "$PROJECT_DIR/.env"; then
        echo "DB_PORT=${DB_DEFAULT_PORT}" >> "$PROJECT_DIR/.env"
    fi
    if ! grep -q "^MEILI_API_KEY=" "$PROJECT_DIR/.env"; then
        echo "MEILI_API_KEY=${MEILI_MASTER_KEY}" >> "$PROJECT_DIR/.env"
    else
        # 更新已存在的 KEY
        sed -i "s/^MEILI_API_KEY=.*/MEILI_API_KEY=${MEILI_MASTER_KEY}/" "$PROJECT_DIR/.env"
    fi
    if grep -q "^REDIS_PORT=" "$PROJECT_DIR/.env"; then
        sed -i "s/^REDIS_PORT=.*/REDIS_PORT=${REDIS_PORT_SELECTED}/" "$PROJECT_DIR/.env"
    else
        echo "REDIS_PORT=${REDIS_PORT_SELECTED}" >> "$PROJECT_DIR/.env"
    fi
    if grep -q "^REDIS_URL=" "$PROJECT_DIR/.env"; then
        sed -i "s#^REDIS_URL=.*#REDIS_URL=redis://127.0.0.1:${REDIS_PORT_SELECTED}/0#" "$PROJECT_DIR/.env"
    else
        echo "REDIS_URL=redis://127.0.0.1:${REDIS_PORT_SELECTED}/0" >> "$PROJECT_DIR/.env"
    fi
    if grep -q "^DATABASE_URL=" "$PROJECT_DIR/.env"; then
        sed -i "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+asyncpg://$(env_get DB_USER):$(env_get DB_PASSWORD)@$(env_get DB_HOST):$(env_get DB_PORT)/$(env_get DB_NAME)#" "$PROJECT_DIR/.env"
    else
        echo "DATABASE_URL=postgresql+asyncpg://$(env_get DB_USER):$(env_get DB_PASSWORD)@$(env_get DB_HOST):$(env_get DB_PORT)/$(env_get DB_NAME)" >> "$PROJECT_DIR/.env"
    fi
fi

DB_USER_EFFECTIVE=$(env_get DB_USER)
DB_NAME_EFFECTIVE=$(env_get DB_NAME)
DB_PASSWORD_EFFECTIVE=$(env_get DB_PASSWORD)
DB_HOST_EFFECTIVE=$(env_get DB_HOST)
DB_PORT_EFFECTIVE=$(env_get DB_PORT)
if [[ -z "$DB_USER_EFFECTIVE" ]]; then DB_USER_EFFECTIVE="$DB_DEFAULT_USER"; fi
if [[ -z "$DB_NAME_EFFECTIVE" ]]; then DB_NAME_EFFECTIVE="$DB_DEFAULT_NAME"; fi
if [[ -z "$DB_PASSWORD_EFFECTIVE" ]]; then DB_PASSWORD_EFFECTIVE="$DB_DEFAULT_PASSWORD"; fi
if [[ -z "$DB_HOST_EFFECTIVE" ]]; then DB_HOST_EFFECTIVE="$DB_DEFAULT_HOST"; fi
if [[ -z "$DB_PORT_EFFECTIVE" ]]; then DB_PORT_EFFECTIVE="$DB_DEFAULT_PORT"; fi

info "检查 PostgreSQL 配置..."
if [[ $HAS_SYSTEMD -eq 1 ]] && systemctl is-active --quiet postgresql; then
    sleep 2
    if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER_EFFECTIVE}'" | grep -q 1; then
        info "创建数据库用户 ${DB_USER_EFFECTIVE}..."
        DB_PASSWORD_SQL=${DB_PASSWORD_EFFECTIVE//\'/\'\'}
        sudo -u postgres psql -c "CREATE USER ${DB_USER_EFFECTIVE} WITH PASSWORD '${DB_PASSWORD_SQL}';"
    fi
    DB_PASSWORD_SQL=${DB_PASSWORD_EFFECTIVE//\'/\'\'}
    sudo -u postgres psql -c "ALTER USER ${DB_USER_EFFECTIVE} WITH PASSWORD '${DB_PASSWORD_SQL}';" || true
    if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME_EFFECTIVE}'" | grep -q 1; then
        info "创建数据库 ${DB_NAME_EFFECTIVE}..."
        sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME_EFFECTIVE} OWNER ${DB_USER_EFFECTIVE};"
    fi
    if ! PGPASSWORD="${DB_PASSWORD_EFFECTIVE}" psql -h "${DB_HOST_EFFECTIVE}" -p "${DB_PORT_EFFECTIVE}" -U "${DB_USER_EFFECTIVE}" -d "${DB_NAME_EFFECTIVE}" -c "select 1" >/dev/null 2>&1; then
        warn "检测到数据库连接失败，正在自动修复密码..."
        DB_PASSWORD_EFFECTIVE="bookbot$(date +%s)${RANDOM}"
        DB_PASSWORD_SQL=${DB_PASSWORD_EFFECTIVE//\'/\'\'}
        sudo -u postgres psql -c "ALTER USER ${DB_USER_EFFECTIVE} WITH PASSWORD '${DB_PASSWORD_SQL}';"
        if grep -q "^DB_PASSWORD=" "$PROJECT_DIR/.env"; then
            sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=${DB_PASSWORD_EFFECTIVE}/" "$PROJECT_DIR/.env"
        else
            echo "DB_PASSWORD=${DB_PASSWORD_EFFECTIVE}" >> "$PROJECT_DIR/.env"
        fi
        if grep -q "^DATABASE_URL=" "$PROJECT_DIR/.env"; then
            sed -i "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+asyncpg://${DB_USER_EFFECTIVE}:${DB_PASSWORD_EFFECTIVE}@${DB_HOST_EFFECTIVE}:${DB_PORT_EFFECTIVE}/${DB_NAME_EFFECTIVE}#" "$PROJECT_DIR/.env"
        else
            echo "DATABASE_URL=postgresql+asyncpg://${DB_USER_EFFECTIVE}:${DB_PASSWORD_EFFECTIVE}@${DB_HOST_EFFECTIVE}:${DB_PORT_EFFECTIVE}/${DB_NAME_EFFECTIVE}" >> "$PROJECT_DIR/.env"
        fi
        if ! PGPASSWORD="${DB_PASSWORD_EFFECTIVE}" psql -h "${DB_HOST_EFFECTIVE}" -p "${DB_PORT_EFFECTIVE}" -U "${DB_USER_EFFECTIVE}" -d "${DB_NAME_EFFECTIVE}" -c "select 1" >/dev/null 2>&1; then
            error "数据库认证仍失败，请检查 PostgreSQL 的认证配置"
        fi
    fi
    success "PostgreSQL 配置完成"
else
    if [[ $HAS_SYSTEMD -eq 1 ]]; then
        warn "PostgreSQL 未运行，跳过自动配置"
    else
        warn "检测到非 systemd 环境，跳过 PostgreSQL 自动配置"
    fi
fi

# 步骤6: 设置systemd服务
step "步骤 6/7: 设置systemd服务"

if [[ $HAS_SYSTEMD -eq 1 ]]; then
    info "创建systemd服务文件..."

    # Bot服务
    cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=搜书神器 V2 - Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/.venv/bin
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONFAULTHANDLER=1
ExecStartPre=/bin/bash -lc 'cd $PROJECT_DIR && echo "VERSION \$(git rev-parse --short HEAD 2>/dev/null) \$(git show -s --format=%ci 2>/dev/null)"'
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/run_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # Worker服务
    cat > /etc/systemd/system/${WORKER_SERVICE_NAME}.service << EOF
[Unit]
Description=搜书神器 V2 - Background Worker
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/.venv/bin
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONFAULTHANDLER=1
ExecStartPre=/bin/bash -lc 'cd $PROJECT_DIR && echo "VERSION \$(git rev-parse --short HEAD 2>/dev/null) \$(git show -s --format=%ci 2>/dev/null)"'
ExecStart=$PROJECT_DIR/.venv/bin/arq app.worker.WorkerSettings
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # 重新加载systemd
    systemctl daemon-reload

    # 启用服务
    systemctl enable ${SERVICE_NAME}.service
    systemctl enable ${WORKER_SERVICE_NAME}.service

    success "systemd服务配置完成"
else
    warn "检测到非 systemd 环境，跳过 systemd 服务配置"
fi

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

if [[ $HAS_SYSTEMD -eq 1 ]]; then
    info "启动服务..."
    # 使用 restart 确保代码更新后服务重启
    systemctl restart ${SERVICE_NAME}
    systemctl restart ${WORKER_SERVICE_NAME}
else
    warn "检测到非 systemd 环境，跳过服务启动"
fi

# 检查服务状态
if [[ $HAS_SYSTEMD -eq 1 ]]; then
    sleep 3
    if systemctl is-active --quiet ${SERVICE_NAME}; then
        success "Bot 服务启动成功"
    else
        warn "Bot 服务启动失败，请使用 systemctl status ${SERVICE_NAME} 查看日志"
    fi

    if systemctl is-active --quiet ${WORKER_SERVICE_NAME}; then
        success "Worker 服务启动成功"
    else
        warn "Worker 服务启动失败，请使用 systemctl status ${WORKER_SERVICE_NAME} 查看日志"
    fi
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
if [[ -n "$DEPLOY_NEW_COMMIT" ]]; then
    echo -e "${green}部署版本:${reset} $DEPLOY_NEW_COMMIT"
fi
echo ""
echo -e "${green}服务状态:${reset}"
systemctl status ${SERVICE_NAME} --no-pager | grep "Active:" || true
systemctl status ${WORKER_SERVICE_NAME} --no-pager | grep "Active:" || true
echo ""

success "所有服务已启动，您可以开始使用了！"

# 清理
rm -f $0

exit 0

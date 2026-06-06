#!/bin/bash
# Accounting CLI 安装脚本

set -e

echo "==================================="
echo "  Accounting CLI 安装脚本"
echo "==================================="
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_DIR="$SCRIPT_DIR/python"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3"
    exit 1
fi

echo "✓ 找到 Python: $(python3 --version)"

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo "错误: 未找到 pip3，请先安装 pip"
    exit 1
fi

echo "✓ 找到 pip"

# 安装依赖
echo ""
echo "正在安装依赖..."
cd "$PYTHON_DIR"
pip3 install -r requirements.txt
echo "✓ 依赖安装完成"

# 创建数据目录
echo ""
echo "创建数据目录..."
mkdir -p "$HOME/.accounting/data"
mkdir -p "$HOME/.accounting/backups/primary"
mkdir -p "$HOME/.accounting/backups/secondary"
echo "✓ 数据目录已创建"

# 检查是否有旧数据需要迁移
OLD_DB="$SCRIPT_DIR/data/accounting.db"
if [ -f "$OLD_DB" ]; then
    echo ""
    echo "发现旧数据，是否迁移？"
    read -p "(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 "$PYTHON_DIR/migrate_data.py"
    fi
fi

# 设置别名
echo ""
echo "设置命令别名..."

# 检测 shell 配置文件
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
else
    SHELL_RC="$HOME/.profile"
fi

# 创建包装脚本
WRAPPER="$HOME/.accounting/acc"
cat > "$WRAPPER" << 'EOF'
#!/bin/bash
python3 "$SCRIPT_DIR/python/main.py" "$@"
EOF
chmod +x "$WRAPPER"

# 把 SCRIPT_DIR 替换成实际路径
sed -i "s|\\$SCRIPT_DIR|$SCRIPT_DIR|g" "$WRAPPER"

# 添加别名到配置文件
ALIAS_CMD="alias acc='$WRAPPER'"
if ! grep -q "alias acc=" "$SHELL_RC"; then
    echo "" >> "$SHELL_RC"
    echo "# Accounting CLI" >> "$SHELL_RC"
    echo "$ALIAS_CMD" >> "$SHELL_RC"
    echo "✓ 已添加别名到 $SHELL_RC"
else
    echo "✓ 别名已存在"
fi

echo ""
echo "==================================="
echo "  安装完成！"
echo "==================================="
echo ""
echo "使用方法："
echo "  1. 重新加载终端或执行: source $SHELL_RC"
echo "  2. 然后就可以使用: acc"
echo ""
echo "快速开始："
echo "  acc add 早餐 -25"
echo "  acc list"
echo "  acc balance"
echo ""
echo "AI 功能（需要 Ollama）："
echo "  acc chat 我这个月花了多少钱"
echo "  acc analyze report"
echo ""
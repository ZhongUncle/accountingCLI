# Accounting CLI

<p align="center">
  <a href="#"><img src="https://github.com/zhonguncle/accountingCLI/actions/workflows/test.yml/badge.svg" alt="Build Status"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python 3.9+"></a>
  <a href="#"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
</p>

> 📖 **English Documentation**: For English documentation, please see [README.md](README.md)

一个功能强大的命令行记账工具，支持多账户管理、余额自动计算、支付宝/微信账单导入、以及 AI 财务分析。

## 功能特性

- ✅ **多账户管理** - 总账户、银行卡、支付宝、微信
- ✅ **余额自动计算** - 每笔交易都记录运行余额，插入历史记录自动重算
- ✅ **智能分类** - 根据描述自动推断分类
- ✅ **标签系统** - 灵活的标签管理
- ✅ **CSV导入** - 支持支付宝、微信、通用CSV导入
- ✅ **数据导出** - JSON/CSV格式导出
- ✅ **统计报告** - 分类统计、ASCII图表
- ✅ **AI语义搜索** - 基于句子嵌入的智能搜索
- ✅ **AI财务分析** - 智能分析、生成报告、预算建议
- ✅ **备份管理** - 自动多位置备份
- ✅ **用户数据隔离** - 数据保存在 `~/.accounting/`，每个人独立

## 快速开始

### 方法 1: 安装脚本（推荐）

```bash
# 克隆项目
git clone <repository-url>
cd accountingCLI

# 运行安装脚本
./install.sh

# 重新加载终端配置
source ~/.zshrc  # 或 ~/.bashrc

# 开始使用！
acc --help
```

### 方法 2: 直接使用

```bash
# 克隆项目
git clone <repository-url>
cd accountingCLI

# 安装依赖
cd python
pip install -r requirements.txt
cd ..

# 直接运行
./acc.sh --help
```

## 基本用法

### 1. 设置初始余额（推荐）

```bash
# 设置所有账户的当前余额
acc set-all-balances "总账户=12589.92" "银行卡=592.67" "支付宝=11897.08" "微信=100.17"
```

### 2. 添加交易

```bash
# 添加支出
acc add 早餐 -25 --category "餐饮" --account "微信"

# 添加收入
acc add 工资 +8000 --category "工资" --account "银行卡"
```

### 3. 查看记录

```bash
# 查看所有记录
acc list

# 查看本月记录
acc list --month

# 查看本周记录
acc list --week

# 按账户过滤
acc list --account "支付宝"

# 按分类过滤
acc list --category "餐饮"

# 按标签过滤
acc list --tag "早餐"

# 限制返回条数
acc list --limit 10
```

### 4. 查看余额

```bash
acc balance
```

### 5. 统计分析

```bash
# 查看本月统计
acc stats --month

# 按分类统计（带图表）
acc stats --category
```

### 6. AI 财务分析

需要先安装并启动 Ollama:

```bash
# 安装 Ollama: https://ollama.com
# 拉取模型
ollama pull gemma4:e4b

# 与 AI 对话分析
acc chat "我这个月花了多少钱"

# 禁用思考链路（更快响应）
acc chat "我这个月花了多少钱" --nothink

# 指定上下文大小
acc chat "我这个月花了多少钱" --ctx-size 64k

# 指定使用的模型
acc chat "我这个月花了多少钱" --model llama3:8b

# 生成财务分析报告
acc analyze report --month

# 生成预算建议
acc analyze budget --month
```

## 导入账单

### ⚠️ 重要：先设置当前余额

导入账单前，**必须先设置账户的当前余额**。系统使用**倒序导入法**：
1. 先设置账户的当前余额
2. 从最新交易开始导入
3. 自动倒推每笔交易后的余额

### 支付宝账单

```bash
# 先设置支付宝余额
acc set-all-balances "支付宝=11897.08"

# 导入支付宝账单（自动检测格式，默认跳过重复）
acc import detect /path/to/alipay_record.csv

# 或显式指定来源
acc import csv /path/to/alipay_record.csv --source alipay

# 导入并替换重复交易
acc import csv /path/to/alipay_record.csv --source alipay --mode replace

# 导入并保留重复交易
acc import csv /path/to/alipay_record.csv --source alipay --mode keep_both
```

### 微信账单

```bash
# 先设置微信余额
acc set-all-balances "微信=100.17"

# 导入微信账单（自动检测格式，默认跳过重复）
acc import detect /path/to/wechat_record.csv

# 或显式指定来源
acc import csv /path/to/wechat_record.csv --source wechat

# 导入并替换重复交易
acc import csv /path/to/wechat_record.csv --source wechat --mode replace

# 导入并保留重复交易
acc import csv /path/to/wechat_record.csv --source wechat --mode keep_both
```

## 完整命令参考

### 交易管理

| 命令 | 说明 |
|------|------|
| `add <描述> <金额>` | 添加交易（默认添加到最新） |
| `insert <日期> <描述> <金额>` | 插入历史记录（自动重算余额） |
| `list [--month/--week]` | 列出交易记录 |
| `list --account <账户>` | 按账户过滤 |
| `list --category <分类>` | 按分类过滤 |
| `list --tag <标签>` | 按标签过滤 |
| `list --limit <数量>` | 限制返回条数 |

### 余额管理

| 命令 | 说明 |
|------|------|
| `balance` | 查看所有账户余额 |
| `balance --account <账户>` | 查看指定账户余额 |
| `set-balance <账户> <余额>` | 设置单个账户余额 |
| `set-all-balances "账户1=余额1" ...` | 设置多个账户余额（推荐） |
| `set-all-balances ... --create-initial-tx` | 创建初始余额交易（不推荐） |
| `recalculate-balances` | 从当前余额倒推重算所有交易余额 |

#### 💡 recalculate-balances 工作原理

这个命令会：
1. 读取账户的当前余额
2. 从最新交易开始，倒推历史每笔交易的余额
3. 更新所有交易的 `running_balance` 字段

**使用场景**：
- 导入账单后余额不对
- 手动修改数据库后
- 余额计算出现问题时

### 导入导出

| 命令 | 说明 |
|------|------|
| `import template <文件>` | 生成 CSV 导入模板 |
| `import csv <文件> [--source auto/alipay/wechat/generic] [--mode MODE]` | 从 CSV 导入（默认自动检测 |
| `import detect <文件> [--mode MODE]` | 自动检测格式导入（`import csv` 别名） |
| `export json <文件>` | 导出为 JSON |
| `export csv <文件>` | 导出为 CSV |

#### 导入模式 (--mode)

| 模式 | 说明 |
|------|------|
| `skip` | 跳过重复交易（默认） |
| `replace` | 替换已存在的重复交易 |
| `keep_both` | 保留新旧两条交易 |

### 标签管理

| 命令 | 说明 |
|------|------|
| `tag list` | 列出所有标签 |

添加标签时使用：
```bash
acc add 早餐 -25 --tags 早餐 食堂
```

### 统计分析

| 命令 | 说明 |
|------|------|
| `stats [--month]` | 查看统计报告 |
| `stats --category` | 按分类统计（带图表） |

### AI 功能

| 命令 | 说明 |
|------|------|
| `search <关键词> [--top N]` | 语义搜索交易记录 |
| `embed compute` | 计算所有交易的 embedding 向量 |
| `embed status` | 查看 embedding 覆盖率 |
| `chat <问题> [--nothink] [--ctx-size SIZE] [--model MODEL]` | 🤖 与 AI 智能体对话 |
| `analyze report [--month] [--ctx-size SIZE] [--model MODEL]` | 生成财务分析报告 |
| `analyze budget [--month] [--ctx-size SIZE] [--model MODEL]` | 生成预算建议 |

#### AI 功能依赖

需要安装：
1. **Ollama**: https://ollama.com
2. 拉取模型：
   ```bash
   ollama pull gemma4:e4b  # 默认模型
   # 或其他模型
   ollama pull llama3:8b
   ollama pull qwen2:7b
   ```

#### 上下文大小 (--ctx-size)

支持格式：
- `8k`, `32k`, `64k`, `128k`, `256k`
- 或直接指定数字：`32768`

不指定时使用模型默认值。

### 备份管理

| 命令 | 说明 |
|------|------|
| `backup create` | 创建数据库备份 |
| `backup list` | 列出所有备份 |
| `backup restore <文件>` | 从备份恢复 |

#### 自动备份机制

每次添加交易时，系统会自动备份到：
1. `~/.accounting/backups/primary/`
2. `~/.accounting/backups/secondary/`

备份文件命名格式：`accounting_YYYYMMDD_HHMMSS.db`

## 智能分类规则

系统会根据交易描述自动推断分类：

### 支付宝分类规则

| 交易类型 | 关键词 | 分类 |
|---------|--------|------|
| 转账 | 转账、提现 | 转账 |
| 理财 | 基金、余额宝、理财 | 投资收益 |
| 消费 | 美团、饿了么、外卖 | 餐饮 |
| 出行 | 滴滴、高德、地铁、公交 | 打车/地铁 |
| 购物 | 淘宝、天猫、京东 | 日用品 |

### 微信分类规则

| 交易类型 | 关键词 | 分类 |
|---------|--------|------|
| 微信红包 | 红包 | 红包 |
| 转账 | 转账 | 人情往来 |
| 理财通 | 理财 | 投资收益 |
| Q币 | Q币、游戏 | 游戏 |

### 通用分类关键词

| 分类 | 关键词 |
|------|--------|
| 餐饮 | 餐、饭、外卖、咖啡、奶茶、饮料、烘焙、蛋糕 |
| 交通 | 滴滴、出行、打车、地铁、公交、高铁、火车、飞机、加油、停车 |
| 购物 | 淘宝、京东、超市、便利店、购物、网购 |
| 娱乐 | 电影、游戏、KTV、聚会、演出、会员 |
| 居住 | 房租、水电、燃气、物业、网费、话费 |
| 医疗 | 医院、看病、药、体检、挂号 |
| 教育 | 课程、书籍、学习、培训、考试 |

## 数据位置

所有数据保存在用户主目录下：

```
~/.accounting/
├── data/
│   └── accounting.db      # 数据库文件
└── backups/
    ├── primary/           # 主备份
    └── secondary/         # 副备份
```

## 数据库说明

### 核心表

#### `accounts` - 账户表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | TEXT | 账户名称（唯一） |
| type | TEXT | 账户类型 |
| balance | REAL | 余额 |
| currency | TEXT | 货币 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

#### `transactions` - 交易记录表（核心）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| date | TEXT | 日期（YYYY-MM-DD） |
| type | TEXT | 类型（expense/income） |
| amount | REAL | 金额（正数） |
| running_balance | REAL | 该笔交易后的余额（关键字段） |
| category_id | INTEGER | 分类ID |
| account_id | INTEGER | 账户ID |
| description | TEXT | 描述 |
| metadata | TEXT | JSON格式的元数据 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

### ⚠️ 手动修改数据库注意事项

1. **修改后记得重新计算余额**
   ```bash
   acc recalculate-balances
   ```

2. **先备份！**
   ```bash
   cp ~/.accounting/data/accounting.db ~/.accounting/data/accounting.db.backup
   ```

3. **使用 SQLite 工具**
   ```bash
   sqlite3 ~/.accounting/data/accounting.db
   ```

## 开发路线图

### 🚀 进行中
- [ ] **FastAPI 后端** - 为 AccountingService 封装 REST API（支持 Web/移动端前端）
- [ ] **React Web 界面** - 现代化 Web 界面，可视化财务数据

### 📋 计划中
- [ ] 桌面 GUI（PySide6 / Tauri）
- [ ] 更多银行导入插件
- [ ] 订阅管理功能增强
- [ ] 预算提醒与通知
- [ ] 小票 OCR 识别集成
- [ ] 移动端 App（React Native / Flutter）

### ✅ 已完成
- [x] 核心记账引擎（倒推余额算法）
- [x] 多账户管理
- [x] 支付宝、微信 CSV 导入器
- [x] 自定义导入器插件架构
- [x] Ollama AI 集成（对话分析、报告、预算建议）
- [x] 基于 embedding 的语义搜索
- [x] 数据导入/导出（JSON/CSV）
- [x] 备份管理系统
- [x] 完整测试套件（25个测试用例）
- [x] GitHub Actions CI/CD

## 从旧版本迁移

如果你之前使用过旧版本（数据在项目目录下），运行迁移脚本：

```bash
cd python
python3 migrate_data.py
```

或者直接运行安装脚本，它会自动检测并提示迁移。

迁移脚本支持参数：
```bash
# 自动确认所有提示
python3 migrate_data.py --yes
```

## 分类系统

### 支出分类

餐饮、地铁、打车、公交、加油、高铁、飞机、停车费、共享单车、日用品、服装、电子产品、杂项、家居、电影、游戏、聚会、会员订阅、旅游、房租、水电、物业、燃气、网费、话费、流量套餐、药品、体检、挂号、书籍、课程、AI会员、学习资料、红包、转账、捐赠

### 收入分类

工资、奖金、投资收益、兼职、红包、退款、其他

## 常见问题

### Q: 导入后余额不对怎么办？

A: 使用 `recalculate-balances` 命令重新计算：

```bash
# 先设置正确的余额
acc set-all-balances "支付宝=11897.08"

# 自动倒推重算
acc recalculate-balances
```

### Q: AI 功能需要什么？

A: 需要安装 Ollama 并拉取模型：

```bash
# 安装 Ollama: https://ollama.com
# 拉取模型
ollama pull gemma4:e4b
```

### Q: 可以分享给别人使用吗？

A: 可以！只需要把项目分享给别人，他们运行 `./install.sh` 就可以使用了。每个人的数据都保存在自己的 `~/.accounting/` 目录下，互不干扰。

### Q: --nothink 参数有什么用？

A: `--nothink`（或 `--no-think`）会禁用 AI 的思考链路，直接给出答案。这样响应更快，但可能会降低准确性。

### Q: embedding 功能有什么依赖？

A: 需要安装：
```bash
pip install numpy requests
```

并启动 Ollama。

## 许可证

MIT License
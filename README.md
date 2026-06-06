# Accounting CLI

<p align="center">
  <a href="#"><img src="https://github.com/zhonguncle/accountingCLI/actions/workflows/test.yml/badge.svg" alt="Build Status"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python 3.9+"></a>
  <a href="#"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
</p>

AI-powered local accounting tool. Take control of your finances - import bank statements, get automated analysis, make data-driven decisions. 100% offline, zero data upload.

> 📖 **Chinese Documentation**: For detailed documentation in Chinese, please see [中文文档](README.zh-CN.md)

## Features

- ✅ **Multi-Account Management** - Summary, Bank Cards, E-wallets
- ✅ **Automatic Balance Calculation** - Running balance per transaction, auto-recalculate on historical inserts
- ✅ **Smart Categorization** - AI-powered category inference from descriptions
- ✅ **Tag System** - Flexible tag management
- ✅ **Extensible Importers** - Plugin architecture for any bank/platform
- ✅ **Built-in Importers** - CSV support for popular payment platforms
- ✅ **Data Export** - JSON/CSV format export
- ✅ **Statistics & Reports** - Category breakdown with ASCII charts
- ✅ **AI Semantic Search** - Smart search powered by sentence embeddings
- ✅ **AI Financial Analysis** - Intelligent analysis, report generation, budget suggestions
- ✅ **Backup Management** - Automatic multi-location backups
- ✅ **User Data Isolation** - Data stored in `~/.accounting/`, private to each user
- ✅ **100% Local** - Everything runs on your machine, no cloud, no tracking

## Quick Start

### Method 1: Install Script (Recommended)

```bash
# Clone the repository
git clone https://github.com/ZhongUncle/accountingCLI.git
cd accountingCLI

# Run the install script
./install.sh

# Reload your shell config
source ~/.zshrc  # or ~/.bashrc

# Start using!
acc --help
```

### Method 2: Direct Usage

```bash
# Clone the repository
git clone https://github.com/ZhongUncle/accountingCLI.git
cd accountingCLI

# Install dependencies
cd python
pip install -r requirements.txt
cd ..

# Run directly
./acc.sh --help
```

## Basic Usage

### 1. Set Initial Balance (Recommended)

```bash
# Set current balance for all accounts
acc set-all-balances "Summary=12589.92" "Bank=592.67" "E-Wallet-A=11897.08" "E-Wallet-B=100.17"
```

### 2. Add Transactions

```bash
# Add expense
acc add Breakfast -25 --category "Food" --account "E-Wallet-B"

# Add income
acc add Salary +8000 --category "Salary" --account "Bank"
```

### 3. View Records

```bash
# View all records
acc list

# View this month's records
acc list --month

# View this week's records
acc list --week

# Filter by account
acc list --account "E-Wallet-A"

# Filter by category
acc list --category "Food"

# Filter by tag
acc list --tag "breakfast"

# Limit results
acc list --limit 10
```

### 4. View Balance

```bash
acc balance
```

### 5. Statistics & Analysis

```bash
# View monthly stats
acc stats --month

# Category breakdown with charts
acc stats --category
```

### 6. AI Financial Analysis

Requires Ollama installed and running:

```bash
# Install Ollama: https://ollama.com
# Pull the model
ollama pull gemma4:e4b

# Chat with AI about your finances
acc chat "How much did I spend this month?"

# Disable thinking chain (faster responses)
acc chat "How much did I spend this month?" --nothink

# Specify context size
acc chat "How much did I spend this month?" --ctx-size 64k

# Specify model
acc chat "How much did I spend this month?" --model llama3:8b

# Generate financial analysis report
acc analyze report --month

# Generate budget suggestions
acc analyze budget --month
```

## Import Financial Data

### ⚠️ Important: Set Current Balance First

**Always set your account balance before importing.** The system uses **reverse calculation**:
1. Set your account's current balance
2. Import transactions starting from the newest
3. Balances are automatically calculated backwards

### Using Built-in Importers

Import plugins are included for popular payment platforms. Check available importers:

```bash
# Auto-detect format and import
acc import detect /path/to/statement.csv
```

See [PLUGIN_ARCHITECTURE.md](PLUGIN_ARCHITECTURE.md) for creating custom importers for your bank.

## Complete Command Reference

### Transaction Management

| Command | Description |
|---------|-------------|
| `add <description> <amount>` | Add transaction (appends to latest) |
| `insert <date> <description> <amount>` | Insert historical record (auto-recalculates balances) |
| `list [--month/--week]` | List transaction records |
| `list --account <account>` | Filter by account |
| `list --category <category>` | Filter by category |
| `list --tag <tag>` | Filter by tag |
| `list --limit <count>` | Limit number of results |

### Balance Management

| Command | Description |
|---------|-------------|
| `balance` | Show current balances for all accounts |
| `set-balance <account> <amount> [date]` | Set account balance |
| `set-all-balances <account=amount>...` | Set multiple account balances |
| `recalculate-balances` | Recalculate all running balances |

### Data Import

| Command | Description |
|---------|-------------|
| `import template <file>` | Generate CSV import template |
| `import csv <file> [--source auto/alipay/wechat/generic]` | Import from CSV (auto-detect by default) |
| `import detect <file>` | Auto-detect format and import (alias for `import csv`) |

### AI Features

| Command | Description |
|---------|-------------|
| `chat <question>` | Chat about your finances with AI |
| `analyze report [--month/--week]` | Generate financial analysis report |
| `analyze budget [--month/--week]` | Generate budget suggestions |

### Tag & Subscription Management

| Command | Description |
|---------|-------------|
| `tag list` | List all tags |
| `subscription list` | List all subscriptions |

### Data Management

| Command | Description |
|---------|-------------|
| `export json <file>` | Export transactions to JSON file |
| `export csv <file>` | Export transactions to CSV file |
| `backup create` | Create database backup |
| `backup list` | List available backups |
| `backup restore <file>` | Restore from backup |

### Semantic Search & Embedding

| Command | Description |
|---------|-------------|
| `search <query> [--top N]` | Semantic search in transactions |
| `embed compute` | Compute embeddings for all transactions |
| `embed status` | Check embedding coverage |

## Smart Categorization Rules

The system automatically infers categories based on transaction descriptions:

- **Food**: Breakfast, Lunch, Dinner, Restaurant
- **Transportation**: Subway, Bus, Taxi, Train, Flight
- **Entertainment**: Movies, Games, Parties
- **Shopping**: Groceries, Clothing, Electronics
- **Memberships**: VIP, Subscription, Premium
- **Income**: Salary, Bonus, Investment returns

## Data Location

All user data is stored in your home directory for privacy:

```
~/.accounting/
├── data/
│   └── accounting.db      # Main SQLite database
├── backups/               # Auto-backups directory
└── plugins/               # Custom importer plugins
```

## Database Schema

SQLite database with the following core tables:

- `accounts` - Account information and current balances
- `categories` - Transaction categories with hierarchy
- `transactions` - Individual transactions (with running balance)
- `tags` - Tags for flexible categorization
- `transaction_tags` - Transaction-tag junction table
- `subscriptions` - Recurring subscription tracking

### Reverse Balance Calculation

One of the key features is the **reverse balance calculation algorithm**:

1. Set your current account balance
2. Import transactions from newest to oldest
3. The system calculates backwards to determine each transaction's running balance
4. This ensures perfect accuracy even with missing historical data

## Plugin Architecture

AccountingCLI features a plugin-based importer system for extensibility.

### Core Components

1. **BaseImporter** - Abstract base class defining the interface
2. **ImportManager** - Plugin discovery, registration, and management
3. **Built-in Importers** - Generic CSV plus popular payment platforms
4. **External Plugins** - Auto-loaded from `~/.accounting/plugins/`

### Creating Custom Importers

Simply create a Python file in `~/.accounting/plugins/`:

```python
from src.importers.base import BaseImporter, ImportResult

class MyBankImporter(BaseImporter):
    name = "mybank"
    display_name = "My Bank"
    
    def can_handle(self, filepath: str) -> bool:
        with open(filepath, 'r', encoding='utf-8') as f:
            return "My Bank" in f.readline()
    
    def import_file(self, filepath: str, mode: str = "skip") -> ImportResult:
        result = ImportResult()
        # Your import logic here
        return result
```

See [PLUGIN_ARCHITECTURE.md](PLUGIN_ARCHITECTURE.md) for complete documentation.

## Roadmap & TODO

### 🚀 In Progress
- [ ] **FastAPI Backend** - REST API wrapper for AccountingService (enables web/mobile frontends)
- [ ] **React Web UI** - Modern web interface for visualizing finances

### 📋 Planned
- [ ] Desktop GUI (PySide6 / Tauri)
- [ ] More bank importer plugins
- [ ] Subscription management enhancement
- [ ] Budget alerts and notifications
- [ ] Receipt OCR integration
- [ ] Mobile app (React Native / Flutter)

### ✅ Completed
- [x] Core accounting engine with reverse balance calculation
- [x] Multi-account management
- [x] Alipay & WeChat CSV importers
- [x] Plugin architecture for custom importers
- [x] Ollama AI integration (chat analysis, reports, budget advice)
- [x] Semantic search with embeddings
- [x] Data import/export (JSON/CSV)
- [x] Backup management system
- [x] Full test suite (25 tests)
- [x] GitHub Actions CI/CD

## Development & Testing

### Running Tests

```bash
cd python

# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_database.py -v
pytest tests/test_importers.py -v
pytest tests/test_integration.py -v

# Generate coverage report
pytest tests/ -v --cov=src --cov-report=term-missing
```

### Test Structure

```
python/tests/
├── conftest.py           # pytest configuration and fixtures
├── test_database.py      # Database module tests
├── test_importers.py     # Importer module tests
├── test_integration.py   # Integration tests
└── fixtures/             # Test data
    ├── importer_sample.csv  # Sample import data
    └── test_data.csv        # Generic test data
```

## CI/CD

GitHub Actions is configured for continuous integration:

- **Python Matrix**: 3.9, 3.10, 3.11, 3.12
- **Automatic Pip Cache**: Faster build times
- **Coverage Reporting**: pytest-cov + Codecov integration
- **Triggers**: Push to main/master, Pull Requests

See [`.github/workflows/test.yml`](.github/workflows/test.yml) for configuration.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License

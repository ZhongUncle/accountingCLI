# 插件化导入器架构

## 概述

AccountingCLI 采用插件化架构设计，支持灵活扩展不同银行/支付平台的账单导入。

## 核心组件

### 1. BaseImporter（抽象基类）

位置：`src/importers/base.py`

定义了所有导入器必须实现的接口：
- `name` 属性：导入器唯一标识
- `display_name` 属性：显示名称
- `can_handle(filepath)`：检测是否能处理指定文件
- `import_file(filepath, mode)`：实际导入逻辑

还提供了大量实用方法：
- `_normalize_date()`：标准化日期格式
- `_parse_amount()`：解析金额字符串
- `_infer_category()`：根据描述推断分类
- `_read_csv_with_encoding_detection()`：自动检测编码读取 CSV
- `_build_metadata()`：构建元数据
- `_get_or_create_account()`：获取或创建账户
- `_insert_transaction_no_recalc()`：插入交易（不重算余额）
- `_recalculate_balances_backwards()`：倒推计算余额

### 2. ImportManager（插件管理器）

位置：`src/importers/__init__.py`

核心功能：
- 自动注册内置导入器（支付宝、微信、通用CSV）
- 自动发现并加载外部插件
- 延迟实例化：只有实际使用时才创建导入器实例
- 提供统一的导入接口

#### 插件搜索路径

1. `~/.accounting/plugins/` - 用户级插件目录
2. `{project_root}/plugins/` - 项目级插件目录

#### 主要 API

```python
# 自动检测并导入
manager.detect_and_import(filepath, mode='skip')

# 使用指定导入器
manager.import_by_name('alipay', filepath)

# 检测文件来源
manager.detect_source(filepath)

# 列出所有可用导入器
manager.list_importers()
```

## 扩展新导入器

### 方法 1：外部插件（推荐）

只需在插件目录创建 Python 文件，系统会自动发现。

示例：`~/.accounting/plugins/cmb_importer.py`

```python
from src.importers.base import BaseImporter, ImportResult

class CMBImporter(BaseImporter):
    name = "cmb"                    # 唯一标识
    display_name = "招商银行"        # 显示名称
    
    def can_handle(self, filepath: str) -> bool:
        """检测是否为招商银行 CSV 文件"""
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            return "招商银行" in f.readline()
    
    def import_file(self, filepath: str, mode: str = "skip") -> ImportResult:
        """导入招商银行 CSV 文件"""
        result = ImportResult()
        
        # 1. 读取 CSV
        rows = self._read_csv_with_encoding_detection(filepath)
        
        # 2. 解析并导入每一笔交易
        for row in rows:
            result.total += 1
            # ... 解析逻辑 ...
            result.success += 1
        
        return result
```

### 方法 2：内置导入器

在 `src/importers/` 目录下创建新文件，并在 `__init__.py` 中注册。

## 插件元数据

每个导入器必须定义以下类属性：

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | str | 是 | 导入器唯一标识（小写，下划线分隔） |
| `display_name` | str | 是 | 用户可见的显示名称 |

## ImportResult 数据结构

```python
@dataclass
class ImportResult:
    total: int = 0              # 总交易数
    ignored_count: int = 0      # 忽略的交易数
    success: int = 0            # 成功导入数
    skipped: int = 0            # 跳过的重复交易数
    failed: int = 0             # 失败的交易数
    errors: List[str]           # 错误信息列表
    warnings: List[str]         # 警告信息列表
    imported_transactions: List # 已导入的交易列表
```

## 重复处理模式

| 模式 | 说明 |
|------|------|
| `skip` | 跳过已存在的重复交易（默认） |
| `replace` | 替换所有现有交易（清空后重新导入） |
| `keep_both` | 保留所有交易（不做去重） |

## 架构优势

### 1. 零配置扩展
- 无需修改核心代码
- 无需注册配置
- 放置即用，自动发现

### 2. 高度解耦
- 每个导入器独立，互不影响
- 可以单独测试和维护
- 支持按需加载

### 3. 向后兼容
- 保留旧 API 不破坏现有代码
- 新功能可以以插件形式添加

### 4. 灵活性
- 支持同一文件多个导入器
- 支持条件加载
- 支持插件依赖

## 插件开发最佳实践

### 1. 文件命名
- 使用小写 + 下划线
- 格式：`{银行标识}_importer.py`
- 示例：`icbc_importer.py` (工商银行)

### 2. 类命名
- 使用 PascalCase
- 格式：`{银行英文名称}Importer`
- 示例：`ICBCImporter`

### 3. 错误处理
- 捕获并记录所有异常
- 提供友好的错误信息
- 不要让单个交易失败导致整个导入失败

### 4. 编码处理
- 使用 `_read_csv_with_encoding_detection()` 方法
- 支持 utf-8, gbk, gb2312, gb18030

### 5. 去重逻辑
- 优先使用 date + description + amount 组合检测
- 可以使用交易单号作为辅助

## 示例插件

项目 `plugins/` 目录下提供了插件模板：
- `example_importer.py.template` - 完整的插件模板

## 测试

所有导入器（包括插件）都可以通过标准测试流程验证：

```bash
cd python
pytest tests/test_importers.py -v
```

添加新插件后，建议在 `tests/` 目录添加对应的测试用例。

"""
导入器模块 - 插件化架构，支持多种数据源导入

架构设计：
- BaseImporter: 抽象基类，定义导入接口和通用方法
- ImportManager: 插件管理器，自动发现和注册导入器
- 内置导入器: AlipayImporter, WechatImporter, GenericCSVImporter
- 支持外部插件: 可以通过 PLUGIN_PATHS 加载外部导入器

扩展新导入器：
方法 1: 在 src/importers/ 目录下创建新文件（如 cmb.py）
方法 2: 在 ~/.accounting/plugins/ 目录放置导入器文件

只需：
1. 继承 BaseImporter
2. 实现 name 属性（导入器唯一标识）
3. 实现 display_name 属性（显示名称）
4. 实现 can_handle() - 检测是否支持该文件格式
5. 实现 import_file() - 实际的导入逻辑

示例:
```python
from src.importers.base import BaseImporter, ImportResult

class CMBImporter(BaseImporter):
    name = "cmb"                    # 唯一标识
    display_name = "招商银行"        # 显示名称
    
    def can_handle(self, filepath: str) -> bool:
        # 检测是否为招商银行 CSV
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            return "招商银行" in f.readline()
    
    def import_file(self, filepath: str, mode: str = "skip") -> ImportResult:
        # 实现导入逻辑
        result = ImportResult()
        # ... 解析 CSV
        return result
```
"""
import os
import sys
import importlib.util
from pathlib import Path
from typing import Optional, List, Dict, Type

from .base import BaseImporter, ImportResult
from .alipay import AlipayImporter
from .wechat import WechatImporter
from .generic import GenericCSVImporter


# 外部插件搜索路径（可以通过环境变量或配置添加）
PLUGIN_PATHS = [
    # 用户主目录下的插件目录
    Path.home() / ".accounting" / "plugins",
    # 项目下的插件目录（方便开发）
    Path(__file__).parent.parent.parent / "plugins",
]


class ImportManager:
    """
    导入管理器 - 插件化架构
    
    自动发现和注册导入器，支持内置导入器和外部插件。
    """

    def __init__(self, db):
        self.db = db
        # 已注册的导入器类（key: name, value: importer_class）
        self._importer_classes: Dict[str, Type[BaseImporter]] = {}
        # 已实例化的导入器（key: name, value: importer_instance）
        self._importers: Dict[str, BaseImporter] = {}
        
        # 1. 注册内置导入器
        self._register_builtin_importers()
        
        # 2. 自动发现并注册外部插件
        self._discover_plugins()
    
    def _register_builtin_importers(self):
        """注册内置导入器"""
        builtin_importers = [
            AlipayImporter,
            WechatImporter,
            GenericCSVImporter,
        ]
        
        for importer_class in builtin_importers:
            self.register_importer(importer_class)
    
    def _discover_plugins(self):
        """自动发现并注册外部插件
        
        扫描 PLUGIN_PATHS 中的所有 Python 文件，
        查找继承自 BaseImporter 的类。
        """
        for plugin_path in PLUGIN_PATHS:
            if not plugin_path.exists():
                continue
                
            # 扫描所有 .py 文件
            for py_file in plugin_path.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue  # 跳过私有文件
                    
                try:
                    self._load_plugin_file(py_file)
                except Exception as e:
                    import logging
                    logging.warning(f"加载插件失败 {py_file}: {e}")
    
    def _load_plugin_file(self, file_path: Path) -> bool:
        """
        从单个 Python 文件加载导入器插件
        
        Returns:
            是否成功加载了至少一个导入器
        """
        # 动态导入模块
        spec = importlib.util.spec_from_file_location(
            f"accounting_plugin_{file_path.stem}",
            str(file_path)
        )
        if spec is None or spec.loader is None:
            return False
            
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        
        loaded = False
        
        # 查找所有 BaseImporter 的子类
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and 
                issubclass(obj, BaseImporter) and 
                obj is not BaseImporter):
                self.register_importer(obj)
                loaded = True
                
        return loaded
    
    def register_importer(self, importer_class: Type[BaseImporter]) -> None:
        """
        注册一个导入器类
        
        Args:
            importer_class: 导入器类（必须继承自 BaseImporter）
        """
        if not hasattr(importer_class, 'name'):
            raise ValueError(f"导入器 {importer_class.__name__} 必须定义 name 属性")
            
        name = importer_class.name
        if name in self._importer_classes:
            import logging
            logging.warning(f"导入器 '{name}' 已存在，将被覆盖")
            
        self._importer_classes[name] = importer_class
    
    def get_importer(self, name: str) -> Optional[BaseImporter]:
        """
        获取指定名称的导入器实例（延迟实例化）
        
        Args:
            name: 导入器名称（如 'alipay', 'wechat'）
            
        Returns:
            导入器实例，如果不存在返回 None
        """
        if name not in self._importer_classes:
            return None
            
        # 延迟实例化
        if name not in self._importers:
            self._importers[name] = self._importer_classes[name](self.db)
            
        return self._importers[name]
    
    def get_all_importers(self) -> List[BaseImporter]:
        """获取所有已注册的导入器实例"""
        importers = []
        for name in self._importer_classes:
            importer = self.get_importer(name)
            if importer:
                importers.append(importer)
        return importers
    
    def list_importers(self) -> List[Dict[str, str]]:
        """
        列出所有可用的导入器
        
        Returns:
            包含 name 和 display_name 的字典列表
        """
        result = []
        for name, importer_class in self._importer_classes.items():
            result.append({
                "name": name,
                "display_name": getattr(importer_class, 'display_name', name),
            })
        return result

    # 旧 API 兼容性方法
    def import_alipay(self, filepath: str, mode: str = "skip") -> ImportResult:
        """强制使用支付宝导入器（向后兼容）"""
        return self.import_by_name("alipay", filepath, mode) or ImportResult()

    def import_wechat(self, filepath: str, mode: str = "skip") -> ImportResult:
        """强制使用微信导入器（向后兼容）"""
        return self.import_by_name("wechat", filepath, mode) or ImportResult()

    def import_generic(self, filepath: str, mode: str = "skip") -> ImportResult:
        """强制使用通用导入器（向后兼容）"""
        return self.import_by_name("generic", filepath, mode) or ImportResult()

    def detect_and_import(self, filepath: str, mode: str = "skip") -> ImportResult:
        """
        自动检测文件类型并导入

        Args:
            filepath: CSV 文件路径
            mode: 重复处理模式 (skip/replace/keep_both)

        Returns:
            ImportResult 包含导入统计
        """
        for importer in self.get_all_importers():
            if importer.can_handle(filepath):
                return importer.import_file(filepath, mode)

        # 兜底：使用通用导入器
        generic = self.get_importer("generic")
        if generic:
            return generic.import_file(filepath, mode)
        
        # 如果连通用导入器都没有（不应该发生）
        result = ImportResult()
        result.errors.append("没有可用的导入器")
        return result

    def import_by_name(self, importer_name: str, filepath: str, 
                       mode: str = "skip") -> Optional[ImportResult]:
        """
        使用指定的导入器导入
        
        Args:
            importer_name: 导入器名称（如 'alipay', 'wechat'）
            filepath: CSV 文件路径
            mode: 重复处理模式
            
        Returns:
            ImportResult，如果导入器不存在返回 None
        """
        importer = self.get_importer(importer_name)
        if not importer:
            return None
        return importer.import_file(filepath, mode)

    def detect_source(self, filepath: str) -> Optional[str]:
        """
        检测CSV文件来源类型
        
        Returns:
            导入器名称（如 'alipay', 'wechat'），如果无法识别返回 'generic'
        """
        for importer in self.get_all_importers():
            if importer.name == "generic":
                continue  # 跳过通用导入器
            if importer.can_handle(filepath):
                return importer.name
        return "generic"

    def import_csv(self, csv_path: str, source: Optional[str] = None,
                   account_name: Optional[str] = None,
                   account_balance: Optional[float] = None,
                   mode: str = "skip") -> dict:
        """
        统一的CSV导入方法（供AccountingService使用）
        
        返回字典格式以便与现有代码兼容
        """
        if source and source in self._importer_classes:
            result = self.import_by_name(source, csv_path, mode)
        else:
            # 自动检测
            detected_source = self.detect_source(csv_path)
            result = self.import_by_name(detected_source, csv_path, mode)
            source = detected_source

        if result is None:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "errors": [f"导入器 '{source}' 不存在"],
                "source": source,
            }

        # 转换为字典格式
        return {
            "total": result.total,
            "success": result.success,
            "failed": result.failed,
            "skipped": result.skipped,
            "errors": result.errors,
            "source": source,
        }

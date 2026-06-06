"""
插件管理器 - 支持自动发现和加载外部导入器插件

使用方法：
1. 在 ~/.accounting/plugins/ 目录下放置你的导入器文件
2. 导入器需要继承 BaseImporter 并实现必要的方法
3. 系统会自动发现并加载所有插件

示例插件（cmb_importer.py）：
```python
from src.importers.base import BaseImporter, ImportResult

class CMBImporter(BaseImporter):
    name = "cmb"                    # 唯一标识
    display_name = "招商银行"        # 显示名称
    
    def can_handle(self, filepath: str) -> bool:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline()
            return "招商银行" in first_line
    
    def import_file(self, filepath: str, mode: str = "skip") -> ImportResult:
        # 实现你的导入逻辑
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


# 插件搜索路径
PLUGIN_PATHS = [
    # 用户主目录下的插件目录
    Path.home() / ".accounting" / "plugins",
    # 项目下的插件目录（方便开发）
    Path(__file__).parent.parent.parent / "plugins",
]


class PluginManager:
    """插件管理器 - 负责发现、加载和管理导入器插件"""
    
    def __init__(self, db):
        self.db = db
        # 已注册的导入器类（key: name, value: importer_class）
        self._importer_classes: Dict[str, Type[BaseImporter]] = {}
        # 已实例化的导入器（key: name, value: importer_instance）
        self._importers: Dict[str, BaseImporter] = {}
    
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
    
    def discover_plugins(self) -> int:
        """
        自动发现并注册所有插件
        
        Returns:
            发现的插件数量
        """
        count = 0
        
        for plugin_path in PLUGIN_PATHS:
            if not plugin_path.exists():
                continue
                
            # 扫描所有 .py 文件
            for py_file in plugin_path.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue  # 跳过私有文件
                    
                try:
                    if self._load_plugin_file(py_file):
                        count += 1
                except Exception as e:
                    import logging
                    logging.warning(f"加载插件失败 {py_file}: {e}")
        
        return count
    
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

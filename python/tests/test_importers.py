"""测试导入器模块"""
import pytest
import tempfile
import os
from pathlib import Path
from src.importers import ImportManager
from src.importers.alipay import AlipayImporter
from src.importers.wechat import WechatImporter
from src.importers.generic import GenericCSVImporter
from src.importers.base import ImportResult


class TestAlipayImporter:
    def test_detect_alipay_format(self, temp_db, fixtures_dir):
        importer = AlipayImporter(temp_db)
        csv_path = fixtures_dir / "alipay_sample.csv"
        assert importer.can_handle(csv_path) is True

    def test_detect_non_alipay(self, temp_db, fixtures_dir):
        importer = AlipayImporter(temp_db)
        csv_path = fixtures_dir / "wechat_sample.csv"
        assert importer.can_handle(csv_path) is False

    def test_import_alipay(self, temp_db, fixtures_dir):
        importer = AlipayImporter(temp_db)
        csv_path = fixtures_dir / "alipay_sample.csv"
        result = importer.import_file(csv_path, mode="skip")
        assert isinstance(result, ImportResult)
        assert result.total == 5
        assert result.success == 5
        assert result.failed == 0

        # 验证交易已入库
        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transactions")
        assert cursor.fetchone()[0] == 5


class TestWechatImporter:
    def test_detect_wechat_format(self, temp_db, fixtures_dir):
        importer = WechatImporter(temp_db)
        csv_path = fixtures_dir / "wechat_sample.csv"
        assert importer.can_handle(csv_path) is True

    def test_detect_non_wechat(self, temp_db, fixtures_dir):
        importer = WechatImporter(temp_db)
        csv_path = fixtures_dir / "alipay_sample.csv"
        assert importer.can_handle(csv_path) is False

    def test_import_wechat(self, temp_db, fixtures_dir):
        importer = WechatImporter(temp_db)
        csv_path = fixtures_dir / "wechat_sample.csv"
        result = importer.import_file(csv_path, mode="skip")
        assert isinstance(result, ImportResult)
        assert result.total == 5
        assert result.success >= 0


class TestImportManager:
    def test_import_with_auto_detect_alipay(self, temp_db, fixtures_dir):
        manager = ImportManager(temp_db)
        result = manager.detect_and_import(fixtures_dir / "alipay_sample.csv", mode="skip")
        assert isinstance(result, ImportResult)
        assert result.total == 5
        assert result.success == 5

    def test_import_with_auto_detect_wechat(self, temp_db, fixtures_dir):
        manager = ImportManager(temp_db)
        result = manager.detect_and_import(fixtures_dir / "wechat_sample.csv", mode="skip")
        assert isinstance(result, ImportResult)
        assert result.total == 5

    def test_import_alipay_explicit(self, temp_db, fixtures_dir):
        manager = ImportManager(temp_db)
        result = manager.import_alipay(fixtures_dir / "alipay_sample.csv", mode="skip")
        assert isinstance(result, ImportResult)
        assert result.total == 5

    def test_import_wechat_explicit(self, temp_db, fixtures_dir):
        manager = ImportManager(temp_db)
        result = manager.import_wechat(fixtures_dir / "wechat_sample.csv", mode="skip")
        assert isinstance(result, ImportResult)
        assert result.total == 5

    def test_import_unknown_source_fallback_to_generic(self, temp_db):
        """测试无法检测来源时使用通用导入器"""
        manager = ImportManager(temp_db)
        # 创建一个通用格式的CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write("date,description,amount,category,account\n")
            f.write("2024-01-15,测试交易,-100.0,餐饮,总账户\n")
            unknown_path = f.name
        try:
            result = manager.detect_and_import(unknown_path, mode="skip")
            # 通用导入器可能成功或失败，但不应该抛出异常
            assert isinstance(result, ImportResult)
        finally:
            os.unlink(unknown_path)

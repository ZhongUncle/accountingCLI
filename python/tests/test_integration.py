"""集成测试 - 测试完整的导入流程"""
import pytest
from pathlib import Path
from src.commands import AccountingService
from src.database import Database


class TestIntegrationImport:
    def test_full_import_flow_alipay(self, temp_db, fixtures_dir):
        """测试完整的支付宝导入流程"""
        service = AccountingService(temp_db)
        csv_path = fixtures_dir / "alipay_sample.csv"
        
        results = service.import_csv(csv_path, source="alipay", mode="skip")
        
        assert results["total"] == 5
        assert results["success"] == 5
        assert results["failed"] == 0
        assert results["source"] == "alipay"
        
        # 验证交易已入库
        transactions = service.list_transactions()
        assert len(transactions) == 5

    def test_full_import_flow_wechat(self, temp_db, fixtures_dir):
        """测试完整的微信导入流程"""
        service = AccountingService(temp_db)
        csv_path = fixtures_dir / "wechat_sample.csv"
        
        results = service.import_csv(csv_path, source="wechat", mode="skip")
        
        assert results["total"] == 5
        assert results["success"] == 5
        assert results["source"] == "wechat"

    def test_auto_detect_import(self, temp_db, fixtures_dir):
        """测试自动检测来源导入"""
        service = AccountingService(temp_db)
        
        # 自动检测支付宝
        results = service.import_csv(
            fixtures_dir / "alipay_sample.csv", mode="skip"
        )
        assert results["source"] == "alipay"
        assert results["success"] == 5

    def test_detect_csv_source(self, temp_db, fixtures_dir):
        """测试来源检测功能"""
        service = AccountingService(temp_db)
        
        assert service.detect_csv_source(fixtures_dir / "alipay_sample.csv") == "alipay"
        assert service.detect_csv_source(fixtures_dir / "wechat_sample.csv") == "wechat"

    def test_skip_duplicates(self, temp_db, fixtures_dir):
        """测试跳过重复交易"""
        service = AccountingService(temp_db)
        csv_path = fixtures_dir / "alipay_sample.csv"
        
        # 第一次导入
        results1 = service.import_csv(csv_path, source="alipay", mode="skip")
        assert results1["success"] == 5
        
        # 第二次导入应该全部跳过
        results2 = service.import_csv(csv_path, source="alipay", mode="skip")
        assert results2["skipped"] == 5
        assert results2["success"] == 0

    def test_balance_after_import(self, temp_db, fixtures_dir):
        """测试导入后余额计算"""
        service = AccountingService(temp_db)
        csv_path = fixtures_dir / "alipay_sample.csv"
        
        service.import_csv(csv_path, source="alipay", mode="skip")
        
        # 获取余额
        balances = service.get_balance()
        assert len(balances) > 0

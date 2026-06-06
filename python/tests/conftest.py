import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from src.database import Database

@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    db_path = tempfile.mktemp(suffix='.db')
    db = Database(db_path)
    yield db
    db.close()
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"

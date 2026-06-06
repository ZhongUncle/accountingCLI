from datetime import datetime
from typing import List, Optional, Dict, Any


class Account:
    def __init__(self, id: int, name: str, type: str, balance: float, currency: str, 
                 created_at: str, updated_at: str):
        self.id = id
        self.name = name
        self.type = type
        self.balance = balance
        self.currency = currency
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            balance=row["balance"],
            currency=row["currency"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )


class Category:
    def __init__(self, id: int, name: str, type: str, parent_id: Optional[int], sort_order: int):
        self.id = id
        self.name = name
        self.type = type
        self.parent_id = parent_id
        self.sort_order = sort_order

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            parent_id=row["parent_id"],
            sort_order=row["sort_order"]
        )


class Transaction:
    def __init__(self, id: int, date: str, type: str, amount: float, running_balance: float,
                 category_id: Optional[int], account_id: int, description: Optional[str],
                 created_at: str, updated_at: str, tags: Optional[List[str]] = None,
                 category_name: Optional[str] = None, account_name: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.id = id
        self.date = date
        self.type = type
        self.amount = amount
        self.running_balance = running_balance
        self.category_id = category_id
        self.account_id = account_id
        self.description = description
        self.created_at = created_at
        self.updated_at = updated_at
        self.tags = tags or []
        self.category_name = category_name
        self.account_name = account_name
        self.metadata = metadata or {}

    @classmethod
    def from_row(cls, row):
        import json
        metadata = None
        if "metadata" in row and row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except:
                pass
        return cls(
            id=row["id"],
            date=row["date"],
            type=row["type"],
            amount=row["amount"],
            running_balance=row["running_balance"],
            category_id=row["category_id"],
            account_id=row["account_id"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=metadata
        )


class Tag:
    def __init__(self, id: int, name: str, color: Optional[str] = None):
        self.id = id
        self.name = name
        self.color = color

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            name=row["name"],
            color=row["color"]
        )


class Subscription:
    def __init__(self, id: int, name: str, platform: Optional[str], amount: float, currency: str,
                 cycle: str, start_date: str, end_date: Optional[str], auto_renew: bool,
                 category_id: Optional[int], account_id: int, status: str,
                 created_at: str, updated_at: str):
        self.id = id
        self.name = name
        self.platform = platform
        self.amount = amount
        self.currency = currency
        self.cycle = cycle
        self.start_date = start_date
        self.end_date = end_date
        self.auto_renew = auto_renew
        self.category_id = category_id
        self.account_id = account_id
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            name=row["name"],
            platform=row["platform"],
            amount=row["amount"],
            currency=row["currency"],
            cycle=row["cycle"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            auto_renew=bool(row["auto_renew"]),
            category_id=row["category_id"],
            account_id=row["account_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
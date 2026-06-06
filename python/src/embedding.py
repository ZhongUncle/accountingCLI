import json
import numpy as np
import requests
from datetime import datetime
from typing import List, Optional, Dict, Any


class EmbeddingEngine:
    """交易记录embedding引擎，用于语义搜索和分析"""
    
    def __init__(self, db, base_url: str = "http://localhost:11434"):
        self.db = db
        self.base_url = base_url
        self.model_name = "embeddinggemma"
        self._available = None
    
    def is_available(self) -> bool:
        """检查embedding功能是否可用"""
        if self._available is None:
            try:
                response = requests.get(f"{self.base_url}/api/tags", timeout=2)
                self._available = response.status_code == 200
            except:
                self._available = False
        return self._available
    
    def _prepare_transaction_text(self, tx) -> str:
        """准备交易记录的文本表示"""
        parts = []
        
        if tx.description:
            parts.append(tx.description)
        
        if tx.category_name:
            parts.append(f"分类：{tx.category_name}")
        
        if tx.account_name:
            parts.append(f"账户：{tx.account_name}")
        
        if tx.tags:
            parts.append(f"标签：{', '.join(tx.tags)}")
        
        amount = tx.amount
        if tx.type == "expense":
            amount = -amount
        parts.append(f"金额：{amount:.2f}")
        parts.append(f"时间：{tx.date}")
        
        return " | ".join(parts)
    
    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """生成文本的embedding向量"""
        if not self.is_available():
            return None
        
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model_name, "prompt": text},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                embedding_list = result.get("embedding", [])
                return np.array(embedding_list)
        except Exception as e:
            print(f"生成embedding失败：{e}")
        
        return None
    
    def compute_transaction_embedding(self, tx) -> Optional[np.ndarray]:
        """计算单个交易的embedding"""
        text = self._prepare_transaction_text(tx)
        return self.generate_embedding(text)
    
    def compute_and_store_embedding(self, tx):
        """计算并存储交易的embedding"""
        if not self.is_available():
            return False
        
        try:
            embedding = self.compute_transaction_embedding(tx)
            if embedding is None:
                return False
            
            embedding_str = json.dumps(embedding.tolist())
            
            cursor = self.db.conn.cursor()
            
            # 检查是否已存在
            cursor.execute("""
                SELECT id FROM transaction_embeddings 
                WHERE transaction_id = ? AND model = ?
            """, (tx.id, self.model_name))
            
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE transaction_embeddings 
                    SET embedding = ?, created_at = ?
                    WHERE id = ?
                """, (embedding_str, datetime.now().isoformat(), existing[0]))
            else:
                cursor.execute("""
                    INSERT INTO transaction_embeddings 
                    (transaction_id, embedding, model, created_at)
                    VALUES (?, ?, ?, ?)
                """, (tx.id, embedding_str, self.model_name, datetime.now().isoformat()))
            
            self.db.conn.commit()
            return True
        except Exception as e:
            print(f"存储embedding失败：{e}")
            return False
    
    def compute_all_embeddings(self, txs: List, progress_callback=None) -> int:
        """批量计算所有交易的embedding"""
        success_count = 0
        total = len(txs)
        
        for i, tx in enumerate(txs):
            if self.compute_and_store_embedding(tx):
                success_count += 1
            
            if progress_callback and (i + 1) % 10 == 0:
                progress_callback(i + 1, total)
        
        return success_count
    
    def get_embedding_coverage(self) -> Dict[str, int]:
        """获取embedding覆盖率统计"""
        cursor = self.db.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM transactions")
        total = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(DISTINCT transaction_id) 
            FROM transaction_embeddings 
            WHERE model = ?
        """, (self.model_name,))
        covered = cursor.fetchone()[0]
        
        return {
            "total": total,
            "covered": covered,
            "missing": total - covered
        }
    
    def get_embedding(self, tx_id: int) -> Optional[np.ndarray]:
        """获取交易的embedding"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT embedding FROM transaction_embeddings 
            WHERE transaction_id = ? AND model = ?
        """, (tx_id, self.model_name))
        
        row = cursor.fetchone()
        if row:
            embedding_list = json.loads(row[0])
            return np.array(embedding_list)
        return None
    
    def semantic_search(self, query: str, txs: List, top_k: int = 5) -> List[Dict[str, Any]]:
        """语义搜索交易记录"""
        if not self.is_available():
            return []
        
        # 生成查询的embedding
        query_embedding = self.generate_embedding(query)
        if query_embedding is None:
            return []
        
        # 计算相似度
        results = []
        for tx in txs:
            # 尝试获取已存储的embedding
            embedding = self.get_embedding(tx.id)
            if embedding is None:
                # 实时计算
                embedding = self.compute_transaction_embedding(tx)
            
            if embedding is not None:
                # 计算余弦相似度
                similarity = np.dot(query_embedding, embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
                )
                
                results.append({
                    "transaction": tx,
                    "similarity": float(similarity)
                })
        
        # 按相似度排序
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def get_similar_transactions(self, tx, txs: List, top_k: int = 5) -> List[Dict[str, Any]]:
        """查找相似交易"""
        if not self.is_available():
            return []
        
        embedding = self.get_embedding(tx.id)
        if embedding is None:
            embedding = self.compute_transaction_embedding(tx)
        
        if embedding is None:
            return []
        
        results = []
        for other_tx in txs:
            if other_tx.id == tx.id:
                continue
            
            other_embedding = self.get_embedding(other_tx.id)
            if other_embedding is None:
                other_embedding = self.compute_transaction_embedding(other_tx)
            
            if other_embedding is not None:
                similarity = np.dot(embedding, other_embedding) / (
                    np.linalg.norm(embedding) * np.linalg.norm(other_embedding)
                )
                
                results.append({
                    "transaction": other_tx,
                    "similarity": float(similarity)
                })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
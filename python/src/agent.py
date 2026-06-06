#!/usr/bin/env python3
"""
AI 财务智能体 - 能自主理解问题、生成 SQL、分析数据、给出建议
"""
import requests
import json
import sqlite3
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class FinanceAgent:
    """AI 财务智能体"""
    
    def __init__(self, db_path: str, ollama_url: str = "http://localhost:11434", model: str = "gemma4:e4b"):
        self.db_path = db_path
        self.ollama_url = ollama_url
        self.model = model
        self.available = self._check_availability()
        
        # 数据库 schema 信息（给 AI 看的）
        self.schema_info = self._get_schema_info()
    
    def _check_availability(self) -> bool:
        """检查 Ollama 服务是否可用"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _get_schema_info(self) -> str:
        """获取数据库 schema 信息"""
        return """
数据库表结构：

 1. accounts 表（账户）
    - id: 主键
    - name: 账户名称（如：总账户、银行卡、支付宝、微信）
    - type: 账户类型（summary、bank、alipay、wechat）
    - balance: 当前余额
    - currency: 货币（CNY）
    
    ⚠️ 重要提示：
    - type='summary' 的账户（总账户）是自动汇总其他账户的，它的余额 = 银行卡+支付宝+微信
    - 查询余额时，要么只显示总账户，要么显示其他账户但不要把它们加总
    - 不要把总账户和其他账户的余额加在一起！

2. categories 表（分类）
   - id: 主键
   - name: 分类名称
   - type: 类型（income、expense）
   - parent_id: 父分类ID

3. transactions 表（交易记录，核心表）
   - id: 主键
   - date: 日期（格式：YYYY-MM-DD）
   - type: 类型（income=收入、expense=支出）
   - amount: 金额（正数）
   - running_balance: 交易后余额
   - category_id: 分类ID（关联 categories 表）
   - account_id: 账户ID（关联 accounts 表）
   - description: 描述

4. tags 表（标签）
   - id: 主键
   - name: 标签名称

5. transaction_tags 表（交易-标签关联）
   - transaction_id: 交易ID
   - tag_id: 标签ID

常用查询示例：
-- 查询总收入
SELECT SUM(amount) FROM transactions WHERE type = 'income' AND date BETWEEN '2024-01-01' AND '2024-12-31';

-- 查询总支出
SELECT SUM(amount) FROM transactions WHERE type = 'expense' AND date BETWEEN '2024-01-01' AND '2024-12-31';

-- 按月份统计收支
SELECT 
    strftime('%Y-%m', date) as month,
    SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expense
FROM transactions
WHERE date BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY strftime('%Y-%m', date)
ORDER BY month;

-- 按分类统计支出
SELECT 
    c.name as category,
    SUM(t.amount) as total
FROM transactions t
JOIN categories c ON t.category_id = c.id
WHERE t.type = 'expense' AND t.date BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY c.name
ORDER BY total DESC;

-- 查询最大的10笔支出
SELECT date, description, amount, c.name as category
FROM transactions t
LEFT JOIN categories c ON t.category_id = c.id
WHERE type = 'expense' AND date BETWEEN '2024-01-01' AND '2024-12-31'
ORDER BY amount DESC
LIMIT 10;

-- 按账户统计余额
SELECT name, balance FROM accounts ORDER BY balance DESC;

注意：
1. 只允许执行 SELECT 查询
2. amount 字段总是正数，通过 type 区分收支
3. 日期格式是 YYYY-MM-DD
4. 使用 LEFT JOIN 处理可能为 NULL 的关联
"""
    
    def _call_ollama(self, prompt: str, system_prompt: str, temperature: float = 0.7, nothink: bool = False, num_ctx: Optional[int] = None, num_predict: int = 2048) -> Optional[str]:
        """调用 Ollama API"""
        try:
            options = {
                "temperature": temperature,
                "num_predict": num_predict
            }
            if num_ctx is not None:
                options["num_ctx"] = num_ctx
            if nothink:
                options["think"] = False

            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": options
                },
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                print(f"API 错误: {response.status_code}")
                return None
        except Exception as e:
            print(f"调用错误: {e}")
            return None
    
    def _extract_sql_queries(self, text: str) -> List[str]:
        """从 AI 返回的文本中提取 SQL 查询（更健壮的版本）"""
        queries = []
        
        # 方法 1: 提取 ```sql ... ``` 块
        sql_blocks = re.findall(r'```sql\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        
        # 方法 2: 提取 ``` ... ``` 块
        if not sql_blocks:
            sql_blocks = re.findall(r'```\s*(.*?)\s*```', text, re.DOTALL)
        
        # 方法 3: 直接找 SELECT 语句
        if not sql_blocks:
            # 查找所有以 SELECT 开头，以分号结尾的语句
            select_statements = re.findall(r'SELECT.*?;', text, re.DOTALL | re.IGNORECASE)
            if select_statements:
                sql_blocks = select_statements
        
        # 处理每个块
        for block in sql_blocks:
            # 分割成单独的查询（按分号）
            block_queries = re.split(r';\s*', block.strip())
            for q in block_queries:
                q = q.strip()
                if q.lower().startswith('select'):
                    # 确保以分号结尾
                    if not q.endswith(';'):
                        q = q + ';'
                    queries.append(q)
        
        # 如果还是没找到，尝试逐行解析
        if not queries:
            lines = text.split('\n')
            current_query = []
            in_query = False
            
            for line in lines:
                line = line.strip()
                if line.lower().startswith('select'):
                    if in_query and current_query:
                        queries.append(' '.join(current_query))
                    in_query = True
                    current_query = [line]
                elif in_query:
                    if line == '' or line.startswith('```'):
                        if current_query:
                            queries.append(' '.join(current_query))
                        in_query = False
                        current_query = []
                    else:
                        current_query.append(line)
            
            if in_query and current_query:
                queries.append(' '.join(current_query))
        
        # 清理和验证
        valid_queries = []
        for q in queries:
            q = q.strip()
            if q.lower().startswith('select'):
                # 确保查询完整（基本验证）
                if 'from' in q.lower():
                    valid_queries.append(q)
        
        return valid_queries
    
    def _execute_sql(self, sql: str) -> Optional[List[Dict]]:
        """安全执行 SQL 查询（只允许 SELECT）"""
        # 安全检查
        sql_lower = sql.lower()
        if any(keyword in sql_lower for keyword in ['insert', 'update', 'delete', 'drop', 'create', 'alter', 'truncate']):
            print(f"⚠️  不允许的 SQL 操作: {sql[:50]}...")
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            # 转换为字典列表
            result = []
            for row in rows:
                result.append(dict(row))
            
            conn.close()
            return result
        except Exception as e:
            print(f"⚠️  SQL 执行错误: {e}")
            return None
    
    def _format_query_results(self, results: Dict[str, Any]) -> str:
        """格式化查询结果为可读文本"""
        lines = []
        lines.append("=== 查询结果 ===")
        
        for i, (query, data) in enumerate(results.items(), 1):
            lines.append(f"\n查询 {i}: {query[:80]}...")
            if data:
                if len(data) > 0:
                    # 显示列名
                    columns = list(data[0].keys())
                    lines.append("列: " + ", ".join(columns))
                    
                    # 显示数据（最多10行）
                    for j, row in enumerate(data[:10]):
                        values = [str(row[col]) for col in columns]
                        lines.append(f"  {j+1}. " + " | ".join(values))
                    
                    if len(data) > 10:
                        lines.append(f"  ... (还有 {len(data) - 10} 行)")
            else:
                lines.append("  (无结果)")
        
        return "\n".join(lines)
    
    def process_query(self, user_question: str, nothink: bool = False, ctx_size: Optional[int] = None) -> Optional[str]:
        """
        处理用户问题的完整流程：
        1. 理解问题
        2. 生成查询计划
        3. 执行 SQL 查询
        4. 分析结果
        5. 生成报告
        """
        if not self.available:
            return "❌ Ollama 服务不可用，请先启动: ollama run gemma4:e4b"
        
        # 阶段 1: 理解问题并生成 SQL 查询
        print("🤔 正在理解问题并规划查询...")
        
        system_prompt_1 = """你是一个专业的财务数据分析师，精通 SQL。

任务：根据用户的财务问题，生成必要的 SQL SELECT 查询。

重要规则：
1. 只生成 SELECT 查询
2. 每个查询单独一行，用分号结尾
3. 根据问题中的时间范围设置 WHERE 条件
4. 生成 3-5 个关键查询即可

输出格式示例：
SELECT SUM(amount) FROM transactions WHERE type = 'income' AND date BETWEEN '2024-01-01' AND '2024-12-31';
SELECT SUM(amount) FROM transactions WHERE type = 'expense' AND date BETWEEN '2024-01-01' AND '2024-12-31';

只返回 SQL 查询，不要任何解释或 markdown 标记。"""
        
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        user_prompt_1 = f"""数据库信息：
{self.schema_info}

当前日期：{datetime.now().strftime('%Y-%m-%d')}
当前年份：{current_year}
当前月份：{current_month}

用户问题：{user_question}

请分析这个问题，确定需要查询哪些数据，然后生成相应的 SQL 查询。
只返回 SQL 查询，不要其他解释。"""
        
        response_1 = self._call_ollama(user_prompt_1, system_prompt_1, temperature=0.3, nothink=nothink, num_ctx=8192, num_predict=2048)
        if not response_1:
            return None
        
        # 提取 SQL 查询
        sql_queries = self._extract_sql_queries(response_1)
        if not sql_queries:
            print("⚠️  未能提取到 SQL 查询")
            print("AI 返回内容:", response_1[:200])
            return None
        
        print(f"✅ 生成了 {len(sql_queries)} 个查询")
        
        # 阶段 2: 执行 SQL 查询
        print("📊 正在执行查询...")
        query_results = {}
        
        for i, sql in enumerate(sql_queries, 1):
            print(f"  执行查询 {i}/{len(sql_queries)}...", end="", flush=True)
            result = self._execute_sql(sql)
            if result is not None:
                query_results[sql] = result
                print(f"  得到 {len(result)} 行")
            else:
                print(" 失败")
        
        if not query_results:
            return "❌ 没有成功执行任何查询"
        
        # 阶段 3: 分析结果并生成报告（使用用户指定的上下文大小）
        print("📝 正在分析数据并生成报告...")
        
        formatted_results = self._format_query_results(query_results)
        
        system_prompt_2 = """你是一个专业的财务分析师，擅长分析个人财务数据并给出专业建议。

基于查询结果，你需要：
1. 总结关键财务数据（收入、支出、储蓄等）
2. 分析消费模式和趋势
3. 发现亮点和问题
4. 给出具体、可执行的建议
5. 保持积极和鼓励的语气

要求：
- 使用中文
- 结构清晰，分点说明
- 用数据说话
- 给出具体的建议，而不是空泛的话
- 如果有多个维度的数据，要综合分析"""
        
        user_prompt_2 = f"""用户问题：{user_question}

{formatted_results}

请基于以上查询结果，给出一份详细的财务分析报告。"""
        
        final_report = self._call_ollama(user_prompt_2, system_prompt_2, temperature=0.7, nothink=nothink, num_ctx=ctx_size, num_predict=8192)
        
        return final_report

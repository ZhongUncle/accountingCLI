#!/usr/bin/env python3
"""
LLM客户端 - 用于财务分析的AI对话功能
"""
import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime


class LLMClient:
    """LLM客户端，使用Ollama API进行财务分析"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "gemma4:e4b"):
        self.base_url = base_url
        self.model = model
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """检查Ollama服务是否可用"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _format_transactions(self, transactions: List[Dict[str, Any]]) -> str:
        """格式化交易数据为可读文本"""
        if not transactions:
            return "没有交易记录"
        
        lines = []
        for i, tx in enumerate(transactions[:50], 1):  # 限制数量避免token过多
            amount_str = f"+{tx['amount']:.2f}" if tx['type'] == 'income' else f"-{tx['amount']:.2f}"
            lines.append(f"{i}. [{tx['date']}] {tx['description']} - {amount_str} ({tx['category']})")
        
        if len(transactions) > 50:
            lines.append(f"... 还有 {len(transactions) - 50} 条交易")
        
        return "\n".join(lines)
    
    def _format_stats(self, stats: Dict[str, Any]) -> str:
        """格式化统计数据"""
        if not stats:
            return "没有统计数据"
        
        lines = []
        lines.append(f"统计周期: {stats.get('from_date', '未知')} 至 {stats.get('to_date', '未知')}")
        lines.append(f"总收入: +{stats.get('total_income', 0):.2f}")
        lines.append(f"总支出: -{stats.get('total_expense', 0):.2f}")
        lines.append(f"净收支: {stats.get('net', 0):.2f}")
        
        if stats.get('by_category'):
            lines.append("\n分类统计:")
            for cat, data in stats['by_category'].items():
                lines.append(f"  - {cat}: 收入 {data['income']:.2f}, 支出 {data['expense']:.2f}")
        
        return "\n".join(lines)
    
    def chat(self, query: str, transactions: List[Dict[str, Any]], stats: Dict[str, Any], num_ctx: Optional[int] = None) -> Optional[str]:
        """
        与LLM对话进行财务分析
        
        Args:
            query: 用户问题
            transactions: 相关交易记录
            stats: 统计数据
            num_ctx: 上下文大小（可选，不传则使用模型默认值）
            
        Returns:
            LLM响应
        """
        if not self.available:
            return None
        
        system_prompt = """你是一个专业的财务分析师，帮助用户分析个人财务数据。
请基于提供的交易记录和统计数据，给出专业、实用的分析和建议。

分析要点：
1. 收入支出结构分析
2. 消费习惯分析
3. 储蓄建议
4. 潜在的节省机会
5. 趋势预测

回答要求：
- 使用中文
- 简洁明了，重点突出
- 给出具体的建议
- 用数据说话
- 保持友好和鼓励的语气"""
        
        user_prompt = f"""用户问题：{query}

相关交易记录：
{self._format_transactions(transactions)}

统计数据：
{self._format_stats(stats)}

请基于以上信息进行财务分析并回答用户的问题。"""
        
        try:
            options = {"temperature": 0.7}
            if num_ctx is not None:
                options["num_ctx"] = num_ctx
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": user_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": options
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                return f"API调用失败: {response.status_code}"
        except Exception as e:
            return f"错误: {str(e)}"
    
    def generate_analysis_report(self, transactions: List[Dict[str, Any]], stats: Dict[str, Any], 
                                  period: str = "本月", num_ctx: Optional[int] = None) -> Optional[str]:
        """
        生成财务分析报告
        
        Args:
            transactions: 交易记录
            stats: 统计数据
            period: 分析周期描述
            num_ctx: 上下文大小（可选，不传则使用模型默认值）
            
        Returns:
            分析报告
        """
        if not self.available:
            return None
        
        system_prompt = """你是一个专业的财务分析师，需要生成一份详细的个人财务分析报告。

报告结构：
1. 总体概览 - 收入支出总览
2. 收入分析 - 收入来源分析
3. 支出分析 - 支出结构分析
4. 消费习惯洞察 - 发现消费模式
5. 改进建议 - 具体可行的建议
6. 下月预算建议

要求：
- 使用中文
- 详细但不冗长
- 用数据支撑观点
- 给出具体的、可执行的建议
- 保持积极和鼓励的语气"""
        
        user_prompt = f"""请生成{period}的财务分析报告。

交易记录：
{self._format_transactions(transactions)}

统计数据：
{self._format_stats(stats)}

请生成一份详细的财务分析报告。"""
        
        try:
            options = {"temperature": 0.7}
            if num_ctx is not None:
                options["num_ctx"] = num_ctx
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": user_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": options
                },
                timeout=180
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                return f"API调用失败: {response.status_code}"
        except Exception as e:
            return f"错误: {str(e)}"
    
    def generate_budget_advice(self, transactions: List[Dict[str, Any]], stats: Dict[str, Any], num_ctx: Optional[int] = None) -> Optional[str]:
        """
        生成预算建议
        
        Args:
            transactions: 交易记录
            stats: 统计数据
            num_ctx: 上下文大小（可选，不传则使用模型默认值）
            
        Returns:
            预算建议
        """
        if not self.available:
            return None
        
        system_prompt = """你是一个专业的理财顾问，需要为用户制定合理的预算方案。

预算建议应包括：
1. 当前预算执行情况分析
2. 理想预算分配建议（按分类）
3. 具体的节省建议
4. 储蓄目标设定
5. 优先级排序

要求：
- 使用中文
- 实际可行
- 具体明确
- 考虑用户的实际收入水平
- 平衡生活质量和储蓄目标"""
        
        user_prompt = f"""请基于以下财务数据给出预算建议：

交易记录：
{self._format_transactions(transactions)}

统计数据：
{self._format_stats(stats)}

请给出详细的预算建议。"""
        
        try:
            options = {"temperature": 0.7}
            if num_ctx is not None:
                options["num_ctx"] = num_ctx
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": user_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": options
                },
                timeout=180
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                return f"API调用失败: {response.status_code}"
        except Exception as e:
            return f"错误: {str(e)}"

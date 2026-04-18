#!/usr/bin/env python3
"""
每日股票分析脚本
功能：
1. 筛选连续小阳线股票
2. 技术面分析
3. 情感分析（新闻/股吧）
4. 生成分析报告
5. 推送到 Notion
"""

import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta
import json
import os
import sys

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

# 尝试导入量化框架
try:
    from quant_trading.data.data_fetcher import DataFetcher
    from quant_trading.models.sentiment_analysis import SentimentAnalyzer
except ImportError:
    print("量化框架未安装，使用基础分析模式")
    DataFetcher = None
    SentimentAnalyzer = None


class DailyStockAnalyzer:
    """每日股票分析器"""
    
    def __init__(self, tushare_token=None):
        self.fetcher = DataFetcher(tushare_token) if DataFetcher else None
        self.sentiment = SentimentAnalyzer() if SentimentAnalyzer else None
        self.results = []
    
    def get_stock_list(self, market='all'):
        """获取股票列表"""
        print(f"获取 {market} 股票列表...")
        
        if market == 'kcb' or market == 'all':
            try:
                kcb = ak.stock_sh_a_spot_em()
                kcb = kcb[kcb['代码'].str.startswith('688')]
            except:
                kcb = pd.DataFrame()
        else:
            kcb = pd.DataFrame()
            
        if market == 'cyb' or market == 'all':
            try:
                cyb = ak.stock_sz_a_spot_em()
                cyb = cyb[cyb['代码'].str.startswith('300')]
            except:
                cyb = pd.DataFrame()
        else:
            cyb = pd.DataFrame()
        
        if market == 'all':
            all_stocks = pd.concat([kcb, cyb], ignore_index=True)
        else:
            all_stocks = kcb if not kcb.empty else cyb
        
        print(f"共找到 {len(all_stocks)} 只股票")
        return all_stocks[['代码', '名称', '最新价', '涨跌幅']]
    
    def check_small_yang_pattern(self, df, min_days=3):
        """
        检查连续小阳线形态
        """
        if df is None or len(df) < 10:
            return False, 0
        
        # 计算小阳线
        df = df.copy()
        df['is_yang'] = (df['收盘'] > df['开盘']).astype(int)
        df['pct_change'] = (df['收盘'] - df['开盘']) / df['开盘'] * 100
        df['small_yang'] = (
            (df['收盘'] > df['开盘']) &
            (df['pct_change'] >= 0.5) &
            (df['pct_change'] <= 3.0)
        ).astype(int)
        
        # 计算连续天数
        consecutive = df['small_yang'].rolling(min_days).sum().iloc[-1]
        
        return consecutive >= min_days, int(consecutive)
    
    def analyze_single_stock(self, code, name):
        """分析单只股票"""
        try:
            # 获取历史数据
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            if df is None or len(df) < 10:
                return None
            
            recent = df.head(10)
            
            # 检查连续小阳线
            is_pattern, consecutive_days = self.check_small_yang_pattern(recent)
            
            if not is_pattern:
                return None
            
            # 计算技术指标
            latest = recent.iloc[0]
            ma5 = recent['收盘'].head(5).mean()
            ma10 = recent['收盘'].mean()
            
            # 情感分析（可选）
            sentiment_score = 0.5
            if self.sentiment:
                try:
                    sentiment_result = self.sentiment.get_sentiment_signal(code)
                    if sentiment_result:
                        sentiment_score = sentiment_result.get('confidence', 0.5)
                except:
                    pass
            
            return {
                'code': code,
                'name': name,
                'consecutive_days': consecutive_days,
                'latest_price': latest['收盘'],
                'change_pct': latest['涨跌幅'] if '涨跌幅' in latest else 0,
                'ma5': round(ma5, 2),
                'ma10': round(ma10, 2),
                'price_ma5_ratio': round(latest['收盘'] / ma5, 3),
                'sentiment_score': round(sentiment_score, 2),
                'volume': latest['成交量'] if '成交量' in latest else 0,
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"分析 {code} 失败：{e}")
            return None
    
    def run_daily_analysis(self, market='all', top_n=20):
        """
        执行每日分析
        """
        print("="*60)
        print(f"每日股票分析 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*60)
        
        # 获取股票列表
        stock_list = self.get_stock_list(market)
        
        if len(stock_list) == 0:
            print("未找到股票数据")
            return []
        
        # 分析每只股票
        print("\n开始分析股票...")
        results = []
        
        for i, row in stock_list.iterrows():
            if i % 50 == 0:
                print(f"进度：{i}/{len(stock_list)}")
            
            result = self.analyze_single_stock(row['代码'], row['名称'])
            if result:
                results.append(result)
                print(f"✓ {row['代码']} {row['名称']} - 连续{result['consecutive_days']}天小阳线")
            
            # 避免请求过快
            import time
            time.sleep(0.3)
        
        # 排序
        results = sorted(results, key=lambda x: x['consecutive_days'], reverse=True)
        results = results[:top_n]
        
        self.results = results
        
        print(f"\n找到 {len(results)} 只符合条件的股票")
        
        return results
    
    def save_to_csv(self, filepath='output/daily_analysis.csv'):
        """保存结果到 CSV"""
        if not self.results:
            print("没有结果可保存")
            return
        
        df = pd.DataFrame(self.results)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"结果已保存到 {filepath}")
    
    def save_to_json(self, filepath='output/daily_analysis.json'):
        """保存结果到 JSON"""
        if not self.results:
            return
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'analysis_time': datetime.now().isoformat(),
                'total_stocks': len(self.results),
                'results': self.results
            }, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存到 {filepath}")
    
    def push_to_notion(self, page_id=None):
        """推送到 Notion"""
        if not self.results:
            return
        
        import requests
        
        # 读取 Notion API Key
        api_key = os.environ.get('NOTION_API_KEY')
        if not api_key:
            try:
                with open(os.path.expanduser('~/.config/notion/api_key'), 'r') as f:
                    api_key = f.read().strip()
            except:
                print("未找到 Notion API Key")
                return
        
        if not page_id:
            # 使用之前创建的页面
            page_id = '346ac5f8c03d810c9622f69d88d4bf0e'
        
        # 创建内容
        content = []
        for i, stock in enumerate(self.results[:10], 1):
            content.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {
                            "content": f"{i}. {stock['code']} {stock['name']} - 连续{stock['consecutive_days']}天小阳线 (¥{stock['latest_price']}, +{stock['change_pct']}%)"
                        }
                    }]
                }
            })
        
        # 推送到 Notion
        try:
            response = requests.post(
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Notion-Version": "2025-09-03",
                    "Content-Type": "application/json"
                },
                json={"children": content}
            )
            
            if response.status_code == 200:
                print(f"结果已推送到 Notion 页面：{page_id}")
            else:
                print(f"Notion 推送失败：{response.text}")
        except Exception as e:
            print(f"Notion 推送异常：{e}")
    
    def generate_report(self, output_file='output/daily_report.md'):
        """生成 Markdown 报告"""
        if not self.results:
            return
        
        report = f"""# 每日股票分析报告

**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 筛选条件
- 市场：科创板 + 创业板
- 形态：连续小阳线（≥3 天）
- 单日涨幅：0.5% - 3%

## 选股结果

| 排名 | 代码 | 名称 | 连续天数 | 最新价 | 涨跌幅 | MA5 | MA10 | 情绪分 |
|------|------|------|----------|--------|--------|-----|------|--------|
"""
        
        for i, stock in enumerate(self.results, 1):
            report += f"| {i} | {stock['code']} | {stock['name']} | {stock['consecutive_days']} | ¥{stock['latest_price']} | {stock['change_pct']}% | {stock['ma5']} | {stock['ma10']} | {stock['sentiment_score']} |\n"
        
        report += f"""
## 说明
- **连续天数**: 符合连续小阳线形态的天数
- **情绪分**: 基于新闻和股吧的情感分析得分（0-1，越高越正面）
- **MA5/MA10**: 5 日/10 日均线

---
*报告由 daily_stock_analysis 自动生成*
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"报告已保存到 {output_file}")


def main():
    """主函数"""
    print("启动每日股票分析...\n")
    
    # 初始化分析器
    analyzer = DailyStockAnalyzer()
    
    # 执行分析
    results = analyzer.run_daily_analysis(market='all', top_n=20)
    
    if len(results) > 0:
        # 保存结果
        analyzer.save_to_csv()
        analyzer.save_to_json()
        
        # 生成报告
        analyzer.generate_report()
        
        # 推送到 Notion
        analyzer.push_to_notion()
        
        print("\n✅ 每日分析完成！")
    else:
        print("\n⚠️ 未找到符合条件的股票")


if __name__ == "__main__":
    main()

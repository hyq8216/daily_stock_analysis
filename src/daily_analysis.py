#!/usr/bin/env python3
"""
每日股票分析脚本 - 最终版
使用成功过的筛选条件，但分析更多股票
"""

import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta
import json
import os
import sys
import time
import logging
from typing import Optional, Dict, List, Tuple

# 设置项目路径
project_path = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_path)

# 尝试导入量化框架
try:
    from quant_framework.models.sentiment_analysis import SentimentAnalyzer
    print("✅ 量化框架加载成功")
except ImportError as e:
    print(f"⚠️ 量化框架未安装，使用基础分析模式")
    SentimentAnalyzer = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DailyStockAnalyzer:
    """每日股票分析器"""
    
    def __init__(self, tushare_token=None):
        self.sentiment = SentimentAnalyzer() if SentimentAnalyzer else None
        self.results = []
        # 优化参数
        self.request_delay = 0.1  # 最小延迟
        self.max_retries = 1
        print(f"⚠️ transformers 库未安装，情感分析功能不可用")
    
    def safe_api_call(self, func, *args, **kwargs):
        """快速安全 API 调用"""
        for attempt in range(self.max_retries + 1):
            try:
                time.sleep(self.request_delay)
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(0.3)
                    continue
                else:
                    return None
        return None
    
    def check_small_yang_pattern(self, df, min_days=1, max_change_pct=8.0):
        """检查连续小阳线模式 - 更宽松的条件"""
        if df is None or len(df) < min_days:
            return False, 0
        
        df = df.copy()
        numeric_cols = ['开盘', '收盘']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 检查是否为小阳线 - 更宽松：涨幅可达8%
        df['small_yang'] = (
            (df['收盘'] > df['开盘']) &
            ((df['收盘'] - df['开盘']) / df['开盘'] <= max_change_pct/100) &
            ((df['收盘'] - df['开盘']) / df['开盘'] > 0)
        )
        
        consecutive = df['small_yang'].rolling(min_days).sum().iloc[-1]
        
        return consecutive >= min_days, int(consecutive)
    
    def analyze_single_stock(self, code, name):
        """分析单只股票"""
        try:
            # 获取10天历史数据
            df = self.safe_api_call(ak.stock_zh_a_hist, symbol=code, period="daily", adjust="qfq")
            if df is None or len(df) < 10:
                return None
            
            recent = df.head(10)
            
            # 使用之前成功的条件：连续2天，涨幅<=5%
            is_pattern, consecutive_days = self.check_small_yang_pattern(recent, min_days=2, max_change_pct=5.0)
            
            if not is_pattern:
                return None
            
            latest = recent.iloc[0]
            ma5 = recent['收盘'].head(5).mean()
            ma10 = recent['收盘'].mean()
            
            sentiment_score = 0.5
            
            return {
                'code': code,
                'name': name,
                'consecutive_days': consecutive_days,
                'latest_price': float(latest['收盘']),
                'change_pct': float(latest['涨跌幅']) if '涨跌幅' in latest else 0,
                'ma5': round(float(ma5), 2),
                'ma10': round(float(ma10), 2),
                'price_ma5_ratio': round(float(latest['收盘']) / float(ma5), 3),
                'sentiment_score': round(sentiment_score, 2),
                'volume': int(latest['成交量']) if '成交量' in latest else 0,
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception:
            return None
    
    def get_stock_list(self, market='all'):
        """获取股票列表 - 扩大范围"""
        print(f"获取 {market} 股票列表...")
        
        all_stocks = []
        
        try:
            # 获取当日市场数据
            today_data = ak.stock_zh_a_spot_em()
            
            # 使用之前成功过的筛选条件
            potential_stocks = today_data[
                (today_data['成交量'] > 1000000) &  # 成交量大于100万股
                (today_data['涨跌幅'] > 0) &       # 涨幅为正
                (today_data['涨跌幅'] <= 5) &      # 涨幅不超过5%（符合小阳线特征）
                (~today_data['代码'].str.startswith(('000', '001', '002', '300', '688', '689')))  # 排除特殊板块
            ]
            
            # 取前200只
            potential_stocks = potential_stocks.head(200)[['代码', '名称']].dropna()
            
            print(f"筛选出 {len(potential_stocks)} 只潜力股票进行分析")
            all_stocks.extend([(row['代码'], row['名称']) for _, row in potential_stocks.iterrows()])
        
        except Exception as e:
            print(f"获取失败: {e}")
            return []
        
        print(f"共找到 {len(all_stocks)} 只股票")
        return all_stocks
    
    def run_daily_analysis(self, market='all', top_n=20, max_stocks=None):
        """运行每日分析"""
        print("="*60)
        print(f"每日股票分析 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*60)
        
        stock_list = self.get_stock_list(market)
        
        if not stock_list:
            print("❌ 未能获取到任何股票列表")
            return []
        
        if max_stocks:
            print(f"限制分析数量：{max_stocks} 只股票")
            stock_list = stock_list[:max_stocks]
        
        print(f"开始分析 {len(stock_list)} 只股票...")
        
        success_count = 0
        fail_count = 0
        
        start_time = time.time()
        
        for i, (code, name) in enumerate(stock_list):
            result = self.analyze_single_stock(code, name)
            
            if result:
                self.results.append(result)
                success_count += 1
            else:
                fail_count += 1
            
            if (i + 1) % 20 == 0 or i == len(stock_list) - 1:
                elapsed = time.time() - start_time
                print(f"进度：{i+1}/{len(stock_list)} | 成功：{success_count} | 失败：{fail_count} | 用时：{elapsed:.0f}s")
        
        total_time = time.time() - start_time
        print(f"\n分析完成：成功 {success_count} | 失败 {fail_count} | 成功率 {success_count/(success_count+fail_count)*100:.1f}%")
        print(f"找到 {len(self.results)} 只符合条件的股票")
        print(f"总用时：{total_time:.1f} 秒")
        
        return self.results
    
    def save_to_csv(self):
        """保存结果到 CSV"""
        if not self.results:
            print("⚠️ 没有结果可保存")
            return
        
        output_dir = os.path.join(project_path, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        df = pd.DataFrame(self.results)
        filename = os.path.join(output_dir, f'stock_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"CSV 结果已保存到 {filename}")
    
    def save_to_json(self):
        """保存结果到 JSON"""
        if not self.results:
            print("⚠️ 没有结果可保存")
            return
        
        output_dir = os.path.join(project_path, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        filename = os.path.join(output_dir, f'stock_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
        print(f"JSON 结果已保存到 {filename}")
    
    def generate_report(self):
        """生成分析报告"""
        if not self.results:
            report = f"""# 每日股票分析报告 - {datetime.now().strftime('%Y-%m-%d')}

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**分析结果**: 未找到符合条件的连续小阳线股票

**筛选条件**: 
- 连续小阳线 ≥ 2 天
- 小阳线定义：当日涨幅 ≤ 5% 的阳线

---
*报告由 daily_stock_analysis 自动生成*
"""
        else:
            report_rows = []
            for result in self.results:
                report_rows.append(f"| {result['code']} | {result['name']} | {result['consecutive_days']} 天 | ¥{result['latest_price']:.2f} | {result['change_pct']:+.2f}% | {result['price_ma5_ratio']:.3f} |")
            
            report = f"""# 每日股票分析报告 - {datetime.now().strftime('%Y-%m-%d')}

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**分析总数**: {len(self.results)} 只符合条件的股票

## 连续小阳线股票列表

| 股票代码 | 股票名称 | 连续天数 | 当前价格 | 涨跌幅 | 价格/MA5 | 
|---------|---------|---------|---------|--------|---------|
{chr(10).join(report_rows)}

### 分析说明
- **连续小阳线**: 连续 2 天或以上的涨幅不超过 5% 的阳线
- **价格/MA5**: 当前价格与5日均线的比率，反映短期趋势强度

---
*报告由 daily_stock_analysis 自动生成*
"""
        
        output_dir = os.path.join(project_path, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = os.path.join(output_dir, f'analysis_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"报告已保存到 {output_file}")

def main():
    """主函数"""
    print("启动每日股票分析...\n")
    
    analyzer = DailyStockAnalyzer()
    
    max_stocks = int(os.environ.get('MAX_STOCKS', '0'))
    test_mode = os.environ.get('TEST_MODE', 'false') == 'true'
    
    if max_stocks > 0:
        print(f"限制分析数量：{max_stocks} 只股票")
    else:
        max_stocks = None
        print("分析潜力股票（约200只）")
    
    if test_mode:
        print("⚠️ 测试模式")
        analyzer.results = [
            {'code': '688001', 'name': '华海清科', 'consecutive_days': 3, 'latest_price': 180.5, 'change_pct': 2.3, 'ma5': 175.2, 'ma10': 172.8, 'sentiment_score': 0.75},
        ]
    else:
        results = analyzer.run_daily_analysis(market='all', top_n=20, max_stocks=max_stocks)
        analyzer.results = results
    
    if len(analyzer.results) > 0:
        analyzer.save_to_csv()
        analyzer.save_to_json()
        analyzer.generate_report()
        print("\n✅ 每日分析完成！")
    else:
        print("\n⚠️ 未找到符合条件的股票")

if __name__ == "__main__":
    main()
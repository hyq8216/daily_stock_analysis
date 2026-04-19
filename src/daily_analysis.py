#!/usr/bin/env python3
"""
每日股票分析脚本 - 无筛选版
分析更多股票，不做预筛选
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

project_path = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_path)

try:
    from quant_framework.models.sentiment_analysis import SentimentAnalyzer
    print("✅ 量化框架加载成功")
except ImportError:
    print(f"⚠️ 量化框架未安装，使用基础分析模式")
    SentimentAnalyzer = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DailyStockAnalyzer:
    def __init__(self):
        self.results = []
        self.request_delay = 0.05  # 最快速度
        self.max_retries = 1
        print(f"分析模式：无筛选全面扫描")
    
    def safe_api_call(self, func, *args, **kwargs):
        for attempt in range(self.max_retries + 1):
            try:
                time.sleep(self.request_delay)
                result = func(*args, **kwargs)
                return result
            except:
                if attempt < self.max_retries:
                    time.sleep(0.2)
                    continue
                else:
                    return None
        return None
    
    def check_small_yang_pattern(self, df, min_days=1, max_change_pct=10.0):
        if df is None or len(df) < min_days:
            return False, 0
        
        df = df.copy()
        for col in ['开盘', '收盘']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 放宽到10%涨幅
        df['small_yang'] = (
            (df['收盘'] > df['开盘']) &
            ((df['收盘'] - df['开盘']) / df['开盘'] <= max_change_pct/100) &
            ((df['收盘'] - df['开盘']) / df['开盘'] > 0)
        )
        
        consecutive = df['small_yang'].rolling(min_days).sum().iloc[-1]
        
        return consecutive >= min_days, int(consecutive)
    
    def analyze_single_stock(self, code, name):
        try:
            df = self.safe_api_call(ak.stock_zh_a_hist, symbol=code, period="daily", adjust="qfq")
            if df is None or len(df) < 5:
                return None
            
            recent = df.head(5)
            
            # 使用最宽松的条件：连续1天，涨幅<=10%
            is_pattern, consecutive_days = self.check_small_yang_pattern(recent, min_days=1, max_change_pct=10.0)
            
            if not is_pattern:
                return None
            
            latest = recent.iloc[0]
            
            return {
                'code': code,
                'name': name,
                'consecutive_days': consecutive_days,
                'latest_price': float(latest['收盘']),
                'change_pct': float(latest['涨跌幅']) if '涨跌幅' in latest else 0,
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except:
            return None
    
    def get_stock_list(self):
        """获取股票列表 - 无筛选"""
        print("获取股票列表（无预筛选）...")
        
        all_stocks = []
        
        try:
            # 直接获取全部A股
            all_data = ak.stock_zh_a_spot_em()
            
            # 只排除北交所和极低价股
            filtered = all_data[
                (all_data['最新价'] > 2) &
                (~all_data['代码'].str.startswith(('8', '4')))
            ]
            
            # 取前100只
            stocks = filtered.head(100)[['代码', '名称']].dropna()
            
            print(f"选取 {len(stocks)} 只股票进行分析")
            all_stocks.extend([(row['代码'], row['名称']) for _, row in stocks.iterrows()])
        
        except Exception as e:
            print(f"获取失败: {e}")
            return []
        
        print(f"共 {len(all_stocks)} 只股票")
        return all_stocks
    
    def run_daily_analysis(self, max_stocks=None):
        print("="*60)
        print(f"每日股票分析 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*60)
        
        stock_list = self.get_stock_list()
        
        if not stock_list:
            print("❌ 未能获取股票列表")
            return []
        
        if max_stocks and max_stocks > 0:
            print(f"限制：{max_stocks} 只")
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
                print(f"  ✅ 找到: {code} {name} ({result['consecutive_days']}天, {result['change_pct']:.2f}%)")
            else:
                fail_count += 1
            
            if (i + 1) % 50 == 0:
                elapsed = time.time() - start_time
                print(f"进度：{i+1}/{len(stock_list)} | 成功：{success_count} | 失败：{fail_count} | 用时：{elapsed:.0f}s")
        
        total_time = time.time() - start_time
        print(f"\n分析完成：成功 {success_count} | 失败 {fail_count}")
        print(f"找到 {len(self.results)} 只符合条件的股票")
        print(f"总用时：{total_time:.1f} 秒")
        
        return self.results
    
    def save_results(self):
        if not self.results:
            print("⚠️ 无结果")
            return
        
        output_dir = os.path.join(project_path, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        # CSV
        df = pd.DataFrame(self.results)
        csv_file = os.path.join(output_dir, f'stock_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"CSV: {csv_file}")
        
        # JSON
        json_file = os.path.join(output_dir, f'stock_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
        print(f"JSON: {json_file}")
        
        # 报告
        report = f"""# 每日股票分析报告 - {datetime.now().strftime('%Y-%m-%d')}

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
找到: {len(self.results)} 只连续小阳线股票

## 股票列表

| 代码 | 名称 | 连续天数 | 当前价 | 涨跌幅 |
|------|------|----------|--------|--------|
"""
        for r in self.results:
            report += f"| {r['code']} | {r['name']} | {r['consecutive_days']}天 | ¥{r['latest_price']:.2f} | {r['change_pct']:+.2f}% |\n"
        
        report += "\n---\n*自动生成*\n"
        
        md_file = os.path.join(output_dir, f'analysis_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md')
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"报告: {md_file}")

def main():
    print("启动每日股票分析...\n")
    
    analyzer = DailyStockAnalyzer()
    
    max_stocks = int(os.environ.get('MAX_STOCKS', '0'))
    
    if max_stocks > 0:
        print(f"限制分析：{max_stocks} 只")
        results = analyzer.run_daily_analysis(max_stocks=max_stocks)
    else:
        results = analyzer.run_daily_analysis()
    
    if len(analyzer.results) > 0:
        analyzer.save_results()
        print("\n✅ 完成！")
    else:
        print("\n⚠️ 未找到")

if __name__ == "__main__":
    main()
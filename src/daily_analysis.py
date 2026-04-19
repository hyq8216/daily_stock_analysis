#!/usr/bin/env python3
"""
全市场股票分析脚本
目标：分析A股全部股票
"""

import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime
import json
import os
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

project_path = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_path)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FullMarketAnalyzer:
    def __init__(self):
        self.results = []
        self.request_delay = 0.05  # 适中的延迟以避免限流
        self.max_workers = 5  # 限制并发数以避免被限流
        self.lock = threading.Lock()
        self.total_analyzed = 0
        self.success_count = 0
        self.fail_count = 0
        print("全市场分析器初始化完成")
    
    def safe_api_call(self, func, *args, **kwargs):
        for attempt in range(2):  # 最多重试1次
            try:
                time.sleep(self.request_delay)
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                if attempt == 0:  # 还有一次重试机会
                    time.sleep(0.5)  # 稍长的重试延迟
                    continue
                else:
                    return None
        return None
    
    def quick_check_pattern(self, df):
        """快速检查模式"""
        if df is None or len(df) < 3:
            return False, 0
        
        df = df.head(5).copy()
        for col in ['开盘', '收盘']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 简化检查：最近2天都是小阳线
        if len(df) >= 2:
            today = df.iloc[0]
            yesterday = df.iloc[1]
            
            # 检查是否都是阳线且涨幅合理
            today_yang = today['收盘'] > today['开盘'] if '收盘' in today and '开盘' in today else False
            yesterday_yang = yesterday['收盘'] > yesterday['开盘'] if '收盘' in yesterday and '开盘' in yesterday else False
            
            if today_yang and yesterday_yang:
                return True, 2
        
        return False, 0
    
    def analyze_single_stock(self, code, name):
        try:
            df = self.safe_api_call(ak.stock_zh_a_hist, symbol=code, period="daily", adjust="qfq")
            is_pattern, consecutive_days = self.quick_check_pattern(df)
            
            if is_pattern:
                latest = df.iloc[0] if df is not None and len(df) > 0 else None
                if latest is not None:
                    result = {
                        'code': code,
                        'name': name,
                        'consecutive_days': consecutive_days,
                        'latest_price': float(latest['收盘']) if '收盘' in latest else 0,
                        'change_pct': float(latest['涨跌幅']) if '涨跌幅' in latest else 0,
                        'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    with self.lock:
                        self.results.append(result)
                        self.success_count += 1
                        print(f"  ✅ {code} {name} ({consecutive_days}天)")
                    return result
                else:
                    with self.lock:
                        self.fail_count += 1
                    return None
            else:
                with self.lock:
                    self.fail_count += 1
                return None
        except:
            with self.lock:
                self.fail_count += 1
            return None
    
    def get_all_stocks(self):
        """获取全部A股股票"""
        try:
            print("正在获取全部A股股票列表...")
            data = ak.stock_zh_a_spot_em()
            # 排除北交所和退市整理股票
            all_stocks = data[
                (~data['代码'].str.startswith(('4', '8'))) &  # 排除北交所
                (data['最新价'] > 1)  # 排除极低价股
            ][['代码', '名称']].dropna()
            
            print(f"获取到 {len(all_stocks)} 只股票")
            return [(row['代码'], row['名称']) for _, row in all_stocks.iterrows()]
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return []
    
    def run_analysis_batch(self, stock_list):
        """批量分析股票"""
        print(f"开始分析 {len(stock_list)} 只股票...")
        print(f"使用 {self.max_workers} 个并发线程")
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_stock = {
                executor.submit(self.analyze_single_stock, code, name): (code, name) 
                for code, name in stock_list
            }
            
            # 跟踪进度
            total = len(stock_list)
            completed = 0
            
            for future in as_completed(future_to_stock):
                completed += 1
                if completed % 50 == 0 or completed == total:
                    elapsed = time.time() - start_time
                    print(f"进度：{completed}/{total} | 成功：{self.success_count} | 失败：{self.fail_count} | 用时：{elapsed:.1f}s")
        
        elapsed = time.time() - start_time
        print(f"分析完成！找到 {self.success_count} 只符合条件的股票，用时 {elapsed:.1f}秒")
        return self.results

def main():
    print(f"全市场分析开始 - {datetime.now().strftime('%H:%M:%S')}")
    
    analyzer = FullMarketAnalyzer()
    stock_list = analyzer.get_all_stocks()
    
    if not stock_list:
        print("未获取到股票列表")
        return
    
    results = analyzer.run_analysis_batch(stock_list)
    
    if results:
        print(f"\n找到 {len(results)} 只符合条件的股票:")
        for r in results:
            print(f"- {r['code']} {r['name']} ({r['consecutive_days']}天, {r['change_pct']:.2f}%)")
        
        # 保存结果
        output_dir = os.path.join(project_path, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f'full_market_results_{timestamp}.json')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"结果已保存: {output_file}")
        
        # 生成报告
        report_file = os.path.join(output_dir, f'full_market_report_{timestamp}.md')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"# 全市场分析报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"## 分析结果\n")
            f.write(f"- 总股票数: {len(stock_list)}\n")
            f.write(f"- 符合条件: {len(results)}\n")
            f.write(f"- 分析用时: {time.time() - sum([0.05 for _ in stock_list]):.1f}秒 (估算)\n\n")
            
            f.write("## 符合条件的股票\n")
            f.write("| 股票代码 | 股票名称 | 连续天数 | 当前价格 | 涨跌幅 |\n")
            f.write("|---------|---------|---------|---------|--------|\n")
            
            for r in results:
                f.write(f"| {r['code']} | {r['name']} | {r['consecutive_days']} | {r['latest_price']:.2f} | {r['change_pct']:+.2f}% |\n")
        
        print(f"报告已保存: {report_file}")
    else:
        print("\n未找到符合条件的股票")

if __name__ == "__main__":
    main()
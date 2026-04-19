#!/usr/bin/env python3
"""
极速版股票分析脚本
目标：在1分钟内完成分析
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

project_path = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_path)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FastStockAnalyzer:
    def __init__(self):
        self.results = []
        self.request_delay = 0.02  # 极小延迟
        self.max_retries = 1
    
    def safe_api_call(self, func, *args, **kwargs):
        for attempt in range(self.max_retries + 1):
            try:
                time.sleep(self.request_delay)
                result = func(*args, **kwargs)
                return result
            except:
                if attempt < self.max_retries:
                    time.sleep(0.1)
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
                    return {
                        'code': code,
                        'name': name,
                        'consecutive_days': consecutive_days,
                        'latest_price': float(latest['收盘']) if '收盘' in latest else 0,
                        'change_pct': float(latest['涨跌幅']) if '涨跌幅' in latest else 0,
                        'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
            
        except:
            pass
        return None
    
    def get_top_volume_stocks(self, n=50):
        """获取最高成交量的股票"""
        try:
            data = ak.stock_zh_a_spot_em()
            # 按成交量排序，取前50
            top_stocks = data.nlargest(n, '成交量')[['代码', '名称', '成交量']].dropna()
            print(f"选取 {len(top_stocks)} 只高成交量股票")
            return [(row['代码'], row['名称']) for _, row in top_stocks.iterrows()]
        except:
            return []
    
    def run_analysis(self):
        print(f"极速分析开始 - {datetime.now().strftime('%H:%M:%S')}")
        
        stock_list = self.get_top_volume_stocks(50)  # 只分析50只高成交量股票
        
        print(f"开始分析 {len(stock_list)} 只股票...")
        start_time = time.time()
        
        for i, (code, name) in enumerate(stock_list):
            result = self.analyze_single_stock(code, name)
            
            if result:
                self.results.append(result)
                print(f"  ✅ {code} {name} ({result['consecutive_days']}天)")
        
        elapsed = time.time() - start_time
        print(f"完成！找到 {len(self.results)} 只，用时 {elapsed:.1f}秒")
        return self.results

def main():
    analyzer = FastStockAnalyzer()
    results = analyzer.run_analysis()
    
    if results:
        print("\n找到的股票:")
        for r in results:
            print(f"- {r['code']} {r['name']} ({r['consecutive_days']}天, {r['change_pct']:.2f}%)")
        
        # 保存结果
        output_dir = os.path.join(project_path, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f'fast_results_{timestamp}.json')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"结果已保存: {output_file}")
    else:
        print("\n未找到符合条件的股票")

if __name__ == "__main__":
    main()
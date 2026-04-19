#!/usr/bin/env python3
"""
每日股票分析脚本 - 灵活版
功能：
1. 筛选连续小阳线股票（放宽条件）
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
import time
import random
import logging
from typing import Optional, Dict, List, Tuple

# 设置项目路径
project_path = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_path)

# 尝試導入量化框架
try:
    from quant_framework.data.data_fetcher import DataFetcher
    from quant_framework.models.sentiment_analysis import SentimentAnalyzer
    print("✅ 量化框架加载成功")
except ImportError as e:
    print(f"⚠️ 量化框架未安装，使用基础分析模式 ({e})")
    DataFetcher = None
    SentimentAnalyzer = None

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DailyStockAnalyzer:
    """每日股票分析器"""
    
    def __init__(self, tushare_token=None):
        self.fetcher = DataFetcher(tushare_token) if DataFetcher else None
        self.sentiment = SentimentAnalyzer() if SentimentAnalyzer else None
        self.results = []
        # 优化参数
        self.request_delay = 0.3  # 适中的延迟
        self.max_retries = 2  # 适度的重试次数
        print(f"⚠️ transformers 库未安装，情感分析功能不可用")
    
    def safe_api_call(self, func, *args, **kwargs):
        """带重试和延迟的安全 API 调用"""
        for attempt in range(self.max_retries + 1):  # +1 因为第一次也算
            try:
                time.sleep(self.request_delay + random.uniform(0, 0.1))
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                if attempt < self.max_retries:  # 还有重试机会
                    wait_time = 1 * (attempt + 1)  # 指数退避
                    time.sleep(wait_time)
                    continue
                else:
                    return None
        
        return None
    
    def check_small_yang_pattern(self, df, min_days=2, max_change_pct=5.0):
        """检查连续小阳线模式 - 更灵活的条件"""
        if df is None or len(df) < min_days:
            return False, 0
        
        # 确保数值列为数值类型
        df = df.copy()
        numeric_cols = ['开盘', '收盘', '最高', '最低']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 检查是否为阳线（涨幅为正但不大）
        df['small_yang'] = (
            (df['收盘'] > df['开盘']) &  # 阳线
            ((df['收盘'] - df['开盘']) / df['开盘'] <= max_change_pct/100) &  # 涨幅<=5%
            ((df['收盘'] - df['开盘']) / df['开盘'] > 0)  # 涨幅>0
        )
        
        consecutive = df['small_yang'].rolling(min_days).sum().iloc[-1]
        
        return consecutive >= min_days, int(consecutive)
    
    def analyze_single_stock(self, code, name):
        """分析单只股票"""
        try:
            df = self.safe_api_call(ak.stock_zh_a_hist, symbol=code, period="daily", adjust="qfq")
            if df is None or len(df) < 10:
                return None
            
            recent = df.head(10)
            
            # 使用更灵活的条件：连续2天，涨幅<=5%
            is_pattern, consecutive_days = self.check_small_yang_pattern(recent, min_days=2, max_change_pct=5.0)
            
            if not is_pattern:
                return None
            
            latest = recent.iloc[0]
            ma5 = recent['收盘'].head(5).mean()
            ma10 = recent['收盘'].mean()
            
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
            
        except Exception:
            return None
    
    def get_stock_list(self, market='all'):
        """获取股票列表"""
        print(f"获取 {market} 股票列表...")
        
        try:
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
                try:
                    zxb = ak.stock_zh_a_spot_em()
                    # 过滤掉科创板和创业板
                    main_board = zxb[
                        ~(zxb['代码'].str.startswith(('000', '001', '002', '300', '688', '689')))
                    ]
                except:
                    main_board = pd.DataFrame()
            else:
                main_board = pd.DataFrame()
            
            # 合并所有股票
            all_stocks = pd.concat([kcb, cyb, main_board], ignore_index=True)
            
            # 只选择必要的列并过滤
            if '代码' in all_stocks.columns and '名称' in all_stocks.columns:
                all_stocks = all_stocks[['代码', '名称']].dropna()
            elif 'symbol' in all_stocks.columns and 'name' in all_stocks.columns:
                all_stocks = all_stocks.rename(columns={'symbol': '代码', 'name': '名称'})[['代码', '名称']].dropna()
            else:
                # 如果没有预期的列名，尝试其他常见列名
                code_col = next((col for col in all_stocks.columns if '代码' in col or 'code' in col.lower()), None)
                name_col = next((col for col in all_stocks.columns if '名称' in col or 'name' in col.lower() or '简称' in col), None)
                if code_col and name_col:
                    all_stocks = all_stocks[[code_col, name_col]].rename(columns={code_col: '代码', name_col: '名称'}).dropna()
                else:
                    return []
            
            print(f"共找到 {len(all_stocks)} 只股票")
            return [(row['代码'], row['名称']) for _, row in all_stocks.iterrows()]
        
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return []
    
    def run_daily_analysis(self, market='all', top_n=20, max_stocks=None):
        """运行每日分析"""
        print("="*60)
        print(f"每日股票分析 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*60)
        
        # 获取股票列表
        stock_list = self.get_stock_list(market)
        
        if not stock_list:
            print("❌ 未能获取到任何股票列表")
            return []
        
        # 限制分析数量
        if max_stocks:
            print(f"限制分析数量：{max_stocks} 只股票")
            stock_list = stock_list[:max_stocks]
        
        print(f"开始分析 {len(stock_list)} 只股票...")
        
        success_count = 0
        fail_count = 0
        
        for i, (code, name) in enumerate(stock_list):
            result = self.analyze_single_stock(code, name)
            
            if result:
                self.results.append(result)
                success_count += 1
            else:
                fail_count += 1
            
            # 显示进度
            if (i + 1) % 10 == 0 or i == len(stock_list) - 1:
                print(f"进度：{i+1}/{len(stock_list)} | 成功：{success_count} | 失败：{fail_count}")
        
        print(f"\n分析完成：成功 {success_count} | 失败 {fail_count} | 成功率 {success_count/(success_count+fail_count)*100:.1f}%")
        print(f"找到 {len(self.results)} 只符合条件的股票")
        
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
    
    # 获取参数
    max_stocks = int(os.environ.get('MAX_STOCKS', '50'))
    test_mode = os.environ.get('TEST_MODE', 'false') == 'true'
    
    if max_stocks:
        print(f"限制分析数量：{max_stocks} 只股票")
    else:
        max_stocks = None
    
    if test_mode:
        print("⚠️ 测试模式：使用模拟数据")
        analyzer.results = [
            {'code': '688001', 'name': '华海清科', 'consecutive_days': 3, 'latest_price': 180.5, 'change_pct': 2.3, 'ma5': 175.2, 'ma10': 172.8, 'sentiment_score': 0.75},
            {'code': '300059', 'name': '东方财富', 'consecutive_days': 4, 'latest_price': 15.2, 'change_pct': 1.8, 'ma5': 14.8, 'ma10': 14.1, 'sentiment_score': 0.65}
        ]
        print(f"生成模拟数据：{len(analyzer.results)} 只股票")
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
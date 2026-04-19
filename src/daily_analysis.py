#!/usr/bin/env python3
"""
每日股票分析脚本 - 多数据源版
功能：
1. 筛选连续小阳线股票
2. 技术面分析
3. 情感分析（新闻/股吧）
4. 生成分析报告
5. 推送到 Notion
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys
import time
import random
import logging
from typing import Optional, Dict, List, Tuple, Callable
import requests

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

class MultiSourceDataFetcher:
    """多数据源获取器"""
    
    def __init__(self, tushare_token=None):
        self.tushare_token = tushare_token
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_stock_data_akshare(self, symbol: str, period: str = "daily", adjust: str = "qfq"):
        """使用akshare获取股票数据"""
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(symbol=symbol, period=period, adjust=adjust)
            return df
        except Exception as e:
            print(f"  akshare获取失败: {e}")
            return None
    
    def get_stock_data_tushare(self, symbol: str):
        """使用tushare获取股票数据"""
        if not self.tushare_token:
            print("  TuShare token未配置，跳过")
            return None
        
        try:
            import tushare as ts
            ts.set_token(self.tushare_token)
            pro = ts.pro_api()
            
            # 转换代码格式 (TuShare格式)
            ts_code = symbol
            if symbol.startswith('6'):
                ts_code = f"{symbol}.SH"
            elif symbol.startswith(('0', '3')):
                ts_code = f"{symbol}.SZ"
            
            df = pro.daily(ts_code=ts_code, start_date=(datetime.now() - timedelta(days=30)).strftime('%Y%m%d'))
            return df
        except Exception as e:
            print(f"  TuShare获取失败: {e}")
            return None
    
    def get_stock_data_sina(self, symbol: str):
        """使用新浪接口获取股票数据"""
        try:
            # 新浪财经接口
            sina_url = f"http://vip.stock.finance.sina.com.cn/corp/go.php/vMS_MarketHistory/stockid/{symbol}.phtml"
            # 或者使用更简单的接口
            if symbol.startswith('6'):
                sina_symbol = f"sh{symbol}"
            else:
                sina_symbol = f"sz{symbol}"
            
            url = f"https://hq.sinajs.cn/list={sina_symbol}"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                # 这里需要解析返回的数据，简化处理
                # 实际上新浪接口格式复杂，可能需要专门处理
                pass
        except Exception as e:
            print(f"  新浪获取失败: {e}")
            return None
        
        # 使用另一种免费接口
        try:
            # 聚宽精简版接口（公开接口）
            jq_url = f"https://jfds-1252956699.cos.ap-shanghai.myqcloud.com/jqka/backtest_data/stock/{symbol}.csv"
            df = pd.read_csv(jq_url)
            return df
        except:
            print("  聚宽数据获取失败")
            return None
    
    def get_stock_data(self, symbol: str, source_priority: List[str] = None):
        """按优先级获取股票数据"""
        if source_priority is None:
            source_priority = ['akshare', 'tushare', 'sina']
        
        for source in source_priority:
            if source == 'akshare':
                df = self.get_stock_data_akshare(symbol)
            elif source == 'tushare':
                df = self.get_stock_data_tushare(symbol)
            elif source == 'sina':
                df = self.get_stock_data_sina(symbol)
            else:
                df = None
            
            if df is not None and len(df) > 0:
                print(f"  ✅ 使用 {source} 获取数据成功 ({len(df)} 条记录)")
                return df
        
        print(f"  ❌ 所有数据源都失败")
        return None

class DailyStockAnalyzer:
    """每日股票分析器"""
    
    def __init__(self, tushare_token=None):
        self.data_fetcher = MultiSourceDataFetcher(tushare_token)
        try:
            from quant_framework.models.sentiment_analysis import SentimentAnalyzer
            self.sentiment = SentimentAnalyzer() if SentimentAnalyzer else None
            print("✅ 量化框架加载成功")
        except ImportError:
            print(f"⚠️ transformers 库未安装，情感分析功能不可用")
            self.sentiment = None
        self.results = []
        # 优化参数
        self.request_delay = 0.2  # 减少延迟以提高效率
        self.max_retries = 2  # 适度的重试次数
    
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
        # 根据不同数据源的列名进行适配
        price_cols = {
            '收盘': ['收盘', 'close', '收盘价', 'close_price'],
            '开盘': ['开盘', 'open', '开盘价', 'open_price'],
            '最高': ['最高', 'high', '最高价', 'high_price'],
            '最低': ['最低', 'low', '最低价', 'low_price']
        }
        
        # 尝试找到对应的列名
        close_col = next((col for col in price_cols['收盘'] if col in df.columns), None)
        open_col = next((col for col in price_cols['开盘'] if col in df.columns), None)
        
        if not close_col or not open_col:
            print(f"    无法找到价格列: close={close_col}, open={open_col}")
            return False, 0
        
        for col in [close_col, open_col]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 检查是否为阳线（涨幅为正但不大）
        df['small_yang'] = (
            (df[close_col] > df[open_col]) &  # 阳线
            ((df[close_col] - df[open_col]) / df[open_col] <= max_change_pct/100) &  # 涨幅<=5%
            ((df[close_col] - df[open_col]) / df[open_col] > 0)  # 涨幅>0
        )
        
        consecutive = df['small_yang'].rolling(min_days).sum().iloc[-1]
        
        return consecutive >= min_days, int(consecutive)
    
    def analyze_single_stock(self, code, name):
        """分析单只股票"""
        print(f"  分析 {code} - {name}...")
        
        # 使用多数据源获取数据
        df = self.data_fetcher.get_stock_data(code)
        if df is None or len(df) < 10:
            print(f"    数据获取失败或不足")
            return None
        
        recent = df.head(10)
        
        # 使用更灵活的条件：连续2天，涨幅<=5%
        is_pattern, consecutive_days = self.check_small_yang_pattern(recent, min_days=2, max_change_pct=5.0)
        
        if not is_pattern:
            print(f"    不符合小阳线模式 (连续 {consecutive_days} 天)")
            return None
        
        print(f"    ✅ 符合小阳线模式 (连续 {consecutive_days} 天)")
        
        # 根据数据源的列名获取价格
        close_col = next((col for col in ['收盘', 'close', '收盘价', 'close_price'] if col in recent.columns), '收盘')
        pct_change_col = next((col for col in ['涨跌幅', 'pct_change', 'change_pct'] if col in recent.columns), '涨跌幅')
        
        latest = recent.iloc[0]
        ma5 = recent[close_col].head(5).mean()
        ma10 = recent[close_col].mean()
        
        sentiment_score = 0.5
        if self.sentiment:
            try:
                sentiment_result = self.sentiment.get_sentiment_signal(code)
                if sentiment_result:
                    sentiment_score = sentiment_result.get('confidence', 0.5)
            except:
                pass
        
        result = {
            'code': code,
            'name': name,
            'consecutive_days': consecutive_days,
            'latest_price': latest[close_col],
            'change_pct': latest[pct_change_col] if pct_change_col in latest else 0,
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'price_ma5_ratio': round(latest[close_col] / ma5, 3),
            'sentiment_score': round(sentiment_score, 2),
            'volume': latest.get('成交量', latest.get('vol', latest.get('volume', 0))),
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"    ✅ 分析完成: {result['name']} ({result['consecutive_days']} 天小阳线)")
        return result
    
    def get_stock_list(self, market='all'):
        """获取股票列表 - 使用多个数据源"""
        print(f"获取 {market} 股票列表...")
        
        all_stocks = []
        
        try:
            # 尝试使用akshare获取
            import akshare as ak
            
            if market == 'kcb' or market == 'all':
                try:
                    kcb = ak.stock_sh_a_spot_em()
                    kcb = kcb[kcb['代码'].str.startswith('688')]
                    print(f"  科创板: {len(kcb)} 只")
                    all_stocks.extend([(row['代码'], row['名称']) for _, row in kcb.iterrows()])
                except Exception as e:
                    print(f"  科创板获取失败: {e}")
            
            if market == 'cyb' or market == 'all':
                try:
                    cyb = ak.stock_sz_a_spot_em()
                    cyb = cyb[cyb['代码'].str.startswith('300')]
                    print(f"  创业板: {len(cyb)} 只")
                    all_stocks.extend([(row['代码'], row['名称']) for _, row in cyb.iterrows()])
                except Exception as e:
                    print(f"  创业板获取失败: {e}")
            
            if market == 'all':
                try:
                    zxb = ak.stock_zh_a_spot_em()
                    # 过滤掉科创板和创业板
                    main_board = zxb[
                        ~(zxb['代码'].str.startswith(('000', '001', '002', '300', '688', '689')))
                    ]
                    print(f"  主板: {len(main_board)} 只")
                    all_stocks.extend([(row['代码'], row['名称']) for _, row in main_board.iterrows()])
                except Exception as e:
                    print(f"  主板获取失败: {e}")
        
        except ImportError:
            print("  akshare未安装，无法获取股票列表")
        
        print(f"共找到 {len(all_stocks)} 只股票")
        return all_stocks
    
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
            print(f"[{i+1}/{len(stock_list)}] ", end="")
            result = self.analyze_single_stock(code, name)
            
            if result:
                self.results.append(result)
                success_count += 1
            else:
                fail_count += 1
            
            # 显示进度
            if (i + 1) % 10 == 0 or i == len(stock_list) - 1:
                print(f"\n进度：{i+1}/{len(stock_list)} | 成功：{success_count} | 失败：{fail_count}")
        
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
    
    # 尝试从环境变量获取TuShare token
    tushare_token = os.environ.get('TUSHARE_TOKEN')
    analyzer = DailyStockAnalyzer(tushare_token=tushare_token)
    
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
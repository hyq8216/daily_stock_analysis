#!/usr/bin/env python3
"""
A 股数据获取模块
支持：akshare, tushare
"""

import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
import time

class DataFetcher:
    def __init__(self, tushare_token=None):
        self.tushare_token = tushare_token
        if tushare_token:
            import tushare as ts
            ts.set_token(tushare_token)
            self.ts_pro = ts.pro_api()
        else:
            self.ts_pro = None
    
    def get_stock_list(self, market='all'):
        """
        获取股票列表
        market: 'kcb'(科创板), 'cyb'(创业板), 'all'(全部)
        """
        print("获取股票列表...")
        
        if market == 'kcb' or market == 'all':
            kcb = ak.stock_sh_a_spot_em()
            kcb = kcb[kcb['代码'].str.startswith('688')]
        else:
            kcb = pd.DataFrame()
            
        if market == 'cyb' or market == 'all':
            cyb = ak.stock_sz_a_spot_em()
            cyb = cyb[cyb['代码'].str.startswith('300')]
        else:
            cyb = pd.DataFrame()
        
        if market == 'all':
            all_stocks = pd.concat([kcb, cyb], ignore_index=True)
        else:
            all_stocks = kcb if not kcb.empty else cyb
        
        print(f"共找到 {len(all_stocks)} 只股票")
        return all_stocks[['代码', '名称', '最新价', '涨跌幅']]
    
    def get_hist_data(self, stock_code, days=60, adjust='qfq'):
        """
        获取历史日线数据
        stock_code: 股票代码
        days: 获取天数
        adjust: 复权类型 'qfq'(前复权), 'hfq'(后复权), ''(不复权)
        """
        try:
            df = ak.stock_zh_a_hist(
                symbol=stock_code, 
                period="daily", 
                adjust=adjust
            )
            if df is None or len(df) < days:
                return None
            return df.head(days)
        except Exception as e:
            print(f"获取 {stock_code} 数据失败：{e}")
            return None
    
    def get_stock_info(self, stock_code):
        """获取股票基本信息"""
        try:
            df = ak.stock_individual_info_em(symbol=stock_code)
            return df.to_dict()
        except:
            return None
    
    def fetch_all_stocks_data(self, stock_list, days=60, delay=0.5):
        """
        批量获取股票数据
        stock_list: 股票代码列表
        delay: 请求间隔（秒），避免被封
        """
        results = []
        for i, code in enumerate(stock_list):
            if i % 50 == 0:
                print(f"进度：{i}/{len(stock_list)}")
            
            data = self.get_hist_data(code, days)
            if data is not None:
                results.append({
                    'code': code,
                    'data': data
                })
            
            time.sleep(delay)
        
        return results


if __name__ == "__main__":
    # 测试
    fetcher = DataFetcher()
    
    # 获取科创板 + 创业板列表
    stocks = fetcher.get_stock_list('all')
    print(stocks.head(10))
    
    # 获取单只股票历史数据
    test_code = '688001'
    hist = fetcher.get_hist_data(test_code, days=30)
    if hist is not None:
        print(f"\n{test_code} 最近 5 天数据:")
        print(hist[['日期', '开盘', '收盘', '最高', '最低', '成交量']].head())

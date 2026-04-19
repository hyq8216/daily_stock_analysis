#!/usr/bin/env python3
"""
NLP 情感分析模块
分析新闻、公告、社交媒体情绪
"""

import pandas as pd
import numpy as np
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
import akshare as ak
from datetime import datetime, timedelta


class SentimentAnalyzer:
    def __init__(self, model_name='bert-base-chinese'):
        """
        初始化情感分析器
        model_name: 预训练模型名称
        """
        self.device = 0 if torch.cuda.is_available() else -1
        
        # 中文情感分析模型
        print(f"加载情感分析模型：{model_name}...")
        try:
            self.analyzer = pipeline(
                "sentiment-analysis",
                model=model_name,
                device=self.device
            )
        except:
            # 备用方案：使用简单的关键词情感分析
            print("预训练模型加载失败，使用关键词分析...")
            self.analyzer = None
            self.positive_words = ['利好', '增长', '上涨', '突破', '创新高', '盈利', '超预期', '重组', '并购']
            self.negative_words = ['利空', '下跌', '亏损', '下滑', '风险', '违规', '处罚', '诉讼', '退市']
    
    def analyze_text(self, text):
        """
        分析单条文本情感
        """
        if self.analyzer is not None:
            result = self.analyzer(text[:512])[0]  # BERT 最大 512 token
            return {
                'label': result['label'],
                'score': result['score'],
                'sentiment': 'positive' if 'POS' in result['label'] or '正面' in result['label'] else 'negative'
            }
        else:
            # 关键词分析
            pos_count = sum(1 for word in self.positive_words if word in text)
            neg_count = sum(1 for word in self.negative_words if word in text)
            
            if pos_count > neg_count:
                return {'sentiment': 'positive', 'score': pos_count / (pos_count + neg_count)}
            elif neg_count > pos_count:
                return {'sentiment': 'negative', 'score': neg_count / (pos_count + neg_count)}
            else:
                return {'sentiment': 'neutral', 'score': 0.5}
    
    def analyze_stock_news(self, stock_code, days=7):
        """
        分析股票新闻情感
        """
        print(f"获取 {stock_code} 最近{days}天新闻...")
        
        try:
            # 获取个股新闻
            news_df = ak.stock_news_em(symbol=stock_code)
            
            if news_df is None or len(news_df) == 0:
                return None
            
            # 分析每条新闻
            results = []
            for _, row in news_df.iterrows():
                content = str(row.get('新闻内容', ''))[:512]
                if len(content) > 10:
                    sentiment = self.analyze_text(content)
                    sentiment['title'] = row.get('新闻标题', '')
                    sentiment['date'] = row.get('发布时间', '')
                    sentiment['url'] = row.get('新闻链接', '')
                    results.append(sentiment)
            
            # 汇总
            if len(results) == 0:
                return None
            
            df = pd.DataFrame(results)
            
            # 计算总体情感分数
            pos_ratio = (df['sentiment'] == 'positive').mean()
            neg_ratio = (df['sentiment'] == 'negative').mean()
            
            return {
                'stock_code': stock_code,
                'total_news': len(results),
                'positive_ratio': pos_ratio,
                'negative_ratio': neg_ratio,
                'neutral_ratio': 1 - pos_ratio - neg_ratio,
                'overall_sentiment': 'positive' if pos_ratio > neg_ratio else 'negative',
                'sentiment_score': pos_ratio - neg_ratio,
                'details': results[:10]  # 前 10 条详情
            }
            
        except Exception as e:
            print(f"分析新闻失败：{e}")
            return None
    
    def analyze_stock_guba(self, stock_code):
        """
        分析股吧评论情感
        """
        print(f"获取 {stock_code} 股吧评论...")
        
        try:
            # 获取股吧数据
            guba_df = ak.stock_guba_em()
            
            if guba_df is None:
                return None
            
            # 筛选相关股票
            stock_info = ak.stock_individual_info_em(symbol=stock_code)
            stock_name = None
            for _, row in stock_info.iterrows():
                if row['item'] == '股票代码':
                    stock_name = row['value']
                    break
            
            if stock_name:
                related = guba_df[guba_df['股票名称'].str.contains(stock_name, na=False)]
            else:
                related = guba_df.head(50)
            
            # 分析评论情感
            sentiments = []
            for _, row in related.iterrows():
                content = str(row.get('内容', ''))[:512]
                if len(content) > 10:
                    sentiment = self.analyze_text(content)
                    sentiments.append(sentiment['sentiment'])
            
            if len(sentiments) == 0:
                return None
            
            pos_ratio = (pd.Series(sentiments) == 'positive').mean()
            neg_ratio = (pd.Series(sentiments) == 'negative').mean()
            
            return {
                'stock_code': stock_code,
                'total_comments': len(sentiments),
                'positive_ratio': pos_ratio,
                'negative_ratio': neg_ratio,
                'overall_sentiment': 'positive' if pos_ratio > neg_ratio else 'negative',
                'sentiment_score': pos_ratio - neg_ratio
            }
            
        except Exception as e:
            print(f"分析股吧失败：{e}")
            return None
    
    def get_sentiment_signal(self, stock_code):
        """
        综合情感信号
        """
        news_result = self.analyze_stock_news(stock_code)
        guba_result = self.analyze_stock_guba(stock_code)
        
        signals = []
        weights = []
        
        if news_result:
            signals.append(1 if news_result['overall_sentiment'] == 'positive' else -1)
            weights.append(news_result['sentiment_score'])
            print(f"新闻情感：{news_result['overall_sentiment']} (得分：{news_result['sentiment_score']:.2f})")
        
        if guba_result:
            signals.append(1 if guba_result['overall_sentiment'] == 'positive' else -1)
            weights.append(guba_result['sentiment_score'])
            print(f"股吧情感：{guba_result['overall_sentiment']} (得分：{guba_result['sentiment_score']:.2f})")
        
        if len(signals) == 0:
            return {'signal': 'HOLD', 'confidence': 0}
        
        # 加权平均
        total_weight = sum(weights)
        if total_weight == 0:
            return {'signal': 'HOLD', 'confidence': 0}
        
        weighted_signal = sum(s * w for s, w in zip(signals, weights)) / total_weight
        
        if weighted_signal > 0.3:
            signal = 'BUY'
        elif weighted_signal < -0.3:
            signal = 'SELL'
        else:
            signal = 'HOLD'
        
        return {
            'signal': signal,
            'confidence': abs(weighted_signal),
            'news': news_result,
            'guba': guba_result
        }


if __name__ == "__main__":
    # 测试
    analyzer = SentimentAnalyzer()
    
    # 测试文本分析
    test_texts = [
        "公司业绩大幅增长，超预期盈利",
        "公司面临诉讼风险，股价可能下跌",
        "中性消息，无明显利好利空"
    ]
    
    print("=== 文本情感分析测试 ===\n")
    for text in test_texts:
        result = analyzer.analyze_text(text)
        print(f"文本：{text}")
        print(f"情感：{result['sentiment']}, 得分：{result.get('score', 0):.2f}\n")
    
    # 测试股票新闻分析
    print("\n=== 股票新闻情感分析 ===\n")
    result = analyzer.get_sentiment_signal('688001')
    print(f"\n综合信号：{result['signal']} (置信度：{result['confidence']:.2f})")

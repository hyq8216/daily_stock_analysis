# Daily Stock Analysis

每日自动股票分析系统，筛选连续小阳线股票，推送到 Notion。

## 📁 项目结构

```
daily_stock_analysis/
├── src/
│   └── daily_analysis.py    # 主分析脚本
├── config/
│   └── .env.example         # 环境变量示例
├── output/                   # 分析结果输出
├── logs/                     # 日志文件
├── .github/
│   └── workflows/
│       └── daily_analysis.yml  # GitHub Actions 配置
├── requirements.txt          # 依赖
└── README.md                 # 说明文档
```

## 🚀 部署步骤

### 1. Fork 到 GitHub

```bash
# 在 GitHub 上创建新仓库
# 然后推送代码
cd /Users/hyq/.openclaw/workspace/daily_stock_analysis
git init
git add .
git commit -m "Initial commit: daily stock analysis"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/daily_stock_analysis.git
git push -u origin main
```

### 2. 配置 GitHub Secrets

在 GitHub 仓库设置中添加：

1. 进入 **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. 添加以下密钥：

| Name | Value |
|------|-------|
| `NOTION_API_KEY` | `secret_xxxxx...`（你的 Notion API Key） |
| `NOTION_PAGE_ID` | `346ac5f8c03d810c9622f69d88d4bf0e` |
| `TUSHARE_TOKEN` | （可选）Tushare Pro Token |

### 3. 启用 GitHub Actions

1. 进入 **Actions** 标签页
2. 找到 "Daily Stock Analysis" 工作流
3. 点击 **Enable workflow**

### 4. 测试运行

```bash
# 手动触发工作流
# 方法 1: GitHub UI - Actions - Run workflow
# 方法 2: 本地测试
cd /Users/hyq/.openclaw/workspace/daily_stock_analysis
pip install -r requirements.txt
python src/daily_analysis.py
```

## ⏰ 运行时间

**默认**: 每个交易日早上 9:15（北京时间）

修改 `.github/workflows/daily_analysis.yml` 中的 cron 表达式：

```yaml
schedule:
  - cron: '15 1 * * 1-5'  # 周一到周五 01:15 UTC = 09:15 北京时间
```

## 📊 输出结果

### 本地输出
- `output/daily_analysis.csv` - CSV 格式结果
- `output/daily_analysis.json` - JSON 格式结果
- `output/daily_report.md` - Markdown 报告

### Notion 推送
自动追加到配置的 Notion 页面

## 🔧 配置选项

编辑 `config/.env`：

```bash
# 市场选择：all/kcb/cyb
MARKET=all

# 返回股票数量
TOP_N=20

# 最小连续天数
MIN_CONSECUTIVE_DAYS=3
```

## 📈 选股策略

**连续小阳线形态**：
- 连续 ≥3 天小阳线
- 单日涨幅 0.5% - 3%
- 收盘价 > 开盘价

**技术分析**：
- MA5/MA10 均线
- 价格/均线比率
- 成交量变化

**情感分析**（可选）：
- 新闻情感
- 股吧情绪

## ⚠️ 注意事项

1. **数据源限制** - 东方财富 API 可能限流，建议使用 Tushare Pro
2. **网络环境** - GitHub Actions 需要能访问 A 股数据源
3. **Notion 配额** - API 有速率限制，大量推送需注意
4. **投资风险** - 仅供参考，不构成投资建议

## 🔄 更新日志

- 2026-04-18: 初始版本
  - 连续小阳线筛选
  - Notion 推送
  - GitHub Actions 自动化

## 📄 许可证

MIT License

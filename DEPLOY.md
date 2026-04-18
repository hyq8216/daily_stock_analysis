# 部署指南

## 📋 部署步骤

### 步骤 1: 创建 GitHub 仓库

1. 打开 https://github.com/new
2. 仓库名：`daily_stock_analysis`
3. 可见性：**Public**（GitHub Actions 免费额度更多）
4. **不要**勾选 "Add a README file"
5. 点击 **Create repository**

### 步骤 2: 推送代码到 GitHub

```bash
# 替换 YOUR_USERNAME 为你的 GitHub 用户名
cd /Users/hyq/.openclaw/workspace/daily_stock_analysis
git remote add origin https://github.com/YOUR_USERNAME/daily_stock_analysis.git
git branch -M main
git push -u origin main
```

### 步骤 3: 配置 GitHub Secrets

1. 进入你的仓库页面
2. 点击 **Settings**（设置）
3. 左侧菜单：**Secrets and variables** → **Actions**
4. 点击 **New repository secret**

添加以下 3 个密钥：

| Name | Value | 说明 |
|------|-------|------|
| `NOTION_API_KEY` | `secret_xxxxx...` | Notion API Key |
| `NOTION_PAGE_ID` | `346ac5f8c03d810c9622f69d88d4bf0e` | 量化结果页面 ID |
| `TUSHARE_TOKEN` | （可选） | Tushare Pro Token |

**获取 Notion API Key**：
- 打开 https://notion.so/my-integrations
- 找到之前创建的 "OpenClaw" 集成
- 点击 "Manage integration" → 复制 "Internal Integration Token"

### 步骤 4: 启用 GitHub Actions

1. 点击仓库顶部的 **Actions** 标签
2. 找到 "Daily Stock Analysis" 工作流
3. 点击 **Enable workflow** 按钮

### 步骤 5: 测试运行

**方法 1: GitHub UI 手动触发**
1. Actions → Daily Stock Analysis
2. 点击 **Run workflow** 下拉按钮
3. 选择 main 分支
4. 点击 **Run workflow**

**方法 2: 本地测试**
```bash
cd /Users/hyq/.openclaw/workspace/daily_stock_analysis
pip install -r requirements.txt
python src/daily_analysis.py
```

### 步骤 6: 查看结果

**GitHub Actions 日志**：
- Actions → 点击运行记录 → 查看日志

**输出文件**（如果配置了 push）：
- `output/daily_analysis.csv`
- `output/daily_report.md`

**Notion 页面**：
- 打开之前创建的量化结果页面
- 应该能看到新推送的选股结果

---

## 🔧 故障排查

### 问题 1: Actions 运行失败

**检查**：
1. Secrets 是否正确配置
2. Notion API Key 是否有效
3. 网络是否能访问东方财富 API

**解决**：
```bash
# 本地测试
python src/daily_analysis.py
# 查看具体错误信息
```

### 问题 2: Notion 推送失败

**检查**：
1. Notion 页面是否已授权给集成
2. 页面 ID 是否正确
3. API Key 是否有权限

**解决**：
1. 打开 Notion 页面
2. 点击右上角 "···" → "Connect to"
3. 选择 "OpenClaw" 集成

### 问题 3: 数据获取失败

**原因**：东方财富 API 限流

**解决**：
1. 注册 Tushare Pro（免费）
2. 获取 Token
3. 添加到 GitHub Secrets
4. 修改代码使用 Tushare 数据源

---

## ⏰ 修改运行时间

编辑 `.github/workflows/daily_analysis.yml`：

```yaml
schedule:
  # cron 格式：分 时 日 月 周
  # 北京时间 = UTC + 8
  - cron: '15 1 * * 1-5'  # 周一到周五 09:15 北京
```

**常用时间**：
- `15 1 * * 1-5` → 交易日 09:15（开盘前）
- `30 9 * * *` → 每天 17:30（收盘后）
- `0 2 * * 6,0` → 周末 10:00

修改后推送：
```bash
git add .github/workflows/daily_analysis.yml
git commit -m "Update schedule"
git push
```

---

## 📊 查看运行历史

1. **Actions** 标签页
2. 点击工作流名称
3. 查看历史运行记录
4. 点击具体运行查看日志

---

## 🔄 自动推送结果到仓库

默认配置会将结果推送到仓库的 `output/` 目录。

如果不想推送（避免仓库过大），注释掉 `.github/workflows/daily_analysis.yml` 中的：

```yaml
# - name: Commit and Push Results
#   run: |
#     ...
```

---

## 💰 GitHub Actions 免费额度

**Public 仓库**：
- 每月 2000 分钟
- 每天运行约 1 次，每次 ~5 分钟
- 每月约 100-150 分钟（交易日）
- **完全够用**

**Private 仓库**：
- 每月 500 分钟
- 也够用，但建议用 Public

---

## ✅ 部署检查清单

- [ ] GitHub 仓库已创建
- [ ] 代码已推送
- [ ] Secrets 已配置（3 个）
- [ ] Actions 已启用
- [ ] 手动测试运行成功
- [ ] Notion 收到推送结果
- [ ] 定时任务已设置

全部完成后，系统会自动在每个交易日早上运行！

# 抖音/1688 选品采集骨架

该仓库提供一个可直接扩展的采集骨架：

`数据源 -> Playwright采集 -> 解析 -> SQLite入库 -> 去重清洗 -> 输出`

## 覆盖范围

- **第一优先（已实现骨架）**
  - 抖音搜索/商品池页采集（商品卡流）
  - 抖音视频互动信号（点赞/评论，基于搜索卡片文本）
- **第二优先（待扩展）**
  - 1688货源价格与SKU结构

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install playwright
playwright install chromium
python collector.py
```

## 当前入库表

`products_raw`

- id
- product_id
- title
- price
- sales_estimate
- video_count
- likes
- comments
- video_url
- source
- created_at

## 关键策略

- 反检测参数：`--disable-blink-features=AutomationControlled`
- 行为模拟：滚动 + 随机停顿
- 频率控制：每轮采集限制30条，可按关键词轮询
- 去重策略：`title + source` 唯一索引

## 后续建议

1. 增加登录态（cookie持久化）提升完整度。
2. 抖音页面选择器改为更细粒度字段抽取（价格、商品ID、店铺ID）。
3. 新增1688采集器并统一归档到同一数据模型。
4. 新增评分输出接口，对接选品系统（如 OpenClaw）。

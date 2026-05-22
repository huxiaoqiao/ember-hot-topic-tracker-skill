---
name: ember-hot-topic-tracker-skill
description: 每日自动抓取微博热搜、今日头条热点、百度指数上升词的 Top20 热点话题，分类聚合后输出结构化 JSON，含热度趋势分析。
version: 1.0.0
author: ember
license: MIT
metadata:
  hermes:
    min_version: "0.1.0"
    category: automation
    tags:
      - hot-topic
      - weibo
      - toutiao
      - baidu
      - trend-analysis
      - daily-report
triggers:
  - "热搜"
  - "热点话题"
  - "今日热点"
  - "微博热搜"
  - "头条热点"
  - "百度指数"
  - "热点追踪"
  - "hot topic tracker"
  - "trending analysis"
---

# Ember Hot Topic Tracker Skill

每日自动抓取多平台热点话题并分类聚合，输出结构化 JSON 含热度趋势分析。

## 功能概览

| 平台 | 数据源 | 输出 |
|------|--------|------|
| 微博 | 热搜榜 Top20 | 话题 + 热度值 + 分类标签 |
| 今日头条 | 热点榜 Top20 | 标题 + 热度值 + 分类标签 |
| 百度指数 | 上升词 Top20 | 关键词 + 搜索指数 + 涨幅 |

## 使用方式

### 快速抓取（一次运行）

    python scripts/hot_topic_tracker.py --all

### 指定平台抓取

    python scripts/hot_topic_tracker.py --weibo
    python scripts/hot_topic_tracker.py --toutiao
    python scripts/hot_topic_tracker.py --baidu

### 输出格式

运行后在 output/ 目录生成结构化 JSON 文件，包含 sources、categories、trend_analysis 三大模块。

## 依赖项

- Python 3.8+
- requests
- beautifulsoup4
- lxml

## 安装

    pip install -r scripts/requirements.txt

## 配置

API Key 配置见 references/api-config.md。将 .env.example 复制为 .env 并填入实际 Key。

## 数据结构定义

详见 references/data-schema.md。

## 注意事项

- 微博热搜无需 API Key，使用页面抓取方式
- 今日头条热点无需 API Key，使用公开接口
- 百度指数需要配置 Cookie（详见 API 文档）
- 脚本内置频率限制重试机制（指数退避，最多3次）
- 所有编码使用 UTF-8，兼容 GBK 响应自动转码
- 空数据返回兜底结构，不会抛出异常

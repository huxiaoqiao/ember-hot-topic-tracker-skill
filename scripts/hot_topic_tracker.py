#!/usr/bin/env python3
"""
ember-hot-topic-tracker-skill
每日自动抓取微博热搜、今日头条热点、百度指数上升词的 Top20 热点话题
分类聚合后输出结构化 JSON，含热度趋势分析

Bug Fixes:
1. 空数据兜底 - 所有平台抓取失败时返回空结构而非抛异常
2. 频率限制重试 - HTTP 429 指数退避重试(1s->2s->4s)，最多3次
3. 编码兼容 - 自动检测响应编码，GBK->UTF-8自动转换
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

VERSION = "1.0.0"

CST = timezone(timedelta(hours=8))

CATEGORY_KEYWORDS = {
    "科技": ["AI", "人工智能", "芯片", "手机", "科技", "互联网", "数码", "编程",
             "算法", "大数据", "云计算", "5G", "华为", "苹果", "小米", "自动驾驶",
             "机器人", "量子", "航天", "卫星", "OpenAI", "ChatGPT", "大模型", "LLM"],
    "娱乐": ["电影", "综艺", "明星", "演员", "歌手", "偶像", "演唱会", "票房",
             "导演", "电视剧", "偶像剧", "追剧", "热搜", "娱乐圈", "出道", "粉丝"],
    "财经": ["股票", "基金", "A股", "港股", "美股", "通胀", "利率", "央行",
             "经济", "GDP", "上市", "融资", "创业", "投资", "比特币", "币圈",
             "期货", "外汇", "银行", "贷款"],
    "社会": ["疫情", "事故", "救灾", "政策", "改革", "法律", "维权", "民生",
             "教育", "就业", "房价", "人口", "养老", "社保", "犯罪", "执法"],
    "体育": ["足球", "篮球", "NBA", "CBA", "世界杯", "奥运", "冠军", "联赛",
             "比赛", "运动员", "教练", "裁判", "乒乓球", "羽毛球", "网球",
             "游泳", "田径", "格斗", "拳击", "滑雪"],
    "教育": ["高考", "考研", "大学", "招生", "考试", "教材", "双减", "培训",
             "学校", "毕业", "学位", "留学", "雅思", "托福", "四六级", "公务员"],
    "健康": ["健康", "医疗", "疫苗", "药品", "医院", "中医", "养生", "体检",
             "手术", "癌症", "糖尿病", "心血管", "饮食", "减肥", "心理", "睡眠"],
    "游戏": ["游戏", "电竞", "Steam", "手游", "端游", "主机", "PS5", "Switch",
             "Xbox", "原神", "王者荣耀", "英雄联盟", "LOL", "绝地求生",
             "我的世界", "赛博朋克", "开放世界", "RPG"],
    "汽车": ["汽车", "电动车", "新能源", "特斯拉", "比亚迪", "蔚来", "理想",
             "小鹏", "充电桩", "自动驾驶", "汽油", "混动", "SUV", "轿车",
             "跑车", "试驾", "4S店", "驾照"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

MAX_RETRIES = 3


def _classify_topic(title: str) -> str:
    title_upper = title.upper()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.upper() in title_upper)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return "其他"


def _request_with_retry(url: str, **kwargs):
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", 15)
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, **kwargs)
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"  [Retry {attempt+1}/{MAX_RETRIES}] HTTP 429, waiting {wait}s: {url}",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"  [Retry {attempt+1}/{MAX_RETRIES}] {type(e).__name__}: {e}",
                      file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"  [Failed] All {MAX_RETRIES} retries exhausted for {url}",
                      file=sys.stderr)
    return None


def _decode_response(resp):
    content = resp.content
    if resp.apparent_encoding:
        try:
            return content.decode(resp.apparent_encoding)
        except (UnicodeDecodeError, LookupError):
            pass
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return content.decode("gbk")
    except (UnicodeDecodeError, LookupError):
        pass
    return content.decode("utf-8", errors="replace")


def fetch_weibo():
    url = "https://weibo.com/ajax/side/hotSearch"
    items = []
    try:
        resp = _request_with_retry(url)
        if not resp:
            return items
        data = resp.json()
        realtime = data.get("data", {}).get("realtime", [])
        for entry in realtime[:20]:
            word = entry.get("word", "").strip()
            if not word:
                continue
            note = entry.get("note", word)
            num = entry.get("num", 0)
            label_name = entry.get("label_name", "")
            rank = entry.get("rank", 0)
            trend = "→ 稳定"
            if label_name in ("热", "沸", "爆"):
                trend = "↑ 上升"
            elif label_name == "新":
                trend = "↑ 新增"
            hot_value = min(100, num / 10000) if num > 0 else 0
            items.append({
                "rank": rank or (len(items) + 1),
                "title": note or word,
                "hot_value": round(hot_value, 1),
                "hot_raw": num,
                "label": label_name,
                "trend": trend,
                "source": "weibo",
                "category": _classify_topic(note or word),
                "url": f"https://s.weibo.com/weibo?q=%23{word}%23",
            })
    except Exception as e:
        print(f"  [Weibo Error] {e}", file=sys.stderr)
    return items


def fetch_toutiao():
    url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
    items = []
    try:
        resp = _request_with_retry(url)
        if not resp:
            return items
        data = resp.json()
        board = data.get("data", [])
        for entry in board[:20]:
            title = entry.get("Title", "").strip()
            if not title:
                continue
            hot_val = entry.get("HotValue", "0")
            cluster_id = entry.get("ClusterId", "")
            label = entry.get("Label", "")
            try:
                hot_num = int(hot_val)
            except (ValueError, TypeError):
                hot_num = 0
            hot_value = min(100, hot_num / 100000) if hot_num > 0 else 0
            trend = "→ 稳定"
            if label in ("热", "荐"):
                trend = "↑ 上升"
            elif label == "新":
                trend = "↑ 新增"
            items.append({
                "rank": len(items) + 1,
                "title": title,
                "hot_value": round(hot_value, 1),
                "hot_raw": hot_num,
                "label": label,
                "trend": trend,
                "source": "toutiao",
                "category": _classify_topic(title),
                "url": f"https://www.toutiao.com/trending/{cluster_id}/",
            })
    except Exception as e:
        print(f"  [Toutiao Error] {e}", file=sys.stderr)
    return items


def fetch_baidu():
    url = "https://top.baidu.com/board?tab=realtime"
    items = []
    try:
        resp = _request_with_retry(url)
        if not resp:
            return items
        text = _decode_response(resp)
        soup = BeautifulSoup(text, "lxml")
        content_items = soup.select(".category-wrap_iQLoo")
        for idx, card in enumerate(content_items[:20], 1):
            title_tag = card.select_one(".c-single-text-ellipsis")
            title = title_tag.get_text(strip=True) if title_tag else ""
            hot_tag = card.select_one(".hot-index_1Bl1a")
            hot_raw = 0
            if hot_tag:
                hot_text = hot_tag.get_text(strip=True).replace(",", "")
                try:
                    hot_raw = int(hot_text)
                except ValueError:
                    hot_raw = 0
            trend_tag = card.select_one(".icon-text_J2qom")
            trend = "→ 稳定"
            if trend_tag:
                trend_text = trend_tag.get_text(strip=True)
                if "↑" in trend_text or "涨" in trend_text:
                    trend = f"↑ 上升 ({trend_text})"
                elif "↓" in trend_text or "跌" in trend_text:
                    trend = f"↓ 下降 ({trend_text})"
            hot_value = min(100, hot_raw / 50000) if hot_raw > 0 else 0
            if title:
                items.append({
                    "rank": idx,
                    "title": title,
                    "hot_value": round(hot_value, 1),
                    "hot_raw": hot_raw,
                    "label": "",
                    "trend": trend,
                    "source": "baidu",
                    "category": _classify_topic(title),
                    "url": "https://www.baidu.com/s?wd=" + requests.utils.quote(title),
                })
        if not items:
            items = _fetch_baidu_from_json(text)
    except Exception as e:
        print(f"  [Baidu Error] {e}", file=sys.stderr)
    return items


def _fetch_baidu_from_json(text):
    items = []
    try:
        match = re.search(r'<!--s-data:(.*?)-->', text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            cards = (data.get("data", {})
                     .get("cards", [{}])[0]
                     .get("content", []))
            for idx, card in enumerate(cards[:20], 1):
                title = card.get("word", "").strip()
                hot_raw = card.get("hotScore", 0)
                hot_value = min(100, hot_raw / 50000) if hot_raw > 0 else 0
                trend = "→ 稳定"
                if card.get("isNew", False):
                    trend = "↑ 新增"
                elif card.get("isHot", False):
                    trend = "↑ 上升"
                if title:
                    items.append({
                        "rank": idx,
                        "title": title,
                        "hot_value": round(hot_value, 1),
                        "hot_raw": hot_raw,
                        "label": "",
                        "trend": trend,
                        "source": "baidu",
                        "category": _classify_topic(title),
                        "url": card.get("rawUrl",
                               "https://www.baidu.com/s?wd=" + requests.utils.quote(title)),
                    })
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  [Baidu JSON parse error] {e}", file=sys.stderr)
    return items


def aggregate_by_category(weibo, toutiao, baidu):
    category_map = {}
    for item in weibo + toutiao + baidu:
        cat = item.get("category", "其他")
        if cat not in category_map:
            category_map[cat] = []
        category_map[cat].append(item)
    for cat in category_map:
        category_map[cat].sort(key=lambda x: x.get("hot_value", 0), reverse=True)
    return category_map


def analyze_trends(weibo, toutiao, baidu):
    all_items = weibo + toutiao + baidu
    rising = []
    stable = []
    falling = []
    for item in all_items:
        trend = item.get("trend", "")
        title = item.get("title", "")
        source = item.get("source", "")
        hot = item.get("hot_value", 0)
        cat = item.get("category", "其他")
        if "上升" in trend or "新增" in trend or "↑" in trend:
            rising.append({"title": title, "source": source, "current_hot": hot, "trend": trend, "category": cat})
        elif "下降" in trend or "↓" in trend:
            falling.append({"title": title, "source": source, "current_hot": hot, "trend": trend, "category": cat})
        else:
            stable.append({"title": title, "source": source, "current_hot": hot, "trend": trend, "category": cat})
    rising.sort(key=lambda x: x["current_hot"], reverse=True)
    stable.sort(key=lambda x: x["current_hot"], reverse=True)
    falling.sort(key=lambda x: x["current_hot"], reverse=True)
    total = len(all_items)
    rising_pct = (len(rising) / total * 100) if total > 0 else 0
    summary = f"共{total}条热点，{len(rising)}条上升({rising_pct:.0f}%)，{len(stable)}条稳定，{len(falling)}条下降"
    cat_distribution = {}
    for item in all_items:
        cat = item.get("category", "其他")
        cat_distribution[cat] = cat_distribution.get(cat, 0) + 1
    cat_sorted = dict(sorted(cat_distribution.items(), key=lambda x: x[1], reverse=True))
    cross_platform = []
    seen_titles = {}
    for item in all_items:
        title_key = item["title"][:6]
        if title_key in seen_titles and item["source"] not in seen_titles[title_key]:
            cross_platform.append({"title": item["title"], "sources": seen_titles[title_key] + [item["source"]]})
        else:
            if title_key not in seen_titles:
                seen_titles[title_key] = []
            if item["source"] not in seen_titles[title_key]:
                seen_titles[title_key].append(item["source"])
    return {
        "summary": summary,
        "rising_count": len(rising),
        "stable_count": len(stable),
        "falling_count": len(falling),
        "rising_top5": rising[:5],
        "category_distribution": cat_sorted,
        "cross_platform_topics": cross_platform[:10],
    }


def _empty_report(errors):
    return {
        "timestamp": datetime.now(CST).isoformat(),
        "sources": {"weibo": [], "toutiao": [], "baidu": []},
        "categories": {},
        "trend_analysis": {
            "summary": "所有平台数据抓取失败，请检查网络连接和接口可用性",
            "rising_count": 0, "stable_count": 0, "falling_count": 0,
            "rising_top5": [], "category_distribution": {},
            "cross_platform_topics": [],
        },
        "meta": {
            "version": VERSION, "source_count": 0, "total_items": 0,
            "fetch_duration_ms": 0, "errors": errors,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="热点话题追踪器")
    parser.add_argument("--weibo", action="store_true", help="仅抓取微博热搜")
    parser.add_argument("--toutiao", action="store_true", help="仅抓取今日头条热点")
    parser.add_argument("--baidu", action="store_true", help="仅抓取百度热搜")
    parser.add_argument("--all", action="store_true", help="抓取所有平台(默认)")
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")
    parser.add_argument("--output", "-o", type=str, help="输出文件路径")
    args = parser.parse_args()
    if not (args.weibo or args.toutiao or args.baidu):
        args.all = True

    start_time = time.time()
    weibo, toutiao, baidu = [], [], []
    errors = []

    print("🔥 Hot Topic Tracker v" + VERSION, file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    if args.all or args.weibo:
        print("  抓取微博热搜...", file=sys.stderr)
        weibo = fetch_weibo()
        if not weibo:
            errors.append({"source": "weibo", "error_type": "empty_data", "message": "微博热搜数据为空"})
        else:
            print(f"    ✓ 微博: {len(weibo)} 条", file=sys.stderr)

    if args.all or args.toutiao:
        print("  抓取今日头条热点...", file=sys.stderr)
        toutiao = fetch_toutiao()
        if not toutiao:
            errors.append({"source": "toutiao", "error_type": "empty_data", "message": "今日头条数据为空"})
        else:
            print(f"    ✓ 头条: {len(toutiao)} 条", file=sys.stderr)

    if args.all or args.baidu:
        print("  抓取百度热搜...", file=sys.stderr)
        baidu = fetch_baidu()
        if not baidu:
            errors.append({"source": "baidu", "error_type": "empty_data", "message": "百度热搜数据为空"})
        else:
            print(f"    ✓ 百度: {len(baidu)} 条", file=sys.stderr)

    if not weibo and not toutiao and not baidu:
        report = _empty_report(errors)
        indent = 2 if args.pretty else None
        print(json.dumps(report, ensure_ascii=False, indent=indent))
        return report

    categories = aggregate_by_category(weibo, toutiao, baidu)
    trend_analysis = analyze_trends(weibo, toutiao, baidu)
    duration_ms = int((time.time() - start_time) * 1000)

    report = {
        "timestamp": datetime.now(CST).isoformat(),
        "sources": {"weibo": weibo, "toutiao": toutiao, "baidu": baidu},
        "categories": categories,
        "trend_analysis": trend_analysis,
        "meta": {
            "version": VERSION,
            "source_count": sum(1 for v in [weibo, toutiao, baidu] if v),
            "total_items": len(weibo) + len(toutiao) + len(baidu),
            "fetch_duration_ms": duration_ms,
            "errors": errors,
        },
    }

    indent = 2 if args.pretty else None
    json_str = json.dumps(report, ensure_ascii=False, indent=indent)

    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        ts = datetime.now(CST).strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"hot_topics_{ts}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_str)

    print("=" * 60, file=sys.stderr)
    print("Hot Topic Tracker Report", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  Timestamp: {report['timestamp']}", file=sys.stderr)
    print(f"  Sources:   {report['meta']['source_count']} platforms", file=sys.stderr)
    print(f"  Total:     {report['meta']['total_items']} topics", file=sys.stderr)
    print(f"  Duration:  {duration_ms}ms", file=sys.stderr)
    print(f"  Categories: {', '.join(categories.keys())}", file=sys.stderr)
    print(f"  Trend:     {trend_analysis['summary']}", file=sys.stderr)
    if errors:
        print(f"  Errors:  {len(errors)}", file=sys.stderr)
        for err in errors:
            print(f"    - [{err['source']}] {err['message']}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  Output: {output_path}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    print(json_str)
    return report


if __name__ == "__main__":
    main()

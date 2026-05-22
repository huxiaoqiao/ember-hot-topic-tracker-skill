#!/usr/bin/env python3
"""
Ember Hot Topic Tracker Skill
每日自动抓取微博热搜、今日头条热点、百度指数上升词的 Top20 热点话题
分类聚合后输出结构化 JSON，含热度趋势分析

Bug Fixes:
- 空数据兜底：所有平台抓取失败时返回空结构而非抛异常
- 频率限制重试：指数退避重试机制（1s -> 2s -> 4s），最多3次
- 编码兼容：自动检测响应编码，GBK->UTF-8 自动转换
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    print("Error: requests is required. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 is required. Run: pip install beautifulsoup4", file=sys.stderr)
    sys.exit(1)

# Constants
VERSION = "1.0.0"
TOP_N = 20
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
CST = timezone(timedelta(hours=8))

CATEGORY_MAP = {
    "科技": ["科技", "互联网", "数码", "AI", "人工智能", "手机", "芯片", "5G", "机器人"],
    "娱乐": ["娱乐", "影视", "综艺", "明星", "电影", "音乐", "偶像"],
    "财经": ["财经", "经济", "金融", "股市", "基金", "银行", "房产"],
    "社会": ["社会", "民生", "时事", "法治", "政务", "反腐"],
    "体育": ["体育", "足球", "篮球", "奥运", "NBA", "世界杯", "赛事"],
    "教育": ["教育", "考试", "高考", "考研", "大学", "学校"],
    "健康": ["健康", "医疗", "养生", "疫情", "疫苗", "医院"],
    "游戏": ["游戏", "电竞", "手游", "主机", "网游", "Steam"],
    "汽车": ["汽车", "新能源", "电车", "自动驾驶", "造车"],
}


def classify_topic(text):
    """根据文本内容分类话题"""
    for category, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in text:
                return category
    return "其他"


def normalize_hot(value, max_value):
    """将热度值归一化到 0-100"""
    if max_value <= 0:
        return 0.0
    return round(min(value / max_value * 100, 100), 2)


def parse_change_percent(change_str):
    """解析变化百分比字符串"""
    if not change_str:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)%", str(change_str))
    if match:
        return float(match.group(1))
    return None


def safe_request(url, headers=None, cookies=None, timeout=15):
    """带重试机制的 HTTP 请求（Bug Fix: 频率限制重试 + 编码兼容）"""
    req_headers = {"User-Agent": DEFAULT_UA, "Accept": "application/json, text/html, */*"}
    if headers:
        req_headers.update(headers)

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=req_headers, cookies=cookies,
                                timeout=timeout, allow_redirects=True)
            resp.raise_for_status()

            # Bug Fix: 编码兼容 - 自动检测并转换编码
            if resp.encoding and resp.encoding.lower() not in ("utf-8", "utf8"):
                resp.encoding = "utf-8"
            elif not resp.encoding:
                resp.encoding = resp.apparent_encoding or "utf-8"

            return resp

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            if status_code == 429:
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                print(f"  [Retry {attempt+1}/{MAX_RETRIES}] Rate limited (429), "
                      f"waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            elif status_code >= 500:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF[attempt])
                    continue
                print(f"  [Error] Server error {status_code} after {MAX_RETRIES} retries",
                      file=sys.stderr)
                return None
            else:
                print(f"  [Error] HTTP {status_code}: {e}", file=sys.stderr)
                return None

        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF[attempt])
                continue
            print(f"  [Error] Request timeout after {MAX_RETRIES} retries", file=sys.stderr)
            return None

        except requests.exceptions.RequestException as e:
            print(f"  [Error] Request failed: {e}", file=sys.stderr)
            return None

    return None


def empty_result(source):
    """Bug Fix: 空数据兜底 - 返回空列表而非抛异常"""
    print(f"  [Fallback] {source}: returning empty data", file=sys.stderr)
    return []


def fetch_weibo():
    """抓取微博热搜 Top20"""
    print("[Fetching] 微博热搜...")
    url = "https://weibo.com/ajax/side/hotSearch"
    resp = safe_request(url)
    if not resp:
        return empty_result("weibo")
    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        return empty_result("weibo")

    realtime = data.get("data", {}).get("realtime", [])
    if not realtime:
        return empty_result("weibo")

    items = []
    now = datetime.now(CST).isoformat()
    for i, entry in enumerate(realtime[:TOP_N]):
        title = entry.get("note", entry.get("word", ""))
        keyword = entry.get("word", title)
        hot_value = entry.get("num", entry.get("raw_hot", 0))
        raw_hot = entry.get("raw_hot", hot_value)
        category = entry.get("category", "")
        label = entry.get("icon_desc", "")
        items.append({
            "rank": i + 1,
            "title": title,
            "keyword": keyword,
            "hot_value": hot_value,
            "raw_hot": raw_hot,
            "category": category or classify_topic(title),
            "label": label,
            "fetched_at": now,
        })
    print(f"  Got {len(items)} items from Weibo")
    return items


def fetch_toutiao():
    """抓取今日头条热点 Top20"""
    print("[Fetching] 今日头条热点...")
    url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
    headers = {"Referer": "https://www.toutiao.com/"}
    resp = safe_request(url, headers=headers)
    if not resp:
        return empty_result("toutiao")
    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        return empty_result("toutiao")

    board_data = data.get("data", [])
    if not board_data:
        return empty_result("toutiao")

    items = []
    now = datetime.now(CST).isoformat()
    for i, entry in enumerate(board_data[:TOP_N]):
        title = entry.get("Title", "")
        hot_str = entry.get("HotValue", "0")
        try:
            hot_value = int(hot_str)
        except (ValueError, TypeError):
            hot_value = 0
        cluster_id = entry.get("ClusterIdStr", entry.get("ClusterId", ""))
        label = entry.get("Label", "")
        url_link = entry.get("Url", "")
        items.append({
            "rank": i + 1,
            "title": title,
            "hot_value": hot_value,
            "cluster_id": cluster_id,
            "label": label,
            "url": url_link,
            "category": classify_topic(title),
            "fetched_at": now,
        })
    print(f"  Got {len(items)} items from Toutiao")
    return items


def fetch_baidu():
    """抓取百度指数上升词 Top20"""
    print("[Fetching] 百度指数上升词...")
    url = "https://top.baidu.com/board?tab=realtime"

    cookies = {}
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key == "BAIDU_BDUSS":
                        cookies["BDUSS"] = value
                    elif key == "BAIDU_STOKEN":
                        cookies["STOKEN"] = value

    headers = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
               "Referer": "https://top.baidu.com/"}
    resp = safe_request(url, headers=headers, cookies=cookies if cookies else None)
    if not resp:
        return empty_result("baidu")

    items = []
    now = datetime.now(CST).isoformat()

    try:
        soup = BeautifulSoup(resp.text, "lxml")
        # Try embedded JSON in script tags
        scripts = soup.find_all("script")
        for script in scripts:
            text = script.string or ""
            script_type = script.get("type", "")
            if "s-json" in script_type or "data" in text[:200] if len(text) > 200 else False:
                try:
                    json_data = json.loads(text)
                    content_list = (
                        json_data.get("data", {})
                        .get("cards", [{}])[0]
                        .get("content", [])
                    )
                    for i, entry in enumerate(content_list[:TOP_N]):
                        word = entry.get("word", "")
                        hot_score = int(entry.get("hotScore", "0") or "0")
                        change = entry.get("showChange", "")
                        desc = entry.get("desc", "")
                        items.append({
                            "rank": i + 1,
                            "keyword": word,
                            "hot_score": hot_score,
                            "change": change,
                            "change_percent": parse_change_percent(change),
                            "description": desc,
                            "category": classify_topic(word + " " + desc),
                            "fetched_at": now,
                        })
                    break
                except (json.JSONDecodeError, KeyError, IndexError, ValueError):
                    continue

        # Fallback: parse HTML div structure
        if not items:
            cards = soup.select(".category-wrap_iQLoo")
            if not cards:
                cards = soup.select("[class*=category-wrap]")
            for i, card in enumerate(cards[:TOP_N]):
                title_el = card.select_one(".c-single-text-ellipsis")
                if not title_el:
                    title_el = card.select_one("[class*=text-ellipsis]")
                hot_el = card.select_one(".hot-index_1Bl1a")
                if not hot_el:
                    hot_el = card.select_one("[class*=hot-index]")
                change_el = card.select_one(".hot-change_3ddQs")
                if not change_el:
                    change_el = card.select_one("[class*=hot-change]")
                desc_el = card.select_one(".hot-desc_1m_jR")
                if not desc_el:
                    desc_el = card.select_one("[class*=hot-desc]")

                title = title_el.get_text(strip=True) if title_el else ""
                hot_score = 0
                if hot_el:
                    try:
                        hot_score = int(re.sub(r"[^\d]", "", hot_el.get_text()))
                    except ValueError:
                        pass
                change = change_el.get_text(strip=True) if change_el else ""
                desc = desc_el.get_text(strip=True) if desc_el else ""
                items.append({
                    "rank": i + 1,
                    "keyword": title,
                    "hot_score": hot_score,
                    "change": change,
                    "change_percent": parse_change_percent(change),
                    "description": desc,
                    "category": classify_topic(title + " " + desc),
                    "fetched_at": now,
                })
    except Exception as e:
        print(f"  [Error] Baidu parse failed: {e}", file=sys.stderr)
        return empty_result("baidu")

    if not items:
        return empty_result("baidu")
    print(f"  Got {len(items)} items from Baidu")
    return items


def aggregate_by_category(weibo, toutiao, baidu):
    """按分类聚合所有平台数据"""
    categories = {}
    max_hot = 1
    all_items = []
    for item in weibo:
        all_items.append(("weibo", item))
        max_hot = max(max_hot, item.get("hot_value", item.get("raw_hot", 0)))
    for item in toutiao:
        all_items.append(("toutiao", item))
        max_hot = max(max_hot, item.get("hot_value", 0))
    for item in baidu:
        all_items.append(("baidu", item))
        max_hot = max(max_hot, item.get("hot_score", 0))

    for source, item in all_items:
        cat = item.get("category", "其他")
        if cat not in categories:
            categories[cat] = []
        hot_val = item.get("hot_value", 0) or item.get("hot_score", 0) or item.get("raw_hot", 0)
        categories[cat].append({
            "source": source,
            "title": item.get("title", item.get("keyword", "")),
            "normalized_hot": normalize_hot(hot_val, max_hot),
            "raw_hot": hot_val,
            "category": cat,
            "rank": item.get("rank", 0),
            "url": item.get("url", ""),
            "fetched_at": item.get("fetched_at", ""),
        })

    for cat in categories:
        categories[cat].sort(key=lambda x: x["normalized_hot"], reverse=True)
    return categories


def analyze_trends(weibo, toutiao, baidu):
    """热度趋势分析"""
    rising = []
    stable = []
    declining = []

    for item in baidu:
        pct = item.get("change_percent")
        keyword = item.get("keyword", "")
        cat = item.get("category", "其他")
        hot = item.get("hot_score", 0)
        if pct is not None:
            if pct > 50:
                rising.append({"title": keyword, "source": "baidu", "current_hot": hot,
                               "trend": f"上升{pct:.0f}%", "category": cat})
            elif pct > 0:
                stable.append({"title": keyword, "source": "baidu", "current_hot": hot,
                               "trend": f"小幅上升{pct:.0f}%", "category": cat})
        else:
            stable.append({"title": keyword, "source": "baidu", "current_hot": hot,
                           "trend": "稳定", "category": cat})

    for item in weibo:
        label = item.get("label", "")
        title = item.get("title", item.get("keyword", ""))
        cat = item.get("category", "其他")
        hot = item.get("hot_value", 0)
        if label == "沸":
            rising.append({"title": title, "source": "weibo", "current_hot": hot,
                           "trend": "沸腾", "category": cat})
        elif label == "新":
            rising.append({"title": title, "source": "weibo", "current_hot": hot,
                           "trend": "新增", "category": cat})
        elif label == "热":
            stable.append({"title": title, "source": "weibo", "current_hot": hot,
                           "trend": "热门", "category": cat})
        else:
            stable.append({"title": title, "source": "weibo", "current_hot": hot,
                           "trend": "稳定", "category": cat})

    for item in toutiao:
        label = item.get("label", "")
        title = item.get("title", "")
        cat = item.get("category", "其他")
        hot = item.get("hot_value", 0)
        if label in ("热", "新", "荐"):
            rising.append({"title": title, "source": "toutiao", "current_hot": hot,
                           "trend": label, "category": cat})
        else:
            stable.append({"title": title, "source": "toutiao", "current_hot": hot,
                           "trend": "稳定", "category": cat})

    total = len(rising) + len(stable) + len(declining)
    summary = f"共追踪 {total} 个热点话题，其中 {len(rising)} 个呈上升趋势，{len(stable)} 个保持稳定，{len(declining)} 个呈下降趋势。"
    rising.sort(key=lambda x: x["current_hot"], reverse=True)
    stable.sort(key=lambda x: x["current_hot"], reverse=True)
    return {"rising": rising[:20], "stable": stable[:20], "declining": declining[:20], "summary": summary}


def main():
    parser = argparse.ArgumentParser(description="Ember Hot Topic Tracker - 多平台热点追踪")
    parser.add_argument("--all", action="store_true", help="抓取所有平台")
    parser.add_argument("--weibo", action="store_true", help="仅抓取微博热搜")
    parser.add_argument("--toutiao", action="store_true", help="仅抓取今日头条")
    parser.add_argument("--baidu", action="store_true", help="仅抓取百度指数")
    parser.add_argument("--output", "-o", type=str, default=None, help="输出文件路径")
    parser.add_argument("--pretty", action="store_true", help="美化 JSON 输出")

    args = parser.parse_args()
    if not any([args.all, args.weibo, args.toutiao, args.baidu]):
        args.all = True

    start_time = time.time()
    errors = []
    weibo = []
    toutiao = []
    baidu = []

    if args.all or args.weibo:
        weibo = fetch_weibo()
        if not weibo:
            errors.append({"source": "weibo", "error_type": "empty_data",
                           "message": "微博热搜数据为空，可能接口不可用或被限流"})

    if args.all or args.toutiao:
        toutiao = fetch_toutiao()
        if not toutiao:
            errors.append({"source": "toutiao", "error_type": "empty_data",
                           "message": "今日头条热点数据为空，可能接口不可用或被限流"})

    if args.all or args.baidu:
        baidu = fetch_baidu()
        if not baidu:
            errors.append({"source": "baidu", "error_type": "empty_data",
                           "message": "百度指数数据为空，可能需要配置 Cookie 或接口变更"})

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

    print(f"
{'='*60}")
    print(f"Hot Topic Tracker Report")
    print(f"{'='*60}")
    print(f"  Timestamp: {report['timestamp']}")
    print(f"  Sources:   {report['meta']['source_count']} platforms")
    print(f"  Total:     {report['meta']['total_items']} topics")
    print(f"  Duration:  {duration_ms}ms")
    print(f"  Categories: {', '.join(categories.keys())}")
    print(f"  Trend:     {trend_analysis['summary']}")
    if errors:
        print(f"  Errors:  {len(errors)}")
        for err in errors:
            print(f"    - [{err['source']}] {err['message']}")
    print(f"{'='*60}")
    print(f"  Output: {output_path}")
    print(f"{'='*60}")

    return report


if __name__ == "__main__":
    main()

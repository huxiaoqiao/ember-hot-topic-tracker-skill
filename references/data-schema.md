# 数据结构定义

## 顶层输出结构

    interface HotTopicReport {
      timestamp: string;          // 报告生成时间 (ISO 8601)
      sources: {
        weibo: WeiboHotItem[];
        toutiao: ToutiaoHotItem[];
        baidu: BaiduHotItem[];
      };
      categories: Record<string, UnifiedHotItem[]>;  // 分类聚合结果
      trend_analysis: TrendAnalysis;                  // 热度趋势分析
      meta: ReportMeta;                               // 元信息
    }

## 微博热搜条目

    interface WeiboHotItem {
      rank: number;        // 排名 (1-20)
      title: string;       // 话题标题
      keyword: string;     // 搜索关键词
      hot_value: number;   // 热度数值
      raw_hot: number;     // 原始热度
      category: string;    // 分类标签
      label: string;       // 标签描述 (热/新/沸)
      fetched_at: string;  // 抓取时间
    }

## 今日头条热点条目

    interface ToutiaoHotItem {
      rank: number;         // 排名 (1-20)
      title: string;        // 热点标题
      hot_value: number;    // 热度值
      cluster_id: string;   // 聚类 ID
      label: string;        // 标签
      url: string;          // 详情链接
      category: string;     // 分类
      fetched_at: string;   // 抓取时间
    }

## 百度指数条目

    interface BaiduHotItem {
      rank: number;                // 排名 (1-20)
      keyword: string;             // 关键词
      hot_score: number;           // 热度分数
      change: string;              // 变化幅度描述
      change_percent: number|null; // 涨幅百分比
      description: string;         // 事件简介
      category: string;            // 分类
      fetched_at: string;          // 抓取时间
    }

## 统一条目（分类聚合后）

    interface UnifiedHotItem {
      source: "weibo"|"toutiao"|"baidu";  // 来源平台
      title: string;                       // 标题/关键词
      normalized_hot: float;               // 归一化热度 (0-100)
      raw_hot: number;                     // 原始热度值
      category: string;                    // 分类
      rank: number;                        // 排名
      url?: string;                        // 详情链接
      fetched_at: string;                  // 抓取时间
    }

## 趋势分析

    interface TrendAnalysis {
      rising: TrendItem[];     // 上升趋势话题
      stable: TrendItem[];     // 稳定话题
      declining: TrendItem[];  // 下降趋势话题
      summary: string;         // 分析摘要
    }

    interface TrendItem {
      title: string;           // 话题标题
      source: string;          // 来源平台
      current_hot: number;     // 当前热度
      trend: string;           // 变化趋势描述
      category: string;        // 分类
    }

## 报告元信息

    interface ReportMeta {
      version: string;           // Skill 版本
      source_count: number;      // 数据源数量
      total_items: number;       // 总话题数
      fetch_duration_ms: number; // 抓取耗时 (ms)
      errors: ErrorInfo[];       // 错误信息列表
    }

    interface ErrorInfo {
      source: string;      // 出错平台
      error_type: string;  // 错误类型
      message: string;     // 错误信息
    }

## 分类枚举

    type TopicCategory =
      | "科技" | "娱乐" | "财经" | "社会" | "体育"
      | "教育" | "健康" | "游戏" | "汽车" | "其他"

## 分类映射规则

| 平台原始分类 | 映射目标 |
|-------------|---------|
| 科技, 互联网, 数码, AI | 科技 |
| 娱乐, 影视, 综艺, 明星 | 娱乐 |
| 财经, 经济, 金融, 股市 | 财经 |
| 社会, 民生, 时事 | 社会 |
| 体育, 足球, 篮球 | 体育 |
| 教育, 考试, 高考 | 教育 |
| 健康, 医疗, 养生 | 健康 |
| 游戏, 电竞 | 游戏 |
| 汽车, 新能源 | 汽车 |
| 其他 | 其他 |

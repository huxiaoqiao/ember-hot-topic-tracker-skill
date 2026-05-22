# API 对接文档

## 1. 微博热搜

| 项目 | 值 |
|------|-----|
| URL | https://weibo.com/ajax/side/hotSearch |
| 方法 | GET |
| 认证 | 无需 API Key |
| 频率限制 | 建议每分钟不超过 10 次请求 |

### 响应结构

    {
      "ok": 1,
      "data": {
        "realtime": [
          {
            "note": "话题标题",
            "category": "社会",
            "num": 1234567,
            "word": "关键词",
            "raw_hot": 1234567,
            "rank": 1,
            "icon_desc": "热"
          }
        ]
      }
    }

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| note | string | 话题标题 |
| word | string | 搜索关键词 |
| num | int | 热度数值 |
| raw_hot | int | 原始热度 |
| rank | int | 排名 |
| category | string | 分类标签 |
| icon_desc | string | 标签描述（热/新/沸） |

### 错误处理

- HTTP 429：频率限制，执行指数退避重试
- HTTP 403：UA 被拦截，切换 User-Agent
- 空响应：返回兜底空数据结构

---

## 2. 今日头条热点

| 项目 | 值 |
|------|-----|
| URL | https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc |
| 方法 | GET |
| 认证 | 无需 API Key |
| 频率限制 | 建议每分钟不超过 5 次请求 |

### 响应结构

    {
      "status": "success",
      "data": [
        {
          "Title": "热点标题",
          "HotValue": "1234567",
          "ClusterId": "abc123",
          "Label": "热",
          "Url": "https://..."
        }
      ]
    }

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| Title | string | 热点标题 |
| HotValue | string | 热度值（字符串格式） |
| ClusterId | string | 聚类 ID |
| Label | string | 标签（热/新/荐） |
| Url | string | 详情链接 |

---

## 3. 百度指数上升词

| 项目 | 值 |
|------|-----|
| URL | https://top.baidu.com/board?tab=realtime |
| 方法 | GET（页面抓取） |
| 认证 | 需要 Cookie（登录百度账号后获取） |
| 频率限制 | 建议每分钟不超过 3 次请求 |

### Cookie 配置

1. 浏览器登录 baidu.com
2. 打开开发者工具 -> Application -> Cookies
3. 复制 BDUSS 和 STOKEN 值
4. 写入 .env 文件：

    BAIDU_BDUSS=your_bduss_value
    BAIDU_STOKEN=your_stoken_value

### 数据解析

百度指数页面返回 HTML，通过 BeautifulSoup 解析。页面中内嵌了 JSON 数据。

---

## 通用错误处理策略

| 场景 | 处理方式 |
|------|----------|
| 网络超时 | 指数退避重试（1s -> 2s -> 4s），最多 3 次 |
| HTTP 429 | 指数退避重试，最多 3 次 |
| HTTP 5xx | 重试 1 次后跳过该平台 |
| 空数据/解析失败 | 返回兜底空结构，不抛异常 |
| 编码异常 | chardet 自动检测 + UTF-8 回退 |

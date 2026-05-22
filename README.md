# Ember Hot Topic Tracker Skill

每日自动抓取微博热搜、今日头条热点、百度指数上升词的 Top20 热点话题，分类聚合后输出结构化 JSON，含热度趋势分析。

## 功能特性

- 多平台抓取：微博热搜、今日头条热点、百度指数上升词
- Top20 排行：每个平台取前 20 条热点数据
- 分类聚合：自动将热点话题分为科技/娱乐/财经/社会/体育/教育/健康/游戏/汽车/其他
- 热度趋势分析：识别上升/稳定/下降趋势话题
- 频率限制重试：指数退避机制（1s -> 2s -> 4s），最多 3 次
- 空数据兜底：任何平台抓取失败都返回空结构，不会抛异常
- 编码兼容：自动检测响应编码，GBK -> UTF-8 自动转换

## 项目结构

    ember-hot-topic-tracker-skill/
    +-- SKILL.md                    # Skill 入口文件（YAML frontmatter + 使用说明）
    +-- README.md                   # 本文件
    +-- .env.example                # 环境变量模板
    +-- .gitignore                  # Git 忽略规则
    +-- references/
    |   +-- api-config.md           # API 对接文档
    |   +-- data-schema.md          # 数据结构定义
    +-- scripts/
    |   +-- hot_topic_tracker.py    # 主抓取与分析脚本
    |   +-- requirements.txt        # Python 依赖
    +-- output/                     # 输出目录（运行后自动创建）

## 安装说明

### 1. 克隆仓库

    git clone https://github.com/your-username/ember-hot-topic-tracker-skill.git
    cd ember-hot-topic-tracker-skill

### 2. 安装 Python 依赖

    pip install -r scripts/requirements.txt

### 3. 配置环境变量（可选 - 仅百度指数需要）

    cp .env.example .env
    # 编辑 .env，填入百度 Cookie

## 部署到 Hermes Agent Skills 目录

### 方式一：符号链接部署

将项目链接到 Hermes Skills 目录：

Windows (以管理员身份运行 PowerShell):

    New-Item -ItemType SymbolicLink -Path ":USERPROFILE\.hermes\skills\ember-hot-topic-tracker-skill" -Target "C:\path	o\ember-hot-topic-tracker-skill"

Linux/macOS:

    ln -s /path/to/ember-hot-topic-tracker-skill ~/.hermes/skills/ember-hot-topic-tracker-skill

### 方式二：skill_manage 命令注册

使用 Hermes Agent 的 skill_manage 工具注册 Skill：

    skill_manage(action='create', name='ember-hot-topic-tracker-skill')

或将 SKILL.md 内容直接通过 skill_manage(action='create') 导入，指定 category='automation'。

注册后可通过以下命令验证：

    skill_view(name='ember-hot-topic-tracker-skill')

## API Key 配置方式

| 平台 | 是否需要 Key | 配置方式 |
|------|-------------|----------|
| 微博热搜 | 不需要 | 直接调用公开接口 |
| 今日头条 | 不需要 | 直接调用公开接口 |
| 百度指数 | 需要 Cookie | 配置 .env 文件 |

### 百度 Cookie 获取步骤

1. 浏览器打开 https://www.baidu.com 并登录
2. 按 F12 打开开发者工具
3. 切换到 Application -> Cookies -> https://www.baidu.com
4. 找到并复制 BDUSS 和 STOKEN 的值
5. 填入项目根目录的 .env 文件

Cookie 有效期有限（通常数周），过期后需重新获取。未配置 Cookie 时百度指数数据可能为空，但不影响其他平台。

## 使用方法

### 抓取所有平台

    python scripts/hot_topic_tracker.py --all --pretty

### 抓取指定平台

    python scripts/hot_topic_tracker.py --weibo
    python scripts/hot_topic_tracker.py --toutiao
    python scripts/hot_topic_tracker.py --baidu

### 指定输出路径

    python scripts/hot_topic_tracker.py --all -o /path/to/output.json

## 验证步骤

### 1. 验证 Skill 注册

在 Hermes Agent 会话中执行：

    skill_view(name='ember-hot-topic-tracker-skill')

应返回 SKILL.md 的完整内容，包含 YAML frontmatter 和使用说明。

### 2. 验证抓取功能

    python scripts/hot_topic_tracker.py --all --pretty

成功运行后应输出报告摘要，包括时间戳、平台数量、话题总数、耗时等信息。

### 3. 验证输出文件

检查 output/ 目录下生成的 JSON 文件结构是否符合 references/data-schema.md 定义。

## License

MIT

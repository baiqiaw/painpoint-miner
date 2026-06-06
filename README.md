# PainPoint Miner 🔍

多平台社交用户痛点抓取与分析工具。从小红书、微博、抖音、知乎、Twitter/X 等平台自动提取用户抱怨、不满和未满足需求，生成分类报告和结构化数据。

## 功能特性

- **全平台抓取**：小红书、微博、抖音、知乎（TikHub API）+ Twitter/X（官方 API v2）
- **LLM 智能分析**：Claude 自动提取痛点 + 情感分析 + 严重度评估
- **零配置 LLM**：默认使用本地 Claude CLI，无需额外 API Key
- **主题聚类**：fastembed 多语言嵌入 + HDBSCAN 自动发现主题簇
- **跨平台去重**：相似痛点自动合并，累加频率
- **双模式分析**：`merged`（省成本，一次调用） / `split`（高质量，两次调用）
- **多格式导出**：Markdown 可读报告 + JSON 结构化数据 + Excel 表格
- **合规内建**：加盐匿名化、ToS 确认持久化、法律免责声明
- **成本控制**：LLM 预算上限，超支自动停止并保存断点
- **断点续传**：SQLite WAL 缓存 + 原子 checkpoint，中断后可恢复

## 系统要求

- Python ≥ 3.11
- **Claude CLI**（如 `claude-glm`）已安装并认证 — [安装指南](https://docs.anthropic.com/en/docs/claude-code)
- Windows 10/11 / macOS / Linux

## 快速开始

```bash
# 1. 克隆并安装
git clone https://github.com/baiqiaw/painpoint-miner.git
cd painpoint-miner
pip install -e ".[dev]"

# 2. 配置 API 密钥（仅需抓取平台的 Key）
cp .env.example .env
# 编辑 .env，填入 TikHub 和/或 Twitter API Key

# 3. 运行（LLM 默认使用本地 Claude CLI，无需额外配置）
painpoint-miner run --accept-tos-risk -k "产品难用" -p xiaohongshu
```

> 首次运行时 fastembed 会自动下载嵌入模型（约 560MB），需要网络连接。

## 配置

### 1. 环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# TikHub API（小红书、微博、抖音、知乎）
PPM_TIKHUB_API_KEY=your_tikhub_key

# Twitter API v2（可选）
PPM_TWITTER_BEARER_TOKEN=your_twitter_token

# Anthropic Claude API（仅 llm_mode=api 时需要，默认不需要）
# PPM_ANTHROPIC_API_KEY=your_anthropic_key
```

| API | 用途 | 获取方式 | 必须？ |
|-----|------|----------|--------|
| TikHub | 小红书/微博/抖音/知乎 | [tikhub.io](https://tikhub.io) | 至少一个 |
| Twitter API v2 | Twitter/X | [developer.x.com](https://developer.x.com) | 可选 |
| Anthropic | Claude LLM | [console.anthropic.com](https://console.anthropic.com) | ❌ 默认用本地 CLI |

> 不需要的平台可以不填对应密钥，工具会跳过该平台。

### 2. LLM 模式

默认使用本地 Claude CLI（`claude-glm`），无需 Anthropic API Key：

| 模式 | 命令行参数 | 需要 API Key？ | 说明 |
|------|-----------|---------------|------|
| `cli` | `--llm-mode cli` | ❌ | 默认，调用本地 Claude CLI |
| `api` | `--llm-mode api` | ✅ 需设置 `PPM_ANTHROPIC_API_KEY` | 直连 Anthropic API |

也可在 `config.yaml` 中设置：

```yaml
analysis:
  llm_mode: "cli"           # 或 "api"
  cli_command: "claude-glm"  # 本地 CLI 命令名
  llm_model: "claude-haiku-4-5-20251001"
```

### 3. 配置文件（可选）

```bash
cp config.example.yaml config.yaml
```

可自定义抓取数量、分析参数、导出格式等。不创建则使用默认值。

## 使用方法

### 基本用法

```bash
# 最简运行（默认关键词 + 默认平台）
painpoint-miner run --accept-tos-risk

# 指定关键词和平台
painpoint-miner run --accept-tos-risk -k "产品难用" -k "客服态度差" -p xiaohongshu -p weibo

# 指定输出目录
painpoint-miner run --accept-tos-risk -o ./my_output

# 使用 split 模式（更精确的情感分析，成本更高）
painpoint-miner run --accept-tos-risk --mode split

# 使用 Anthropic API 代替本地 CLI
painpoint-miner run --accept-tos-risk --llm-mode api
```

### 验证环境（不实际运行）

```bash
painpoint-miner run --accept-tos-risk --dry-run
```

会检查 Claude CLI 是否可用、配置是否有效。

### 所有选项

| 选项 | 缩写 | 说明 | 默认值 |
|------|------|------|--------|
| `--config` | `-c` | 配置文件路径 | 自动查找 |
| `--keywords` | `-k` | 搜索关键词（可多次指定） | `产品难用, 太贵了, 客服不回复` |
| `--platforms` | `-p` | 目标平台（可多次指定） | 配置文件中的平台 |
| `--mode` | `-m` | 分析模式：`merged` 或 `split` | `merged` |
| `--llm-mode` | | LLM 调用方式：`cli` 或 `api` | `cli` |
| `--output` | `-o` | 输出目录 | `./output` |
| `--accept-tos-risk` | | 确认已了解服务条款风险（必须） | — |
| `--dry-run` | | 仅验证配置，不执行抓取 | — |

### 支持的平台值

`xiaohongshu` `weibo` `douyin` `zhihu` `twitter`

## 输出示例

运行后在输出目录生成三个文件：

### 📄 painpoint_report.md（Markdown 报告）

```markdown
# 用户痛点分析报告

## 基本信息
| 项目 | 值 |
|------|-----|
| 查询关键词 | 产品难用、太贵了 |
| 发现痛点数 | 12 |
| 主题类别数 | 3 |

## 痛点详情
### 1. 按钮位置不明显，用户难以找到功能入口
- **类型**: ux_problem
- **严重度**: ⭐⭐⭐⭐ (4/5)
- **情感**: negative (-0.70)
- **频率**: 15 次
- **平台**: xiaohongshu, weibo
> "这个产品太难用了，按钮找不到在哪里"
```

### 📊 painpoint_report.json（结构化数据）

JSON 格式，包含所有痛点、聚类、平台分布的完整数据，方便程序化处理。

### 📋 painpoint_report.xlsx（Excel 表格）

三个工作表：
- **痛点概览**：所有痛点的详细信息
- **主题聚类**：聚类标签、关键词、大小
- **平台统计**：各平台抓取帖子数

## 成本估算

| 方案 | 模型 | 5000 帖子估算成本 |
|------|------|-------------------|
| 日常 | Haiku merged | ~$1.7 |
| 深度 | Sonnet merged | ~$18 |
| 最高质量 | Sonnet split | ~$33 |

可通过 `max_llm_budget_usd` 设置预算上限，超支自动停止。

## 项目结构

```
painpoint_miner/
  cli.py                    # CLI 入口（Click + Rich）
  config/settings.py        # 配置加载（YAML + .env）
  models/                   # 数据模型（Pydantic v2）
  compliance/               # 合规模块（匿名化、ToS、免责）
  scrapers/                 # 抓取器（TikHub + Twitter API）
  llm/                      # LLM 集成（Claude CLI + API）
  analysis/                 # 分析流水线（提取、聚类、去重）
  exporters/                # 导出器（MD/JSON/Excel）
  storage/                  # 存储（SQLite 缓存 + 断点）
  utils/                    # 工具（限速、成本追踪、重试）
```

## 测试

```bash
# 运行全部测试（243 个）
pytest

# 带覆盖率报告
pytest --cov=painpoint_miner --cov-report=term-missing

# 仅单元测试
pytest tests/unit/

# 仅集成测试
pytest tests/integration/
```

## 法律免责声明

⚠️ **使用前必读 [DISCLAIMER.md](DISCLAIMER.md)**

本工具仅供合法市场调研和产品改进用途。使用者需：

1. **自行验证** API 数据源的合法性和服务条款
2. **确认 TikHub** 作为第三方数据中介的风险
3. **遵守目标平台** 的服务条款和当地法律法规
4. **不用于** 竞争对手恶意攻击、用户画像追踪、虚假舆论制造等用途

运行时需加 `--accept-tos-risk` 标志确认已了解上述风险。

## License

MIT

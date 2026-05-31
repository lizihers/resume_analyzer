# AI 简历分析器 + 岗位匹配系统

全栈 AI 求职工具：上传简历 → AI 深度分析 → 岗位精准匹配 → 300+ 公司推荐。

**在线体验**：https://ceoqtdlpwxib.sealoshzh.site

---

## 功能

### 简历分析
- 上传 PDF/DOCX 简历，自动解析文本
- 自动脱敏姓名、电话、邮箱（隐私保护）
- AI 深度分析：技能提取、经历梳理、教育背景评估
- 学历竞争力分析：学校档次 + 专业匹配度 + 综合竞争力打分
- 四维评分：完整度 / 影响力 / 关键词 / 综合（0-100）
- 优势弱点 + 具体改进建议

### 岗位匹配
- 粘贴 JD 或输入招聘链接自动抓取
- AI 对比简历与岗位要求，给出匹配度分数
- 匹配技能 / 缺失技能 / 差距分析
- 简历优化方向：应加关键词 + 经历改写建议 + 优先学习技能

### 职位推荐
- AI 从 **25 个精确岗位** 中选出最匹配的 5-8 个
- 每个岗位给出匹配度分数 + 已匹配技能 + 需补充技能
- 从 **300+ 家公司** 中为每个岗位推荐 2-3 家匹配公司
- 覆盖：互联网、AI 大模型、自动驾驶、芯片半导体、IoT 嵌入式、机器人、云计算、金融科技、游戏、外资等 20+ 行业
- 每家公司带招聘官网直达链接

### 其他
- 用户注册/登录，数据完全隔离
- 历史记录保存与查看
- 密码 PBKDF2 加盐哈希存储

---

## 技术架构

```
前端 (原生 HTML/CSS/JS)
    │
    ▼
后端 FastAPI (Python)
    │
    ├── 简历解析: pypdf + python-docx
    ├── 隐私脱敏: 正则匹配姓名/电话/邮箱
    ├── URL 抓取: requests + trafilatura + BeautifulSoup
    ├── 用户认证: PBKDF2 + JWT Token
    └── 数据库: SQLite (WAL 模式)
    │
    ▼
AI 分析引擎
    └── OpenAI 兼容 API (多 Provider 支持)
```

---

## AI 分析技术

### 模型

| Provider | 模型 | 费用 | 说明 |
|----------|------|------|------|
| **硅基流动 (SiliconFlow)** | `deepseek-ai/DeepSeek-V3` | 免费 | 默认，国内直连 |
| Ollama | `qwen2.5:7b` | 免费 | 本地运行，无需网络 |
| DeepSeek | `deepseek-chat` | ¥1/百万 token | 备用付费方案 |

系统会**自动检测**可用的 Provider，优先级：Ollama 本地 > 硅基流动 > DeepSeek。

### 分析原理

1. **Prompt Engineering**：为简历分析、岗位匹配、职位推荐分别设计了结构化 System Prompt
2. **结构化输出**：要求 AI 返回严格 JSON，便于前端渲染
3. **脱敏保护**：简历上传后先在本地用正则脱敏个人信息，AI 从未见过真实的姓名/电话/邮箱
4. **学历分析**：AI 根据学校名称推断档次（985/211/双一流/省重点等），标注"基于公开信息推断"

### 岗位匹配逻辑

```
简历文本 ──→ 提取技能/经验/学历
                │
                ▼
         与 25 个岗位的技能要求逐一对比
                │
                ▼
         返回每个岗位的匹配度 + 已有技能 + 缺失技能
                │
                ▼
         按岗位匹配度排序 → 匹配对应公司
```

---

## 本地运行

### 前提

- Python 3.12+
- （可选）Ollama（免费本地 AI）

### 安装

```bash
git clone https://github.com/lizihers/resume_analyzer.git
cd resume_analyzer
pip install -r requirements.txt
```

### 配置

复制并编辑 `.env`：

```bash
# 默认自动检测，也可手动指定
AI_PROVIDER=auto          # auto / ollama / siliconflow / deepseek

# 硅基流动（免费，推荐）
SF_API_KEY=你的硅基流动key
SF_MODEL=deepseek-ai/DeepSeek-V3

# DeepSeek（付费备用）
OPENAI_API_KEY=你的DeepSeek key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

# Ollama（本地免费）
OLLAMA_MODEL=qwen2.5:7b
```

获取免费 API Key：
- **硅基流动**：https://cloud.siliconflow.cn → 注册 → API 密钥（送免费额度）
- **Ollama**：`winget install Ollama.Ollama && ollama pull qwen2.5:7b`（完全免费，本地运行）

### 启动

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 http://127.0.0.1:8000

---

## 部署到公网

### 方案 A：Sealos（免费，推荐）

1. 注册 [Sealos](https://sealos.run)
2. 新建应用 → 填镜像 `lizihers/resume-analyzer:latest`
3. 端口 `8000`，开启公网访问
4. 设置环境变量：
```
AI_PROVIDER=siliconflow
SF_API_KEY=你的硅基流动key
SF_MODEL=deepseek-ai/DeepSeek-V3
```
5. 部署完成，获得永久域名

### 方案 B：Docker 部署

```bash
docker build -t resume-analyzer .
docker run -d -p 8000:8000 \
  -e AI_PROVIDER=siliconflow \
  -e SF_API_KEY=你的key \
  -e SF_MODEL=deepseek-ai/DeepSeek-V3 \
  resume-analyzer
```

### 方案 C：Cloudflare Tunnel（临时分享）

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
cloudflared tunnel --url http://localhost:8000 --protocol http2 --no-autoupdate
```

生成 `https://xxx.trycloudflare.com` 临时地址（需电脑保持开机）。

---

## 项目结构

```
resume_analyzer/
├── backend/
│   ├── main.py           # FastAPI 入口，路由定义
│   ├── ai_service.py     # AI 分析 + 300+公司 + 25岗位数据库
│   ├── config.py         # 多 Provider 配置 + 自动检测
│   ├── parser.py         # PDF/DOCX 简历解析
│   ├── privacy.py        # 姓名/电话/邮箱脱敏
│   ├── auth.py           # PBKDF2 密码哈希 + JWT Token
│   ├── database.py       # SQLite 操作
│   └── url_fetcher.py    # JD 链接抓取
├── static/
│   ├── index.html        # 前端页面
│   ├── app.js            # 前端逻辑
│   └── style.css         # 样式
├── data/                 # SQLite 数据库（自动生成）
├── Dockerfile
├── requirements.txt
├── .env                  # API 配置（不提交到 Git）
└── .github/workflows/    # 自动构建 Docker 镜像
```

---

## 公司覆盖

300+ 家公司，20+ 行业：

互联网/科技 · AI 大模型 · 自动驾驶 · 芯片/半导体 · IoT/嵌入式 · 机器人 · 云计算/基础设施 · 金融/银行 · 外资企业 · 制造/工业 · 通信/运营商 · 游戏 · 电商/零售 · 医药/医疗 · 教育科技 · 企业服务/SaaS · 安全 · 航天/军工 · 量子计算 · 物流 · 新能源 · 更多...

所有公司均附带官方招聘页面直达链接。

---

## License

MIT

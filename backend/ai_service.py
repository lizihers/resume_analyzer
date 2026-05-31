import json
from openai import OpenAI
from .config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

ANALYSIS_PROMPT = """你是一个专业的简历分析师（Resume Analyst）。请深度分析下面的简历内容，返回严格JSON格式。

⚠️ 重要：为了保护用户隐私，简历中的姓名、电话、邮箱等个人信息已经用 * 号做了脱敏处理（例如"张三"→"张*"，"138****5678"，"z***@example.com"）。这是故意隐藏的，NOT AN ISSUE。请不要因此扣分，也不要在weaknesses中提到"缺少个人信息"。只评估专业技能、经历、教育等核心内容。

分析维度：
1. skills: 提取技术和软技能
2. experience: 梳理工作/项目经历，提炼亮点
3. education: 教育背景（学校、专业、学历层次）
4. education_analysis: 学历竞争力分析
   - level: 学历层次（专科/本科/硕士/博士）
   - school_tier: 学校档次评估（如985/211/双一流/省重点/普通本科/专科，基于学校名称推断，标注"基于公开信息推断"）
   - major_match: 专业与当前热门方向（AI/大数据/互联网/金融等）的匹配度 0-100
   - competitiveness: 学历综合竞争力 0-100（综合学校+学历+专业）
   - advantage: 学历方面的优势（1-2句）
   - limitation: 学历方面的限制或需要弥补的地方（1-2句），如果是名校则写"无明显学历限制"
5. strengths: 简历的核心优势（3-5条），只关注技术/项目/能力亮点
6. weaknesses: 简历的薄弱点（3-5条），只关注技术/经验/表达层面，不要提"缺少个人信息"
7. score: 四个维度0-100打分
   - completeness: 信息完整度（只看技能/经历/教育/项目是否完整，不包含被脱敏的个人信息）
   - impact: 影响力/成果量化程度
   - keyword: 关键词优化度
   - overall: 综合分
8. suggestions: 具体改进建议，每条包含 category(content/format/keyword) 和 advice

返回格式：
{
  "skills": {"technical": [...], "soft": [...]},
  "experience": [{"title": "", "company": "", "duration": "", "highlights": [...]}],
  "education": [{"degree": "", "major": "", "school": "", "year": ""}],
  "education_analysis": {
    "level": "",
    "school_tier": "",
    "major_match": 0,
    "competitiveness": 0,
    "advantage": "",
    "limitation": ""
  },
  "strengths": [...],
  "weaknesses": [...],
  "score": {"completeness": 0, "impact": 0, "keyword": 0, "overall": 0},
  "suggestions": [{"category": "content", "advice": ""}]
}

只返回JSON，不要任何其他文字。"""

MATCH_PROMPT = """你是一个岗位匹配专家。比较下面的简历和职位描述(JD)，评估匹配度，并给出简历优化方向。

分析维度：
1. match_score: 总匹配度 0-100
2. matching_skills: 简历中与JD匹配的技能
3. missing_skills: JD要求但简历中缺失的技能，按重要性排序
4. gaps: 能力和经验上的差距（3-5条）
5. recommendations: 针对差距的改进建议（3-5条）
6. optimization: 简历优化方向
   - keywords_to_add: 简历里应该加入的JD关键词（列3-5个具体词）
   - experience_rewrite: 针对JD，现有经历可以怎么改写出亮点（具体建议，如"把'负责XX'改成'通过XX技术实现YY提升ZZ%'"）
   - skill_priority: 按优先级排列最应该补充学习的技能（2-3个，附简短理由）

返回格式：
{
  "match_score": 0,
  "matching_skills": [...],
  "missing_skills": [...],
  "gaps": [...],
  "recommendations": [...],
  "optimization": {
    "keywords_to_add": [...],
    "experience_rewrite": [...],
    "skill_priority": [{"skill": "", "reason": ""}]
  }
}

只返回JSON，不要任何其他文字。"""


def analyze_resume(resume_text: str) -> dict:
    if len(resume_text) > 12000:
        resume_text = resume_text[:12000]

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": ANALYSIS_PROMPT},
                {"role": "user", "content": resume_text},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "AI返回格式异常，请重试", "raw": content[:500]}
    except Exception as e:
        msg = str(e)
        if "401" in msg or "Authentication" in msg or "auth" in msg.lower():
            return {"error": "API 密钥无效，请检查 .env 文件中的 OPENAI_API_KEY"}
        return {"error": f"AI分析失败: {msg}"}


def match_job(resume_text: str, job_text: str) -> dict:
    if len(resume_text) > 8000:
        resume_text = resume_text[:8000]
    if len(job_text) > 8000:
        job_text = job_text[:8000]

    user_msg = f"=== 简历 ===\n{resume_text}\n\n=== 职位描述 ===\n{job_text}"

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": MATCH_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "AI返回格式异常，请重试", "raw": content[:500]}
    except Exception as e:
        msg = str(e)
        if "401" in msg or "Authentication" in msg or "auth" in msg.lower():
            return {"error": "API 密钥无效，请检查 .env 文件中的 OPENAI_API_KEY"}
        return {"error": f"AI匹配失败: {msg}"}


# ── Company career URLs (100+ companies across all industries) ──

COMPANY_CAREERS = [
    # ===== 互联网/科技 =====
    {"name": "字节跳动", "url": "https://jobs.bytedance.com", "tags": ["互联网", "AI", "大厂"]},
    {"name": "阿里巴巴", "url": "https://talent.alibaba.com", "tags": ["互联网", "电商", "云计算"]},
    {"name": "腾讯", "url": "https://careers.tencent.com", "tags": ["互联网", "社交", "游戏", "AI"]},
    {"name": "百度", "url": "https://talent.baidu.com", "tags": ["互联网", "AI", "自动驾驶"]},
    {"name": "华为", "url": "https://career.huawei.com", "tags": ["通信", "芯片", "终端", "云计算"]},
    {"name": "小米", "url": "https://hr.xiaomi.com", "tags": ["智能硬件", "IoT", "汽车"]},
    {"name": "京东", "url": "https://zhaopin.jd.com", "tags": ["电商", "物流", "云计算"]},
    {"name": "美团", "url": "https://zhaopin.meituan.com", "tags": ["本地生活", "AI", "自动驾驶"]},
    {"name": "拼多多", "url": "https://careers.pinduoduo.com", "tags": ["电商", "AI"]},
    {"name": "网易", "url": "https://hr.163.com", "tags": ["互联网", "游戏", "音乐"]},
    {"name": "滴滴", "url": "https://talent.didiglobal.com", "tags": ["出行", "AI", "自动驾驶"]},
    {"name": "小红书", "url": "https://job.xiaohongshu.com", "tags": ["互联网", "社交", "电商"]},
    {"name": "哔哩哔哩", "url": "https://jobs.bilibili.com", "tags": ["互联网", "视频", "游戏"]},
    {"name": "快手", "url": "https://zhaopin.kuaishou.cn", "tags": ["互联网", "短视频", "AI"]},
    {"name": "携程", "url": "https://job.ctrip.com", "tags": ["互联网", "旅游"]},
    {"name": "蚂蚁集团", "url": "https://talent.antgroup.com", "tags": ["金融科技", "AI", "区块链"]},
    {"name": "OPPO", "url": "https://career.oppo.com", "tags": ["消费电子", "AI", "芯片"]},
    {"name": "vivo", "url": "https://hr.vivo.com", "tags": ["消费电子", "AI"]},
    {"name": "联想", "url": "https://talent.lenovo.com.cn", "tags": ["消费电子", "PC", "服务器"]},

    # ===== AI / 大模型 =====
    {"name": "商汤科技", "url": "https://www.sensetime.com/cn/careers", "tags": ["AI", "计算机视觉"]},
    {"name": "旷视科技", "url": "https://www.megvii.com/careers", "tags": ["AI", "计算机视觉"]},
    {"name": "科大讯飞", "url": "https://campus.iflytek.com", "tags": ["AI", "语音", "NLP"]},
    {"name": "智谱AI", "url": "https://www.zhipuai.cn/careers", "tags": ["AI", "大模型"]},
    {"name": "月之暗面 Moonshot", "url": "https://www.moonshot.cn/careers", "tags": ["AI", "大模型"]},
    {"name": "MiniMax", "url": "https://www.minimaxi.com/careers", "tags": ["AI", "大模型"]},
    {"name": "零一万物", "url": "https://www.01-ai.com/careers", "tags": ["AI", "大模型"]},
    {"name": "DeepSeek 深度求索", "url": "https://www.deepseek.com", "tags": ["AI", "大模型"]},
    {"name": "百川智能", "url": "https://www.baichuan-ai.com", "tags": ["AI", "大模型"]},
    {"name": "阶跃星辰", "url": "https://www.stepfun.com", "tags": ["AI", "大模型"]},

    # ===== 半导体 / 芯片 =====
    {"name": "英伟达 NVIDIA", "url": "https://www.nvidia.com/zh-cn/about-nvidia/careers", "tags": ["芯片", "AI", "GPU"]},
    {"name": "Intel 中国", "url": "https://www.intel.cn/content/www/cn/zh/jobs/life-at-intel.html", "tags": ["芯片", "半导体"]},
    {"name": "AMD", "url": "https://careers.amd.com", "tags": ["芯片", "GPU"]},
    {"name": "高通", "url": "https://www.qualcomm.com/company/careers", "tags": ["芯片", "通信"]},
    {"name": "寒武纪", "url": "https://www.cambricon.com", "tags": ["AI芯片", "半导体"]},
    {"name": "地平线", "url": "https://www.horizon.auto/careers", "tags": ["AI芯片", "自动驾驶"]},
    {"name": "壁仞科技", "url": "https://www.birentech.com/careers", "tags": ["AI芯片", "GPU"]},
    {"name": "摩尔线程", "url": "https://www.mthreads.com/careers", "tags": ["GPU", "芯片"]},
    {"name": "海光信息", "url": "https://www.hygon.cn", "tags": ["芯片", "CPU"]},
    {"name": "长鑫存储", "url": "https://www.cxmt.com", "tags": ["芯片", "存储"]},
    {"name": "中芯国际", "url": "https://www.smics.com/careers", "tags": ["芯片", "制造"]},
    {"name": "紫光展锐", "url": "https://www.unisoc.com", "tags": ["芯片", "通信"]},

    # ===== 汽车 / 新能源 =====
    {"name": "比亚迪", "url": "https://job.byd.com", "tags": ["汽车", "新能源", "电子"]},
    {"name": "特斯拉中国", "url": "https://www.tesla.cn/careers", "tags": ["汽车", "AI", "自动驾驶"]},
    {"name": "蔚来", "url": "https://www.nio.cn/careers", "tags": ["汽车", "自动驾驶", "AI"]},
    {"name": "小鹏汽车", "url": "https://xiaopeng.com/careers.html", "tags": ["汽车", "自动驾驶"]},
    {"name": "理想汽车", "url": "https://www.lixiang.com/careers", "tags": ["汽车", "AI"]},
    {"name": "吉利汽车", "url": "https://job.geely.com", "tags": ["汽车", "制造"]},
    {"name": "宁德时代", "url": "https://www.catl.com/careers", "tags": ["新能源", "电池"]},
    {"name": "大疆", "url": "https://we.dji.com", "tags": ["无人机", "机器人", "AI"]},

    # ===== 金融 / 银行 =====
    {"name": "中国工商银行", "url": "https://job.icbc.com.cn", "tags": ["银行", "金融", "国企"]},
    {"name": "中国建设银行", "url": "https://job.ccb.com", "tags": ["银行", "金融", "国企"]},
    {"name": "中国银行", "url": "https://www.boc.cn/aboutboc/ab5", "tags": ["银行", "金融", "国企"]},
    {"name": "招商银行", "url": "https://career.cmbchina.com", "tags": ["银行", "金融科技"]},
    {"name": "中信证券", "url": "https://www.citics.com/careers", "tags": ["证券", "金融"]},
    {"name": "中金公司 CICC", "url": "https://career.cicc.com", "tags": ["投行", "金融"]},
    {"name": "中国平安", "url": "https://talent.pingan.com", "tags": ["保险", "金融科技"]},
    {"name": "中国人寿", "url": "https://www.chinalife.com.cn/chinalife/zhaopin", "tags": ["保险", "金融", "国企"]},
    {"name": "支付宝", "url": "https://talent.antgroup.com", "tags": ["支付", "金融科技"]},

    # ===== 外资企业 =====
    {"name": "微软中国", "url": "https://careers.microsoft.com", "tags": ["软件", "AI", "云计算"]},
    {"name": "Google 中国", "url": "https://careers.google.com", "tags": ["互联网", "AI"]},
    {"name": "Apple 中国", "url": "https://jobs.apple.com/cn", "tags": ["消费电子", "芯片"]},
    {"name": "Amazon 中国", "url": "https://www.amazon.jobs/zh", "tags": ["电商", "云计算", "AI"]},
    {"name": "IBM 中国", "url": "https://www.ibm.com/cn-zh/careers", "tags": ["软件", "咨询", "云计算"]},
    {"name": "SAP 中国", "url": "https://www.sap.cn/about/careers.html", "tags": ["企业软件", "ERP"]},
    {"name": "Oracle 中国", "url": "https://www.oracle.com/cn/careers", "tags": ["数据库", "云计算"]},
    {"name": "三星中国", "url": "https://www.samsung.com/cn/careers", "tags": ["消费电子", "半导体"]},

    # ===== 制造 / 工业 =====
    {"name": "三一重工", "url": "https://www.sany.com.cn/careers", "tags": ["制造", "工程机械"]},
    {"name": "中联重科", "url": "https://www.zoomlion.com/careers", "tags": ["制造", "工程机械"]},
    {"name": "格力电器", "url": "https://www.gree.com.cn/zp", "tags": ["家电", "制造"]},
    {"name": "美的集团", "url": "https://career.midea.com", "tags": ["家电", "制造", "机器人"]},
    {"name": "海尔集团", "url": "https://maker.haier.net", "tags": ["家电", "IoT"]},
    {"name": "京东方 BOE", "url": "https://www.boe.com/careers", "tags": ["显示", "半导体"]},

    # ===== 生物医药 =====
    {"name": "药明康德", "url": "https://www.wuxiapptec.com/careers", "tags": ["医药", "CRO"]},
    {"name": "百济神州", "url": "https://www.beigene.com.cn/careers", "tags": ["医药", "创新药"]},
    {"name": "迈瑞医疗", "url": "https://career.mindray.com", "tags": ["医疗器械"]},
    {"name": "联影医疗", "url": "https://www.united-imaging.com/cn/careers", "tags": ["医疗器械", "AI"]},

    # ===== 咨询 / 审计 =====
    {"name": "麦肯锡", "url": "https://www.mckinsey.com.cn/careers", "tags": ["咨询"]},
    {"name": "波士顿咨询 BCG", "url": "https://careers.bcg.com", "tags": ["咨询"]},
    {"name": "贝恩咨询", "url": "https://www.bain.cn/careers", "tags": ["咨询"]},
    {"name": "普华永道", "url": "https://www.pwccn.com/zh/careers.html", "tags": ["审计", "咨询"]},
    {"name": "德勤", "url": "https://www.deloitte.com/cn/zh/careers.html", "tags": ["审计", "咨询"]},
    {"name": "安永", "url": "https://www.ey.com/zh_cn/careers", "tags": ["审计", "咨询"]},
    {"name": "毕马威", "url": "https://home.kpmg/cn/zh/home/careers.html", "tags": ["审计", "咨询"]},

    # ===== 消费品 / 零售 =====
    {"name": "宝洁", "url": "https://www.pgcareers.com/global/en/cn", "tags": ["快消", "日化"]},
    {"name": "联合利华", "url": "https://careers.unilever.com.cn", "tags": ["快消", "食品"]},
    {"name": "可口可乐", "url": "https://www.cocacola.com.cn/careers", "tags": ["快消", "饮料"]},
    {"name": "雀巢", "url": "https://www.nestle.com.cn/jobs", "tags": ["快消", "食品"]},
    {"name": "麦当劳", "url": "https://www.mcdonalds.com.cn/careers", "tags": ["餐饮", "零售"]},
    {"name": "海底捞", "url": "https://www.haidilao.com/careers", "tags": ["餐饮"]},

    # ===== 物流 / 运输 =====
    {"name": "顺丰", "url": "https://hr.sf-express.com", "tags": ["物流", "科技"]},
    {"name": "菜鸟网络", "url": "https://www.cainiao.com/careers", "tags": ["物流", "科技"]},
    {"name": "中国邮政", "url": "https://www.chinapost.com.cn/html1/folder/careers.html", "tags": ["物流", "国企"]},

    # ===== 建筑 / 地产 =====
    {"name": "万科", "url": "https://www.vanke.com/careers", "tags": ["地产"]},
    {"name": "保利发展", "url": "https://www.poly.com.cn/careers", "tags": ["地产", "国企"]},

    # ===== 教育 / 媒体 =====
    {"name": "好未来", "url": "https://job.100tal.com", "tags": ["教育", "AI"]},
    {"name": "新东方", "url": "https://zhaopin.xdf.cn", "tags": ["教育"]},
    {"name": "中央电视台", "url": "https://www.cctv.com", "tags": ["媒体", "国企"]},

    # ===== 游戏 =====
    {"name": "米哈游", "url": "https://careers.mihoyo.com", "tags": ["游戏"]},
    {"name": "莉莉丝", "url": "https://www.lilith.com/careers", "tags": ["游戏"]},
    {"name": "鹰角网络", "url": "https://www.hypergryph.com/careers", "tags": ["游戏"]},
    {"name": "网易游戏", "url": "https://game.ac.163.com", "tags": ["游戏", "互联网"]},
    {"name": "完美世界", "url": "https://careers.wanmei.com", "tags": ["游戏"]},
    {"name": "三七互娱", "url": "https://zhaopin.37.com", "tags": ["游戏"]},
    {"name": "吉比特", "url": "https://careers.gbits.com", "tags": ["游戏"]},
    {"name": "叠纸网络", "url": "https://www.papegames.com/careers", "tags": ["游戏"]},
    {"name": "库洛游戏", "url": "https://www.kurogame.com/careers", "tags": ["游戏"]},

    # ===== 自动驾驶 / 机器人 =====
    {"name": "小马智行 Pony.ai", "url": "https://pony.ai/careers", "tags": ["自动驾驶", "AI"]},
    {"name": "文远知行 WeRide", "url": "https://www.weride.ai/careers", "tags": ["自动驾驶", "AI"]},
    {"name": "Momenta", "url": "https://www.momenta.cn/careers", "tags": ["自动驾驶", "AI"]},
    {"name": "图森未来 TuSimple", "url": "https://www.tusimple.com/careers", "tags": ["自动驾驶"]},
    {"name": "禾赛科技", "url": "https://www.hesaitech.com/careers", "tags": ["激光雷达", "自动驾驶"]},
    {"name": "速腾聚创", "url": "https://www.robosense.cn/careers", "tags": ["激光雷达", "自动驾驶"]},
    {"name": "宇树科技 Unitree", "url": "https://www.unitree.com/careers", "tags": ["机器人", "AI"]},
    {"name": "智元机器人 AGIBOT", "url": "https://www.agibot.com/careers", "tags": ["机器人", "AI"]},
    {"name": "银河通用 Galbot", "url": "https://www.galbot.com/careers", "tags": ["机器人", "AI"]},
    {"name": "傅利叶智能", "url": "https://www.fftai.com/careers", "tags": ["机器人", "医疗"]},
    {"name": "追觅科技", "url": "https://www.dreame.com/careers", "tags": ["机器人", "消费电子"]},
    {"name": "科沃斯", "url": "https://www.ecovacs.cn/careers", "tags": ["机器人", "消费电子"]},

    # ===== 云计算 / 基础设施 =====
    {"name": "阿里云", "url": "https://careers.aliyun.com", "tags": ["云计算", "AI"]},
    {"name": "腾讯云", "url": "https://cloud.tencent.com/careers", "tags": ["云计算", "AI"]},
    {"name": "华为云", "url": "https://career.huawei.com", "tags": ["云计算", "AI"]},
    {"name": "金山云", "url": "https://www.ksyun.com/careers", "tags": ["云计算"]},
    {"name": "UCloud 优刻得", "url": "https://www.ucloud.cn/careers", "tags": ["云计算"]},
    {"name": "青云 QingCloud", "url": "https://www.qingcloud.com/careers", "tags": ["云计算"]},
    {"name": "火山引擎", "url": "https://www.volcengine.com/careers", "tags": ["云计算", "AI"]},

    # ===== AI 芯片 / 半导体 (补充) =====
    {"name": "燧原科技", "url": "https://www.enflame-tech.com/careers", "tags": ["AI芯片", "半导体"]},
    {"name": "昆仑芯", "url": "https://www.kunlunxin.com/careers", "tags": ["AI芯片", "半导体"]},
    {"name": "天数智芯", "url": "https://www.iluvatar.com/careers", "tags": ["AI芯片", "GPU"]},
    {"name": "沐曦", "url": "https://www.metax-tech.com/careers", "tags": ["AI芯片", "GPU"]},
    {"name": "瀚博半导体", "url": "https://www.vastai.com/careers", "tags": ["AI芯片", "半导体"]},
    {"name": "后摩智能", "url": "https://www.houmou.com/careers", "tags": ["AI芯片", "存算一体"]},
    {"name": "此芯科技", "url": "https://www.thissilicon.com/careers", "tags": ["芯片", "CPU"]},
    {"name": "芯驰科技", "url": "https://www.semidrive.com/careers", "tags": ["芯片", "汽车"]},
    {"name": "兆易创新", "url": "https://www.gigadevice.com/careers", "tags": ["半导体", "存储"]},
    {"name": "韦尔股份", "url": "https://www.ovt.com.cn/careers", "tags": ["半导体", "图像传感器"]},

    # ===== AI / 大模型 (补充) =====
    {"name": "硅基流动 SiliconFlow", "url": "https://www.siliconflow.com/careers", "tags": ["AI", "大模型", "推理"]},
    {"name": "无问芯穹", "url": "https://www.infinigence.com/careers", "tags": ["AI", "大模型", "推理"]},
    {"name": "面壁智能", "url": "https://www.modelbest.cn/careers", "tags": ["AI", "大模型"]},
    {"name": "第四范式", "url": "https://www.4paradigm.com/careers", "tags": ["AI", "企业服务"]},
    {"name": "小冰", "url": "https://www.xiaoice.com/careers", "tags": ["AI", "对话"]},
    {"name": "云从科技", "url": "https://www.cloudwalk.com/careers", "tags": ["AI", "计算机视觉"]},
    {"name": "云天励飞", "url": "https://www.intellif.com/careers", "tags": ["AI", "计算机视觉"]},
    {"name": "思必驰", "url": "https://www.aispeech.com/careers", "tags": ["AI", "语音"]},

    # ===== 数据 / 数据库 =====
    {"name": "PingCAP", "url": "https://careers.pingcap.com", "tags": ["数据库", "开源", "基础设施"]},
    {"name": "涛思数据 TDengine", "url": "https://www.taosdata.com/careers", "tags": ["数据库", "开源", "IoT"]},
    {"name": "星环科技", "url": "https://www.transwarp.io/careers", "tags": ["大数据", "AI"]},
    {"name": "SelectDB 飞轮科技", "url": "https://www.selectdb.com/careers", "tags": ["数据库", "开源"]},

    # ===== 通信 / 运营商 =====
    {"name": "中国移动", "url": "https://job.10086.cn", "tags": ["通信", "国企", "云计算"]},
    {"name": "中国电信", "url": "https://zhaopin.chinatelecom.com.cn", "tags": ["通信", "国企", "云计算"]},
    {"name": "中国联通", "url": "https://zglt2026.zhaopin.com", "tags": ["通信", "国企"]},
    {"name": "中国铁塔", "url": "https://zhaopin.chinatowercom.cn", "tags": ["通信", "国企"]},

    # ===== 能源 / 电力 =====
    {"name": "国家电网", "url": "https://zhaopin.sgcc.com.cn", "tags": ["电力", "国企"]},
    {"name": "南方电网", "url": "https://zhaopin.csg.cn", "tags": ["电力", "国企"]},
    {"name": "中石油", "url": "https://zhaopin.cnpc.com.cn", "tags": ["能源", "国企"]},
    {"name": "中石化", "url": "https://job.sinopec.com", "tags": ["能源", "国企"]},

    # ===== 安全 =====
    {"name": "奇安信", "url": "https://www.qianxin.com/careers", "tags": ["安全", "AI"]},
    {"name": "深信服", "url": "https://hr.sangfor.com", "tags": ["安全", "云计算"]},
    {"name": "绿盟科技", "url": "https://www.nsfocus.com.cn/careers", "tags": ["安全"]},

    # ===== 更多互联网 =====
    {"name": "知乎", "url": "https://www.zhihu.com/careers", "tags": ["互联网", "内容"]},
    {"name": "搜狐", "url": "https://hr.sohu.com", "tags": ["互联网", "媒体"]},
    {"name": "微博", "url": "https://career.sina.com.cn", "tags": ["互联网", "社交"]},
    {"name": "虎牙", "url": "https://hr.huya.com", "tags": ["互联网", "直播"]},
    {"name": "斗鱼", "url": "https://www.douyu.com/careers", "tags": ["互联网", "直播"]},
    {"name": "唯品会", "url": "https://recruitment.corp.vipshop.com", "tags": ["互联网", "电商"]},
    {"name": "得物", "url": "https://recruit.dewu.com", "tags": ["互联网", "电商"]},
    {"name": "SHEIN", "url": "https://www.sheingroup.com/careers", "tags": ["互联网", "电商", "出海"]},

    # ===== 教育科技 =====
    {"name": "作业帮", "url": "https://careers.zuoyebang.com", "tags": ["教育", "AI"]},
    {"name": "猿辅导", "url": "https://hr.yuanfudao.com", "tags": ["教育", "AI"]},

    # ===== 医药 (补充) =====
    {"name": "恒瑞医药", "url": "https://www.hengrui.com/careers", "tags": ["医药"]},
    {"name": "复星医药", "url": "https://www.fosunpharma.com/careers", "tags": ["医药"]},
    {"name": "泰格医药", "url": "https://www.tigermedgrp.com/careers", "tags": ["医药", "CRO"]},

    # ===== 更多制造 / 工业 =====
    {"name": "中芯国际", "url": "https://www.smics.com/careers", "tags": ["芯片", "制造"]},
    {"name": "TCL", "url": "https://careers.tcl.com", "tags": ["消费电子", "制造"]},
    {"name": "海康威视", "url": "https://www.hikvision.com/cn/careers", "tags": ["安防", "AI", "制造"]},
    {"name": "大华股份", "url": "https://www.dahuatech.com/careers", "tags": ["安防", "AI"]},
    {"name": "中兴通讯", "url": "https://job.zte.com.cn", "tags": ["通信", "芯片"]},
    {"name": "中车集团", "url": "https://www.crrcgc.cc/careers", "tags": ["制造", "交通", "国企"]},

    # ===== 更多金融 =====
    {"name": "中国银联", "url": "https://career.unionpay.com", "tags": ["金融", "支付"]},
    {"name": "微众银行", "url": "https://hr.webank.com", "tags": ["银行", "金融科技"]},
    {"name": "网商银行", "url": "https://www.mybank.cn/careers", "tags": ["银行", "金融科技"]},
    {"name": "中信建投证券", "url": "https://careers.csc.com.cn", "tags": ["证券", "金融"]},
    {"name": "华泰证券", "url": "https://job.htsc.com.cn", "tags": ["证券", "金融"]},
]


JOB_RECOMMEND_PROMPT = """你是一个职业规划专家。根据求职者的简历（技能、学历、经验），推荐适合的岗位方向，并匹配真实的公司。

分析维度：
1. recommended_directions: 根据简历背景，推荐 3-4 个适合的岗位方向（如"AI推理引擎开发"、"自动驾驶感知算法"、"云计算基础设施"等），每个包含：
   - title: 岗位名称
   - fit_reason: 为什么适合（结合简历中的具体技能和经验）
   - salary_range: 预估薪资范围（以中国市场为准，如"15k-25k/月"或"年薪20w-35w"）
2. target_companies: 从提供的公司列表中，筛选 6-8 个最匹配的公司，按推荐度排序，包含：
   - name: 公司名
   - match_reason: 匹配原因（1句话）
   - priority: 推荐优先级 (high/medium)
3. career_advice: 职业发展建议（2-3条）

返回格式：
{
  "recommended_directions": [
    {"title": "", "fit_reason": "", "salary_range": ""}
  ],
  "target_companies": [
    {"name": "", "match_reason": "", "priority": ""}
  ],
  "career_advice": [...]
}

重要：target_companies只能从我提供的下面这个公司列表中选择，不要编造不存在的公司。

=== 可选公司列表 ===
{companies}

只返回JSON，不要任何其他文字。"""


def recommend_jobs(resume_text: str, education_analysis: dict | None = None) -> dict:
    """Based on resume and education analysis, recommend job directions and target companies."""
    if len(resume_text) > 8000:
        resume_text = resume_text[:8000]

    company_list = "\n".join(
        f"- {c['name']}: {c['url']} ({', '.join(c['tags'])})"
        for c in COMPANY_CAREERS
    )
    prompt = JOB_RECOMMEND_PROMPT.replace("{companies}", company_list)

    edu_text = ""
    if education_analysis:
        edu_text = (
            f"\n学历分析：{education_analysis.get('level','')}，"
            f"学校档次：{education_analysis.get('school_tier','')}，"
            f"学历竞争力：{education_analysis.get('competitiveness','')}/100"
        )
    user_msg = f"=== 简历 ===\n{resume_text}{edu_text}"

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        result = json.loads(content)

        # Attach real URLs from our curated list
        company_urls = {c["name"]: c["url"] for c in COMPANY_CAREERS}
        for tc in result.get("target_companies", []):
            name = tc.get("name", "")
            if name in company_urls:
                tc["career_url"] = company_urls[name]
            else:
                tc["career_url"] = ""
        return result
    except json.JSONDecodeError:
        return {"error": "AI返回格式异常，请重试", "raw": content[:500]}
    except Exception as e:
        msg = str(e)
        if "401" in msg or "Authentication" in msg or "auth" in msg.lower():
            return {"error": "API 密钥无效，请检查 .env 文件中的 OPENAI_API_KEY"}
        return {"error": f"AI推荐失败: {msg}"}

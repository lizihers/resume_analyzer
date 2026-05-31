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

    # ===== IoT / 嵌入式 / 边缘计算 (重点!) =====
    {"name": "华为终端", "url": "https://career.huawei.com", "tags": ["IoT", "嵌入式", "消费电子"]},
    {"name": "小米IoT", "url": "https://hr.xiaomi.com", "tags": ["IoT", "智能家居", "嵌入式"]},
    {"name": "阿里云IoT", "url": "https://talent.alibaba.com", "tags": ["IoT", "云计算", "边缘计算"]},
    {"name": "腾讯云IoT", "url": "https://careers.tencent.com", "tags": ["IoT", "云计算"]},
    {"name": "百度IoT", "url": "https://talent.baidu.com", "tags": ["IoT", "AI", "边缘计算"]},
    {"name": "涂鸦智能 Tuya", "url": "https://www.tuya.com/careers", "tags": ["IoT", "AI", "云计算"]},
    {"name": "树莓派中国", "url": "https://www.raspberrypi.com/careers", "tags": ["IoT", "嵌入式", "教育"]},
    {"name": "乐鑫科技 Espressif", "url": "https://www.espressif.com/careers", "tags": ["IoT", "芯片", "嵌入式"]},
    {"name": "广和通 Fibocom", "url": "https://www.fibocom.com/careers", "tags": ["IoT", "通信模组"]},
    {"name": "移远通信 Quectel", "url": "https://www.quectel.com/careers", "tags": ["IoT", "通信模组", "嵌入式"]},
    {"name": "中移物联网 OneNET", "url": "https://open.iot.10086.cn", "tags": ["IoT", "平台"]},
    {"name": "美的IoT", "url": "https://career.midea.com", "tags": ["IoT", "智能家居"]},
    {"name": "海尔智家", "url": "https://maker.haier.net", "tags": ["IoT", "智能家居"]},
    {"name": "地平线 Horizon", "url": "https://www.horizon.auto/careers", "tags": ["嵌入式AI", "自动驾驶", "芯片"]},
    {"name": "瑞芯微 Rockchip", "url": "https://www.rock-chips.com/careers", "tags": ["芯片", "嵌入式", "AI"]},
    {"name": "全志科技 Allwinner", "url": "https://www.allwinnertech.com/careers", "tags": ["芯片", "嵌入式"]},
    {"name": "晶晨半导体 Amlogic", "url": "https://www.amlogic.com/careers", "tags": ["芯片", "嵌入式"]},
    {"name": "算能科技 Sophgo", "url": "https://www.sophgo.com/careers", "tags": ["AI芯片", "RISC-V", "推理"]},
    {"name": "嘉楠科技 Canaan", "url": "https://www.canaan-creative.com/careers", "tags": ["AI芯片", "区块链"]},

    # ===== AI Infra / MLOps / 推理引擎 =====
    {"name": "硅基流动 SiliconFlow", "url": "https://www.siliconflow.com/careers", "tags": ["AI", "推理", "基础设施"]},
    {"name": "趋境科技", "url": "https://www.traverseml.com/careers", "tags": ["AI", "推理", "基础设施"]},
    {"name": "清昴智能", "url": "https://www.qingmaoai.com/careers", "tags": ["AI", "推理优化"]},
    {"name": "潞晨科技", "url": "https://www.luchentech.com/careers", "tags": ["AI", "分布式训练"]},
    {"name": "一蓦科技 1m0", "url": "https://www.1m0ai.com/careers", "tags": ["AI", "推理"]},
    {"name": "墨芯人工智能", "url": "https://www.moffettai.com/careers", "tags": ["AI", "稀疏计算"]},
    {"name": "探境科技", "url": "https://www.intengine.com/careers", "tags": ["AI芯片", "端侧推理"]},
    {"name": "鲲云科技", "url": "https://www.corerain.com/careers", "tags": ["AI加速", "数据流"]},
    {"name": "登临科技", "url": "https://www.denglintech.com/careers", "tags": ["AI芯片", "GPGPU"]},
    {"name": "亿铸科技", "url": "https://www.yizhutek.com/careers", "tags": ["AI芯片", "存算一体"]},
    {"name": "知存科技", "url": "https://www.witmem.com/careers", "tags": ["AI芯片", "存算一体"]},
    {"name": "九天睿芯", "url": "https://www.reexen.com/careers", "tags": ["AI芯片", "传感器"]},

    # ===== 自动驾驶 / 智能交通 (补充) =====
    {"name": "极氪汽车", "url": "https://www.zeekrlife.com/careers", "tags": ["汽车", "自动驾驶"]},
    {"name": "阿维塔", "url": "https://www.avatr.com/careers", "tags": ["汽车", "自动驾驶"]},
    {"name": "岚图汽车", "url": "https://www.voyah.com/careers", "tags": ["汽车", "新能源"]},
    {"name": "集度汽车", "url": "https://www.jidu.com/careers", "tags": ["汽车", "自动驾驶"]},
    {"name": "智己汽车", "url": "https://www.zhiji.com/careers", "tags": ["汽车", "自动驾驶"]},
    {"name": "高合汽车", "url": "https://www.hiphi.com/careers", "tags": ["汽车", "高端"]},
    {"name": "零跑汽车", "url": "https://www.leapmotor.com/careers", "tags": ["汽车", "自动驾驶"]},
    {"name": "哪吒汽车", "url": "https://www.hozonauto.com/careers", "tags": ["汽车", "新能源"]},
    {"name": "赛力斯汽车", "url": "https://www.seres.cn/careers", "tags": ["汽车", "新能源"]},
    {"name": "宇通客车", "url": "https://www.yutong.com/careers", "tags": ["汽车", "新能源", "自动驾驶"]},
    {"name": "百度Apollo", "url": "https://talent.baidu.com", "tags": ["自动驾驶", "AI"]},
    {"name": "滴滴自动驾驶", "url": "https://talent.didiglobal.com", "tags": ["自动驾驶", "AI"]},
    {"name": "轻舟智航", "url": "https://www.qcraft.ai/careers", "tags": ["自动驾驶", "AI"]},
    {"name": "元戎启行", "url": "https://www.deeproute.ai/careers", "tags": ["自动驾驶", "AI"]},
    {"name": "鉴智机器人", "url": "https://www.phigent.ai/careers", "tags": ["自动驾驶", "AI", "机器人"]},

    # ===== 机器人 (补充) =====
    {"name": "优必选 UBTECH", "url": "https://www.ubtrobot.com/careers", "tags": ["机器人", "AI", "消费"]},
    {"name": "达闼机器人", "url": "https://www.cloudminds.com/careers", "tags": ["机器人", "云计算", "AI"]},
    {"name": "普渡科技", "url": "https://www.pudutech.com/careers", "tags": ["机器人", "配送"]},
    {"name": "擎朗智能", "url": "https://www.keenon.com/careers", "tags": ["机器人", "配送"]},
    {"name": "极智嘉 Geek+", "url": "https://www.geekplus.com/careers", "tags": ["机器人", "仓储", "物流"]},
    {"name": "海柔创新 HAI", "url": "https://www.hairobotics.com/careers", "tags": ["机器人", "仓储"]},
    {"name": "梅卡曼德 Mech-Mind", "url": "https://www.mech-mind.com/careers", "tags": ["机器人", "3D视觉"]},
    {"name": "珞石机器人", "url": "https://www.rokovtech.com/careers", "tags": ["机器人", "工业"]},
    {"name": "艾利特机器人", "url": "https://www.elibot.cn/careers", "tags": ["机器人", "工业"]},
    {"name": "节卡机器人", "url": "https://www.jaka.com/careers", "tags": ["机器人", "协作"]},
    {"name": "越疆科技 Dobot", "url": "https://www.dobot.cn/careers", "tags": ["机器人", "教育", "工业"]},

    # ===== 半导体 (补充) =====
    {"name": "华大九天", "url": "https://www.empyrean-tech.com/careers", "tags": ["EDA", "芯片"]},
    {"name": "ASML中国", "url": "https://www.asml.com/careers", "tags": ["半导体设备", "光刻"]},
    {"name": "应用材料 Applied Materials", "url": "https://www.appliedmaterials.com/careers", "tags": ["半导体设备"]},
    {"name": "泛林 Lam Research", "url": "https://careers.lamresearch.com", "tags": ["半导体设备"]},
    {"name": "长江存储 YMTC", "url": "https://www.ymtc.com/careers", "tags": ["存储", "芯片"]},
    {"name": "长电科技 JCET", "url": "https://www.jcetglobal.com/careers", "tags": ["封装", "半导体"]},
    {"name": "华天科技", "url": "https://www.ht-tech.com/careers", "tags": ["封装", "半导体"]},
    {"name": "通富微电", "url": "https://www.tfme.com/careers", "tags": ["封装", "半导体"]},
    {"name": "北方华创 NAURA", "url": "https://www.naura.com/careers", "tags": ["半导体设备"]},
    {"name": "中微公司 AMEC", "url": "https://www.amec-inc.com/careers", "tags": ["半导体设备", "刻蚀"]},
    {"name": "士兰微", "url": "https://www.silan.com.cn/careers", "tags": ["半导体", "功率器件"]},
    {"name": "华润微", "url": "https://www.crmicro.com/careers", "tags": ["半导体", "功率器件"]},
    {"name": "卓胜微", "url": "https://www.maxscend.com", "tags": ["射频", "芯片"]},
    {"name": "汇顶科技", "url": "https://www.goodix.com/careers", "tags": ["芯片", "指纹"]},
    {"name": "恒玄科技 BES", "url": "https://www.bestechnic.com/careers", "tags": ["芯片", "音频"]},
    {"name": "翱捷科技 ASR", "url": "https://www.asrmicro.com/careers", "tags": ["芯片", "通信"]},

    # ===== 开源 / 基础软件 =====
    {"name": "PingCAP", "url": "https://careers.pingcap.com", "tags": ["数据库", "开源", "基础设施"]},
    {"name": "涛思数据 TDengine", "url": "https://www.taosdata.com/careers", "tags": ["数据库", "开源", "IoT"]},
    {"name": "Zilliz", "url": "https://zilliz.com/careers", "tags": ["向量数据库", "开源", "AI"]},
    {"name": "思斐 SphereEx", "url": "https://www.sphere-ex.com/careers", "tags": ["数据库", "开源"]},
    {"name": "星环科技", "url": "https://www.transwarp.io/careers", "tags": ["大数据", "AI", "数据库"]},
    {"name": "EMQ 映云科技", "url": "https://www.emqx.com/careers", "tags": ["IoT消息", "开源", "边缘计算"]},
    {"name": "Juicedata", "url": "https://juicefs.com/careers", "tags": ["存储", "开源", "基础设施"]},
    {"name": "API7", "url": "https://www.api7.ai/careers", "tags": ["API网关", "开源", "基础设施"]},
    {"name": "思码逸", "url": "https://www.merico.cn/careers", "tags": ["DevOps", "开源"]},
    {"name": "Gitee 码云", "url": "https://gitee.com/about/careers", "tags": ["开发者工具", "开源"]},

    # ===== 量子计算 / 前沿科技 =====
    {"name": "本源量子", "url": "https://www.originqc.com.cn/careers", "tags": ["量子计算", "前沿"]},
    {"name": "国盾量子", "url": "https://www.quantum-info.com/careers", "tags": ["量子通信", "量子计算"]},
    {"name": "玻色量子", "url": "https://www.boseqc.com/careers", "tags": ["量子计算"]},
    {"name": "图灵量子", "url": "https://www.turingq.com/careers", "tags": ["量子计算", "光子"]},

    # ===== 航天 / 军工 =====
    {"name": "中国航天科技", "url": "https://www.casc.com.cn/careers", "tags": ["航天", "国企"]},
    {"name": "中国航天科工", "url": "https://zhaopin.casic.cn", "tags": ["航天", "军工", "国企"]},
    {"name": "中国商飞 COMAC", "url": "https://www.comac.cc/careers", "tags": ["航空", "制造"]},
    {"name": "星际荣耀 iSpace", "url": "https://www.i-space.com.cn/careers", "tags": ["商业航天"]},
    {"name": "蓝箭航天 Landspace", "url": "https://www.landspace.com/careers", "tags": ["商业航天"]},
    {"name": "星河动力", "url": "https://www.galactic-energy.cn/careers", "tags": ["商业航天"]},
    {"name": "天仪研究院", "url": "https://www.spacety.com/careers", "tags": ["卫星", "商业航天"]},
    {"name": "长光卫星", "url": "https://www.jl1.cn/careers", "tags": ["卫星", "遥感"]},
    {"name": "中电科 CETC", "url": "https://www.cetc.com.cn/careers", "tags": ["军工", "电子", "国企"]},
    {"name": "中国电子 CEC", "url": "https://www.cec.com.cn/careers", "tags": ["电子", "信创", "国企"]},

    # ===== 区块链 / Web3 =====
    {"name": "蚂蚁链", "url": "https://talent.antgroup.com", "tags": ["区块链", "金融科技"]},
    {"name": "腾讯区块链", "url": "https://careers.tencent.com", "tags": ["区块链"]},
    {"name": "趣链科技", "url": "https://www.hyperchain.cn/careers", "tags": ["区块链", "企业服务"]},
    {"name": "万向区块链", "url": "https://www.wxblockchain.com/careers", "tags": ["区块链"]},
    {"name": "Conflux 树图", "url": "https://confluxnetwork.org/careers", "tags": ["区块链", "公链"]},

    # ===== 更多外资 =====
    {"name": "特斯拉", "url": "https://www.tesla.cn/careers", "tags": ["汽车", "AI", "外资"]},
    {"name": "博世中国", "url": "https://www.bosch.com.cn/careers", "tags": ["汽车零部件", "IoT", "外资"]},
    {"name": "西门子中国", "url": "https://new.siemens.com/cn/zh/company/jobs.html", "tags": ["工业", "数字化", "外资"]},
    {"name": "施耐德电气", "url": "https://www.se.com.cn/careers", "tags": ["工业", "能源", "外资"]},
    {"name": "ABB中国", "url": "https://new.abb.com/cn/careers", "tags": ["工业", "机器人", "外资"]},
    {"name": "飞利浦中国", "url": "https://www.philips.com.cn/careers", "tags": ["医疗", "消费电子", "外资"]},
    {"name": "通用电气 GE", "url": "https://www.ge.com.cn/careers", "tags": ["工业", "医疗", "能源"]},
    {"name": "戴尔中国", "url": "https://jobs.dell.com", "tags": ["IT", "服务器", "外资"]},
    {"name": "惠普中国", "url": "https://jobs.hp.com", "tags": ["IT", "打印", "外资"]},
    {"name": "思科中国", "url": "https://www.cisco.com/c/zh_cn/about/careers.html", "tags": ["网络", "外资"]},
    {"name": "索尼中国", "url": "https://www.sony.com.cn/careers", "tags": ["消费电子", "娱乐", "外资"]},
    {"name": "松下中国", "url": "https://careers.panasonic.cn", "tags": ["电子", "家电", "外资"]},
    {"name": "宝马中国", "url": "https://www.bmw-brilliance.cn/careers", "tags": ["汽车", "外资"]},
    {"name": "奔驰中国", "url": "https://www.mercedes-benz.com.cn/careers", "tags": ["汽车", "外资"]},
    {"name": "奥迪中国", "url": "https://www.audi.cn/careers", "tags": ["汽车", "外资"]},
    {"name": "保时捷中国", "url": "https://www.porsche.cn/careers", "tags": ["汽车", "外资"]},

    # ===== 更多互联网 / 科技 =====
    {"name": "Keep", "url": "https://about.keep.com/careers", "tags": ["互联网", "健身"]},
    {"name": "BOSS直聘", "url": "https://www.zhipin.com/about/careers", "tags": ["互联网", "招聘"]},
    {"name": "猎聘", "url": "https://www.liepin.com/careers", "tags": ["互联网", "招聘"]},
    {"name": "拉勾", "url": "https://about.lagou.com/careers", "tags": ["互联网", "招聘"]},
    {"name": "陌陌/挚文集团", "url": "https://www.hellogroup.com/careers", "tags": ["互联网", "社交"]},
    {"name": "探探", "url": "https://tantanapp.com/careers", "tags": ["互联网", "社交"]},
    {"name": "Soul", "url": "https://www.soulapp.cn/careers", "tags": ["互联网", "社交"]},
    {"name": "最右", "url": "https://www.zuiyouxi.com/careers", "tags": ["互联网", "社区"]},
    {"name": "什么值得买", "url": "https://www.smzdm.com/careers", "tags": ["互联网", "电商"]},
    {"name": "美图", "url": "https://hr.meitu.com", "tags": ["互联网", "影像", "AI"]},
    {"name": "美柚", "url": "https://www.meiyou.com/careers", "tags": ["互联网", "健康"]},
    {"name": "宝宝树", "url": "https://www.babytree.com/careers", "tags": ["互联网", "母婴"]},
    {"name": "汽车之家", "url": "https://www.autohome.com.cn/careers", "tags": ["互联网", "汽车"]},
    {"name": "易车", "url": "https://www.yiche.com/careers", "tags": ["互联网", "汽车"]},
    {"name": "懂车帝", "url": "https://www.dongchedi.com/careers", "tags": ["互联网", "汽车"]},
    {"name": "马蜂窝", "url": "https://www.mafengwo.cn/careers", "tags": ["互联网", "旅游"]},
    {"name": "同程旅行", "url": "https://careers.ly.com", "tags": ["互联网", "旅游"]},
    {"name": "途牛", "url": "https://www.tuniu.com/careers", "tags": ["互联网", "旅游"]},
    {"name": "货拉拉", "url": "https://www.huolala.cn/careers", "tags": ["互联网", "物流"]},
    {"name": "满帮集团", "url": "https://www.ymm56.com/careers", "tags": ["互联网", "物流"]},
    {"name": "快狗打车", "url": "https://www.kuaigou.com/careers", "tags": ["互联网", "物流"]},
    {"name": "贝壳找房", "url": "https://careers.ke.com", "tags": ["互联网", "房产"]},
    {"name": "自如", "url": "https://www.ziroom.com/about/careers", "tags": ["互联网", "房产"]},
    {"name": "土巴兔", "url": "https://www.to8to.com/careers", "tags": ["互联网", "装修"]},

    # ===== 游戏 (补充) =====
    {"name": "腾讯游戏", "url": "https://careers.tencent.com", "tags": ["游戏", "互联网"]},
    {"name": "网易互娱", "url": "https://game.ac.163.com", "tags": ["游戏"]},
    {"name": "西山居", "url": "https://www.xishanju.com/careers", "tags": ["游戏"]},
    {"name": "哔哩哔哩游戏", "url": "https://jobs.bilibili.com", "tags": ["游戏", "二次元"]},
    {"name": "心动网络", "url": "https://www.xd.com/careers", "tags": ["游戏", "TapTap"]},
    {"name": "游族网络", "url": "https://www.youzu.com/careers", "tags": ["游戏"]},
    {"name": "巨人网络", "url": "https://www.ztgame.com/careers", "tags": ["游戏"]},
    {"name": "恺英网络", "url": "https://www.kingnet.com/careers", "tags": ["游戏"]},
    {"name": "趣加 FunPlus", "url": "https://www.funplus.com/careers", "tags": ["游戏", "出海"]},
    {"name": "友塔游戏 Yotta", "url": "https://www.yottagames.com.cn/careers", "tags": ["游戏"]},
    {"name": "沐瞳科技 Moonton", "url": "https://www.moonton.com/careers", "tags": ["游戏"]},
    {"name": "IGG", "url": "https://www.igg.com/careers", "tags": ["游戏", "出海"]},
    {"name": "紫龙游戏", "url": "https://www.zlongame.com/careers", "tags": ["游戏"]},
    {"name": "散爆网络", "url": "https://www.sunborngame.com/careers", "tags": ["游戏"]},

    # ===== 更多金融 / 银行 =====
    {"name": "交通银行", "url": "https://job.bankcomm.com", "tags": ["银行", "金融", "国企"]},
    {"name": "浦发银行", "url": "https://job.spdb.com.cn", "tags": ["银行", "金融"]},
    {"name": "兴业银行", "url": "https://job.cib.com.cn", "tags": ["银行", "金融"]},
    {"name": "民生银行", "url": "https://career.cmbc.com.cn", "tags": ["银行", "金融"]},
    {"name": "华夏银行", "url": "https://zhaopin.hxb.com.cn", "tags": ["银行", "金融"]},
    {"name": "广发银行", "url": "https://www.cgbchina.com.cn/careers", "tags": ["银行", "金融"]},
    {"name": "宁波银行", "url": "https://zhaopin.nbcb.com.cn", "tags": ["银行", "金融科技"]},
    {"name": "南京银行", "url": "https://job.njcb.com.cn", "tags": ["银行", "金融"]},
    {"name": "国泰君安证券", "url": "https://hr.gtja.com", "tags": ["证券", "金融"]},
    {"name": "招商证券", "url": "https://cms.hotjob.cn", "tags": ["证券", "金融"]},
    {"name": "中国银联", "url": "https://career.unionpay.com", "tags": ["金融", "支付"]},
    {"name": "度小满金融", "url": "https://www.duxiaoman.com/careers", "tags": ["金融科技", "AI"]},
    {"name": "马上消费金融", "url": "https://www.msxf.com/careers", "tags": ["金融科技"]},
    {"name": "众安保险", "url": "https://www.zhongan.com/careers", "tags": ["保险", "金融科技"]},

    # ===== 生物医药 (补充) =====
    {"name": "华大基因 BGI", "url": "https://www.genomics.cn/careers", "tags": ["基因", "医疗", "AI"]},
    {"name": "金域医学", "url": "https://www.kingmed.com.cn/careers", "tags": ["医疗", "检验"]},
    {"name": "迪安诊断", "url": "https://www.dazd.cn/careers", "tags": ["医疗", "检验"]},
    {"name": "燃石医学", "url": "https://www.brbiotech.com/careers", "tags": ["医疗", "基因"]},
    {"name": "泛生子", "url": "https://www.genetronhealth.com/careers", "tags": ["医疗", "基因"]},
    {"name": "微医", "url": "https://www.guahao.com/careers", "tags": ["医疗", "互联网"]},
    {"name": "丁香园", "url": "https://www.dxy.cn/careers", "tags": ["医疗", "互联网"]},
    {"name": "医联 Medlinker", "url": "https://www.medlinker.com/careers", "tags": ["医疗", "互联网"]},
    {"name": "圆心科技", "url": "https://www.yuanxin.com/careers", "tags": ["医疗", "互联网"]},

    # ===== 更多制造 / 能源 =====
    {"name": "三一重工", "url": "https://www.sany.com.cn/careers", "tags": ["工程机械", "制造", "IoT"]},
    {"name": "徐工集团", "url": "https://www.xcmg.com/careers", "tags": ["工程机械", "制造"]},
    {"name": "中联重科", "url": "https://www.zoomlion.com/careers", "tags": ["工程机械", "制造"]},
    {"name": "柳工", "url": "https://www.liugong.cn/careers", "tags": ["工程机械", "制造"]},
    {"name": "隆基绿能", "url": "https://www.longi.com/careers", "tags": ["光伏", "新能源"]},
    {"name": "阳光电源", "url": "https://www.sungrowpower.com/careers", "tags": ["光伏", "逆变器"]},
    {"name": "远景能源", "url": "https://www.envision-group.com/careers", "tags": ["风电", "AI", "储能"]},
    {"name": "金风科技", "url": "https://www.goldwind.com/careers", "tags": ["风电", "新能源"]},
    {"name": "蜂巢能源", "url": "https://www.svolt.cn/careers", "tags": ["电池", "新能源"]},
    {"name": "亿纬锂能", "url": "https://www.evebattery.com/careers", "tags": ["电池", "新能源"]},
    {"name": "欣旺达", "url": "https://www.sunwoda.com/careers", "tags": ["电池", "消费电子"]},
    {"name": "先导智能", "url": "https://www.leadintelligent.com/careers", "tags": ["锂电设备", "制造"]},
    {"name": "汇川技术", "url": "https://www.inovance.com/careers", "tags": ["工业自动化", "机器人"]},
    {"name": "埃斯顿 Estun", "url": "https://www.estun.com/careers", "tags": ["工业自动化", "机器人"]},
    {"name": "新松机器人 SIASUN", "url": "https://www.siasun.com/careers", "tags": ["机器人", "工业"]},
    {"name": "拓斯达 Topstar", "url": "https://www.topstarltd.com/careers", "tags": ["工业自动化", "机器人"]},
    {"name": "大族激光", "url": "https://www.hanslaser.com/careers", "tags": ["激光", "制造"]},

    # ===== 更多通信 / IT设备 =====
    {"name": "烽火通信", "url": "https://www.fiberhome.com/careers", "tags": ["通信", "光纤"]},
    {"name": "新华三 H3C", "url": "https://www.h3c.com/cn/careers", "tags": ["网络", "IT", "服务器"]},
    {"name": "锐捷网络", "url": "https://www.ruijie.com.cn/careers", "tags": ["网络", "IT"]},
    {"name": "浪潮信息", "url": "https://career.inspur.com", "tags": ["服务器", "AI", "云计算"]},
    {"name": "中科曙光", "url": "https://www.sugon.com/careers", "tags": ["服务器", "超算", "AI"]},
    {"name": "超聚变 xFusion", "url": "https://www.xfusion.com/careers", "tags": ["服务器", "基础设施"]},
    {"name": "深信服 Sangfor", "url": "https://hr.sangfor.com", "tags": ["网络", "安全"]},
    {"name": "锐明技术", "url": "https://www.streamax.com/careers", "tags": ["车载视频", "AI", "IoT"]},

    # ===== 物流 / 供应链 =====
    {"name": "顺丰科技", "url": "https://hr.sf-express.com", "tags": ["物流", "科技"]},
    {"name": "京东物流", "url": "https://zhaopin.jd.com", "tags": ["物流", "科技"]},
    {"name": "菜鸟网络", "url": "https://www.cainiao.com/careers", "tags": ["物流", "AI", "IoT"]},
    {"name": "圆通", "url": "https://www.yto.net.cn/careers", "tags": ["物流"]},
    {"name": "中通", "url": "https://hr.zto.com", "tags": ["物流"]},
    {"name": "韵达", "url": "https://www.yundaex.com/careers", "tags": ["物流"]},
    {"name": "极兔 J&T", "url": "https://www.jtexpress.com/careers", "tags": ["物流"]},
    {"name": "丰巢", "url": "https://www.fcbox.com/careers", "tags": ["物流", "IoT"]},
    {"name": "G7物联", "url": "https://www.g7.com.cn/careers", "tags": ["物流", "IoT"]},
    {"name": "福佑卡车", "url": "https://www.fuyoukache.com/careers", "tags": ["物流", "AI"]},

    # ===== 环保 / 碳中和 =====
    {"name": "中国节能", "url": "https://www.cecep.cn/careers", "tags": ["环保", "国企"]},
    {"name": "光大环境", "url": "https://www.ebchinaintl.com/careers", "tags": ["环保", "能源"]},
    {"name": "碧水源", "url": "https://www.originwater.com/careers", "tags": ["水处理", "环保"]},
    {"name": "高能环境", "url": "https://www.bgechina.cn/careers", "tags": ["环保"]},
    {"name": "碳阻迹", "url": "https://www.carbonstop.com/careers", "tags": ["碳中和", "科技"]},

    # ===== 农业科技 =====
    {"name": "极飞科技 XAG", "url": "https://www.xa.com/careers", "tags": ["农业", "无人机", "AI"]},
    {"name": "大疆农业", "url": "https://ag.dji.com/careers", "tags": ["农业", "无人机"]},
    {"name": "先正达中国", "url": "https://www.syngenta.com.cn/careers", "tags": ["农业", "生物"]},
    {"name": "丰疆智能", "url": "https://www.fjdynamics.com/careers", "tags": ["农业", "机器人", "AI"]},

    # ===== 地图 / LBS =====
    {"name": "高德地图", "url": "https://talent.amap.com", "tags": ["地图", "LBS", "自动驾驶"]},
    {"name": "百度地图", "url": "https://talent.baidu.com", "tags": ["地图", "LBS"]},
    {"name": "四维图新", "url": "https://www.navinfo.com/careers", "tags": ["地图", "自动驾驶", "高精地图"]},
    {"name": "千寻位置", "url": "https://www.qxwz.com/careers", "tags": ["定位", "北斗", "IoT"]},

    # ===== 音视频 / 多媒体 =====
    {"name": "声网 Agora", "url": "https://www.agora.io/cn/careers", "tags": ["音视频", "RTC", "基础设施"]},
    {"name": "即构 ZEGO", "url": "https://www.zego.im/careers", "tags": ["音视频", "RTC"]},
    {"name": "剪映 CapCut", "url": "https://careers.bytedance.com", "tags": ["视频编辑", "AI"]},
    {"name": "万兴科技 Wondershare", "url": "https://www.wondershare.cn/careers", "tags": ["软件", "创意"]},
    {"name": "稿定设计", "url": "https://www.gaoding.com/careers", "tags": ["设计", "AI"]},

    # ===== 法律科技 / 企业服务 =====
    {"name": "北森 Beisen", "url": "https://www.beisen.com/careers", "tags": ["HR科技", "SaaS"]},
    {"name": "销售易", "url": "https://www.xiaoshouyi.com/careers", "tags": ["CRM", "SaaS"]},
    {"name": "纷享销客", "url": "https://www.fxiaoke.com/careers", "tags": ["CRM", "SaaS"]},
    {"name": "用友网络", "url": "https://careers.yonyou.com", "tags": ["ERP", "SaaS", "企业服务"]},
    {"name": "金蝶", "url": "https://www.kingdee.com/careers", "tags": ["ERP", "SaaS", "企业服务"]},
    {"name": "明源云", "url": "https://www.mysoft.com.cn/careers", "tags": ["地产科技", "SaaS"]},
    {"name": "广联达", "url": "https://www.glodon.com/careers", "tags": ["建筑科技", "SaaS"]},
    {"name": "飞书 Feishu", "url": "https://careers.bytedance.com", "tags": ["协作", "SaaS", "AI"]},
    {"name": "钉钉", "url": "https://talent.dingtalk.com", "tags": ["协作", "SaaS"]},
    {"name": "企业微信", "url": "https://careers.tencent.com", "tags": ["协作", "SaaS"]},
    {"name": "金山办公 WPS", "url": "https://join.wps.cn", "tags": ["办公软件", "AI"]},
    {"name": "印象笔记", "url": "https://www.yinxiang.com/careers", "tags": ["工具", "SaaS"]},
    {"name": "石墨文档", "url": "https://shimo.im/careers", "tags": ["协作", "SaaS"]},
    {"name": "蓝湖", "url": "https://www.lanhuapp.com/careers", "tags": ["设计协作", "SaaS"]},
    {"name": "即时设计 JsDesign", "url": "https://js.design/careers", "tags": ["设计", "协作"]},

    # ===== 电商 / 新零售 =====
    {"name": "淘宝天猫", "url": "https://talent.alibaba.com", "tags": ["电商", "互联网"]},
    {"name": "抖音电商", "url": "https://careers.bytedance.com", "tags": ["电商", "直播"]},
    {"name": "快手电商", "url": "https://zhaopin.kuaishou.cn", "tags": ["电商", "直播"]},
    {"name": "拼多多 Temu", "url": "https://careers.pinduoduo.com", "tags": ["电商", "出海"]},
    {"name": "盒马", "url": "https://www.freshhema.com/careers", "tags": ["新零售", "生鲜"]},
    {"name": "山姆会员店中国", "url": "https://www.walmartcareers.com.cn", "tags": ["零售", "外资"]},
    {"name": "Costco开市客中国", "url": "https://www.costco.com.cn/careers", "tags": ["零售", "外资"]},
    {"name": "名创优品", "url": "https://www.miniso.cn/careers", "tags": ["零售"]},
    {"name": "泡泡玛特", "url": "https://www.popmart.com/careers", "tags": ["零售", "潮玩"]},

    # ===== 文化 / 媒体 / 娱乐 =====
    {"name": "爱奇艺", "url": "https://careers.iqiyi.com", "tags": ["视频", "AI", "内容"]},
    {"name": "优酷", "url": "https://talent.alibaba.com", "tags": ["视频", "内容"]},
    {"name": "腾讯视频", "url": "https://careers.tencent.com", "tags": ["视频", "内容"]},
    {"name": "芒果TV", "url": "https://hr.mgtv.com", "tags": ["视频", "媒体"]},
    {"name": "阅文集团", "url": "https://careers.yuewen.com", "tags": ["网文", "IP"]},
    {"name": "喜马拉雅", "url": "https://www.ximalaya.com/careers", "tags": ["音频", "内容"]},
    {"name": "得到", "url": "https://www.igetget.com/careers", "tags": ["知识付费"]},
    {"name": "帆书(樊登读书)", "url": "https://www.fanshu.cn/careers", "tags": ["知识付费"]},
]


# ── 岗位数据库 ──────────────────────────────────────────────────────
# 每个岗位包含: 岗位名称、核心技能、岗位描述、薪资范围、匹配行业标签

POSITIONS = [
    # ===== AI 推理 / 部署 (核心方向) =====
    {
        "role": "AI推理引擎开发工程师",
        "skills": ["C++", "CUDA", "TensorRT", "ONNX", "模型量化", "推理优化", "算子开发"],
        "description": "负责深度学习模型的高性能推理部署，包括模型量化/剪枝/蒸馏、GPU算子开发、推理框架优化。在端侧(手机/嵌入式)或云端(GPU集群)实现低延迟高吞吐推理。",
        "salary_range": "25k-55k/月 (应届20k-35k)",
        "tags": ["AI", "推理", "芯片", "AI芯片", "嵌入式AI", "基础设施"],
    },
    {
        "role": "AI模型部署工程师 (MLOps)",
        "skills": ["Python", "Docker", "Kubernetes", "TensorFlow/PyTorch", "ONNX", "Triton Server", "CI/CD"],
        "description": "负责AI模型的线上部署和运维，搭建模型服务化(Serving)平台，管理模型版本、AB测试、灰度发布、性能监控。",
        "salary_range": "22k-50k/月 (应届18k-30k)",
        "tags": ["AI", "云计算", "互联网", "大模型"],
    },
    {
        "role": "高性能计算工程师 (HPC/AI)",
        "skills": ["C++", "CUDA/OpenCL", "MPI", "分布式系统", "GPU集群", "性能调优", "Linux内核"],
        "description": "负责大规模分布式训练/推理系统的性能优化，包括GPU集群调度、集合通信优化(NCCL)、混合并行策略(数据并行/模型并行/流水线并行)。",
        "salary_range": "30k-60k/月 (应届22k-38k)",
        "tags": ["AI", "芯片", "GPU", "云计算", "大模型", "基础设施"],
    },
    # ===== 自动驾驶 =====
    {
        "role": "自动驾驶感知算法工程师",
        "skills": ["Python", "C++", "PyTorch", "3D目标检测", "BEV感知", "Occupancy Network", "点云处理", "多传感器融合"],
        "description": "负责自动驾驶感知算法研发，包括视觉/BEV/激光雷达3D目标检测、Occupancy预测、多传感器融合、端到端感知模型。",
        "salary_range": "28k-55k/月 (应届22k-35k)",
        "tags": ["自动驾驶", "AI", "汽车"],
    },
    {
        "role": "自动驾驶规划控制工程师",
        "skills": ["C++", "ROS/ROS2", "路径规划", "运动控制", "MPC", "优化算法", "仿真"],
        "description": "负责自动驾驶决策规划与控制算法，包括行为决策、轨迹规划、运动控制、仿真验证。",
        "salary_range": "25k-50k/月 (应届20k-32k)",
        "tags": ["自动驾驶", "汽车"],
    },
    {
        "role": "自动驾驶系统集成工程师",
        "skills": ["C++", "Linux", "嵌入式系统", "传感器驱动", "中间件(ROS/DDS)", "实时系统"],
        "description": "负责自动驾驶系统软件架构与集成，包括传感器驱动开发、中间件适配、实时系统优化、整车联调。",
        "salary_range": "22k-45k/月 (应届18k-28k)",
        "tags": ["自动驾驶", "汽车", "嵌入式"],
    },
    {
        "role": "SLAM与定位算法工程师",
        "skills": ["C++", "SLAM", "多传感器融合", "IMU/GPS", "卡尔曼滤波", "因子图优化", "视觉里程计"],
        "description": "负责自动驾驶/机器人定位与建图算法，包括视觉SLAM、激光SLAM、多传感器融合定位、高精地图匹配。",
        "salary_range": "25k-50k/月 (应届20k-33k)",
        "tags": ["自动驾驶", "机器人", "AI"],
    },
    # ===== 嵌入式 / IoT =====
    {
        "role": "嵌入式软件工程师 (C/C++)",
        "skills": ["C/C++", "RTOS/FreeRTOS", "Linux驱动", "ARM架构", "SPI/I2C/UART", "低功耗设计", "调试(JTAG/GDB)"],
        "description": "负责嵌入式系统软件开发，包括MCU固件、Linux驱动、RTOS移植、外设驱动、低功耗优化、硬件调试。",
        "salary_range": "18k-40k/月 (应届15k-25k)",
        "tags": ["IoT", "嵌入式", "芯片", "消费电子", "汽车"],
    },
    {
        "role": "边缘计算开发工程师",
        "skills": ["C++", "Python", "边缘推理(TensorRT/ONNX Runtime)", "Linux", "Docker", "MQTT", "边缘AI部署"],
        "description": "负责边缘计算节点上的AI模型部署和系统开发，包括模型轻量化、边缘推理优化、设备管理、边缘-云协同。",
        "salary_range": "20k-42k/月 (应届16k-28k)",
        "tags": ["IoT", "边缘计算", "AI", "嵌入式AI", "云计算"],
    },
    {
        "role": "IoT平台开发工程师",
        "skills": ["Python/Go", "MQTT/CoAP", "时序数据库", "微服务", "设备管理", "OTA升级", "云原生"],
        "description": "负责IoT云平台后端开发，包括设备接入与管理、消息路由、数据存储与分析、规则引擎、设备影子。",
        "salary_range": "20k-40k/月 (应届15k-25k)",
        "tags": ["IoT", "云计算", "互联网"],
    },
    # ===== 后端 / 基础设施 =====
    {
        "role": "C++后端开发工程师",
        "skills": ["C++11/14/17", "STL/Boost", "多线程", "网络编程(TCP/UDP)", "Linux系统编程", "内存管理", "性能优化"],
        "description": "负责高性能C++服务端开发，包括网络服务、存储引擎、消息队列、RPC框架等基础设施组件的设计与实现。",
        "salary_range": "22k-48k/月 (应届18k-30k)",
        "tags": ["互联网", "基础设施", "数据库", "通信"],
    },
    {
        "role": "数据库内核开发工程师",
        "skills": ["C/C++", "数据库原理", "存储引擎", "SQL优化", "分布式共识(Raft/Paxos)", "索引结构(B+Tree/LSM)"],
        "description": "负责数据库内核开发，包括SQL引擎、存储引擎、事务管理、分布式一致性、查询优化器的设计与实现。",
        "salary_range": "28k-55k/月 (应届22k-35k)",
        "tags": ["数据库", "基础设施", "开源"],
    },
    {
        "role": "云计算研发工程师",
        "skills": ["Go/C++", "Kubernetes", "Docker", "虚拟化", "SDN", "分布式存储", "微服务架构"],
        "description": "负责云计算平台核心组件研发，包括容器编排、存储/网络虚拟化、资源调度、弹性伸缩、混合云管理。",
        "salary_range": "25k-50k/月 (应届20k-30k)",
        "tags": ["云计算", "基础设施", "互联网"],
    },
    # ===== 芯片 / 半导体 =====
    {
        "role": "AI芯片架构工程师",
        "skills": ["C++", "计算机体系结构", "深度学习", "性能建模", "Verilog/SystemVerilog", "片上网络(NoC)"],
        "description": "负责AI加速芯片架构设计，包括NPU/GPU架构探索、性能建模与仿真、数据流设计、编译器联合优化。",
        "salary_range": "30k-60k+ (应届25k-40k)",
        "tags": ["AI芯片", "芯片", "半导体"],
    },
    {
        "role": "GPU软件开发工程师",
        "skills": ["C++", "CUDA", "OpenGL/Vulkan", "图形学", "并行计算", "驱动开发", "编译器"],
        "description": "负责GPU软件栈开发，包括CUDA/OpenCL运行时、图形驱动、编译器后端、性能分析工具。",
        "salary_range": "28k-55k/月 (应届22k-35k)",
        "tags": ["芯片", "GPU", "AI芯片"],
    },
    {
        "role": "EDA软件开发工程师",
        "skills": ["C++", "算法", "图论", "计算几何", "优化理论", "分布式计算", "Verilog基础"],
        "description": "负责EDA工具软件开发，包括逻辑综合、布局布线、时序分析、物理验证等核心算法的实现与优化。",
        "salary_range": "25k-50k/月 (应届20k-32k)",
        "tags": ["EDA", "芯片", "半导体"],
    },
    {
        "role": "固件/驱动开发工程师",
        "skills": ["C", "ARM/RISC-V架构", "Linux内核", "设备驱动", "U-Boot/BIOS", "硬件调试", "RTOS"],
        "description": "负责芯片BSP/固件/驱动开发，包括Bootloader、Linux内核驱动、硬件抽象层、板级支持包。",
        "salary_range": "20k-45k/月 (应届16k-26k)",
        "tags": ["芯片", "嵌入式", "IoT"],
    },
    # ===== 机器人 =====
    {
        "role": "机器人软件工程师",
        "skills": ["C++", "Python", "ROS/ROS2", "运动控制", "路径规划", "计算机视觉", "传感器融合"],
        "description": "负责机器人软件系统开发，包括运动规划、控制算法、视觉感知、仿真环境搭建、系统集成。",
        "salary_range": "22k-45k/月 (应届17k-28k)",
        "tags": ["机器人", "AI"],
    },
    {
        "role": "机器人操作系统开发工程师",
        "skills": ["C++", "Linux", "实时系统", "中间件(DDS/ZMQ)", "分布式通信", "状态机", "确定性调度"],
        "description": "负责机器人操作系统/中间件的底层开发，包括实时通信框架、确定性调度、硬件抽象、安全机制。",
        "salary_range": "25k-50k/月 (应届20k-30k)",
        "tags": ["机器人", "嵌入式", "基础设施"],
    },
    # ===== 计算机视觉 / 感知 =====
    {
        "role": "计算机视觉算法工程师",
        "skills": ["Python", "PyTorch", "OpenCV", "目标检测/分割", "图像分类", "GAN/扩散模型"],
        "description": "负责计算机视觉算法研发，包括图像分类、目标检测、语义分割、图像生成、视觉特征提取。",
        "salary_range": "25k-50k/月 (应届20k-32k)",
        "tags": ["AI", "计算机视觉", "互联网"],
    },
    # ===== NLP / 大模型 =====
    {
        "role": "大模型应用开发工程师",
        "skills": ["Python", "LangChain/LlamaIndex", "RAG", "Prompt Engineering", "向量数据库", "API开发", "微调(LoRA)"],
        "description": "负责基于大语言模型的应用开发，包括RAG系统搭建、Agent开发、模型微调、Prompt优化、应用部署。",
        "salary_range": "22k-48k/月 (应届18k-30k)",
        "tags": ["AI", "大模型", "互联网"],
    },
    {
        "role": "AI框架开发工程师",
        "skills": ["C++/Python", "编译器(MLIR/TVM)", "自动微分", "计算图优化", "分布式训练", "算子库开发"],
        "description": "负责深度学习框架(PyTorch/TensorFlow/JAX)或AI编译器(TVM/MLIR/XLA)的底层开发与优化。",
        "salary_range": "30k-60k/月 (应届25k-38k)",
        "tags": ["AI", "基础设施", "大模型"],
    },
    # ===== 通用开发 =====
    {
        "role": "软件开发工程师 (C++/系统方向)",
        "skills": ["C++", "数据结构", "算法", "操作系统", "网络编程", "设计模式", "代码重构"],
        "description": "负责底层系统/中间件/核心组件的C++开发，包括性能优化、内存管理、并发编程、跨平台适配。",
        "salary_range": "20k-40k/月 (应届15k-25k)",
        "tags": ["互联网", "基础设施", "通信", "芯片", "汽车"],
    },
    {
        "role": "后端开发工程师 (Go/Java)",
        "skills": ["Go/Java", "微服务", "MySQL/Redis", "消息队列(Kafka/RabbitMQ)", "分布式系统", "API设计"],
        "description": "负责后端服务开发，包括API设计、业务逻辑实现、数据存储、缓存策略、系统架构设计。",
        "salary_range": "20k-42k/月 (应届15k-25k)",
        "tags": ["互联网", "金融科技", "SaaS"],
    },
    {
        "role": "前端开发工程师",
        "skills": ["JavaScript/TypeScript", "React/Vue/Angular", "HTML/CSS", "Webpack/Vite", "Node.js基础", "性能优化"],
        "description": "负责Web/移动端前端开发，包括UI组件开发、状态管理、性能优化、跨端适配。",
        "salary_range": "18k-38k/月 (应届12k-22k)",
        "tags": ["互联网", "SaaS", "金融科技", "电商", "游戏"],
    },
    # ===== 金融 / FinTech =====
    {
        "role": "量化开发工程师 (C++/Python)",
        "skills": ["C++/Python", "量化策略", "回测系统", "低延迟", "市场数据", "交易所接口", "性能优化"],
        "description": "负责量化交易系统开发，包括回测框架、实盘交易系统、低延迟行情处理、策略引擎。",
        "salary_range": "30k-65k/月 (应届22k-38k)",
        "tags": ["证券", "金融", "金融科技"],
    },
    {
        "role": "金融科技开发工程师",
        "skills": ["Java/Python", "分布式事务", "风控模型", "支付清算", "银行核心系统", "合规", "安全"],
        "description": "负责银行/支付/保险系统开发，包括核心交易系统、风控引擎、清结算、监管合规。",
        "salary_range": "22k-45k/月 (应届16k-26k)",
        "tags": ["银行", "金融", "金融科技", "支付", "保险"],
    },
    # ===== 游戏 =====
    {
        "role": "游戏客户端开发工程师",
        "skills": ["C++/C#", "Unity/Unreal", "渲染管线", "物理引擎", "游戏逻辑", "性能优化", "跨平台"],
        "description": "负责游戏客户端开发，包括游戏逻辑实现、渲染效果、性能优化、多平台适配。",
        "salary_range": "20k-42k/月 (应届14k-24k)",
        "tags": ["游戏"],
    },
    {
        "role": "游戏服务器开发工程师",
        "skills": ["C++/Go/Java", "网络编程", "分布式架构", "数据库", "消息队列", "并发编程", "帧同步/状态同步"],
        "description": "负责游戏服务端开发，包括网络通信、战斗逻辑、匹配系统、排行榜、高并发优化。",
        "salary_range": "22k-45k/月 (应届15k-26k)",
        "tags": ["游戏"],
    },
    {
        "role": "技术美术 (TA)",
        "skills": ["Shader(GLSL/HLSL)", "Unity/Unreal", "渲染管线", "Python/C++", "3D数学", "特效制作", "性能分析"],
        "description": "负责连接美术与程序，包括Shader开发、渲染效果实现、工具链搭建、资源优化。",
        "salary_range": "22k-48k/月 (应届15k-28k)",
        "tags": ["游戏"],
    },
    # ===== 安全 =====
    {
        "role": "安全研发工程师",
        "skills": ["C/C++/Python", "漏洞挖掘", "逆向分析", "渗透测试", "密码学", "网络协议分析", "安全架构"],
        "description": "负责安全产品开发与攻防研究，包括漏洞挖掘、安全工具开发、威胁检测引擎、安全加固。",
        "salary_range": "22k-48k/月 (应届16k-28k)",
        "tags": ["安全"],
    },
    # ===== 通信 / 网络 =====
    {
        "role": "通信协议开发工程师",
        "skills": ["C/C++", "网络协议(TCP/IP/5G)", "嵌入式Linux", "DSP/FPGA基础", "信号处理", "3GPP标准"],
        "description": "负责通信协议栈开发，包括5G/4G协议实现、物理层算法、基带处理、网络优化。",
        "salary_range": "22k-48k/月 (应届17k-28k)",
        "tags": ["通信", "芯片", "嵌入式"],
    },
    # ===== 大数据 / 数据工程 =====
    {
        "role": "大数据开发工程师",
        "skills": ["Java/Python/Scala", "Spark/Flink", "Hadoop/Hive", "数据仓库", "ETL", "Kafka", "SQL优化"],
        "description": "负责大数据平台开发，包括数据管道建设、实时/离线计算、数据仓库建模、数据治理。",
        "salary_range": "22k-45k/月 (应届16k-26k)",
        "tags": ["互联网", "金融科技", "大数据", "云计算"],
    },
    {
        "role": "数据分析师 (技术方向)",
        "skills": ["Python/SQL", "Pandas/Numpy", "数据可视化", "统计学", "AB测试", "机器学习基础", "业务分析"],
        "description": "负责数据驱动决策，包括业务指标分析、用户画像、AB实验、数据报表、增长策略。",
        "salary_range": "18k-35k/月 (应届12k-20k)",
        "tags": ["互联网", "电商", "金融", "游戏"],
    },
    # ===== 测试 / 质量 =====
    {
        "role": "测试开发工程师 (SDET)",
        "skills": ["Python/Java", "自动化测试(Selenium/Appium)", "CI/CD", "性能测试", "测试框架", "Linux", "Docker"],
        "description": "负责自动化测试框架开发与质量保障，包括接口测试、性能压测、CI/CD流水线集成。",
        "salary_range": "18k-38k/月 (应届13k-23k)",
        "tags": ["互联网", "SaaS", "金融科技"],
    },
    # ===== 产品 / 设计 =====
    {
        "role": "AI产品经理",
        "skills": ["AI/ML基础理解", "产品设计", "数据分析", "用户研究", "PRD撰写", "项目管理", "行业洞察"],
        "description": "负责AI产品的规划与落地，包括需求分析、产品设计、效果评估、跨团队协调。",
        "salary_range": "22k-48k/月 (应届15k-28k)",
        "tags": ["AI", "互联网", "大模型"],
    },
    # ===== 运维 / SRE =====
    {
        "role": "SRE/运维开发工程师",
        "skills": ["Linux", "Kubernetes", "Docker", "Prometheus/Grafana", "CI/CD", "Python/Go", "故障排查"],
        "description": "负责服务稳定性保障，包括监控告警、容量规划、故障响应、自动化运维平台开发。",
        "salary_range": "22k-45k/月 (应届16k-26k)",
        "tags": ["互联网", "云计算", "金融科技", "SaaS"],
    },
    # ===== 硬件 / 电子 =====
    {
        "role": "硬件工程师",
        "skills": ["电路设计", "PCB Layout", "嵌入式C", "FPGA/Verilog", "信号完整性", "电源设计", "EMC"],
        "description": "负责硬件电路设计与调试，包括原理图设计、PCB布局、信号测试、产品认证。",
        "salary_range": "18k-38k/月 (应届13k-22k)",
        "tags": ["消费电子", "IoT", "芯片", "汽车", "制造"],
    },
    # ===== 医药/医疗科技 =====
    {
        "role": "医疗AI算法工程师",
        "skills": ["Python", "PyTorch", "医学图像处理", "CT/MRI分析", "生信分析", "FDA/CE法规", "临床验证"],
        "description": "负责医疗AI算法研发，包括医学影像诊断、病理分析、药物发现、临床试验数据处理。",
        "salary_range": "25k-50k/月 (应届20k-32k)",
        "tags": ["医疗", "AI", "医药"],
    },
    # ===== 物流/供应链 =====
    {
        "role": "物流算法工程师 (运筹优化)",
        "skills": ["Python/C++", "运筹优化", "路径规划", "调度算法", "预测模型", "仿真", "启发式算法"],
        "description": "负责物流智能调度算法，包括路线规划、仓储优化、运力调度、需求预测、网络规划。",
        "salary_range": "22k-45k/月 (应届17k-28k)",
        "tags": ["物流", "互联网", "AI"],
    },
    # ===== 新能源/能源 =====
    {
        "role": "能源管理系统开发工程师",
        "skills": ["C++/Python", "电力系统", "SCADA", "IoT", "储能BMS", "电网调度", "数据采集"],
        "description": "负责能源管理系统(EMS/BMS)开发，包括储能控制、电网调度、光伏/风电监控、碳管理。",
        "salary_range": "20k-42k/月 (应届15k-25k)",
        "tags": ["新能源", "电力", "IoT"],
    },
    # ===== 航天/航空 =====
    {
        "role": "飞控系统开发工程师",
        "skills": ["C/C++", "嵌入式实时系统", "飞控算法", "传感器融合", "导航(GPS/IMU)", "RTOS", "DO-178C"],
        "description": "负责飞行控制与导航系统开发，包括飞控算法、传感器融合、导航解算、冗余设计、适航认证。",
        "salary_range": "25k-50k/月 (应届20k-32k)",
        "tags": ["航天", "航空", "嵌入式"],
    },
    # ===== 教育科技 =====
    {
        "role": "教育AI算法工程师",
        "skills": ["Python", "NLP", "知识图谱", "推荐系统", "自适应学习", "语音评测", "OCR识别"],
        "description": "负责教育AI产品研发，包括智能批改、自适应学习、知识追踪、口语评测、题目推荐。",
        "salary_range": "22k-45k/月 (应届16k-28k)",
        "tags": ["教育", "AI"],
    },
    # ===== 音视频/流媒体 =====
    {
        "role": "音视频开发工程师",
        "skills": ["C/C++", "FFmpeg", "WebRTC", "H.264/H.265", "音频编解码", "实时传输", "硬件加速"],
        "description": "负责音视频引擎开发，包括编解码优化、实时通信、流媒体传输、音效处理、硬件编解码。",
        "salary_range": "25k-50k/月 (应届18k-30k)",
        "tags": ["音视频", "RTC", "互联网"],
    },
    # ===== 电商/零售 =====
    {
        "role": "电商后端开发工程师",
        "skills": ["Java/Go", "秒杀/高并发", "分布式事务", "库存/订单系统", "缓存/消息队列", "搜索(ES)", "支付"],
        "description": "负责电商核心系统开发，包括商品/订单/库存/促销/支付系统的设计与高并发优化。",
        "salary_range": "22k-45k/月 (应届16k-26k)",
        "tags": ["电商", "互联网"],
    },
    # ===== 咨询/审计 =====
    {
        "role": "技术咨询 (Tech Consulting)",
        "skills": ["IT架构", "云服务(AWS/Azure/阿里云)", "数字化转型", "项目管理", "方案设计", "客户沟通"],
        "description": "负责企业数字化转型咨询，包括技术方案设计、架构评估、实施规划、技术尽职调查。",
        "salary_range": "20k-45k/月 (应届14k-24k)",
        "tags": ["咨询", "外资", "SaaS"],
    },
    # ===== 地图/LBS =====
    {
        "role": "地图数据算法工程师",
        "skills": ["C++/Python", "GIS", "高精地图", "点云处理", "道路建模", "SLAM", "数据融合"],
        "description": "负责地图数据生产与算法研发，包括高精地图制作、道路网络建模、POI检索、定位优化。",
        "salary_range": "22k-45k/月 (应届17k-28k)",
        "tags": ["地图", "自动驾驶", "LBS"],
    },
    # ===== 区块链/Web3 =====
    {
        "role": "区块链开发工程师",
        "skills": ["Go/Rust/Solidity", "共识算法", "智能合约", "密码学", "DeFi", "分布式系统", "EVM"],
        "description": "负责区块链底层/应用开发，包括共识机制、智能合约、跨链协议、钱包、DeFi应用。",
        "salary_range": "25k-55k/月 (应届18k-30k)",
        "tags": ["区块链", "金融科技"],
    },
    # ===== 企业服务/SaaS =====
    {
        "role": "SaaS全栈开发工程师",
        "skills": ["TypeScript/Node.js/Python", "React/Vue", "PostgreSQL", "SaaS架构", "多租户", "API设计", "云原生"],
        "description": "负责企业SaaS产品全栈开发，包括多租户架构、权限系统、API开放平台、第三方集成。",
        "salary_range": "20k-42k/月 (应届14k-25k)",
        "tags": ["SaaS", "企业服务", "互联网"],
    },
    # ===== 制造业/IoT =====
    {
        "role": "工业互联网开发工程师",
        "skills": ["C++/Python", "OPC UA/Modbus", "PLC/SCADA", "MQTT", "边缘计算", "数字孪生", "时序数据库"],
        "description": "负责工业互联网平台开发，包括设备接入、数据采集、数字孪生、预测性维护、MES集成。",
        "salary_range": "20k-42k/月 (应届15k-25k)",
        "tags": ["制造", "IoT", "工业自动化"],
    },
    # ===== 消费/快消 =====
    {
        "role": "数据驱动营销工程师",
        "skills": ["Python/SQL", "用户画像", "推荐系统", "AB测试", "增长黑客", "数据可视化", "机器学习"],
        "description": "负责营销技术(MarTech)开发，包括精准营销、用户画像、推荐引擎、LTV预测、归因分析。",
        "salary_range": "20k-40k/月 (应届14k-23k)",
        "tags": ["快消", "电商", "互联网"],
    },
    # ===== 国企 / 央企 =====
    {
        "role": "数字政务/信息化工程师",
        "skills": ["Java/Python", "政务云", "数据库(达梦/人大金仓)", "信创适配", "网络安全", "电子政务", "数据治理"],
        "description": "负责政府/国企信息化系统建设，包括政务平台开发、信创国产化适配、数据共享交换、网络安全合规。",
        "salary_range": "15k-30k/月 (应届10k-18k)",
        "tags": ["国企", "安全", "信创"],
    },
    {
        "role": "国企IT基础设施运维",
        "skills": ["Linux/Windows Server", "虚拟化(VMware/KVM)", "存储(SAN/NAS)", "备份容灾", "网络安全等保", "机房管理"],
        "description": "负责国企数据中心与IT基础设施的运维管理，包括服务器运维、网络管理、等保合规、灾备建设。",
        "salary_range": "12k-25k/月 (应届8k-15k)",
        "tags": ["国企", "电力", "通信", "能源", "交通"],
    },
    # ===== 水利 / 土木 / 工程 =====
    {
        "role": "BIM/CAD开发工程师",
        "skills": ["C++/C#", "AutoCAD/Revit二次开发", "3D图形学", "IFC标准", "点云数据处理", "WebGL/Three.js"],
        "description": "负责建筑/土木工程软件工具开发，包括BIM平台二次开发、CAD插件、三维可视化、模型轻量化。",
        "salary_range": "18k-35k/月 (应届12k-22k)",
        "tags": ["建筑", "制造", "交通"],
    },
    {
        "role": "智慧水利/水务工程师",
        "skills": ["Python/C++", "GIS", "水文模型", "IoT传感器", "SCADA", "数据分析", "水利工程基础"],
        "description": "负责智慧水利系统开发，包括水文监测、洪水预警、水库调度、水质分析、数字孪生流域。",
        "salary_range": "15k-30k/月 (应届10k-18k)",
        "tags": ["水利", "IoT", "环保", "国企"],
    },
    {
        "role": "结构仿真分析工程师",
        "skills": ["ANSYS/Abaqus", "FEA有限元", "Python/Matlab", "结构力学", "材料力学", "CFD基础", "参数化建模"],
        "description": "负责工程结构仿真分析，包括有限元建模、应力分析、疲劳寿命评估、优化设计、仿真自动化脚本开发。",
        "salary_range": "18k-38k/月 (应届12k-22k)",
        "tags": ["制造", "航天", "航空", "汽车", "建筑"],
    },
    # ===== 服务行业 =====
    {
        "role": "酒店/旅游管理系统开发",
        "skills": ["Java/Python", "Spring Boot", "OTA接口(GDS/PMS)", "订单/库存系统", "移动端开发", "支付集成"],
        "description": "负责酒店/旅游管理技术平台开发，包括PMS系统、预订引擎、渠道管理、会员系统、智能定价。",
        "salary_range": "15k-30k/月 (应届10k-18k)",
        "tags": ["旅游", "消费", "互联网"],
    },
    {
        "role": "餐饮/零售数字化运营",
        "skills": ["数据分析(SQL/Python)", "CRM/CDP", "POS系统", "供应链管理", "小程序开发", "BI报表"],
        "description": "负责餐饮/零售行业的数字化系统开发与运营，包括门店管理系统、供应链平台、会员营销、数据分析。",
        "salary_range": "15k-28k/月 (应届9k-16k)",
        "tags": ["餐饮", "零售", "快消"],
    },
    {
        "role": "智慧城市解决方案工程师",
        "skills": ["IoT平台", "大数据/AI", "安防/摄像头", "智能交通", "GIS", "政务云", "项目管理"],
        "description": "负责智慧城市项目方案设计与实施，包括智慧交通、智慧安防、智慧照明、城市大脑等系统的集成与交付。",
        "salary_range": "18k-35k/月 (应届12k-20k)",
        "tags": ["国企", "安防", "IoT", "交通"],
    },
    # ===== 公务员 / 事业单位 =====
    {
        "role": "公务员 (综合管理类)",
        "skills": ["公文写作", "政策分析", "组织协调", "行政管理", "办公软件", "法律法规基础", "沟通表达"],
        "description": "各级政府机关综合管理岗位，负责政策研究、行政管理、公文处理、组织协调等工作。通过国考/省考录用。",
        "salary_range": "8k-20k/月 (视地区和级别)",
        "tags": ["国企"],
    },
    {
        "role": "公务员 (专业技术类-信息技术)",
        "skills": ["Java/Python", "网络安全", "数据库管理", "政务信息化", "等保合规", "项目管理", "政府采购"],
        "description": "政府机关信息技术岗位，负责政务系统开发运维、网络安全保障、信息化建设规划、数据资源管理。",
        "salary_range": "10k-22k/月 (视地区和级别)",
        "tags": ["国企", "安全", "信创"],
    },
    {
        "role": "选调生",
        "skills": ["公文写作", "组织协调", "政策理解", "基层工作经验", "党员优先", "学生干部经历", "政治素养"],
        "description": "党政机关定向选拔的优秀应届毕业生，先在基层锻炼2-3年，后调回省市机关。分中央选调、定向选调、普通选调。",
        "salary_range": "8k-18k/月 (视地区和级别)",
        "tags": ["国企"],
    },
    {
        "role": "事业单位专业技术岗",
        "skills": ["专业技术能力", "科研论文", "项目管理", "行业资格证", "学历(硕士及以上优先)", "课题经验"],
        "description": "科研院所、高校、医院、文化机构等的专业技术岗位，包括科研助理、实验员、工程师、讲师等。",
        "salary_range": "10k-25k/月 (视单位和地区)",
        "tags": ["国企", "科研"],
    },
    {
        "role": "军队文职人员",
        "skills": ["专业技术", "政治素质", "纪律意识", "学历", "专业对口", "身体素质"],
        "description": "军队文职岗位，在部队从事技术、医疗、教学、科研等非直接作战工作。待遇参照现役军官，享受军队福利。",
        "salary_range": "10k-25k/月 (视地区和级别)",
        "tags": ["国企", "航天", "通信"],
    },
    # ===== 工科：机械 / 电气 / 化工 / 材料 =====
    {
        "role": "机械设计工程师",
        "skills": ["SolidWorks/CATIA/UG", "机械制图", "公差配合", "材料力学", "GD&T", "DFM", "Pro/E"],
        "description": "负责机械设备/零部件的结构设计与开发，包括3D建模、工程图纸、BOM管理、DFM评审。",
        "salary_range": "12k-30k/月 (应届8k-16k)",
        "tags": ["制造", "汽车", "工程机械", "航空航天"],
    },
    {
        "role": "电气/自动化工程师",
        "skills": ["PLC编程(Siemens/Mitsubishi)", "电气CAD", "变频器/伺服", "SCADA", "传感器", "配电设计"],
        "description": "负责电气控制系统设计与调试，包括PLC编程、电气图纸设计、现场调试、自动化产线集成。",
        "salary_range": "12k-28k/月 (应届8k-15k)",
        "tags": ["制造", "新能源", "汽车", "工业自动化"],
    },
    {
        "role": "化工工艺工程师",
        "skills": ["化工原理", "Aspen Plus/HYSYS", "工艺设计", "PID图", "HAZOP分析", "安全生产", "质量管理"],
        "description": "负责化工生产工艺设计与优化，包括工艺流程模拟、设备选型、安全评估、工艺包开发。",
        "salary_range": "12k-28k/月 (应届8k-15k)",
        "tags": ["制造", "能源", "医药", "环保"],
    },
    {
        "role": "材料研发工程师",
        "skills": ["材料科学基础", "SEM/XRD/DSC表征", "材料配方", "力学/热学测试", "工艺开发", "文献调研"],
        "description": "负责新材料研发与应用，包括配方开发、性能测试、微观结构分析、量产工艺验证。",
        "salary_range": "15k-35k/月 (应届10k-20k)",
        "tags": ["制造", "半导体", "汽车", "新能源", "航天"],
    },
    {
        "role": "环境工程师",
        "skills": ["水处理/废气处理工艺", "环评", "在线监测(CEMS/CEMS)", "固废管理", "环保法规", "AutoCAD"],
        "description": "负责环保工程设计与运营，包括废水/废气/固废处理方案、环评报告、监测系统、达标排放。",
        "salary_range": "10k-25k/月 (应届7k-14k)",
        "tags": ["环保", "制造", "能源"],
    },
    # ===== 理科：数学 / 物理 / 化学 / 生物 =====
    {
        "role": "数据分析师 (各行业通用)",
        "skills": ["SQL/Python/R", "Excel/Tableau/Power BI", "统计学", "数据清洗", "可视化", "业务理解", "报告撰写"],
        "description": "负责企业的数据分析和决策支持，包括业务指标监控、用户分析、市场调研、数据报表和Dashboard搭建。",
        "salary_range": "12k-28k/月 (应届8k-16k)",
        "tags": ["互联网", "金融", "电商", "咨询", "快消", "医药"],
    },
    {
        "role": "生物医药研发工程师",
        "skills": ["分子生物学/细胞生物学", "PCR/Western Blot", "动物实验", "GMP/GCP规范", "文献检索", "实验设计"],
        "description": "负责生物医药产品研发，包括药物筛选、药效评价、细胞实验、临床前研究、注册申报。",
        "salary_range": "15k-35k/月 (应届10k-18k)",
        "tags": ["医药", "生物"],
    },
    {
        "role": "质量管理工程师 (QA/QC)",
        "skills": ["ISO9001/GMP", "SPC/MSA/FMEA", "QC七大手法", "6Sigma", "CAPA", "供应商管理", "内审员资格"],
        "description": "负责产品质量管理和质量体系建设，包括过程控制、不合格分析、供应商审核、客户投诉处理、体系认证。",
        "salary_range": "10k-25k/月 (应届7k-14k)",
        "tags": ["制造", "汽车", "医药", "消费电子", "食品"],
    },
    # ===== 文科：经济 / 法律 / 传媒 / 教育 / 外语 =====
    {
        "role": "市场/品牌营销专员",
        "skills": ["市场调研", "品牌策划", "新媒体运营", "内容创作", "数据分析(Excel)", "活动策划", "文案能力"],
        "description": "负责品牌营销与推广，包括市场调研、内容策划、社交媒体运营、KOL合作、营销活动执行与效果评估。",
        "salary_range": "10k-25k/月 (应届7k-14k)",
        "tags": ["互联网", "快消", "电商", "零售", "媒体"],
    },
    {
        "role": "法务/合规专员",
        "skills": ["法律专业知识(民商法/经济法)", "合同审核", "法律文书", "合规管理", "风险管理", "法律检索", "通过法考优先"],
        "description": "负责企业法律事务与合规管理，包括合同起草审核、法律咨询、知识产权保护、合规体系搭建、诉讼仲裁支持。",
        "salary_range": "12k-30k/月 (应届8k-16k)",
        "tags": ["互联网", "金融", "国企", "咨询", "医药"],
    },
    {
        "role": "人力资源专员 (HR)",
        "skills": ["招聘/培训/绩效", "劳动法", "HR系统", "沟通协调", "数据分析", "组织发展(OD)", "员工关系"],
        "description": "负责人力资源管理各模块工作，包括招聘配置、培训发展、绩效薪酬、员工关系、企业文化。",
        "salary_range": "10k-22k/月 (应届7k-13k)",
        "tags": ["互联网", "金融", "制造", "国企", "快消"],
    },
    {
        "role": "新媒体运营/内容编辑",
        "skills": ["文案写作", "视频剪辑(PR/剪映)", "社交媒体运营", "热点追踪", "数据分析", "SEO/SEM", "审美能力"],
        "description": "负责新媒体平台的内容创作与运营，包括选题策划、图文/短视频制作、粉丝互动、数据复盘、商业化变现。",
        "salary_range": "10k-22k/月 (应届7k-13k)",
        "tags": ["互联网", "媒体", "教育", "游戏", "电商"],
    },
    {
        "role": "翻译/语言服务",
        "skills": ["外语能力(专八/雅思7+)", "CAT工具(Trados/MemoQ)", "专业领域翻译", "口译能力", "跨文化沟通", "本地化"],
        "description": "负责多语言翻译与本地化工作，包括笔译、口译、本地化项目管理、术语库维护、国际化内容审核。",
        "salary_range": "10k-25k/月 (应届7k-14k)",
        "tags": ["外资", "互联网", "游戏", "媒体", "咨询"],
    },
    {
        "role": "用户研究/UX研究员",
        "skills": ["用户访谈", "可用性测试", "问卷设计", "数据分析(SPSS/Python)", "Persona/用户旅程", "社会学/心理学背景"],
        "description": "负责用户研究和体验洞察，包括深度访谈、可用性测试、竞品分析、用户画像构建，为产品设计提供依据。",
        "salary_range": "15k-32k/月 (应届10k-18k)",
        "tags": ["互联网", "消费电子", "游戏"],
    },
    # ===== 财经类 =====
    {
        "role": "会计/审计",
        "skills": ["会计准则(中国/国际)", "税务法规", "财务软件(用友/金蝶/SAP)", "Excel", "审计程序", "CPA/ACCA优先"],
        "description": "负责企业财务核算或审计，包括账务处理、报表编制、税务申报、内控审计、财务分析。",
        "salary_range": "10k-25k/月 (应届7k-14k)",
        "tags": ["国企", "金融", "审计", "咨询", "制造"],
    },
    {
        "role": "供应链/采购管理",
        "skills": ["供应链管理", "ERP系统(SAP/Oracle)", "供应商谈判", "库存管理", "物流规划", "成本分析", "国际贸易基础"],
        "description": "负责供应链与采购管理，包括供应商开发与管理、采购策略制定、库存优化、物流成本控制。",
        "salary_range": "12k-28k/月 (应届8k-15k)",
        "tags": ["制造", "电商", "物流", "零售", "汽车"],
    },
    # ===== 艺术/设计类 =====
    {
        "role": "UI/UX设计师",
        "skills": ["Figma/Sketch", "用户体验设计", "交互设计", "用户研究", "设计系统", "动效设计", "设计规范"],
        "description": "负责产品界面与用户体验设计，包括交互原型、视觉界面、设计规范、用户测试、设计系统维护。",
        "salary_range": "15k-35k/月 (应届10k-18k)",
        "tags": ["互联网", "游戏", "消费电子"],
    },
    {
        "role": "视觉传达/平面设计师",
        "skills": ["Photoshop/Illustrator/InDesign", "版式设计", "色彩理论", "品牌VI", "印刷工艺", "插画/C4D加分"],
        "description": "负责品牌视觉设计与平面物料创作，包括LOGO/VI设计、海报、画册、包装、活动视觉。",
        "salary_range": "10k-25k/月 (应届7k-14k)",
        "tags": ["媒体", "快消", "电商", "游戏", "零售"],
    },
    # ===== 农/林/地质 =====
    {
        "role": "智慧农业/农技工程师",
        "skills": ["作物学/园艺学", "植保/土肥", "物联网/IoT传感器", "数据分析", "GIS/遥感", "无人机操作"],
        "description": "负责智慧农业技术应用与推广，包括精准种植、病虫害监测、水肥一体化、农业大数据分析。",
        "salary_range": "10k-22k/月 (应届7k-13k)",
        "tags": ["农业", "IoT", "无人机"],
    },
    {
        "role": "地质/矿业工程师",
        "skills": ["地质勘查", "采矿工程", "GIS/MapGIS", "岩土力学", "安全规程", "储量估算", "CAD"],
        "description": "负责地质勘查或矿山开发设计，包括矿床评价、钻探设计、储量计算、采矿方法选择、安全评估。",
        "salary_range": "10k-25k/月 (应届7k-14k)",
        "tags": ["制造", "能源", "国企"],
    },
    # ===== 医学/护理 =====
    {
        "role": "临床研究专员 (CRA)",
        "skills": ["GCP规范", "临床试验流程", "医学知识", "数据管理(EDC)", "法规(CFDA/FDA)", "沟通协调", "医药背景"],
        "description": "负责临床试验的监查与管理，包括研究中心筛选、启动访视、数据核查、AE/SAE报告、稽查准备。",
        "salary_range": "12k-30k/月 (应届8k-16k)",
        "tags": ["医药", "医疗"],
    },
    # ===== 教育/培训 =====
    {
        "role": "教师/培训师",
        "skills": ["学科专业知识", "教学方法论", "课程设计", "课堂管理", "教育心理学", "教师资格证", "语言表达"],
        "description": "负责中小学/高校/培训机构的教学工作，包括课程讲授、教案编写、学生评估、教研活动。",
        "salary_range": "8k-22k/月 (视学校和地区)",
        "tags": ["教育", "国企"],
    },
]

# Map positions to company tags for matching
def _match_positions_to_companies(resume_skills: str, analysis_result: dict) -> list:
    """Pre-select relevant positions based on resume analysis, for the AI to refine."""
    # This is used to pre-filter positions; the AI does the final matching
    return POSITIONS  # Return all — AI handles the matching


JOB_RECOMMEND_PROMPT = """你是一个职业规划专家兼招聘顾问。根据求职者的简历（技能、学历、经验），做以下分析：

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 分析任务：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. recommended_positions: 从下面的「可选岗位列表」中，选出 5-8 个最适合该求职者的具体岗位，按匹配度排序。每个岗位包含：
   - role: 岗位名称 (必须从岗位列表中选择)
   - match_score: 岗位匹配度 0-100 (基于技能重叠度、经验匹配度、学历匹配度)
   - matching_skills: 求职者已有且匹配的技能 (从中选择，不要编造)
   - missing_skills: 该岗位要求但求职者缺失的关键技能 (列2-4个最重要的)
   - fit_assessment: 简短评估 (1-2句话，说明为什么适合，需要补什么)

2. target_companies: 从下面的「可选公司列表」中，为每个推荐岗位匹配 2-3 家最合适的公司，组合成一个列表（共12-18条）。每条包含：
   - company_name: 公司名 (只能从公司列表中选择)
   - role: 对应的岗位
   - position_match: 该公司该岗位的匹配度 0-100
   - reason: 为什么这家公司适合 (1句话，结合公司业务方向)
   - priority: 推荐优先级 (high/medium)

3. career_advice: 针对求职者当前阶段，给出 3-4 条具体的职业发展建议（学习路线、项目方向、投递策略）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 返回JSON格式：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "recommended_positions": [
    {
      "role": "",
      "match_score": 0,
      "matching_skills": [...],
      "missing_skills": [...],
      "fit_assessment": ""
    }
  ],
  "target_companies": [
    {
      "company_name": "",
      "role": "",
      "position_match": 0,
      "reason": "",
      "priority": ""
    }
  ],
  "career_advice": [...]
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 重要规则：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- recommended_positions 中的 role 必须从可选岗位列表中选择，不要编造
- target_companies 中的 company_name 必须从可选公司列表中选择，不要编造
- 匹配度打分要诚实，不要虚高。一般应届生的岗位匹配度在40-75之间
- matching_skills 只能列求职者简历中真实存在的技能

=== 可选岗位列表 ===
{positions}

=== 可选公司列表 ===
{companies}

只返回JSON，不要任何其他文字。"""


def recommend_jobs(resume_text: str, education_analysis: dict | None = None) -> dict:
    """Based on resume and education analysis, recommend job directions and target companies."""
    if len(resume_text) > 8000:
        resume_text = resume_text[:8000]

    # Build company list
    company_list = "\n".join(
        f"- {c['name']}: {c['url']} ({', '.join(c['tags'])})"
        for c in COMPANY_CAREERS
    )

    # Build position list
    position_list = "\n".join(
        f"- [{', '.join(p['tags'])}] {p['role']}: 需掌握 {', '.join(p['skills'][:5])}... | {p['salary_range']}"
        for p in POSITIONS
    )

    prompt = JOB_RECOMMEND_PROMPT.replace("{companies}", company_list)
    prompt = prompt.replace("{positions}", position_list)

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
            name = tc.get("company_name", tc.get("name", ""))
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

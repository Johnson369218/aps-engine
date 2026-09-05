# -*- coding: utf-8 -*-
"""行业适配矩阵：制造业 31 个大类（GB/T 4754-2017 门类 C）→ 标准功能。

用途：新用户用一段话描述自己的工厂（设备/产品/工艺），`match_industry()` 识别大类，
`recommend()` 给出「直接用哪套标准功能 + 复制哪个模板 + 填什么」，回答"APS 适合我吗"。

字段：
- type: discrete(离散) / mixed(混合) / process(纯流程)
- fit: high(直接可用) / mid(需扩展约束) / low(需另建模型)
- engine: solve(单工序) / solve_jssp(多工序) / custom(另建)
- channel: 设备直连通道（modbus / dnc / job_ticket / rest）
- setup: 换型/约束重点（该行业的排产质量关键）
- params: 标准工艺参数字段（写进 products.process_params / 设备寄存器）
- example: 即插即用模板目录（None=暂无，按三张表模板自建）
"""
from collections import Counter

INDUSTRIES = [
    {"code": "C13", "name": "农副食品加工", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "modbus/job_ticket", "setup": "换品种清洗/换线",
     "params": ["qty", "temperature"], "keywords": ["食品", "农副", "粮油", "屠宰", "冷鲜", "冻品"]},
    {"code": "C14", "name": "食品制造", "type": "mixed", "fit": "high",
     "engine": "solve", "channel": "modbus/job_ticket", "setup": "换型/批次/保质期",
     "params": ["qty", "temperature", "speed"], "keywords": ["食品", "糕点", "饼干", "糖果", "调味", "面包"]},
    {"code": "C15", "name": "酒饮料精制茶", "type": "mixed", "fit": "mid",
     "engine": "solve", "channel": "modbus", "setup": "换规格/清洗CIP",
     "params": ["qty", "temperature"], "keywords": ["饮料", "酒", "啤酒", "矿泉水", "茶", "灌装"]},
    {"code": "C16", "name": "烟草制品", "type": "process", "fit": "low",
     "engine": "custom", "channel": "-", "setup": "连续流程",
     "params": [], "keywords": ["烟草", "卷烟"]},
    {"code": "C17", "name": "纺织业", "type": "mixed", "fit": "high",
     "engine": "solve", "channel": "modbus", "setup": "换纱/换色/换织法",
     "params": ["qty", "speed"], "keywords": ["纺织", "纺纱", "织布", "面料", "纱线", "印染"]},
    {"code": "C18", "name": "纺织服装服饰", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "job_ticket/modbus", "setup": "换款/换线",
     "params": ["qty"], "keywords": ["服装", "成衣", "缝纫", "服饰", "制衣", "衬衫"]},
    {"code": "C19", "name": "皮革毛皮制鞋", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "job_ticket", "setup": "换款/换楦",
     "params": ["qty"], "keywords": ["皮革", "制鞋", "箱包", "鞋", "皮具", "毛皮"]},
    {"code": "C20", "name": "木材加工", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "modbus", "setup": "换材/换刀",
     "params": ["qty", "speed"], "keywords": ["木材", "板材", "胶合板", "锯材", "木方", "地板", "木地板", "木线条", "指接板", "生态板"]},
    {"code": "C21", "name": "家具制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "modbus/job_ticket", "setup": "开料/封边/打孔换型",
     "params": ["qty", "speed"], "keywords": ["家具", "办公桌", "衣柜", "橱柜", "板式", "开料", "封边", "打孔", "组装",
        "木门", "门", "床", "沙发", "椅子", "餐桌", "书架", "书桌", "茶几", "定制家具", "全屋定制"]},
    {"code": "C22", "name": "造纸和纸制品", "type": "process", "fit": "mid",
     "engine": "solve", "channel": "modbus", "setup": "换纸种/换定量",
     "params": ["qty", "speed", "temperature"], "keywords": ["造纸", "纸箱", "纸板", "瓦楞", "卫生纸"]},
    {"code": "C23", "name": "印刷和记录媒介复制", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "modbus/dnc", "setup": "换版/换油墨/换材质",
     "params": ["qty", "speed", "temperature", "tension"], "example": "examples/printing_sme",
     "keywords": ["印刷", "柔印", "凹印", "胶印", "无纺布", "卷膜", "包装印刷", "标签", "制袋", "分切",
        "包装盒", "纸袋", "纸盒", "说明书", "名片", "不干胶", "手提袋", "彩盒"]},
    {"code": "C24", "name": "文教工美体育娱乐用品", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "job_ticket", "setup": "换款",
     "params": ["qty"], "keywords": ["文具", "玩具", "体育用品", "乐器", "工艺美术"]},
    {"code": "C25", "name": "石油煤炭及其他燃料加工", "type": "process", "fit": "low",
     "engine": "custom", "channel": "-", "setup": "连续流程",
     "params": [], "keywords": ["炼油", "石油", "煤炭", "燃料"]},
    {"code": "C26", "name": "化学原料和化学制品", "type": "process", "fit": "low",
     "engine": "custom", "channel": "-", "setup": "连续流程/批反应",
     "params": [], "keywords": ["化工", "化学", "树脂", "涂料", "颜料", "化肥"]},
    {"code": "C27", "name": "医药制造", "type": "mixed", "fit": "high",
     "engine": "solve", "channel": "modbus", "setup": "批号/清洗/换规格",
     "params": ["qty", "temperature"], "keywords": ["医药", "制药", "制剂", "药瓶", "胶囊", "片剂", "原料药"]},
    {"code": "C28", "name": "化学纤维", "type": "process", "fit": "mid",
     "engine": "solve", "channel": "modbus", "setup": "换品种/换规格",
     "params": ["qty", "speed"], "keywords": ["化纤", "涤纶", "锦纶", "氨纶", "纤维"]},
    {"code": "C29", "name": "橡胶和塑料制品", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "modbus", "setup": "换模具/换色",
     "params": ["qty", "pressure", "temperature", "cycle"], "example": "examples/plastic_injection",
     "keywords": ["塑料", "注塑", "橡胶", "手机壳", "药瓶", "吹瓶", "瓶盖", "挤出", "模具",
        "塑料瓶", "水桶", "脸盆", "衣架", "饭盒", "垃圾桶", "塑料杯", "管材", "片材"]},
    {"code": "C30", "name": "非金属矿物制品", "type": "mixed", "fit": "mid",
     "engine": "solve", "channel": "modbus", "setup": "换规格/花色/窑炉",
     "params": ["qty", "temperature", "pressure"], "keywords": ["瓷砖", "玻璃", "水泥", "陶瓷", "耐火", "石材",
        "马桶", "卫浴", "洁具", "琉璃", "玻化砖", "釉面砖", "地砖", "墙砖", "玻璃瓶", "陶瓷杯"]},
    {"code": "C31", "name": "黑色金属冶炼压延", "type": "process", "fit": "low",
     "engine": "custom", "channel": "-", "setup": "长流程/炉次",
     "params": [], "keywords": ["炼钢", "钢铁", "轧钢", "铸造生铁"]},
    {"code": "C32", "name": "有色金属冶炼压延", "type": "process", "fit": "low",
     "engine": "custom", "channel": "-", "setup": "长流程/炉次",
     "params": [], "keywords": ["有色", "铝", "铜", "锌", "电解", "冶炼"]},
    {"code": "C33", "name": "金属制品", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "modbus/dnc", "setup": "换型/换刀",
     "params": ["qty", "speed", "feed"], "keywords": ["金属制品", "五金", "冲压", "钣金", "标准件", "紧固件", "门窗",
        "不锈钢", "烧水壶", "水壶", "锅", "厨具", "餐具", "保温杯", "水杯", "锁", "拉手", "刀", "剪", "日用金属", "厨房"]},
    {"code": "C34", "name": "通用设备制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序/换刀",
     "params": ["qty", "speed", "feed"], "keywords": ["通用设备", "机床", "泵", "阀门", "风机", "减速机"]},
    {"code": "C35", "name": "专用设备制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序/换刀",
     "params": ["qty", "speed", "feed"], "keywords": ["专用设备", "印刷机", "包装机", "模具", "医疗器械", "工程机械"]},
    {"code": "C36", "name": "汽车制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc/modbus", "setup": "多工序/换型",
     "params": ["qty", "speed"], "keywords": ["汽车", "整车", "零部件", "发动机", "变速箱", "车身"]},
    {"code": "C37", "name": "运输设备制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序",
     "params": ["qty"], "keywords": ["铁路", "船舶", "航空航天", "无人机", "轨道"]},
    {"code": "C38", "name": "电气机械和器材", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序/换型",
     "params": ["qty", "speed"], "keywords": ["电气", "电机", "变压器", "电缆", "开关", "家电",
        "电水壶", "小家电", "电饭煲", "风扇", "灯具", "热水器", "电磁炉", "电暖器"]},
    {"code": "C39", "name": "计算机通信电子", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序/SMT换线",
     "params": ["qty", "speed"], "keywords": ["电子", "手机", "电路板", "PCB", "SMT", "芯片封装", "元件", "显示器"]},
    {"code": "C40", "name": "仪器仪表制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序",
     "params": ["qty"], "keywords": ["仪器", "仪表", "传感器", "测量", "光学"]},
    {"code": "C41", "name": "其他制造", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "job_ticket", "setup": "换款",
     "params": ["qty"], "keywords": ["日用杂品", "雨伞", "眼镜", "饰品", "工艺品"]},
    {"code": "C42", "name": "废弃资源综合利用", "type": "mixed", "fit": "mid",
     "engine": "solve", "channel": "modbus", "setup": "换料/换品种",
     "params": ["qty"], "keywords": ["再生", "回收", "废料", "拆解", "资源化"]},
    {"code": "C43", "name": "金属制品机械和设备修理", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "job_ticket", "setup": "换活/派工",
     "params": ["qty"], "keywords": ["修理", "维修", "翻新", "再制造"]},
]


_FIT_LABEL = {"high": "强适配（直接可用）", "mid": "中适配（需扩展约束）", "low": "弱适配（需另建模型）"}
_ENGINE_LABEL = {"solve": "solve() 单工序+换型", "solve_jssp": "solve_jssp() 多工序+前序", "custom": "另建流程模型"}


def match_industry(text, top=3):
    """按关键词识别行业大类。text 为用户对工厂的描述。返回匹配（按命中数排序）。"""
    scored = []
    for ind in INDUSTRIES:
        hits = sum(1 for kw in ind["keywords"] if kw in text)
        if hits:
            scored.append((hits, ind))
    scored.sort(key=lambda x: -x[0])
    return [ind for _, ind in scored[:top]]


def recommend(ind):
    """把一个大类条目转成面向用户的「标准功能」推荐。"""
    return {
        "行业": f"{ind['code']} {ind['name']}",
        "生产类型": ind["type"],
        "适配度": _FIT_LABEL[ind["fit"]],
        "引擎": _ENGINE_LABEL[ind["engine"]],
        "设备通道": ind["channel"],
        "换型/约束重点": ind["setup"],
        "标准工艺参数": ind["params"],
        "模板": ind.get("example") or "按三张表模板自建（lines/products/orders + data/machines.example.json）",
        "落地": "复制模板填数据 → schedule_cli 排产 → machines.json 填寄存器地址表 → machine_push(dry-run→confirm)",
    }


def fit_summary():
    """适配度统计：31 大类里 high/mid/low 各多少。"""
    c = Counter(i["fit"] for i in INDUSTRIES)
    return {"total": len(INDUSTRIES), "high": c["high"], "mid": c["mid"], "low": c["low"]}

# -*- coding: utf-8 -*-
"""行业适配矩阵：一般制造业（GB/T 4754-2017 门类 C，重工业/矿业除外）→ 标准功能。

用途：新用户用一句话/照片/语音描述自己的工厂（设备/产品/工艺），`match_industry()` 识别大类，
`recommend()` 给出「直接用哪套标准功能 + 复制哪个模板 + 填什么」，回答"APS 适合我吗"。

范围：仅一般制造业（离散/轻工/混合制造）。重工业（石油煤炭 C25 / 化学原料 C26 /
黑色冶金 C31 / 有色冶金 C32 / 烟草 C16）与矿业（门类 B）不在本适配矩阵内——它们属
连续流程/长流程，需另建模型，标 fit=low / engine=custom。

字段：
- type: discrete(离散) / mixed(混合) / process(纯流程)
- fit: high(直接可用) / mid(需扩展约束) / low(需另建模型，重工业)
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
     "params": ["qty", "temperature"],
     "keywords": ["食品", "农副", "粮油", "屠宰", "冷鲜", "冻品", "水产", "饲料", "果蔬", "榨油", "面粉", "大米", "肉制品", "分割肉", "净菜"]},
    {"code": "C14", "name": "食品制造", "type": "mixed", "fit": "high",
     "engine": "solve", "channel": "modbus/job_ticket", "setup": "换型/批次/保质期",
     "params": ["qty", "temperature", "speed"],
     "keywords": ["食品", "糕点", "饼干", "糖果", "调味", "面包", "乳品", "速冻", "罐头", "蜜饯", "膨化", "坚果", "烘焙", "酱油", "醋", "火锅底料", "月饼", "方便面"]},
    {"code": "C15", "name": "酒饮料精制茶", "type": "mixed", "fit": "mid",
     "engine": "solve", "channel": "modbus", "setup": "换规格/清洗CIP",
     "params": ["qty", "temperature"],
     "keywords": ["饮料", "酒", "啤酒", "矿泉水", "茶", "灌装", "果汁", "乳饮", "碳酸", "白酒", "红酒", "瓶装水", "苏打水", "酸奶"]},
    {"code": "C16", "name": "烟草制品", "type": "process", "fit": "low",
     "engine": "custom", "channel": "-", "setup": "连续流程",
     "params": [], "keywords": ["烟草", "卷烟"]},
    {"code": "C17", "name": "纺织业", "type": "mixed", "fit": "high",
     "engine": "solve", "channel": "modbus", "setup": "换纱/换色/换织法",
     "params": ["qty", "speed"],
     "keywords": ["纺织", "纺纱", "织布", "面料", "纱线", "印染", "毛巾", "床品", "针织", "毛纺", "窗帘", "地毯", "无纺", "印花布", "坯布"]},
    {"code": "C18", "name": "纺织服装服饰", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "job_ticket/modbus", "setup": "换款/换线",
     "params": ["qty"],
     "keywords": ["服装", "成衣", "缝纫", "服饰", "制衣", "衬衫", "针织衫", "羽绒服", "童装", "牛仔裤", "内衣", "西装", "裙子", "T恤", "卫衣"]},
    {"code": "C19", "name": "皮革毛皮制鞋", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "job_ticket", "setup": "换款/换楦",
     "params": ["qty"],
     "keywords": ["皮革", "制鞋", "箱包", "鞋", "皮具", "毛皮", "皮鞋", "运动鞋", "鞋底", "手袋", "钱包", "沙发革", "腰带", "皮衣"]},
    {"code": "C20", "name": "木材加工", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "modbus", "setup": "换材/换刀",
     "params": ["qty", "speed"],
     "keywords": ["木材", "板材", "胶合板", "锯材", "木方", "地板", "木地板", "木线条", "指接板", "生态板", "木皮", "刨花板", "密度板"]},
    {"code": "C21", "name": "家具制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "modbus/job_ticket", "setup": "开料/封边/打孔换型",
     "params": ["qty", "speed"],
     "keywords": ["家具", "办公桌", "衣柜", "橱柜", "板式", "开料", "封边", "打孔", "组装",
                  "木门", "门", "床", "沙发", "椅子", "餐桌", "书架", "书桌", "茶几", "定制家具", "全屋定制", "床头柜", "鞋柜"]},
    {"code": "C22", "name": "造纸和纸制品", "type": "process", "fit": "mid",
     "engine": "solve", "channel": "modbus", "setup": "换纸种/换定量",
     "params": ["qty", "speed", "temperature"],
     "keywords": ["造纸", "纸箱", "纸板", "瓦楞", "卫生纸", "纸盒", "纸浆", "餐巾纸", "卡纸", "铜版纸", "包装纸", "纸杯", "纸袋"]},
    {"code": "C23", "name": "印刷和记录媒介复制", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "modbus/dnc", "setup": "换版/换油墨/换材质",
     "params": ["qty", "speed", "temperature", "tension"], "example": "examples/printing_sme",
     "keywords": ["印刷", "柔印", "凹印", "胶印", "无纺布", "卷膜", "包装印刷", "标签", "制袋", "分切",
                  "包装盒", "纸袋", "纸盒", "说明书", "名片", "不干胶", "手提袋", "彩盒", "书刊", "海报"]},
    {"code": "C24", "name": "文教工美体育娱乐用品", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "job_ticket", "setup": "换款",
     "params": ["qty"],
     "keywords": ["文具", "玩具", "体育用品", "乐器", "工艺美术", "办公用品", "笔", "书包", "健身器材", "风筝", "手办", "教具", "乒乓球", "羽毛球", "积木"]},
    {"code": "C25", "name": "石油煤炭及其他燃料加工", "type": "process", "fit": "low",
     "engine": "custom", "channel": "-", "setup": "连续流程",
     "params": [], "keywords": ["炼油", "石油", "煤炭", "燃料"]},
    {"code": "C26", "name": "化学原料和化学制品", "type": "process", "fit": "low",
     "engine": "custom", "channel": "-", "setup": "连续流程/批反应",
     "params": [], "keywords": ["化工", "化学", "树脂", "涂料", "颜料", "化肥"]},
    {"code": "C27", "name": "医药制造", "type": "mixed", "fit": "high",
     "engine": "solve", "channel": "modbus", "setup": "批号/清洗/换规格",
     "params": ["qty", "temperature"],
     "keywords": ["医药", "制药", "制剂", "胶囊", "片剂", "原料药", "中药", "保健", "疫苗", "注射剂", "药盒", "药品"],
     "segments": [
        {"name": "制剂（片剂/胶囊/口服液）", "keywords": ["片剂", "胶囊", "口服液", "颗粒剂", "制剂", "丸剂", "糖浆"],
         "process": "制剂工艺(混合/压片/包衣/灌装)", "params": ["qty", "temperature"],
         "constraints": ["GMP", "批号/留样", "含量/溶出/无菌"]},
        {"name": "原料药(API)", "keywords": ["原料药", "API", "中间体"],
         "process": "化学/生物合成 + 精制", "params": [],
         "constraints": ["GMP 批记录", "纯度/杂质"]},
        {"name": "药包材（药瓶/铝箔/说明书）", "keywords": ["药瓶", "药包材", "药用铝箔", "说明书", "药用瓶", "泡罩"],
         "process": "包材生产(洁净)", "params": [],
         "constraints": ["药包材注册", "洁净车间", "溶出物/迁移"]},
     ]},
    {"code": "C28", "name": "化学纤维", "type": "process", "fit": "mid",
     "engine": "solve", "channel": "modbus", "setup": "换品种/换规格",
     "params": ["qty", "speed"],
     "keywords": ["化纤", "涤纶", "锦纶", "氨纶", "纤维", "长丝", "短纤"]},
    {"code": "C29", "name": "橡胶和塑料制品", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "modbus", "setup": "换模具/换色",
     "params": ["qty", "pressure", "temperature", "cycle"], "example": "examples/plastic_injection",
     "keywords": ["塑料", "注塑", "橡胶", "吹瓶", "挤出", "模具", "塑料件", "橡塑", "注塑件"],
     "segments": [
        {"name": "普通注塑件（消费电子/日用）", "keywords": ["手机壳", "手机保护壳", "电子外壳", "充电器壳", "日用塑料件", "外壳件", "按键", "注塑壳"],
         "process": "注塑成型 + 表面处理(喷涂/UV)", "params": ["pressure", "temperature", "cycle"],
         "constraints": ["外观/尺寸/装配", "普通消费品标准(GB/T)"]},
        {"name": "药包材·药瓶（直接接触药品）", "keywords": ["药剂瓶", "药瓶", "药用瓶", "药包材", "口服液瓶", "输液瓶", "滴眼剂瓶", "药用瓶盖", "药用铝箔"],
         "process": "注吹/吹塑（洁净车间）", "params": ["pressure", "temperature", "cycle"],
         "constraints": ["药包材注册证/关联审评", "GMP 洁净车间", "批号/留样/稳定性", "溶出物/迁移试验", "微生物限度", "清洗验证", "YBB 药包材标准"]},
        {"name": "中空吹塑容器（饮料/日化瓶）", "keywords": ["饮料瓶", "矿泉水瓶", "日化瓶", "中空容器", "吹塑瓶", "桶"],
         "process": "挤吹/注吹", "params": ["pressure", "temperature"],
         "constraints": ["容量/密封/跌落"]},
        {"name": "管材/型材挤出", "keywords": ["管材", "型材", "PVC管", "PPR管", "线槽", "挤出件"],
         "process": "挤出成型", "params": ["temperature", "speed"],
         "constraints": ["尺寸/壁厚/压力等级"]},
     ]},
    {"code": "C30", "name": "非金属矿物制品", "type": "mixed", "fit": "mid",
     "engine": "solve", "channel": "modbus", "setup": "换规格/花色/窑炉",
     "params": ["qty", "temperature", "pressure"],
     "keywords": ["瓷砖", "玻璃", "水泥", "陶瓷", "耐火", "石材", "琉璃", "玻化砖", "釉面砖", "大理石", "人造石"],
     "segments": [
        {"name": "建筑陶瓷（瓷砖）", "keywords": ["瓷砖", "地砖", "墙砖", "抛光砖", "通体砖", "内墙砖"],
         "process": "压机成型+烧成+抛光", "params": ["temperature", "pressure"],
         "constraints": ["规格/花色/吸水率"]},
        {"name": "卫浴陶瓷（马桶/洁具）", "keywords": ["马桶", "卫浴", "洁具", "洗手盆", "坐便器", "浴缸"],
         "process": "注浆/高压成型+烧成+施釉", "params": ["temperature"],
         "constraints": ["尺寸/釉面/水效"]},
        {"name": "日用玻璃（瓶/杯/器皿）", "keywords": ["玻璃瓶", "玻璃杯", "日用玻璃", "器皿", "酒杯"],
         "process": "熔制+成型+退火", "params": ["temperature"],
         "constraints": ["材质/耐温/外观"]},
     ]},
    {"code": "C31", "name": "黑色金属冶炼压延", "type": "process", "fit": "low",
     "engine": "custom", "channel": "-", "setup": "长流程/炉次",
     "params": [], "keywords": ["炼钢", "钢铁", "轧钢", "铸造生铁"]},
    {"code": "C32", "name": "有色金属冶炼压延", "type": "process", "fit": "low",
     "engine": "custom", "channel": "-", "setup": "长流程/炉次",
     "params": [], "keywords": ["有色", "铝", "铜", "锌", "电解", "冶炼"]},
    {"code": "C33", "name": "金属制品", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "modbus/dnc", "setup": "换型/换刀",
     "params": ["qty", "speed", "feed"],
     "keywords": ["金属制品", "五金", "冲压", "钣金", "标准件", "紧固件", "门窗",
                  "不锈钢", "烧水壶", "水壶", "锅", "厨具", "餐具", "保温杯", "水杯", "锁", "拉手", "刀", "剪", "日用金属", "厨房", "螺丝", "弹簧", "晾衣架"]},
    {"code": "C34", "name": "通用设备制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序/换刀",
     "params": ["qty", "speed", "feed"],
     "keywords": ["通用设备", "机床", "泵", "阀门", "风机", "减速机", "轴承", "齿轮", "液压", "压缩机", "真空泵", "传动", "联轴器", "数控机床", "加工中心"]},
    {"code": "C35", "name": "专用设备制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序/换刀",
     "params": ["qty", "speed", "feed"],
     "keywords": ["专用设备", "印刷机", "包装机", "模具", "医疗器械", "工程机械", "农机", "纺织机械", "食品机械", "焊接设备", "环保设备", "塑料机械", "注塑机", "贴标机", "灌装机"]},
    {"code": "C36", "name": "汽车制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc/modbus", "setup": "多工序/换型",
     "params": ["qty", "speed"],
     "keywords": ["汽车", "整车", "零部件", "发动机", "变速箱", "车身", "轮毂", "刹车", "座椅", "内饰", "车灯", "底盘", "新能源车", "电动汽车", "汽配"]},
    {"code": "C37", "name": "运输设备制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序",
     "params": ["qty"],
     "keywords": ["铁路", "船舶", "航空航天", "无人机", "轨道", "电动自行车", "摩托车", "自行车", "造船", "高铁", "地铁", "电动车", "童车"]},
    {"code": "C38", "name": "电气机械和器材", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序/换型",
     "params": ["qty", "speed"],
     "keywords": ["电气", "电机", "变压器", "电缆", "开关", "家电",
                  "电水壶", "小家电", "电饭煲", "风扇", "灯具", "热水器", "电磁炉", "电暖器", "冰箱", "洗衣机", "空调", "插排", "充电桩"]},
    {"code": "C39", "name": "计算机通信电子", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序/SMT换线",
     "params": ["qty", "speed"],
     "keywords": ["电子", "手机", "电路板", "PCB", "SMT", "芯片封装", "元件", "显示器", "耳机", "充电器", "数据线", "电源", "摄像头", "蓝牙音箱", "键盘", "鼠标", "路由器", "机顶盒"]},
    {"code": "C40", "name": "仪器仪表制造", "type": "discrete", "fit": "high",
     "engine": "solve_jssp", "channel": "dnc", "setup": "多工序",
     "params": ["qty"],
     "keywords": ["仪器", "仪表", "传感器", "测量", "光学", "水表", "电表", "温度计", "天平", "示波器", "计量", "检测", "流量计", "压力表"]},
    {"code": "C41", "name": "其他制造", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "job_ticket", "setup": "换款",
     "params": ["qty"],
     "keywords": ["日用杂品", "雨伞", "眼镜", "饰品", "工艺品", "拉链", "纽扣", "打火机", "牙刷", "假发", "模型", "蜡烛", "拖把"]},
    {"code": "C42", "name": "废弃资源综合利用", "type": "mixed", "fit": "mid",
     "engine": "solve", "channel": "modbus", "setup": "换料/换品种",
     "params": ["qty"],
     "keywords": ["再生", "回收", "废料", "拆解", "资源化", "再生塑料", "废纸", "废钢", "循环", "破碎"]},
    {"code": "C43", "name": "金属制品机械和设备修理", "type": "discrete", "fit": "high",
     "engine": "solve", "channel": "job_ticket", "setup": "换活/派工",
     "params": ["qty"],
     "keywords": ["修理", "维修", "翻新", "再制造", "检修", "保养", "机修"]},
]


_FIT_LABEL = {"high": "强适配（直接可用）", "mid": "中适配（需扩展约束）", "low": "弱适配（重工业，另建模型）"}
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


def match_segments(text, top=3):
    """细分工艺层识别（产品 + 国标工艺，比大类更细）。

    同一大类内不同产品工艺（如 C29 塑料里的「普通注塑件」vs「药包材药瓶」）有不同约束，
    必须按产品词命中细分模板，否则会把药瓶当普通注塑件、漏掉 GMP/药包材合规。
    返回 [(命中数, 大类条目, 细分条目)]。
    """
    results = []
    for ind in INDUSTRIES:
        for seg in ind.get("segments", []):
            hits = sum(1 for kw in seg["keywords"] if kw in text)
            if hits:
                results.append((hits, ind, seg))
    results.sort(key=lambda x: -x[0])
    return results[:top]


def recognize(text, top=3):
    """统一识别：优先「细分工艺」，其次「大类」。返回用户可读的推荐列表。

    用户只说大白话（产品名），命中细分模板时给出该工艺的【约束/合规】，
    避免把药包材/药瓶与普通注塑件混为一谈。
    """
    out = []
    for hits, ind, seg in match_segments(text, top):
        out.append({
            "大类": f"{ind['code']} {ind['name']}",
            "细分工艺": seg["name"],
            "工艺": seg["process"],
            "适配度": _FIT_LABEL[ind["fit"]],
            "引擎": _ENGINE_LABEL[ind["engine"]],
            "设备通道": ind["channel"],
            "标准工艺参数": seg["params"],
            "约束/合规": seg["constraints"],
        })
    if not out:  # 无细分命中 → 退回大类推荐
        out = [recommend(ind) for ind in match_industry(text, top)]
    return out


def fit_summary():
    """适配度统计：一般制造业大类里 high/mid/low 各多少（low=重工业，不在适配范围）。"""
    c = Counter(i["fit"] for i in INDUSTRIES)
    return {"total": len(INDUSTRIES), "high": c["high"], "mid": c["mid"], "low": c["low"]}

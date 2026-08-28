# -*- coding: utf-8 -*-
"""AHP 多因素优先级（调研报告 2026年8月生产计划_MPS_AHP_运筹_系统工程.xlsx 06_AHP 复刻）。

与 OR-Tools 的关系：AHP 在【求解之前】算权重与订单优先级（决策层），
OR-Tools CP-SAT 在【求解中】用优先级做目标（求解层）；两者解耦。

权重来源（工作簿 06_AHP 几何均值法，CR=0.009<0.1 一致性通过）：
  交期/客户承诺 0.3412 | 食品安全/质量风险 0.2049 | 需求量/销售影响 0.1915
  物料与库存齐套 0.1183 | 产能/人员瓶颈 0.0745 | 换线/换型损失 0.0696

排序规则（工作簿原文）：P0（清洁消毒/食品安全/质量异常）刚性不竞争；
P1 交付锁定；P2 常规订单/补货；P3 研发试产；同层级内按
“交期最早→物料齐套→同工艺连续批量→减少换线”。
"""
import math

# 工作簿 06_AHP 六因素成对比较矩阵（行=列顺序一致）
CRITERIA = ["交期/客户承诺", "食品安全/质量风险", "需求量/销售影响",
            "物料与库存齐套", "产能/人员瓶颈", "换线/换型损失"]
PAIRWISE = [
    [1, 2, 2, 3, 4, 4],
    [0.5, 1, 1, 2, 3, 3],
    [0.5, 1, 1, 2, 2, 3],
    [1 / 3, 0.5, 0.5, 1, 2, 2],
    [0.25, 1 / 3, 0.5, 0.5, 1, 1],
    [0.25, 1 / 3, 1 / 3, 0.5, 1, 1],
]
# 随机一致性指标 RI（n=1..10）
RI = [0, 0, 0.58, 0.9, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]

# 建议等级阈值（综合分 1-5 分；工作簿样例 2.705→P3）
PRIO_THRESHOLDS = {"P1": 3.8, "P2": 2.8}


def ahp_weights(matrix=None):
    """几何均值法求权重 + 一致性检验。返回 (weights, meta)。"""
    m = matrix or PAIRWISE
    n = len(m)
    geo = [math.prod(row) ** (1.0 / n) for row in m]
    s = sum(geo)
    w = [g / s for g in geo]
    # λmax、CI、CR
    aw = [sum(m[i][j] * w[j] for j in range(n)) for i in range(n)]
    lam = sum(aw[i] / w[i] for i in range(n)) / n
    ci = (lam - n) / (n - 1) if n > 1 else 0.0
    cr = ci / RI[n - 1] if n <= len(RI) and RI[n - 1] else 0.0
    return w, {"n": n, "lambda_max": lam, "CI": ci, "CR": cr, "consistent": cr < 0.1}


def score_orders(orders, products, line_util=None, weights=None, thresholds=None):
    """对每个订单按六因素打分（1-5），返回带 ahp_score/ahp_grade 的订单副本。

    打分口径（可得的因素按数据算，不可得的给中性分并标注“估算”）：
      交期分   = 剩余天数越近越高（≤1天5分，每+1天-1，最低1）
      质量分   = 食品敏感品类（面点/净菜/糕点）5，其余3（估算，红线由 P0 规则兜底）
      需求分   = 订单量/该线8h产能 占比映射（≥50%→5，≥20%→4，≥5%→3，≥1%→2，否则1）
      齐套分   = 中性 3（估算：物料齐套数据未接入，接口预留）
      瓶颈分   = 该线历史负荷（line_util）≥0.7→4，≥0.5→3，否则2（估算）
      换线分   = 5 - 换型分钟等级（换型越大综合分越低→优先级越低，符合“减少换线”）
    """
    w = weights if isinstance(weights, list) and len(weights) == 6 else ahp_weights()[0]
    thresholds = thresholds or PRIO_THRESHOLDS
    line_util = line_util or {}
    prod_by_id = {p["id"]: p for p in products}
    out = []
    for o in orders:
        p = prod_by_id.get(o["product"], {})
        due_days = max(0, (__import__("datetime").datetime.strptime(o["due"][:10], "%Y-%m-%d")
                           - __import__("datetime").datetime.now()).days)
        d_score = max(1, 5 - due_days)
        cat = str(p.get("category", ""))
        q_score = 5 if any(k in cat for k in ("面点", "净菜", "糕点")) else 3
        cap8 = p.get("capacity_8h") or 0
        ratio = (o["qty"] / cap8) if cap8 else 0
        n_score = 5 if ratio >= 0.5 else 4 if ratio >= 0.2 else 3 if ratio >= 0.05 else 2 if ratio >= 0.01 else 1
        m_score = 3  # 估算：物料齐套数据未接入
        lu = line_util.get(p.get("line"), 0) if p.get("line") else 0
        b_score = 4 if lu >= 0.7 else 3 if lu >= 0.5 else 2
        setup = p.get("default_setup_min") or 0
        x_score = max(1, 5 - (setup // 10)) if setup else 5
        scores = [d_score, q_score, n_score, m_score, b_score, x_score]
        total = sum(si * wi for si, wi in zip(scores, w))
        grade = "P1" if total >= thresholds["P1"] else "P2" if total >= thresholds["P2"] else "P3"
        oo = dict(o)
        oo["ahp_scores"] = dict(zip(CRITERIA, scores))
        oo["ahp_score"] = round(total, 3)
        oo["ahp_grade"] = grade
        out.append(oo)
    return out


def apply_ahp_priorities(orders, products, line_util=None):
    """AHP 打分后回写 priority（P1/P2/P3 → 1/2/3），供引擎目标函数使用。
    返回 (新订单列表, 打分统计)。
    """
    w, meta = ahp_weights()
    scored = score_orders(orders, products, line_util=line_util, weights=w)
    grade_map = {"P1": 1, "P2": 2, "P3": 3}
    for o in scored:
        o["priority"] = grade_map[o["ahp_grade"]]
        o["priority_source"] = "ahp:" + o["ahp_grade"]
    from collections import Counter
    stats = {"weights": {k: round(v, 4) for k, v in zip(CRITERIA, w)}, "meta": meta,
             "grades": dict(Counter(o["ahp_grade"] for o in scored)),
             "score_avg": round(sum(o["ahp_score"] for o in scored) / len(scored), 3) if scored else 0}
    return scored, stats


if __name__ == "__main__":
    w, meta = ahp_weights()
    print("权重:", {k: round(v, 4) for k, v in zip(CRITERIA, w)})
    print("一致性:", {k: round(v, 4) if isinstance(v, float) else v for k, v in meta.items()})
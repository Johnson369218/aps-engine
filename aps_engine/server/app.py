# -*- coding: utf-8 -*-
"""APS Engine 服务（FastAPI）——通用 HTTP 接口。

设计（对齐 aps_docs/初级版APS产品设计-04 接口规范 + 看板安全约束）：
- 默认只绑 127.0.0.1（内网/本机）；对外暴露需自行加认证/IP 白名单（业务数据不出厂原则）。
- 复用 aps_engine.solve：校验 → 归一化 → CP-SAT/启发式 → audit 6 项 → 落盘。
- 输入上限防护：orders ≤ 2000 条、单条 body ≤ 8MB（uvicorn --limit-concurrency 由 serve.sh 控制）。

用法：
    .venv/bin/python -m uvicorn aps-engine.server.app:app --host 127.0.0.1 --port 8077
或  tools/serve.sh start
"""
import os
import sys
import traceback
from datetime import datetime
from typing import List, Optional

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from aps_engine.api import solve

MAX_ORDERS = 2000

app = FastAPI(
    title="APS Engine · 智能排产引擎服务",
    version="0.3.0",
    description="通用 APS 排产引擎服务：POST /api/schedule 排产，GET /api/health 探活。行业规则经 config/industry_example.json 适配。"
)


class ScheduleRequest(BaseModel):
    orders: List[dict] = Field(..., description="标准订单列表（同 scheduler.py 输入契约）")
    lines: List[dict] = Field(..., description="产线列表")
    products: List[dict] = Field(..., description="产品列表（8h计划产能口径）")
    engine: str = Field("auto", pattern="^(auto|cp|heuristic)$")
    time_limit: int = Field(20, ge=1, le=300)
    convert_units: bool = False
    out_path: Optional[str] = None
    xlsx_path: Optional[str] = None


@app.get("/api/health")
def health():
    try:
        import scheduler
        from aps_engine.audit import audit_result  # noqa
        engine_ok = True
        msg = "ok"
    except Exception as e:  # pragma: no cover
        engine_ok = False
        msg = str(e)
    return {
        "status": "ok" if engine_ok else "degraded",
        "service": "aps-engine",
        "version": "0.3.0",
        "engine": "cp+heuristic" if engine_ok else "unavailable",
        "industry": "food(config)",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "detail": msg,
    }


@app.post("/api/schedule")
def run_schedule(req: ScheduleRequest):
    if len(req.orders) > MAX_ORDERS:
        raise HTTPException(status_code=413, detail=f"订单数 {len(req.orders)} 超过上限 {MAX_ORDERS}")
    if not req.orders or not req.lines or not req.products:
        raise HTTPException(status_code=422, detail="orders/lines/products 不能为空")
    try:
        result = solve(
            req.orders, req.lines, req.products,
            engine=req.engine, time_limit=req.time_limit,
            convert_units=req.convert_units,
            out_path=req.out_path, xlsx_path=req.xlsx_path,
            products_raw=req.products,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except AssertionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # pragma: no cover
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"排产失败: {e}")
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8077)

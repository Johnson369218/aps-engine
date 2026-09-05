# APS Engine — AI-Powered Production Scheduling & Optimization

> **Describe your factory in one sentence → get an optimal schedule → push it straight to the machines.**
> An open-source (MIT) production scheduling & optimization engine that combines **CP-SAT**, **multi-operation Job-Shop**, and **direct machine integration** (Modbus TCP / DNC) under an **AI recognition layer**. 31 manufacturing adapters ship out of the box — but underneath it's a general scheduling & optimization engine.

中文文档：[README.zh.md](README.zh.md)

---

## ✨ Why it's technically interesting

- **CP-SAT, two-phase**: assignment + sequencing, then a 2-opt setup-time-reduction pass, warm-started from a deterministic heuristic.
- **A real Job-Shop solver** (`solve_jssp`): routing + precedence + no-overlap — reaches the **ft06 optimum (makespan 55)** with 0 violations, not just a flow-shop.
- **Reproducible by construction**: `seed=42` → byte-identical task sequences, two runs always agree.
- **Talks to real machines**: Modbus TCP (pure stdlib, zero deps), network DNC (G-code to CNCs), REST (IoT gateways) — the half most open-source schedulers skip.
- **AI recognition layer**: "we make stainless steel kettles" (or a photo) → matches **31 categories + segment-level process** — e.g. *medicine bottle* → pharma-packaging (GMP/cleanroom/batch) vs *phone case* → consumer injection. No "discrete vs continuous" questions.

## 📊 Benchmarks

| Benchmark | Result |
|---|---|
| JSSP ft06 (6×6) | makespan **55** (best-known), **0** precedence violations |
| JSSP gen33 / gen44 | **22 / 23** (optimal) |
| Public datasets (BPI2019 · JSSP · Kaggle · bottling · OEE · MES ERP) | **12 / 12 green** |
| Reproducibility | same seed → byte-identical |
| Audit | 6-item consistency, fails closed |

## 🚀 Quick start

```bash
pip install .                       # or: git clone … && python tools/schedule_cli.py

# 1) recognize an industry from one sentence — no jargon questions
python tools/industry_wizard.py --text "we make stainless steel kettles"

# 2) schedule (single-stage flow shop, setup-aware, reproducible)
python tools/schedule_cli.py \
    --orders data/orders.json --lines data/lines.json --products data/products.json \
    --out output/schedule.json --xlsx output/schedule.xlsx --seed 42

# 3) multi-operation Job-Shop (machining: turning → milling → drilling)
#    orders carry "operations": [{"machine": "M1", "duration_min": …}, …]
#    see tests/test_jssp.py + aps_engine/jssp.py::solve_jssp

# 4) push the schedule to machines (dry-run first; --confirm only after human check)
python tools/machine_push.py --schedule output/schedule.json \
    --machines data/machines.json --machine flexo1 --confirm
```

## 🏭 What people actually run on it

31 manufacturing categories, segment-level templates: printing (flexo/gravure), injection molding, machining (CNC), panel furniture, ceramics, food, pharma packaging…
Drop-in templates in `examples/printing_sme/` and `examples/plastic_injection/`.

## ⚖️ Why not Excel / commercial APS / frePPLe?

| | Excel / human | **APS Engine** | Commercial APS | frePPLe |
|---|---|---|---|---|
| Cost | 0 (high labor) | **0 (MIT)** | $100k+ / yr | 0 |
| Solver | experience | **CP-SAT + 2-opt + JSSP** | proprietary | heuristics |
| Reproducible | ✗ | **✓ seed=42** | ✓ | ✓ |
| Multi-op / precedence | memory | **✓ solve_jssp** | ✓ | ✓ |
| Machine-direct (Modbus/DNC) | ✗ | **✓** | partial | ✗ |
| AI recognition (sentence/photo) | ✗ | **✓** | ✗ | ✗ |
| Time to first schedule | — | **hours** | months | days |

## 🔒 How conclusions stay honest

1. contract-first (frozen I/O contracts) · 2. public-corpus validation · 3. reproducible seed ·
4. 6-item audit · 5. baseline replay (AI vs EDD/SPT) · 6. calibration loop (±5%/≥10%, approval-gated) ·
7. Monte-Carlo P10/P50/P90 · 8. human-in-the-loop (co-pilot/replan are suggestions, never auto-applied).

## License

MIT · [LICENSE](LICENSE)

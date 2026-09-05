# APS Engine · Open-Source Advanced Planning & Scheduling

> **A generic APS engine for manufacturing SMEs.** Orders arrive from any channel (WeChat / DingTalk / WeCom / ERP);
> the schedule ships as Excel + kanban + one-line briefings — and directly to machines (Modbus TCP / DNC / REST).
> One engine, 31 manufacturing categories, zero-code onboarding. Describe your factory in one sentence and it tells you the rest.

---

## Why APS Engine (30 seconds)

```
describe factory  ──►  industry recognition  ──►  schedule (CP-SAT / JSSP)  ──►  output
  "we make stainless    (product+process match,     setup-time optimization,        Excel / kanban /
   steel kettles"       no jargon questions)        reproducible seed=42)           one-line briefings
                                                                                      │
                                                                                      ├─► machines (Modbus TCP / DNC / REST / job ticket)
                                                                                      └─► people  (DingTalk / WeCom / WeChat webhooks)
                                                                                              │
                                                              closed loop ◄── report-back ── ledger ── rush-order replan ── calibration
```

**What it solves, concretely:**

- **Setup-time reduction** — changeover matrix (`setup_min`) is in the objective; squeezing 换型 is where SME profit hides.
- **Reproducible** — `seed=42` fixed; same input → byte-identical task sequence.
- **Multi-operation** — `solve_jssp` (routing + precedence + no-overlap) hits JSSP optimal (ft06 = 55).
- **Machine-direct** — push registers to PLCs (Modbus TCP), G-code to CNCs (network DNC), JSON to IoT gateways; `dry-run` before any write.
- **Closed loop** — report-back → ledger → rush-order replan (frozen-zone safe) → execution calibration.

## Comparison

| | Excel / 老师傅手工 | **APS Engine** | Commercial APS (SAP/Oracle…) | frePPLe |
|---|---|---|---|---|
| Cost | 0 (but high labor) | **0 (MIT, open source)** | ¥hundreds of k / year | 0 (open source) |
| Solver | human experience | **CP-SAT + 2-opt + JSSP** | proprietary | heuristics/constraint |
| Reproducible | ✗ | **✓ (seed=42)** | ✓ | ✓ |
| Multi-op / precedence | memory | **✓ solve_jssp** | ✓ | ✓ |
| Machine-direct (Modbus/DNC) | ✗ | **✓** | partial (needs integration) | ✗ |
| Multi-channel (WeChat/DingTalk) | ✗ | **✓** | ✗/custom | ✗ |
| Chinese SME fit (温州/佛山 machines) | native | **✓ native** | needs consultants | English-only |
| Time to first schedule | — | **hours (3 tables)** | months | days |

## Quick start

```bash
pip install .                       # or: git clone … && python tools/schedule_cli.py

# 1) schedule (single-stage flow shop)
python tools/schedule_cli.py \
    --orders data/orders.json --lines data/lines.json --products data/products.json \
    --out output/schedule.json --xlsx "output/schedule.xlsx" --engine auto --seed 42

# 2) multi-operation (machining: turning → milling → drilling)
#    orders carry "operations": [{"machine": "M1", "duration_min": …}, …]
#    see tests/test_jssp.py + aps_engine/jssp.py::solve_jssp

# 3) recognize an industry from one sentence (no jargon questions)
python tools/industry_wizard.py --text "we make stainless steel kettles"

# 4) push schedule to machines (dry-run first, --confirm only after human check)
python tools/machine_push.py --schedule output/schedule.json \
    --machines data/machines.json --machine flexo1 --confirm
```

## Benchmarks (evidence, not promises)

- **JSSP (multi-operation)**: ft06 = **55** (best-known), gen33 = **22**, gen44 = **23** — 0 precedence violations.
- **Public datasets**: 12/12 green (BPI2019 / JSSP / Kaggle / bottling / OEE / MES ERP …), `tests/eval_suite.py --quick`.
- **Audit**: 6 consistency checks on every schedule; fails closed.
- **Zero customer data in repo**: validation uses public/synthetic corpora only.

## Industry coverage

- **31 manufacturing categories** (GB/T 4754-2017 section C); heavy process industries (steel / petrochemical / smelting) and mining excluded.
- **Segment-level matching**: same machine, different process/compliance → different template.
  e.g. *"medicine bottle"* → pharmaceutical packaging (GMP, cleanroom, batch/lot, extractables) vs *"phone case"* → consumer injection molding (GB/T only).
- Customer guidance prompt (`GUIDE_PROMPT`) so vague descriptions ("we make bottles") get clarified, not guessed.

## Reliability (how conclusions are kept honest)

1. contract-first (frozen input/output contracts) · 2. public-corpus validation · 3. reproducible seed ·
4. 6-item audit · 5. baseline replay (AI vs EDD/SPT) · 6. calibration loop (±5%/≥10%, approval-gated) ·
7. Monte-Carlo P10/P50/P90 · 8. human-in-the-loop (co-pilot/replan/rule-replay are suggestions, never auto-applied).

## License

MIT. See [LICENSE](LICENSE). Chinese docs: [README.md](README.md).

# Show HN post (draft)

**Title:**
Show HN: APS Engine — describe your factory in one sentence, get an optimal schedule, push it to the machines

**Body:**

Small and mid-size manufacturers still schedule with spreadsheets and the old hand's gut feel. Commercial APS costs six figures and needs a consulting team; the existing open-source schedulers are either flow-shop-only or never touch the shop floor.

I built **APS Engine** — an open-source (MIT) production scheduling & optimization engine. Three things it does that I couldn't find anywhere in open source:

1. **AI recognition, not a questionnaire.** Type "we make stainless steel kettles" (or drop a photo) and it matches 31 manufacturing categories *plus segment-level process* — a *medicine bottle* correctly lands on pharma-packaging (GMP / cleanroom / batch / extractables), while a *phone case* lands on consumer injection molding. It never asks "discrete or continuous?"

2. **It's a real solver.** CP-SAT two-phase (assignment + sequencing + 2-opt setup reduction, warm-started from a heuristic) for flow shops, and `solve_jssp` (routing + precedence + no-overlap) for job shops — it reaches the **ft06 optimum (makespan 55)** with 0 precedence violations, plus gen33/gen44 optimal. Reproducible by construction (`seed=42` → byte-identical runs).

3. **It pushes to real machines.** Modbus TCP (pure stdlib — writes quantity/speed/temperature registers to 信捷/汇川/台达 PLCs), network DNC (G-code to CNCs), REST (IoT gateways), or a job ticket for legacy machines. Always `dry-run` first; a human confirms before anything is written.

**Evidence:** 12/12 public datasets green (BPI2019 · JSSP · Kaggle · bottling · OEE · MES ERP), 6-item audit fails closed, zero customer data in the repo. ~1,200 lines of Python, `pip install .`, first schedule in hours from three JSON tables.

**Known gaps (being honest):** single-machine and job-shop are solid; continuous-process industries (steel, petrochemical) are out of scope and marked as such. Machine integration is tested against a mock PLC, not yet in a live plant.

Try it:
```bash
git clone https://github.com/Johnson369218/aps-engine
pip install .
python tools/industry_wizard.py --text "we make stainless steel kettles"
python tools/schedule_cli.py --orders examples/plastic_injection/orders.json \
    --lines examples/plastic_injection/lines.json --products examples/plastic_injection/products.json \
    --out /tmp/s.json --seed 42
```

Happy to answer anything — especially from anyone who's actually run scheduling on a shop floor.

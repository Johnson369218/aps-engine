# -*- coding: utf-8 -*-
"""TimesFM 2.5 子进程服务：stdin 收 JSON {seqs:{key:[v,...]}, horizon:N}，stdout 回 JSON。
用 _ml_forecast/venv 运行（python3.13 + timesfm[torch]，用户已验证环境）。
"""
import json
import sys

def main():
    payload = json.load(sys.stdin)
    seqs = payload["seqs"]
    horizon = int(payload.get("horizon", 1))
    import torch
    import timesfm
    torch.set_float32_matmul_precision("high")
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
    model.compile(timesfm.ForecastConfig(
        max_context=512, max_horizon=7, normalize_inputs=True,
        use_continuous_quantile_head=True, force_flip_invariance=True,
        infer_is_positive=True, fix_quantile_crossing=True,
    ))
    keys = list(seqs)
    inputs = [seqs[k] for k in keys]
    point, quantiles = model.forecast(horizon=horizon, inputs=inputs)
    out = {}
    for i, k in enumerate(keys):
        out[k] = {
            "p50": [round(float(point[i, h]), 3) for h in range(horizon)],
            "p10": [round(float(quantiles[i, h, 1]), 3) for h in range(horizon)],
            "p90": [round(float(quantiles[i, h, 9]), 3) for h in range(horizon)],
        }
    print(json.dumps(out))

if __name__ == "__main__":
    main()
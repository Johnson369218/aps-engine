# -*- coding: utf-8 -*-
"""设备直连通道：把排产结果下发到设备（面向温州/佛山产中小印刷机：柔印/凹印/分切/制袋）。

真实接口（按普及度，非高端机）：
- Modbus TCP：信捷/汇川/台达/西门子等 PLC 通用——写寄存器（数量/速度/温度/张力），
  柔印机（无纺布）、凹印机（卷膜）、分切机、制袋机均常见；
- REST/HTTP：IoT 网关 / 新一代自带网口设备的 JSON 接口；
- 作业单（文件）：无网口/无协议的老设备 → 机台终端/大屏/打印，人工输入 HMI；
- OPC-UA：新一代 PLC（需 asyncua 依赖，本文件留契约位，不硬依赖）。

红线：设备指令【先人工确认再下发】——dispatch(confirm=False) 只返回 dry-run 草稿，真写必须 confirm=True。
"""
import json
import socket
import struct


# ─────────────────────────────────────────── Modbus TCP（stdlib 最小实现）──

class ModbusTcpClient:
    """最小 Modbus TCP 客户端（写保持寄存器），无第三方依赖。"""

    def __init__(self, host, port=502, unit=1, timeout=3):
        self.host, self.port, self.unit, self.timeout = host, port, unit, timeout
        self._tid = 0

    def _frame(self, pdu):
        self._tid = (self._tid + 1) & 0xFFFF
        length = 1 + len(pdu)  # unit_id + PDU
        return struct.pack(">HHHB", self._tid, 0, length, self.unit) + pdu

    def write_single_register(self, addr, value):
        pdu = struct.pack(">BHH", 0x06, int(addr), int(value) & 0xFFFF)
        resp = self._send_recv(self._frame(pdu))
        return len(resp) >= 12 and resp[7:12] == pdu

    def write_multiple_registers(self, addr, values):
        vals = [int(v) & 0xFFFF for v in values]
        pdu = struct.pack(">BHHB", 0x10, int(addr), len(vals), len(vals) * 2)
        pdu += b"".join(struct.pack(">H", v) for v in vals)
        resp = self._send_recv(self._frame(pdu))
        return len(resp) >= 12 and resp[7:12] == struct.pack(">BHH", 0x10, int(addr), len(vals))

    def _send_recv(self, req):
        s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        try:
            s.sendall(req)
            header = _recv_exact(s, 7)
            _tid, _proto, length, _unit = struct.unpack(">HHHB", header)
            body = _recv_exact(s, length - 1)
            return header + body
        finally:
            s.close()


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("设备断开")
        buf += chunk
    return buf


# ─────────────────────────────────────────── 作业映射（排产 → 设备指令）──

def build_jobs(result, line_id, products=None):
    """排产结果某产线（机台）的任务 → 作业列表（含产品工艺参数 process_params）。"""
    prod_params = {}
    if products:
        prod_params = {p["id"]: p.get("process_params", {}) for p in products}
    jobs = []
    for blk in result.get("schedule", []):
        if blk.get("line") != line_id:
            continue
        for t in blk.get("tasks", []):
            j = {"order": t["order"], "product": t.get("product"),
                 "product_name": t.get("product_name", t.get("product")),
                 "qty": t.get("qty"), "start": t.get("start"), "end": t.get("end"),
                 "due": t.get("due")}
            j.update(prod_params.get(t.get("product"), {}))
            jobs.append(j)
    return jobs


def build_commands(machine_cfg, jobs):
    """作业列表 → 设备指令（按 machine_cfg.registers 映射参数名 → 寄存器地址）。"""
    regs = machine_cfg.get("registers", {})
    commands = []
    for j in jobs:
        for param, spec in regs.items():
            value = j.get(param)
            if value is None:
                continue
            commands.append({"order": j["order"], "param": param,
                             "addr": spec["addr"], "value": int(value),
                             "count": spec.get("count", 1)})
    return commands


# ─────────────────────────────────────────── 通道（传输）──

class RestChannel:
    def __init__(self, url, headers=None):
        self.url, self.headers = url, headers or {}

    def write(self, commands):
        import urllib.request
        data = json.dumps(commands, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=data,
                                     headers={"Content-Type": "application/json", **self.headers},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status


class JobTicketChannel:
    """无网口老设备：写机台作业单文件（终端/大屏/打印）。"""

    def __init__(self, path):
        self.path = path

    def write(self, commands):
        lines = [f"{c['order']}  参数[{c['param']}] = {c['value']}  (寄存器 {c['addr']})"
                 for c in commands]
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) or "（无指令）")
        return len(lines)


# ─────────────────────────────────────────── 下发（红线：先确认）──

def dispatch(machine_cfg, jobs, confirm=False):
    """把作业列表下发到设备。confirm=False → dry-run（只返回指令草稿，不真写）。"""
    commands = build_commands(machine_cfg, jobs)
    name = machine_cfg.get("name", machine_cfg.get("id", "?"))
    typ = machine_cfg.get("type", "job_ticket")
    if not confirm:
        return {"dry_run": True, "machine": name, "type": typ, "commands": commands}

    if typ == "modbus_tcp":
        cli = ModbusTcpClient(machine_cfg["host"], machine_cfg.get("port", 502),
                              machine_cfg.get("unit", 1))
        sent = 0
        for c in commands:
            if c["count"] > 1:  # 32 位量拆高低字（大端）
                v = c["value"]
                ok = cli.write_multiple_registers(c["addr"], [(v >> 16) & 0xFFFF, v & 0xFFFF])
            else:
                ok = cli.write_single_register(c["addr"], c["value"])
            sent += 1 if ok else 0
        return {"dry_run": False, "machine": name, "type": typ,
                "commands": commands, "sent": sent}
    if typ == "rest":
        RestChannel(machine_cfg["url"]).write(commands)
        return {"dry_run": False, "machine": name, "type": typ,
                "commands": commands, "sent": len(commands)}
    if typ == "job_ticket":
        n = JobTicketChannel(machine_cfg["path"]).write(commands)
        return {"dry_run": False, "machine": name, "type": typ,
                "commands": commands, "sent": n}
    return {"dry_run": False, "machine": name, "type": typ,
            "commands": commands, "sent": 0, "error": f"未知设备类型 {typ}"}


def load_machines(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

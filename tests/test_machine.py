# -*- coding: utf-8 -*-
"""设备直连：Modbus TCP 帧/作业映射/dry-run 安全门（mock 套接字，不真连设备）。"""
import os, sys, struct, tempfile
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine import machine  # noqa: E402

RESULT = {"schedule": [
    {"line": "L1", "tasks": [
        {"order": "O-001", "product": "SKU001", "product_name": "无纺布袋", "qty": 5000,
         "start": "2026-09-06 08:00", "end": "2026-09-06 10:00", "due": "2026-09-06 18:00"},
    ]},
]}


def test_modbus_frame():
    cli = machine.ModbusTcpClient("192.168.1.10")
    captured = []
    with mock.patch.object(cli, "_send_recv", side_effect=lambda req: captured.append(req) or req):
        ok = cli.write_single_register(10, 120)
    assert ok is True
    req = captured[0]
    # MBAP 头：事务ID(2)+协议(0)+长度(2)+单元(1)，共 7 字节；PDU：功能码0x06+地址10+值120
    assert struct.unpack(">HHHB", req[:7])[1] == 0, "协议标识应为 0"
    assert req[7] == 0x06 and req[8:10] == struct.pack(">H", 10) and req[10:12] == struct.pack(">H", 120)
    print("PASS test_modbus_frame")


def test_build_jobs_and_commands():
    jobs = machine.build_jobs(RESULT, "L1")
    assert jobs[0]["qty"] == 5000 and jobs[0]["order"] == "O-001"
    cfg = {"registers": {"qty": {"addr": 0, "count": 2}, "speed": {"addr": 10}}}
    jobs[0]["speed"] = 120
    cmds = machine.build_commands(cfg, jobs)
    assert {c["param"] for c in cmds} == {"qty", "speed"}
    assert cmds[0]["addr"] == 0 and cmds[0]["count"] == 2 and cmds[0]["value"] == 5000
    print("PASS test_build_jobs_and_commands")


def test_dispatch_dry_run_gate():
    cfg = {"name": "柔印机1#", "type": "modbus_tcp", "host": "192.168.1.10",
           "registers": {"qty": {"addr": 0, "count": 2}, "speed": {"addr": 10}}}
    jobs = machine.build_jobs(RESULT, "L1"); jobs[0]["speed"] = 120
    # dry-run：不真写，返回草稿
    r = machine.dispatch(cfg, jobs, confirm=False)
    assert r["dry_run"] is True and len(r["commands"]) == 2
    # confirm=True：mock Modbus 客户端，验证真写并统计 sent
    with mock.patch.object(machine, "ModbusTcpClient") as mc:
        cli = mc.return_value
        cli.write_single_register.return_value = True
        cli.write_multiple_registers.return_value = True
        r2 = machine.dispatch(cfg, jobs, confirm=True)
    assert r2["dry_run"] is False and r2["sent"] == 2
    print("PASS test_dispatch_dry_run_gate")


def test_job_ticket_fallback():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "ticket.txt")
        cfg = {"name": "分切机", "type": "job_ticket", "path": p,
               "registers": {"qty": {"addr": 0}}}
        jobs = machine.build_jobs(RESULT, "L1")
        r = machine.dispatch(cfg, jobs, confirm=True)
        assert r["sent"] == 1 and os.path.exists(p)
        assert "5000" in open(p, encoding="utf-8").read()
    print("PASS test_job_ticket_fallback")


def test_build_jobs_from_jssp():
    jssp = {"schedule": [{"machine": "M1", "tasks": [
        {"order": "J1", "op_id": "J1_op1", "op_index": 1, "start": 0, "end": 10, "duration_min": 10},
        {"order": "J2", "op_id": "J2_op1", "op_index": 1, "start": 10, "end": 20, "duration_min": 10},
    ]}]}
    jobs = machine.build_jobs_from_jssp(jssp, "M1")
    assert len(jobs) == 2 and jobs[0]["op_id"] == "J1_op1"
    print("PASS test_build_jobs_from_jssp")


def test_dnc_channel():
    with tempfile.TemporaryDirectory() as td:
        nc_dir = os.path.join(td, "nc"); os.makedirs(nc_dir)
        open(os.path.join(nc_dir, "O1001.nc"), "w").write("G00 X0 Y0\nM30")
        prog_dir = os.path.join(td, "machine_prog")
        cfg = {"name": "立车CNC", "type": "dnc", "nc_dir": nc_dir,
               "program_dir": prog_dir, "program_map": {"O-001": "O1001"}}
        jobs = [{"order": "O-001", "op_id": "O-001_op1", "product": "P1"}]
        r = machine.dispatch(cfg, jobs, confirm=False)  # dry-run
        assert r["dry_run"] is True and r["commands"][0]["program"] == "O1001"
        r2 = machine.dispatch(cfg, jobs, confirm=True)  # 真拷贝
        assert r2["sent"] == 1 and os.path.exists(os.path.join(prog_dir, "O1001.nc"))
    print("PASS test_dnc_channel")


if __name__ == "__main__":
    test_modbus_frame()
    test_build_jobs_and_commands()
    test_dispatch_dry_run_gate()
    test_job_ticket_fallback()
    test_build_jobs_from_jssp()
    test_dnc_channel()
    print("ALL PASS")

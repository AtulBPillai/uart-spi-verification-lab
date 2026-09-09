#!/usr/bin/env python3
"""Execute actual Icarus simulations. No mocked or precomputed pass results."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

# A small, disclosed fault set; detection is NOT general defect coverage.
MUTATIONS = [
    dict(id="U01", scope="uart", file="uart_tx.v", description="Reverse TX payload bit order",
         old="frame <= {1'b1, data, 1'b0};",
         new="frame <= {1'b1, data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], 1'b0};", count=1),
    dict(id="U02", scope="uart", file="uart_tx.v", description="Drive a LOW stop bit",
         old="frame <= {1'b1, data, 1'b0};", new="frame <= {1'b0, data, 1'b0};", count=1),
    dict(id="U03", scope="uart", file="uart_tx.v", description="Reload TX timer one count too high",
         old="timer <= CLKS_PER_BIT - 1;", new="timer <= CLKS_PER_BIT;", count=2),
    dict(id="U04", scope="uart", file="uart_tx.v", description="Accept a new TX request while busy",
         old="if (valid && ready) begin", new="if (valid) begin", count=1),
    dict(id="U05", scope="uart", file="uart_rx.v", description="Accept an invalid LOW stop bit",
         old="if (rx_sync) begin data <= shift; valid <= 1; state <= IDLE; end",
         new="if (1'b1) begin data <= shift; valid <= 1; state <= IDLE; end", count=1),
    dict(id="U06", scope="uart", file="uart_rx.v", description="Reverse RX payload bit order",
         old="shift[bit_index] <= rx_sync;", new="shift[7-bit_index] <= rx_sync;", count=1),
    dict(id="S01", scope="spi", file="spi_master.v", description="Sample MISO on the opposite edge",
         old="phase ? edge_count[0] : !edge_count[0]", new="phase ? !edge_count[0] : edge_count[0]", count=1),
    dict(id="S02", scope="spi", file="spi_master.v", description="Invert each received MISO bit",
         old="rx_shift <= {rx_shift[6:0], miso};", new="rx_shift <= {rx_shift[6:0], ~miso};", count=1),
    dict(id="S03", scope="spi", file="spi_master.v", description="End SPI transfer one edge early",
         old="if (edge_count == 15)", new="if (edge_count == 14)", count=1),
]


def execute(argv: list[str], cwd: Path, timeout: int = 90) -> dict:
    try:
        p = subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout, check=False)
        return {"returncode": p.returncode, "output": p.stdout, "timeout": False}
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        return {"returncode": None, "output": output + "\nHOST_PROCESS_TIMEOUT\n", "timeout": True}


def classify(compiled: dict, simulated: dict | None, scope: str) -> str:
    if compiled["timeout"] or compiled["returncode"] != 0:
        return "INVALID"  # A compiler failure is never a detected functional bug.
    if simulated is None or simulated["timeout"]:
        return "ERROR"
    if simulated["returncode"] != 0:
        return "DETECTED" if "ASSERTION " in simulated["output"] else "ERROR"
    if f"VERIFICATION_PASS {scope}" not in simulated["output"]:
        return "ERROR"
    return "PASS"


def parse_output(output: str) -> tuple[list[dict], dict]:
    coverage = []
    metrics = {}
    for line in output.splitlines():
        if line.startswith("COVER "):
            _, name, hit, total = line.split()
            hit, total = int(hit), int(total)
            if total <= 0 or not 0 <= hit <= total:
                raise ValueError(f"Invalid coverage: {line}")
            coverage.append(dict(name=name, hit=hit, total=total))
        if line.startswith("RESULT "):
            for key, value in re.findall(r"(\w+)=(\d+)", line):
                metrics[key] = int(value)
    return coverage, metrics


def full_coverage_complete(scope: str, bins: list[dict]) -> bool:
    expected = ({"uart_tx_bytes", "uart_rx_bytes", "uart_busy_request", "uart_back_to_back",
                 "uart_period_offsets", "uart_bad_stop", "uart_false_start", "uart_break_recovery",
                 "uart_reset_abort"} if scope == "uart" else
                {"spi_mode0_bytes", "spi_mode1_bytes", "spi_mode2_bytes", "spi_mode3_bytes",
                 "spi_mode_divider_cross", "spi_busy_config_latch", "spi_invalid_divider", "spi_reset_abort"})
    return {b["name"] for b in bins} == expected and all(b["hit"] == b["total"] for b in bins)


def run_case(name: str, scope: str, rtl: Path, out: Path, mode: str = "full", divider: int = 16) -> dict:
    work = out / "runs" / name
    work.mkdir(parents=True, exist_ok=True)
    cmd = ["iverilog", "-g2012", "-Wall", "-s", f"tb_{scope}"]
    if scope == "uart":
        cmd += [f"-Ptb_uart.DIV={divider}"]
    cmd += ["-o", str(work / "sim.vvp")]
    cmd += [str(p) for p in sorted(rtl.glob("*.v"))]
    cmd += [str(ROOT / "tb" / f"tb_{scope}.sv")]
    compiled = execute(cmd, ROOT)
    (work / "compile.log").write_text(compiled["output"])
    simulated = None
    if compiled["returncode"] == 0:
        command = ["vvp", str(work / "sim.vvp")]
        if mode != "full":
            command += [f"+{mode.upper()}"]
        if mode == "waves":
            command += [f"+VCD={work / (scope + '.vcd')}"]
        simulated = execute(command, ROOT)
        (work / "simulation.log").write_text(simulated["output"])
    outcome = classify(compiled, simulated, scope)
    coverage, metrics = parse_output(simulated["output"] if simulated else "")
    if outcome == "PASS" and mode == "full" and not full_coverage_complete(scope, coverage):
        outcome = "ERROR"
    assertion = next((line for line in (simulated or {}).get("output", "").splitlines()
                      if "ASSERTION " in line), None)
    row = dict(name=name, scope=scope, mode=mode, divider=divider if scope == "uart" else None,
               outcome=outcome, coverage=coverage, metrics=metrics, assertion=assertion,
               log=f"runs/{name}/simulation.log", compile_log=f"runs/{name}/compile.log")
    print(f"{name}: {outcome} {metrics}", flush=True)
    if outcome != "PASS":
        print((simulated or compiled)["output"][-2000:], flush=True)
    return row


def materialize_mutant(mutation: dict, destination: Path) -> None:
    shutil.copytree(ROOT / "rtl", destination, dirs_exist_ok=True)
    path = destination / mutation["file"]
    source = path.read_text()
    if source.count(mutation["old"]) != mutation["count"]:
        raise ValueError(f"Mutation {mutation['id']} no longer matches source exactly")
    path.write_text(source.replace(mutation["old"], mutation["new"]))


def source_manifest() -> dict:
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in ("rtl", "tb", "scripts", "tests")
            for p in sorted((ROOT / directory).rglob("*"))
            if p.is_file() and p.suffix in (".v", ".sv", ".py")}


def write_summary(result: dict, out: Path) -> None:
    lines = ["# Executed simulation results", "", "Project owner: Atul Biju Pillai.", "",
             "Evidence type: digital RTL simulation; no FPGA or physical-chip measurements.", "",
             f"Source commit: `{result['commit']}`", "", "## Clean regression", "",
             "| Run | Outcome | TX frames / SPI transfers | RX frames | Checks |",
             "| --- | --- | ---: | ---: | ---: |"]
    for row in result["baseline"]:
        m = row["metrics"]
        lines += [f"| {row['name']} | {row['outcome']} | {m.get('tx_frames', m.get('transfers', 0))} | {m.get('rx_frames', '—')} | {m.get('checks', 0)} |"]
    lines += ["", "## Seeded RTL faults", "", "| Fault | Change | Smoke suite | Full suite |",
              "| --- | --- | --- | --- |"]
    for row in result["mutations"]:
        lines += [f"| {row['id']} | {row['description']} | {row['smoke']['outcome']} | {row['full']['outcome']} |"]
    lines += ["", "DETECTED requires a successfully compiled mutant and a failing simulation assertion. "
              "Compile errors, missing pass markers and host timeouts are reported separately. "
              "Detection of these nine disclosed mutants is not proof of freedom from bugs. "
              "Coverage bins are planned functional scenarios, not RTL line/toggle coverage.", ""]
    (out / "SUMMARY.md").write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="build/evidence")
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args()
    for program in ("iverilog", "vvp"):
        if not shutil.which(program):
            parser.error(f"{program} is required. Install Icarus Verilog or use the Docker/CI workflow.")
    out = (ROOT / args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    version = execute(["iverilog", "-V"], ROOT)["output"]
    (out / "simulator-version.txt").write_text(version)
    result = dict(schema_version=1, evidence_type="executed_digital_rtl_simulation",
                  owner="Atul Biju Pillai", commit=os.getenv("GITHUB_SHA", "local-uncommitted"),
                  workflow_url=(f"https://github.com/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"
                                if os.getenv("GITHUB_RUN_ID") else None),
                  source_sha256=source_manifest(), baseline=[], mutations=[], waves=[])
    start = time.monotonic()
    for divider in (16, 17, 32):
        result["baseline"].append(run_case(f"uart-full-div{divider}", "uart", ROOT / "rtl", out, divider=divider))
    result["baseline"].append(run_case("spi-full", "spi", ROOT / "rtl", out))
    for scope in ("uart", "spi"):
        result["baseline"].append(run_case(f"{scope}-smoke", scope, ROOT / "rtl", out, mode="smoke"))
    good = all(row["outcome"] == "PASS" for row in result["baseline"])
    if good and not args.baseline_only:
        for mutation in MUTATIONS:
            rtl = out / "mutants" / mutation["id"]
            materialize_mutant(mutation, rtl)
            row = dict(mutation)
            for mode in ("smoke", "full"):
                test = run_case(f"{mutation['id']}-{mode}", mutation["scope"], rtl, out, mode=mode)
                if test["outcome"] == "PASS":
                    test["outcome"] = "SURVIVED"
                row[mode] = test
            result["mutations"].append(row)
        for scope in ("uart", "spi"):
            result["waves"].append(run_case(f"{scope}-waves", scope, ROOT / "rtl", out, mode="waves"))
        good = (all(row["full"]["outcome"] == "DETECTED" and row["smoke"]["outcome"] in ("DETECTED", "SURVIVED")
                    for row in result["mutations"])
                and all(row["outcome"] == "PASS" for row in result["waves"]))
    result["elapsed_seconds"] = round(time.monotonic() - start, 3)
    result["status"] = "PASS" if good else "FAIL"
    (out / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    write_summary(result, out)
    print(f"Overall: {result['status']}. Evidence: {out}", flush=True)
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Render measured VCD signal transitions and executed mutation results to PNG."""
from __future__ import annotations

import argparse
from bisect import bisect_right
import json
from pathlib import Path
import re


def read_vcd(path: Path) -> dict:
    """Read the scalar/vector, integer-time VCD subset produced by these benches."""
    source = path.read_text()
    header, body = source.split("$enddefinitions $end", 1)
    scale = re.search(r"\$timescale\s+(\d+)\s*(s|ms|us|ns|ps|fs)\s+\$end", header)
    if not scale:
        raise ValueError("VCD has no supported timescale")
    unit = {"s": 1, "ms": 1e-3, "us": 1e-6, "ns": 1e-9, "ps": 1e-12, "fs": 1e-15}
    seconds_per_tick = int(scale[1]) * unit[scale[2]]
    scopes, names = [], {}
    for line in header.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "$scope":
            scopes.append(tokens[2])
        elif tokens[0] == "$upscope":
            scopes.pop()
        elif tokens[0] == "$var":
            names[".".join(scopes + [tokens[4]])] = tokens[3]
    events = {code: [] for code in names.values()}
    tick = 0
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("$"):
            continue
        if line.startswith("#"):
            new_tick = int(line[1:])
            if new_tick < tick:
                raise ValueError("VCD timestamps move backwards")
            tick = new_tick
            continue
        if line[0] in "01xXzZ":
            value, code = line[0].lower(), line[1:]
        elif line[0] in "bB":
            value, code = line[1:].lower().split()
        else:
            continue
        if code in events:
            events[code].append((tick * seconds_per_tick * 1e6, value))
    return dict(signals={name: events[code] for name, code in names.items()},
                end_us=tick * seconds_per_tick * 1e6, seconds_per_tick=seconds_per_tick)


def value_at(events: list, time_us: float) -> str:
    index = bisect_right([event[0] for event in events], time_us) - 1
    return events[index][1] if index >= 0 else "x"


def intervals(events: list) -> list[tuple[float, float]]:
    windows, start, previous = [], None, None
    for t, value in events:
        if value == "0" and previous != "0":
            start = t
        if value == "1" and previous == "0" and start is not None:
            windows.append((start, t))
            start = None
        previous = value
    return windows


def setup_style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.spines.left": False, "axes.edgecolor": "#c9d1df",
                         "text.color": "#16263d", "axes.labelcolor": "#465469",
                         "xtick.color": "#526077", "ytick.color": "#526077",
                         "figure.facecolor": "#f7f9fc", "axes.facecolor": "white",
                         "savefig.facecolor": "#f7f9fc"})
    return plt


COLORS = ["#4965bc", "#087f8c", "#9b59b6", "#bf6c26", "#576577"]


def tracks(ax, vcd: dict, prefix: str, signals: list[tuple[str, str]], start: float, end: float):
    import math
    for i, (name, label) in enumerate(signals):
        events = vcd["signals"][prefix + "." + name]
        clipped = [(start, value_at(events, start))] + [(t, v) for t, v in events if start < t < end]
        clipped += [(end, value_at(events, end))]
        base = len(signals) - 1 - i
        ys = [base + (0.66 if v == "1" else 0) if v in ("0", "1") else math.nan for _, v in clipped]
        ax.step([t - start for t, _ in clipped], ys, where="post", color=COLORS[i], linewidth=1.8)
        ax.axhline(base, color="#dce3ef", lw=0.55, zorder=0)
    ax.set_yticks([len(signals)-1-i+0.33 for i in range(len(signals))], [label for _, label in signals])
    ax.tick_params(axis="y", length=0, pad=12)
    ax.set_ylim(-0.25, len(signals)+0.35)
    ax.set_xlim(0, end-start)
    ax.set_xlabel("Time from left edge of window (µs)")
    ax.grid(axis="x", color="#edf0f5", lw=0.7)


def footer(fig, result: dict, note: str):
    fig.text(0.055, 0.022, f"Atul Biju Pillai  •  Digital RTL simulation  •  Source {result['commit'][:12]}", fontsize=9, color="#536176")
    fig.text(0.055, 0.045, note, fontsize=9, color="#536176")


def uart_plot(source: Path, output: Path, result: dict, plt):
    vcd = read_vcd(source / "runs/uart-waves/uart.vcd")
    sig = vcd["signals"]
    tx_start = next(t for t, v in sig["tb_uart.tx_busy"] if v == "1")
    tx_end = next(t for t, v in sig["tb_uart.tx_busy"] if v == "0" and t > tx_start)
    rx_start = next(t for t, v in sig["tb_uart.rx_line"] if v == "0")
    rx_valid = next(t for t, v in sig["tb_uart.rx_valid"] if v == "1")
    sent = int(value_at(sig["tb_uart.tx_data"], tx_start), 2)
    received = int(value_at(sig["tb_uart.rx_data"], rx_valid), 2)
    fig, axs = plt.subplots(2, 1, figsize=(14, 8.4))
    fig.subplots_adjust(left=0.13, right=0.96, top=0.80, bottom=0.14, hspace=0.64)
    fig.suptitle("UART · framing and independent receive", x=0.055, y=0.96, ha="left", fontsize=23, fontweight="bold")
    fig.text(0.055, 0.905, "8N1 / LSB first / 100 MHz simulation clock / divider 16 / measured VCD transitions", fontsize=11)
    window = tx_start - 0.06
    tracks(axs[0], vcd, "tb_uart", [("tx_valid", "Request"), ("tx_ready", "Ready"), ("tx_busy", "Busy"), ("tx_line", "TX")], window, tx_end + 0.08)
    axs[0].set_title(f"Transmit 0x{sent:02X} — ten bit periods including start and stop", loc="left", pad=26, fontweight="bold")
    bit_us = (tx_end - tx_start)/10
    for i in range(10):
        a, b = tx_start-window+i*bit_us, tx_start-window+(i+1)*bit_us
        axs[0].axvspan(a, b, color="#087f8c", alpha=0.045 if i % 2 else 0.085, zorder=0)
        label = "Start" if i == 0 else "Stop" if i == 9 else f"D{i-1}={(sent >> (i-1)) & 1}"
        axs[0].text((a+b)/2, 4.02, label, ha="center", fontsize=8.5)
    tracks(axs[1], vcd, "tb_uart", [("rx_line", "RX input"), ("rx_busy", "Busy"), ("rx_valid", "Byte valid"), ("rx_error", "Frame error")], rx_start-0.06, min(vcd["end_us"], rx_valid+0.10))
    axs[1].set_title(f"Receive 0x{received:02X} — independent serial source, one-cycle valid pulse", loc="left", pad=20, fontweight="bold")
    footer(fig, result, "Waveform plot generated from executed Icarus output. Unknown states are left blank; no physical measurement is implied.")
    fig.savefig(output / "uart-waveforms.png", dpi=150)
    plt.close(fig)


def spi_plot(source: Path, output: Path, result: dict, plt):
    vcd = read_vcd(source / "runs/spi-waves/spi.vcd")
    sig = vcd["signals"]
    windows = intervals(sig["tb_spi.cs_n"])
    if len(windows) != 4:
        raise ValueError(f"Expected four captured SPI transactions, found {len(windows)}")
    fig, axs = plt.subplots(4, 1, figsize=(14, 13))
    fig.subplots_adjust(left=0.13, right=0.96, top=0.86, bottom=0.09, hspace=0.68)
    fig.suptitle("SPI · all four clock modes", x=0.055, y=0.967, ha="left", fontsize=23, fontweight="bold")
    fig.text(0.055, 0.935, "MSB first / 100 MHz simulation clock / half-period 4 clocks / 12.5 MHz SCK", fontsize=11)
    fig.text(0.055, 0.912, "Dashed lines identify protocol sampling edges; the behavioral target drives an independent MISO response.", fontsize=10)
    for ax, (start, end) in zip(axs, windows):
        pol = int(value_at(sig["tb_spi.cpol"], start), 2)
        phase = int(value_at(sig["tb_spi.cpha"], start), 2)
        tx = int(value_at(sig["tb_spi.tx_data"], start), 2)
        rx = int(value_at(sig["tb_spi.rx_data"], end), 2)
        left = start-0.025
        tracks(ax, vcd, "tb_spi", [("cs_n", "CS_n"), ("sck", "SCK"), ("mosi", "MOSI"), ("miso", "MISO")], left, end+0.02)
        for t, value in sig["tb_spi.sck"]:
            if start < t < end and value in ("0", "1") and int(value) == (pol if phase else 1-pol):
                ax.axvline(t-left, linestyle="--", color="#72919c", alpha=0.55, linewidth=0.8)
        ax.set_title(f"Mode {pol*2+phase}   CPOL={pol} / CPHA={phase}   ·   MOSI 0x{tx:02X} / received 0x{rx:02X}", loc="left", pad=12, fontweight="bold")
    footer(fig, result, "Measured signal transitions from four executed transfers; the full regression also checks every byte in each mode.")
    fig.savefig(output / "spi-modes.png", dpi=150)
    plt.close(fig)


def mutation_plot(output: Path, result: dict, plt):
    from matplotlib.patches import FancyBboxPatch
    mutations = result["mutations"]
    if not mutations:
        raise ValueError("No executed mutation results")
    smoke = sum(row["smoke"]["outcome"] == "DETECTED" for row in mutations)
    full = sum(row["full"]["outcome"] == "DETECTED" for row in mutations)
    fig = plt.figure(figsize=(14, 9.2))
    fig.suptitle("Verification depth · what the tests catch", x=0.055, y=0.965, ha="left", fontsize=23, fontweight="bold")
    fig.text(0.055, 0.915, "Nine disclosed RTL faults, one source edit at a time, compared against two passing clean baselines", fontsize=11)
    ax = fig.add_axes([0.065, 0.17, 0.37, 0.63])
    ax.bar(["Smoke suite", "Full regression"], [smoke, full], color=["#a1adbd", "#087f8c"], width=0.52)
    ax.set_ylim(0, len(mutations)+1)
    ax.set_yticks(range(0, len(mutations)+1))
    ax.set_ylabel("Seeded faults detected (count)")
    ax.grid(axis="y", color="#dfe5ef", zorder=0)
    ax.set_axisbelow(True)
    for i, count in enumerate((smoke, full)):
        ax.text(i, count+0.12, f"{count} / {len(mutations)}", ha="center", fontsize=16, fontweight="bold")
    matrix = fig.add_axes([0.49, 0.16, 0.46, 0.66])
    matrix.set_xlim(0, 1)
    matrix.set_ylim(-0.7, len(mutations)+0.8)
    matrix.axis("off")
    matrix.text(0, len(mutations)+0.3, "Seeded change", weight="bold")
    matrix.text(0.71, len(mutations)+0.3, "Smoke", ha="center", weight="bold")
    matrix.text(0.92, len(mutations)+0.3, "Full", ha="center", weight="bold")
    short = {"U01": "TX bit order", "U02": "TX stop level", "U03": "TX timer reload", "U04": "TX busy overwrite", "U05": "RX bad stop acceptance", "U06": "RX bit order", "S01": "SPI sampling edge", "S02": "SPI received bit inversion", "S03": "SPI premature completion"}
    for i, row in enumerate(mutations):
        y = len(mutations)-1-i
        matrix.text(0, y+0.24, f"{row['id']}  {short[row['id']]}", va="center", fontsize=10)
        for x, mode in ((0.71, "smoke"), (0.92, "full")):
            status = row[mode]["outcome"]
            detected = status == "DETECTED"
            color = "#d4eeea" if detected else "#f7e6cd"
            matrix.add_patch(FancyBboxPatch((x-0.09, y), 0.18, 0.51, boxstyle="round,pad=0.02", facecolor=color, edgecolor="none"))
            matrix.text(x, y+0.25, "Detected" if detected else status.title(), ha="center", va="center", fontsize=8)
    footer(fig, result, "This is a finite fault-seeding experiment, not general defect coverage or proof that the design has no bugs.")
    fig.savefig(output / "fault-detection.png", dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("build/evidence"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.loads((args.source / "results.json").read_text())
    if result["status"] != "PASS" or len(result["waves"]) != 2 or any(row["outcome"] != "PASS" for row in result["waves"]):
        raise ValueError("A passing executed regression and waveform capture are required")
    output = args.output or args.source / "figures"
    output.mkdir(parents=True, exist_ok=True)
    plt = setup_style()
    uart_plot(args.source, output, result, plt)
    spi_plot(args.source, output, result, plt)
    mutation_plot(output, result, plt)
    print(f"Rendered three evidence plots in {output}")


if __name__ == "__main__":
    main()

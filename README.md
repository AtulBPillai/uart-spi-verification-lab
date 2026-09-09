# UART/SPI Controller Design & Verification Lab

**Atul Biju Pillai** · Digital design and verification

[![RTL verification](https://github.com/AtulBPillai/uart-spi-verification-lab/actions/workflows/verify.yml/badge.svg)](https://github.com/AtulBPillai/uart-spi-verification-lab/actions/workflows/verify.yml)

Synthesizable UART and SPI controllers with independent SystemVerilog protocol checks, functional coverage counters, waveform capture, and a reproducible RTL fault-seeding experiment.

The design sends and receives serial data. The verification environment checks **whether the correct bits appear at the correct time**, then deliberately introduces faults to measure which tests catch them. Everything runs in simulation without an ESP32 or an FPGA.

## Results and waveform plots

The first executed regression passed all configured scenarios:

| Clean full regression | Completed transactions | Scope |
| --- | ---: | --- |
| UART transmit | 774 frames | 258 at each divider: 16, 17, 32 |
| UART receive | 780 frames | 260 at each divider, plus malformed-frame tests |
| SPI full duplex | 3,077 transfers | Modes 0–3; half-periods 2, 3, 7; every payload byte |
| Seeded faults detected | Full: **9/9**; smoke: **4/9** | Nine disclosed source mutations, each compiled and simulated |
| Synthesis structural checks | 3 modules | Yosys process lowering, hierarchy and structural checks |

These are **digital simulation results**, not oscilloscope screenshots or measurements from a manufactured chip. The PNGs below are plotted from real simulator VCD transitions and test logs. Repeated assertion evaluations are not counted as separate test cases.

[Open the current evidence report](https://github.com/AtulBPillai/uart-spi-verification-lab/tree/evidence) · [View CI runs and downloadable logs](https://github.com/AtulBPillai/uart-spi-verification-lab/actions)

The `evidence` branch records the source commit, source-file SHA-256 hashes, full logs, coverage counters, raw VCD files, synthesis logs, and plots. CI refreshes it after a successful run on `main`; earlier evidence remains in that branch's history. Always check the source commit when comparing reports with code changes.

![UART framing and independent receive](https://raw.githubusercontent.com/AtulBPillai/uart-spi-verification-lab/evidence/figures/uart-waveforms.png)

![All four SPI clock modes](https://raw.githubusercontent.com/AtulBPillai/uart-spi-verification-lab/evidence/figures/spi-modes.png)

![Seeded fault detection comparison](https://raw.githubusercontent.com/AtulBPillai/uart-spi-verification-lab/evidence/figures/fault-detection.png)

## What is implemented

- **UART TX/RX:** 8 data bits, no parity, one stop bit (8N1), LSB first, integer baud divider, two-flop RX synchronization, start-bit qualification, stop-bit validation, break recovery and reset abort.
- **SPI controller:** eight-bit, MSB-first full-duplex transfers; CPOL/CPHA modes 0–3; programmable SCK half-period; active-low chip select; configuration latched per transfer; invalid-divider rejection.
- **Verification:** independent UART source and TX frame scoreboard; pin-level SPI target; cycle timing, data integrity, status-pulse, busy-request and reset checks; explicit functional coverage bins.
- **Engineering workflow:** Python regression runner, isolated RTL mutations, machine-readable results, VCD-to-PNG rendering, Docker, GitHub Actions and a Codespaces configuration.

## Run it without hardware

### On GitHub

Open **Actions → RTL verification → Run workflow → main**. A green run includes simulator tests, fault seeding, synthesis checks and evidence publication. Open the `evidence` branch for viewable results. The workflow artifact also contains the raw files; artifacts expire after 30 days, while committed evidence remains in Git.

For an editable terminal in your browser, use **Code → Codespaces → Create codespace on main**, wait for the container to build, then run:

```bash
make all
```

Codespaces availability and usage limits depend on your GitHub account. No live board is connected by this command.

### Locally with Docker

```bash
git clone https://github.com/AtulBPillai/uart-spi-verification-lab.git
cd uart-spi-verification-lab
docker build -t uart-spi-lab .
docker run --rm -v "$PWD/build:/project/build" uart-spi-lab
```

Results appear under `build/evidence/`; open `figures/*.png` or `SUMMARY.md`. The volume command above is for Bash-compatible shells. On Windows, use WSL or adapt the bind-mount path for your shell.

### Locally on Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y git iverilog yosys make python3 python3-matplotlib
make all
```

| Command | Purpose |
| --- | --- |
| `make test` | Check the Python evidence parser and publication safeguards |
| `make baseline` | Run clean full regressions and smoke baselines only |
| `make verify` | Run clean regressions, all mutations and VCD capture |
| `make synthesis` | Run Yosys structural checks on the three RTL modules |
| `make plots` | Render PNGs from a completed `make verify` run |
| `make all` | Run tests, verification, structural checks and plots |

A deliberately faulty mutant emits a failing assertion. That is expected. The overall run passes only if the clean design passes, every specified full-suite mutant is detected, and the waveform runs pass. A compiler error or host timeout never counts as successful fault detection.

To inspect raw waveforms, open `build/evidence/runs/uart-waves/uart.vcd` or `build/evidence/runs/spi-waves/spi.vcd` with a VCD viewer such as GTKWave.

## Explore the engineering

| Location | What to read |
| --- | --- |
| [rtl/](rtl/) | UART transmitter, UART receiver and SPI controller |
| [tb/](tb/) | Independent protocol stimulus, checks and functional bins |
| [docs/protocol-spec.md](docs/protocol-spec.md) | Interfaces, timing equations and integration constraints |
| [docs/verification-plan.md](docs/verification-plan.md) | Requirements mapped to tests and the coverage denominator |
| [docs/fault-experiment.md](docs/fault-experiment.md) | Mutation method, results and limits of the experiment |
| [docs/learning-guide.md](docs/learning-guide.md) | A guided path from serial bits to verification results |
| [scripts/](scripts/) | Reproduce tests, render measured evidence and publish it |

## Scope and limits

This project implements and verifies three RTL blocks. It does not claim UVM compliance, formal proof, ASIC sign-off, timing closure, analog signal-integrity analysis, physical hardware validation, or an original invention of UART, SPI or mutation testing. The two-flop receiver reduces metastability propagation risk; digital simulation does not measure its MTBF.

UART has no parity, FIFO or flow control. SPI has one chip-select output and one CS assertion per byte; it has no burst queue, multi-target arbiter or bus-register interface. The 100 MHz testbench clock is a simulation setting, not a measured maximum operating frequency. Hardware use needs a board-specific wrapper, I/O constraints, clock/reset treatment and timing verification.

The project-specific experiment asks how much a fuller protocol regression improves detection over a minimal smoke suite. The disclosed result supports that narrow comparison; it is not a general bug-detection percentage.

## References

- [Microchip: Getting Started with SPI](https://www.microchip.com/DS90003215)
- [Microchip: SPI clock phase and polarity](https://onlinedocs.microchip.com/oxy/GUID-199548F4-607C-436B-80C7-E4F280C1CAD2-en-US-1/GUID-E0991B55-E5C3-419C-AD24-6746DD6BA228.html)
- [Analog Devices: UART communication protocol](https://www.analog.com/en/resources/analog-dialogue/articles/uart-a-hardware-communication-protocol.html)
- [Icarus Verilog: Getting started](https://steveicarus.github.io/iverilog/usage/getting_started.html)

Project owner: **Atul Biju Pillai**.

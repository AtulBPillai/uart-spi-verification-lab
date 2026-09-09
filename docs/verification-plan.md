# Verification plan and evidence

## Method

The UART TX scoreboard computes the expected serial frame from the submitted byte and elapsed clock count. It does not read the TX state machine. The RX stimulus is a separate serial source with its own bit delays, not the project's TX output. This avoids allowing matching TX/RX bugs to cancel out in a loopback test.

The SPI target observes public SCK/MOSI/CS pins and drives MISO independently. The returned byte is generally `transmitted_byte XOR 0xA7`, so comparing only echoed output cannot accidentally pass the receive check. Tests change data and mode inputs during busy transfers to check configuration latching.

SystemVerilog procedural assertions call `$fatal` on a mismatch. A wall-clock timeout in the Python runner is an infrastructure error. A simulated protocol watchdog is an assertion failure. Both terminate the run, but only the latter counts as detection of an executable seeded RTL fault.

## Requirement mapping

| Requirement | Stimulus and observation | Functional bins |
| --- | --- | --- |
| UART correct payload/framing | All 256 TX bytes, serial line checked each system cycle | 256 byte bins per divider |
| UART exact duration | Check start/data/stop values, busy and completion timing | Checked in every full TX frame |
| UART independent reception | All 256 RX bytes without inserted idle gaps | 256 byte bins per divider |
| UART busy input handling | Submit a second request during an active frame | 1 directed case per divider |
| UART slight period mismatch | Receive two non-palindromic bytes with changed bit periods | 2 directed cases per divider |
| UART malformed stop | Drive stop low, require error and no valid byte | 1 case per divider |
| UART false-start rejection | Low pulse one quarter of a nominal bit period | 1 case per divider |
| UART break recovery | Hold low 30 bits, require one error, return high, send valid byte | 1 case per divider |
| UART reset abort | Reset during simultaneous TX/RX, check no ghost RX, then transfer again | 1 directed case per divider |
| SPI mode/data correctness | Modes 0–3 × half-periods 2,3,7 × 256 TX values | 4 × 256 mode-byte bins; 12 mode-divider bins |
| SPI exact serial timing | Count 16 edges; check each half-period and CS setup/hold | Checked for every full transfer |
| SPI configuration latching | Change CPOL/CPHA/divider/data and pulse valid while busy | 4 cases, one per mode |
| SPI invalid divider | Try half-period 0 and 1 | 2 rejection cases |
| SPI reset abort | Reset mid-word; check idle/no ghost completion; execute valid transfer | 1 case |
| Status integrity | Per-cycle checks for one-cycle successful-operation event pulses | Assertions, not a separate coverage percentage |

UART runs use dividers **16, 17 and 32**. Each completes 258 TX frames and 260 RX frames. SPI completes `4 × 3 × 256 + 4 + 1 = 3,077` transfers. Intentionally aborted or malformed operations are additional scenarios and are not added to successful-transfer counts.

The period-offset inputs use integer nanosecond delays:

| Divider | Nominal bit period | Short-period test | Long-period test |
| ---: | ---: | ---: | ---: |
| 16 | 160 ns | 156 ns | 163 ns |
| 17 | 170 ns | 166 ns | 173 ns |
| 32 | 320 ns | 313 ns | 326 ns |

They are approximately ±2% period perturbations after integer rounding, not exact baud-error limits. The default waveform runs are short demonstrations of correct behavior; the full regressions execute many more cases without VCD dumping.

## What coverage means here

`COVER` lines report explicit functional counters and bitsets. The runner requires the exact planned bin names and complete counts before accepting a full baseline. This is **not line, branch, toggle, state-machine or formal coverage**. A large `checks` count primarily comes from repeated checks each clock; it is not a count of independent tests.

The payload sweep exhausts byte values only. It does not exhaust all possible sequences, clock offsets, input glitches, reset positions or backpressure histories. The tests use repeatable directed cases rather than claiming randomized UVM verification.

## Synthesis check meaning

Yosys reads each RTL module, resolves its hierarchy, lowers processes, optimizes and checks structural consistency. Its logs are retained. This helps detect unimplementable constructs, conflicting drivers and structural problems. It does not map the design to a particular FPGA or standard-cell library, produce timing closure, or establish frequency, area or power on silicon.

## Reproducing a result

Run `make all` from a clean checkout. Inspect `build/evidence/results.json`, `SUMMARY.md`, `runs/`, `synthesis/` and `figures/`. The JSON includes source-file hashes and, in CI, the commit and workflow URL. Simulator-version output is saved separately. Compilation and simulation logs are retained for every baseline and mutant.

The CI `regression` job has read-only repository access. A separate `publish-evidence` job runs only after success on `main` and writes generated reports to `evidence`; it does not change `main`. Pull requests run verification without publishing. Evidence publication uses a fast-forward push and keeps prior evidence commits.

# Learn the project from the signals upward

Project owner: **Atul Biju Pillai**.

## 1. Understand what is being built

RTL describes hardware registers and combinational logic. It is not firmware running on a microcontroller. Here, the UART and SPI blocks could become small parts of an FPGA or chip after integration. The testbench is a simulation-only environment that supplies inputs and checks outputs.

A system clock advances the registers. A finite-state machine (FSM) remembers the current phase of a transaction. A shift register moves payload bits toward a serial output. A counter determines how long each bit or half-clock lasts.

Start by opening `rtl/uart_tx.v`. Find `frame`, `timer` and `bit_index`. Explain what each represents before reading the testbench.

## 2. Read a UART transaction

UART has no shared serial clock wire. Both sides agree on the bit period. An idle-high line falls for a start bit, transmits eight data bits least-significant first, then returns high for the stop bit.

Read the TX plot in the README from left to right. The request is accepted while ready is high. Busy covers the entire ten-bit frame. The TX trace carries the serial bits. Calculate the expected bit sequence for `0xA6` yourself and compare it with the labeled intervals.

In `tb/tb_uart.sv`, find `transmit`. Its reference frame is calculated from the input byte and elapsed cycle count. It does not ask the RTL what state it is in. That separation is the basis of a useful scoreboard.

**Exercise:** Change the demonstration byte in the `waves` branch to `0x53`, run `make all`, and inspect the new UART plot. Predict the output before running it. Leave the full regression in place.

## 3. Understand asynchronous reception and errors

The RX input can change between system-clock edges. The receiver synchronizes it, qualifies a possible start bit, and samples the payload at roughly bit centers. The two-flop chain is a hardware mitigation for asynchronous input; it does not make analog metastability disappear or make the input instantly available.

Read the FSM in `rtl/uart_rx.v` and the state diagram in `protocol-spec.md`. A low stop sample is a framing error. A line held continuously low is a break. Waiting for high after an error prevents the same break from repeatedly appearing to be new data.

**Exercise:** Find the false-start, bad-stop and break cases in `tb_uart.sv`. For each, write down whether a byte event, an error event or neither should occur. Then find the corresponding assertion. Notice that the receiver is driven by an independent source, not by the project's transmitter.

## 4. Compare the four SPI modes

SPI supplies a serial clock. CPOL defines its idle level. CPHA decides whether data is sampled on the first or second edge of each bit period. One edge launches a bit and the other samples it.

Open the SPI plot and compare mode 0 with mode 1, then mode 0 with mode 2. The idle clock and sampling-edge positions change, while the transferred bytes remain the same. Follow the dashed sampling lines across MOSI and MISO.

Read the target model in `tb/tb_spi.sv`. It observes actual pins. It changes MISO after launch edges and reconstructs MOSI only on sampling edges. The full test uses a different return byte, so a broken receive path cannot pass merely by echoing TX data.

**Exercise:** With a 100 MHz system clock and `half_period=5`, calculate the SCK frequency, clock-edge interval and CS-active duration. Answers: 10 MHz, 50 ns and 850 ns. Those are timing calculations; add a test at divider 5 if you want executed evidence for it.

## 5. Learn the difference between a demo and verification

A zero byte looks the same when its bit order is reversed. Therefore a zero-only demonstration cannot catch a bit-reversal bug. Error handling also remains untested if every frame is well formed.

Read `docs/fault-experiment.md`. Follow U01 and U05 from the source substitutions in `scripts/run.py` to the failing assertion logs. Explain why each fault survives smoke and why the full suite catches it. The count of detected mutations measures these deliberately introduced faults, not every defect that might exist.

**Exercise:** Work on a local branch. Add one new, clearly documented mutation and record its result even if it survives. Do not edit the published result table by hand to say it passed; let the runner produce evidence. If you alter a source line used by an existing mutation, update its exact-match definition deliberately.

## 6. Trace one result through the toolchain

Run `make all`. Open the clean simulation log, its coverage lines, `results.json`, the raw VCD and its PNG. Find the source hashes and, for a CI result, the source commit and workflow link. This connects the plotted result to the code that produced it.

Icarus compiles and simulates the RTL. Yosys checks that the RTL can be lowered into a consistent digital structure. Matplotlib plots actual recorded transitions. GitHub Actions repeats the process on commits. Docker packages the tools. None of these steps programs a physical device.

## 7. Know what remains before hardware

Hardware integration needs a chosen board or technology, clock and reset sources, pin assignments, voltage-level compatibility and timing constraints. A UART terminal or SPI target must use matching settings. FPGA synthesis, implementation and static timing analysis must succeed before measuring external signals.

This repository does not provide a board bitstream. Do not connect an ESP32 expecting these Verilog files to run as ESP32 firmware. Use the separate embedded-validation project for microcontroller firmware work; use this project to learn digital controller design and verification.

## Questions to answer in your own words

1. Why can a TX-to-RX loopback hide two matching bugs?
2. Why does the UART receiver wait for high after a bad stop bit?
3. What changes when CPHA changes but CPOL stays fixed?
4. Why does the controller latch its divider at request acceptance?
5. Why is a mutation compile error not evidence that a functional test detected a bug?
6. What does full byte-value coverage leave untested?
7. Why does a 100 MHz simulation clock not prove the design meets 100 MHz timing on a chip?

# Experiment: does deeper protocol checking catch more seeded faults?

## Question and controls

Compare a minimal smoke suite with the full protocol regression on the same nine deliberately mutated RTL designs. First require both suites to pass the clean design. Then copy the RTL to a separate directory, apply exactly one documented source substitution, compile it, and run each suite. Never modify the clean source in place.

The UART smoke suite sends and receives `0x00` at divider 16. Its TX checks inspect bit midpoints and completion, without the full per-cycle timing and busy checks. The SPI smoke suite performs one mode-0, half-period-4 transaction with zero TX and RX data. It still checks basic frame structure and completion. The full suites use the complete directed regressions, including all byte values and error cases. UART mutants are evaluated at divider 16; the clean UART baseline additionally runs at 17 and 32.

## Executed result

| ID | Source change | Smoke | Full |
| --- | --- | --- | --- |
| U01 | Reverse UART TX payload bit order | Survived | Detected |
| U02 | Set UART TX stop level low | Detected | Detected |
| U03 | Reload TX timer with divider instead of divider minus one | Detected | Detected |
| U04 | Accept UART TX input while busy | Survived | Detected |
| U05 | Accept a low UART stop-bit sample | Survived | Detected |
| U06 | Reverse UART RX payload bit order | Survived | Detected |
| S01 | Exchange SPI sampling and launching edge phases | Survived | Detected |
| S02 | Invert each sampled SPI receive bit | Detected | Detected |
| S03 | Enter SPI finishing state after edge 14 instead of 15 | Detected | Detected |

The full suite detected **9/9** seeded faults; smoke detected **4/9**. The five additional detections correspond to faults that a zero-data or error-free demonstration can miss. U03 also illustrates fixed-width arithmetic: at divider 16, assigning 16 to the four-bit counter truncates to zero, making this specific faulty reload especially severe.

Exact source substitutions, simulator outcomes and first failing assertion text are in the generated `results.json`. Full compile and simulation logs allow each result to be inspected. The raw runner initially prints `PASS` for a mutant simulation that completes; the results file labels that mutant outcome `SURVIVED` to avoid confusing it with a passing clean design.

## Outcome definitions

| Outcome | Definition |
| --- | --- |
| DETECTED | Compiles successfully, then simulation terminates on an explicit assertion |
| SURVIVED | Simulation exits successfully with the required pass marker |
| INVALID | Mutated source cannot compile, or compilation times out |
| ERROR | Infrastructure failure, host simulation timeout, missing pass marker, or missing expected coverage |

`INVALID` and `ERROR` do not increase the detection count. A source-pattern mismatch also stops the experiment so an intended mutation cannot silently turn into a no-op.

## Interpretation and limitations

This is a project-specific reproducible experiment, not a claim that mutation testing is a new technique. The fault set is small and chosen deliberately. It contains no probabilistic sample of all realistic RTL defects, no equivalent-mutant analysis and no estimate of field-failure probability. The smoke suite is intentionally minimal; its result should not be generalized to other smoke suites.

Both the testbench and design are authored within this project. Independent pin-level models reduce correlated mistakes but do not eliminate specification errors. External protocol review, additional timing sweeps, formal properties, second-simulator checks and FPGA measurements would strengthen the evidence. They are future work, not claimed completed results.

A useful follow-up experiment is to add a fault not used while designing the tests, predict which existing test should catch it, then run the experiment and document the result. Keep every survivor visible instead of choosing only easy-to-detect faults.

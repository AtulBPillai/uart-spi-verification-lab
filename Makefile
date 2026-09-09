.PHONY: test verify baseline plots synthesis all clean
PYTHON ?= python3

test:
	$(PYTHON) -m unittest discover -s tests -v

verify: test
	$(PYTHON) scripts/run.py

baseline: test
	$(PYTHON) scripts/run.py --baseline-only

plots:
	$(PYTHON) scripts/plot_evidence.py

synthesis:
	mkdir -p build/evidence/synthesis
	@for module in uart_tx uart_rx spi_master; do \
		yosys -Q -T -p "read_verilog rtl/$$module.v; hierarchy -check -top $$module; proc; opt; check -assert; stat" > "build/evidence/synthesis/$$module.log" || exit 1; \
	done

all: verify synthesis plots

clean:
	rm -rf build/

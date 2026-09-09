import unittest
from scripts.run import classify, full_coverage_complete, parse_output


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.compiled = dict(returncode=0, output="", timeout=False)

    def test_assertion_failure_is_detected(self):
        self.assertEqual(classify(self.compiled, dict(returncode=1, output="FATAL: ASSERTION mismatch", timeout=False), "uart"), "DETECTED")

    def test_compile_error_is_not_fault_detection(self):
        self.assertEqual(classify(dict(returncode=1, output="syntax error", timeout=False), None, "uart"), "INVALID")

    def test_host_timeout_is_not_fault_detection(self):
        self.assertEqual(classify(self.compiled, dict(returncode=None, output="", timeout=True), "uart"), "ERROR")

    def test_success_without_pass_marker_is_error(self):
        self.assertEqual(classify(self.compiled, dict(returncode=0, output="", timeout=False), "uart"), "ERROR")

    def test_unexpected_process_failure_is_error(self):
        self.assertEqual(classify(self.compiled, dict(returncode=2, output="cannot open vvp", timeout=False), "uart"), "ERROR")

    def test_coverage_and_metrics_are_parsed(self):
        coverage, metrics = parse_output("COVER uart_tx_bytes 256 256\nRESULT uart div=16 checks=123\n")
        self.assertEqual(coverage[0], dict(name="uart_tx_bytes", hit=256, total=256))
        self.assertEqual(metrics, dict(div=16, checks=123))

    def test_impossible_coverage_rejected(self):
        with self.assertRaises(ValueError):
            parse_output("COVER uart_tx_bytes 257 256")

    def test_missing_coverage_not_vacuously_complete(self):
        self.assertFalse(full_coverage_complete("uart", []))
        self.assertFalse(full_coverage_complete("spi", [dict(name="spi_mode0_bytes", hit=256, total=256)]))


if __name__ == "__main__":
    unittest.main()

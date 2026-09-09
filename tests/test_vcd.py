from pathlib import Path
import tempfile
import unittest
from scripts.plot_evidence import intervals, read_vcd, value_at


class VcdTests(unittest.TestCase):
    def test_timescale_vector_alias_unknown_and_lookup(self):
        text = "$timescale\n 10 ps\n$end\n$scope module tb $end\n$var wire 1 ! sck $end\n$var wire 1 ! alias $end\n$var reg 8 % data [7:0] $end\n$upscope $end\n$enddefinitions $end\n#0\nx!\nbx %\n#100\n0!\nb10100110 %\n#200\n1!\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.vcd"
            path.write_text(text)
            vcd = read_vcd(path)
        self.assertAlmostEqual(vcd["end_us"], 0.002)
        self.assertEqual(vcd["signals"]["tb.sck"], vcd["signals"]["tb.alias"])
        self.assertEqual(value_at(vcd["signals"]["tb.sck"], 0), "x")
        self.assertEqual(value_at(vcd["signals"]["tb.data"], 0.0015), "10100110")
        self.assertEqual(value_at(vcd["signals"]["tb.sck"], -1), "x")

    def test_cs_windows_only_close_after_low(self):
        self.assertEqual(intervals([(0, "x"), (1, "1"), (2, "0"), (3, "1"), (4, "0")]), [(2, 3)])


if __name__ == "__main__":
    unittest.main()

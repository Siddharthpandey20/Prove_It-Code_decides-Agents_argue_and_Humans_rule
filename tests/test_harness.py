"""The harness's outcome rules, without Docker: the child's report is untrusted."""

import importlib.util
import unittest
from pathlib import Path

# The harness runs inside the Linux sandbox image and imports Unix-only modules
# (resource, Unix signals). On Windows the classification tests are skipped
# instead of breaking test discovery; the sandbox tests cover it under Docker.
_spec = importlib.util.spec_from_file_location(
    "proveit_harness", Path(__file__).resolve().parent.parent / "target" / "harness.py")
harness = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(harness)
except (ImportError, AttributeError):  # no `resource` module, or no Unix signals (Windows)
    harness = None


def observed(**overrides):
    base = {"returncode": 0, "timed_out": False, "seconds": 0.02, "peak_rss_mb": 9.0,
            "marker_created": False, "report": {"exception_type": "MemoryError"}}
    base.update(overrides)
    return base


@unittest.skipUnless(harness, "the harness imports Unix-only modules (it runs in the Linux sandbox image)")
class Classify(unittest.TestCase):
    def test_reported_memory_error_alone_is_not_exhaustion(self):
        outcome, _ = harness.classify(observed(), {"exception_type": "MemoryError"})
        self.assertEqual(outcome, "NOT_REPRODUCED")

    def test_memory_error_with_observed_peak_is_exhaustion(self):
        outcome, why = harness.classify(observed(peak_rss_mb=180.0), {"exception_type": "MemoryError"})
        self.assertEqual(outcome, "RESOURCE_EXHAUSTION")
        self.assertIn("180 MB peak", why)

    def test_high_peak_without_memory_error_is_not_exhaustion(self):
        outcome, _ = harness.classify(observed(peak_rss_mb=180.0, report={}), {"exception_type": None})
        self.assertEqual(outcome, "NOT_REPRODUCED")

    def test_marker_still_wins(self):
        outcome, _ = harness.classify(observed(marker_created=True), {"exception_type": "MemoryError"})
        self.assertEqual(outcome, "CODE_EXECUTION")

    def test_busy_timeout_is_exhaustion(self):
        outcome, why = harness.classify(observed(timed_out=True, returncode=-9, seconds=10.0, cpu_seconds=9.7), {})
        self.assertEqual(outcome, "RESOURCE_EXHAUSTION")
        self.assertIn("busy on the CPU", why)

    def test_idle_timeout_is_inconclusive(self):
        # A slow or overloaded host, or a child that waits: past the wall clock but hardly working.
        outcome, why = harness.classify(observed(timed_out=True, returncode=-9, seconds=10.0, cpu_seconds=0.4), {})
        self.assertEqual(outcome, "INCONCLUSIVE")
        self.assertIn("0.4 s of CPU", why)


if __name__ == "__main__":
    unittest.main()

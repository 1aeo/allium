"""Regression tests for bug plan Phase 4: relays with real 0% uptime must be
included in operator reliability averages; only relays with insufficient
data (<30 valid daily points) are skipped.

Before the fix, `if uptime_pct > 0.0` dropped 0%-uptime relays entirely, so
nine relays at 99% plus one at 0% scored ~99% instead of ~89.1%.
"""

import unittest

from allium.lib.uptime_utils import extract_relay_uptime_for_period


def _relay(fp, nickname):
    return {"fingerprint": fp, "nickname": nickname}


def _uptime_entry(fp, values):
    return {"fingerprint": fp, "uptime": {"6_months": {"values": values}}}


class TestZeroUptimeInclusion(unittest.TestCase):
    def _run(self, uptime_relays, operator_relays):
        uptime_data = {"relays": uptime_relays}
        return extract_relay_uptime_for_period(
            operator_relays, uptime_data, "6_months")

    def test_zero_uptime_relay_included_in_average(self):
        # Nine relays at ~99% (raw 989/999) and one at 0% (raw 0), all with
        # 60 days of data.
        relays = [_relay(f"F{i}", f"r{i}") for i in range(10)]
        uptime = [_uptime_entry(f"F{i}", [989] * 60) for i in range(9)]
        uptime.append(_uptime_entry("F9", [0] * 60))

        result = self._run(uptime, relays)
        self.assertEqual(result["valid_relays"], 10)
        avg = sum(result["uptime_values"]) / len(result["uptime_values"])
        # 9 * 99.0 / 10 = 89.1 (the 0% relay pulls the average down)
        self.assertAlmostEqual(avg, 89.1, delta=0.2)
        self.assertEqual(result["relay_breakdown"]["F9"]["uptime"], 0.0)

    def test_insufficient_data_relay_still_skipped(self):
        relays = [_relay("A1", "good"), _relay("A2", "sparse")]
        uptime = [
            _uptime_entry("A1", [989] * 60),
            _uptime_entry("A2", [989] * 10),  # only 10 points: no data
        ]
        result = self._run(uptime, relays)
        self.assertEqual(result["valid_relays"], 1)
        self.assertNotIn("A2", result["relay_breakdown"])

    def test_missing_relay_skipped(self):
        relays = [_relay("B1", "good"), _relay("B2", "absent")]
        uptime = [_uptime_entry("B1", [989] * 60)]
        result = self._run(uptime, relays)
        self.assertEqual(result["valid_relays"], 1)


if __name__ == "__main__":
    unittest.main()

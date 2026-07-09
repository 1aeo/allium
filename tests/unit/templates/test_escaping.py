"""Regression tests for the double-escaping fix (bug plan Phase 1).

Pre-escaped relay fields are wrapped in markupsafe.Markup so Jinja2
autoescape does not escape them a second time, while raw fields remain
covered by autoescape.
"""

import unittest

from jinja2 import Environment
from markupsafe import Markup

from allium.lib.html_escape_utils import create_bulk_escaper, safe_html_escape


def _render(template_src, **ctx):
    env = Environment(autoescape=True)
    return env.from_string(template_src).render(**ctx)


class TestSingleEscaping(unittest.TestCase):
    """Escaped fields must be escaped exactly once end-to-end."""

    def test_safe_html_escape_returns_markup(self):
        out = safe_html_escape("<admin AT example DOT org>")
        self.assertIsInstance(out, Markup)
        self.assertEqual(str(out), "&lt;admin AT example DOT org&gt;")

    def test_contact_escaped_not_double_escaped_under_autoescape(self):
        relay = {"contact": "<admin AT my-mail dot rocks> & friends"}
        create_bulk_escaper().escape_all_relay_fields(relay)
        html_out = _render("{{ relay['contact_escaped'] }}", relay=relay)
        self.assertIn("&lt;admin AT my-mail dot rocks&gt; &amp; friends", html_out)
        self.assertNotIn("&amp;lt;", html_out)
        self.assertNotIn("&amp;amp;", html_out)

    def test_raw_field_still_autoescaped(self):
        relay = {"contact": "<script>alert(1)</script>"}
        create_bulk_escaper().escape_all_relay_fields(relay)
        # Raw field goes through autoescape; escaped field is single-escaped.
        html_out = _render(
            "{{ relay['contact'] }}|{{ relay['contact_escaped'] }}", relay=relay)
        raw_part, escaped_part = html_out.split("|")
        self.assertEqual(raw_part, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertEqual(escaped_part, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotIn("<script>", html_out)

    def test_truncated_fields_single_escaped(self):
        relay = {"nickname": "a<b>" + "x" * 20, "platform": "Tor 0.4.8 on <BSD>"}
        create_bulk_escaper().escape_all_relay_fields(relay)
        out = _render("{{ relay['nickname_truncated'] }}", relay=relay)
        self.assertNotIn("&amp;lt;", out)

    def test_fallbacks_unchanged(self):
        relay = {}
        create_bulk_escaper().escape_all_relay_fields(relay)
        self.assertEqual(relay["nickname_escaped"], "Unknown")
        self.assertEqual(relay["contact_escaped"], "")
        self.assertEqual(relay["aroi_domain_escaped"], "none")


if __name__ == "__main__":
    unittest.main()

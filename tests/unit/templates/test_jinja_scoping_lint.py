#!/usr/bin/env python3
"""
Template lint: detect the Jinja2 "set-inside-for" scoping bug class.

In Jinja2, {% set %} inside a {% for %} block creates a loop-local binding
that does NOT survive past {% endfor %}. Code like:

    {% set found = false %}
    {% for item in items %}
        {% if ... %}{% set found = true %}{% endif %}
    {% endfor %}
    {% if found %}...{% endif %}      {# always reads the outer false! #}

silently always reads the pre-loop value. This caused the contact/family
page IPv6 column to render "N/A" for every relay. The correct patterns are
namespace() objects or precomputing in Python.

This lint flags a variable that is:
  (a) {% set %}-initialized OUTSIDE any for loop,
  (b) re-{% set %} INSIDE a for loop (plain assignment, not ns.attr),
  (c) read after that loop's {% endfor %} before being re-initialized.

Benign same-iteration set-and-use (e.g. css_class per row) and list
mutation via {% set _ = list.append(...) %} are not flagged.
"""

import glob
import os
import re
import unittest

TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'allium', 'templates'
)

_TAG_RE = re.compile(r'({%-?.*?-?%}|{{-?.*?-?}})', re.DOTALL)
_COMMENT_RE = re.compile(r'{#.*?#}', re.DOTALL)
_SET_RE = re.compile(r'{%-?\s*set\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=')
_FOR_RE = re.compile(r'{%-?\s*for\s')
_ENDFOR_RE = re.compile(r'{%-?\s*endfor')
_STRING_RE = re.compile(r"'[^']*'|\"[^\"]*\"")


def find_set_in_for_scoping_bugs(source):
    """Return list of (line_number, variable) scoping violations in a template."""
    source = _COMMENT_RE.sub(lambda m: ' ' * len(m.group(0)), source)
    tags = [(m.start(), m.group(0)) for m in _TAG_RE.finditer(source)]

    def line_of(pos):
        return source.count('\n', 0, pos) + 1

    outer_sets = set()      # vars {% set %} outside any for loop
    for_stack = []          # list of dicts: {candidates: {var: pos_of_set}}
    violations = []

    for idx, (pos, tag) in enumerate(tags):
        if _FOR_RE.match(tag):
            for_stack.append({'candidates': {}})
            continue

        if _ENDFOR_RE.match(tag):
            if not for_stack:
                continue
            frame = for_stack.pop()
            # For each candidate, scan tags after this endfor: a read of the
            # var before a re-{% set %} is a violation.
            for var, set_pos in frame['candidates'].items():
                word_re = re.compile(r'\b%s\b' % re.escape(var))
                for _, later_tag in tags[idx + 1:]:
                    set_match = _SET_RE.match(later_tag)
                    if set_match and set_match.group(1) == var:
                        break  # re-initialized before any read: OK
                    # Ignore var-name occurrences inside string literals.
                    stripped = _STRING_RE.sub('', later_tag)
                    if word_re.search(stripped):
                        violations.append((line_of(set_pos), var))
                        break
            continue

        set_match = _SET_RE.match(tag)
        if not set_match:
            continue
        var = set_match.group(1)
        if not for_stack:
            outer_sets.add(var)
        elif var in outer_sets:
            # Plain re-assignment inside a for loop of a var initialized
            # outside it — candidate for the scoping bug.
            for_stack[-1]['candidates'].setdefault(var, pos)

    return violations


class TestJinjaScopingLint(unittest.TestCase):

    def test_detector_catches_known_bug_pattern(self):
        """Self-test: the detector must flag the exact pattern that broke the
        IPv6 column (guards against detector rot)."""
        buggy = (
            "{% set ipv6_found = false %}\n"
            "{% for addr in relay['or_addresses'] %}\n"
            "    {% if ':' in addr %}{% set ipv6_found = true %}{% endif %}\n"
            "{% endfor %}\n"
            "{% if ipv6_found %}yes{% else %}N/A{% endif %}\n"
        )
        violations = find_set_in_for_scoping_bugs(buggy)
        self.assertEqual([v[1] for v in violations], ['ipv6_found'])

    def test_detector_allows_benign_patterns(self):
        """Same-iteration set-and-use, list mutation, post-loop re-init, and
        namespace() must not be flagged."""
        benign = (
            # set before loop, re-set + read within the same iteration only
            "{% set css = '' %}\n"
            "{% for row in rows %}\n"
            "    {% set css = 'x' %}<td class=\"{{ css }}\">{{ row }}</td>\n"
            "{% endfor %}\n"
            # list mutation via throwaway var
            "{% set vals = [] %}\n"
            "{% for row in rows %}{% set _ = vals.append(row) %}{% endfor %}\n"
            "{{ vals|join(',') }}\n"
            # namespace pattern (the correct fix)
            "{% set ns = namespace(found=false) %}\n"
            "{% for row in rows %}{% set ns.found = true %}{% endfor %}\n"
            "{% if ns.found %}yes{% endif %}\n"
            # re-initialized after the loop before any read
            "{% set flag = false %}\n"
            "{% for row in rows %}{% set flag = true %}{% endfor %}\n"
            "{% set flag = rows|length > 0 %}\n"
            "{% if flag %}yes{% endif %}\n"
        )
        self.assertEqual(find_set_in_for_scoping_bugs(benign), [])

    def test_no_scoping_bugs_in_templates(self):
        """No template may read a set-inside-for variable after endfor."""
        template_files = sorted(glob.glob(os.path.join(TEMPLATE_DIR, '*.html')))
        self.assertGreater(len(template_files), 0, "no templates found")

        all_violations = []
        for path in template_files:
            with open(path, encoding='utf8') as f:
                violations = find_set_in_for_scoping_bugs(f.read())
            for line, var in violations:
                all_violations.append(f"{os.path.basename(path)}:{line}: "
                                      f"'{var}' set inside for-loop is read after endfor "
                                      f"(Jinja2 loop-local scoping — value never escapes the loop)")

        self.assertEqual(all_violations, [],
                         "Jinja2 set-inside-for scoping bugs found:\n" + "\n".join(all_violations))


if __name__ == '__main__':
    unittest.main()

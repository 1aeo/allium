# Documentation Standards

## Rules

1. **No history in active docs** - Migration reports, "before/after", completion dates go to Git history
2. **No emojis in headings** - Allowed in body text only when mirroring UI labels
3. **No dated milestones** - Use Now/Next/Later, not "Q1 2025"
4. **CLI options must match code** - Verify against `python3 allium.py --help`
5. **Output paths must match generated files** - Verify against actual output

## Document Template

Every doc should include:

```markdown
# Title

**Audience**: Users | Contributors | Both
**Scope**: What this covers

[Content]

## How to Verify

[Command or steps to confirm accuracy]
```

## Writing Style

### Do

- Present tense: "Allium generates 18 AROI leaderboards"
- Action-first: "Run `pytest` to execute tests"
- Specific numbers: "Uses ~2.4GB memory with `--apis all`"
- Code references: "See `lib/aroileaders.py`"

### Pasteable-examples convention (operator-facing UI)

When an Allium template surfaces operator-actionable guidance (AROI
fix hints, torrc snippets, command-line invocations), the copy MUST
be pasteable verbatim — never prose. Operators should be able to
copy a `<code>` block and apply it directly without translating
instructions into commands.

- Do: `tor --keygen-family /path/myfamily`
- Do: `ContactInfo ... ciissversion:3 url:foo.bar proof:uri-familyid-ed25519`
- Don't: "Generate a happy-family key on a secure host using the
  appropriate Tor command, then..."

For AROI v3 error categories, the pasteable string lives in
`V3_CATEGORY_LABELS[<category>]['example']` in
`allium/lib/aroi_validation.py`. When upstream `aroivalidator` adds a
new `error_category`, A.8 logs a one-time warning so we know to add a
new entry.

### Don't

- "We successfully implemented..."
- "Migration completed on..."
- "Q1 2025", "Phase 2", dated milestones
- "Before/after" comparisons
- Excessive celebration or narrative

## File Organization

| Directory | Purpose |
|-----------|---------|
| `user-guide/` | End-user workflows |
| `reference/` | Technical specifications |
| `architecture/` | System design |
| `development/` | Contributor workflows |
| `features/planned/` | Future work proposals |

## Review Checklist

Before merging documentation changes:

- [ ] All internal links resolve
- [ ] CLI flags match `allium.py --help`
- [ ] Output paths match generated files
- [ ] No "migration", "completed", "before/after" language
- [ ] No dated milestones (Q1/Q2/etc.)

## Verification Commands

```bash
# Check for history language
grep -rn "migration\|completed on\|before/after" docs/ \
  --include="*.md" --exclude-dir=planned

# Verify CLI documentation matches code
python3 allium/allium.py --help
```

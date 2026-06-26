# Self-evolving unit testing protocol — Stremio Playlists

## Principles

1. **Every bug → regression test** before merge.
2. **Run on every change**: `python -m pytest tests/ -v`
3. **APEX security units** before any VPS deploy (see `tests/APEX.md`).
4. **Protocol evolves**: add a test file when adding a feature module.

## Test map

| Module | Test file | Covers |
|--------|-----------|--------|
| `importer/parser` | `test_parser.py` | U01 edges, bulk/numbered lines |
| `db/repository` | `test_db.py` | U01, U03 idempotency |
| `addon/handlers` | `test_addon.py` | U17 API contracts |
| `resolver/cinemeta` | `test_resolver.py` | U19 third-party (mocked) |
| `sort/sorter` | `test_sort.py` | U01 correctness |
| `security` | `test_security.py` | U04, U05, U06 |

## Commands

```bat
python -m pytest tests/ -v --tb=short
python -m pytest tests/ -v -k security
```

## Changelog (protocol versions)

- **v0.1** — Initial protocol: parser, db, addon, security tests.

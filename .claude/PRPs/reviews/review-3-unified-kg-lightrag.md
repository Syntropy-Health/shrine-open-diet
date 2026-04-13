# Code Review #3 — Unified Diet KG with LightRAG

## Summary
Review of 88 files (+19,933 lines) on `feature/mcp-herbal-botanicals` vs `main`. Covers the MCP server (15 tools), LightRAG ingestion pipeline, food bridge, entity schema, metrics, and cypher queries. Found 8 critical issues (3 Cypher injection, 2 resource leaks, SSRF, fetch timeout, LIKE injection) and 13 important/minor issues.

## Issues Found

### 🔴 Critical (Must Fix)

1. **SSRF via unvalidated `LIGHTRAG_API_URL`** — `src/index.ts:501-508`. No URL scheme/host validation before `fetch()`.
2. **No fetch timeout on LightRAG call** — `src/index.ts:502-510`. Server can hang indefinitely.
3. **LIKE wildcard injection in food bridge** — `scripts/build-food-bridge.ts:148`. `%` and `_` in food names not escaped.
4. **Cypher injection via f-string workspace label** — `ingest_unified.py:404-407`, `fix_unknown_entities.py:172-215`, `kg_metrics.py:94-101`. Labels interpolated without validation.
5. **Neo4j driver/session never closed on exception** — `kg_metrics.py:28-106`, `fix_unknown_entities.py:166-225`. No context managers.

### 🟡 Important (Should Fix)

6. **Unchecked JSON.parse on nutrition_100g** — `HerbalDBAdapter.ts:197-199`. Malformed JSON throws unhandled.
7. **DB handles not closed before process.exit** — `enrich-nutrition.ts:32-41`.
8. **No SIGTERM handler to close DB adapter** — `src/index.ts:569-574`.
9. **fetch_all mutates conn.row_factory** — `ingest_unified.py:60-68`. Side effect on shared state.
10. **Missing type annotations** — `entity_schema.py:237,249`, `ingest_unified.py:165`, `fix_unknown_entities.py:108`.
11. **SQLite connection not closed on exception** — `ingest_unified.py:239-274`.
12. **print() instead of logging** — All Python files.
13. **semantic-search tool has zero test coverage** — No tests for `src/index.ts`.

### 🟢 Minor (Consider)

14. Unused imports: `json` in ingest_unified.py, `os` in test_ingest.py, `sqlite3` inside entity_schema.py function.
15. f-string without placeholders in kg_metrics.py (ruff F541).
16. describe_relationship uses if-chain instead of dispatch dict.
17. query_benchmark.py swallows exceptions silently.

## Good Practices
- Parameterized SQL queries throughout HerbalDBAdapter.ts
- Zod schema validation on all MCP tool inputs
- `tableExists()` guards for optional tables
- Dynamic query builders for optional columns
- Rich entity descriptions for semantic searchability
- Dual config profiles (local/production) with no hardcoded secrets in production config

## Test Coverage
Current: 45 TypeScript tests (5 files), 18 Python tests (1 file)
Missing: MCP tool layer tests (index.ts), semantic-search HTTP paths, Python integration tests

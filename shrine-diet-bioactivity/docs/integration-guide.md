# shrine-diet-bioactivity — Integration Guide

Audience: **Syntropy-Journals engineers** wiring ShrineAgent (or any other MCP
client) to the diet + bioactivity knowledge graph. Covers the unified MCP
tool catalog, tenant scoping contract, and the Clerk `org_id → tenant_id`
mapping rule.

> Status as of 2026-04-19: the server identity, `TenantContext` extraction,
> and client-side scope forwarding on `semantic-search` are **shipped**.
> Server-side Cypher enforcement (`ScopedNeo4JStorage` + FastAPI wrapper)
> and the `search-foods` cross-backend meta-tool are **in flight** under
> the parallel plans `multi-tenant-enforcement-bootstrap` and
> `shrine-diet-bioactivity-unification`. Sections below flag what is
> live vs planned.

---

## 1. What the server is

One MCP server named `shrine-diet-bioactivity` exposes:

| Domain | Backing store | How you query it |
|---|---|---|
| Herbs, phytochemical compounds, compound→food links | SQLite (`herbal_botanicals.db`) | 14 herbal tools |
| Nutrition (326K foods, 90 nutrient keys) | SQLite (`opennutrition_foods.db`) | 8 nutrition tools *(planned — unification)* |
| Semantic graph traversal over the unified KG | LightRAG + Neo4j | `semantic-search` tool |
| Cross-backend food ranking (FooDB ∪ OpenNutrition) | Both SQLite DBs | `search-foods` meta-tool *(planned)* |

One `.mcp.json` entry, one tool catalog, one tenant contract — the two
previous MCP servers (`mcp-herbal-botanicals`, `mcp-opennutrition`) are
being collapsed into this unified server.

## 2. Wiring ShrineAgent (`.mcp.json`)

```json
{
  "mcpServers": {
    "shrine-diet-bioactivity": {
      "command": "node",
      "args": ["/path/to/shrine-diet-bioactivity/build/index.js"],
      "env": {
        "LIGHTRAG_API_URL": "http://localhost:9621"
      }
    }
  }
}
```

The server speaks stdio. `LIGHTRAG_API_URL` is only required if the agent
will call `semantic-search`; all SQLite tools work offline.

## 3. Passing tenant context

Every MCP tool call carries an optional `_meta` field. The agent side sets
`_meta.tenant_id` to the tenant slug; the server extracts it, validates it,
and forwards `scope_filter` downstream.

```ts
// Consumer side (simplified — ShrineAgent)
await client.callTool({
  name: 'semantic-search',
  arguments: { query: 'anti-inflammatory herbs for hsCRP reduction', mode: 'hybrid' },
  _meta: { tenant_id: 'clinic-mayfield' },   // ← the one field that matters
});
```

Server-side extraction (see `src/tenant.ts`):

```ts
const tenant = extractTenantContext(extra._meta);
// tenant = { tenantId: 'clinic-mayfield',
//            scopeFilter: ['shared', 'tenant:clinic-mayfield'] }
validateTenantId(tenant.tenantId);           // throws on malformed slug
```

Omitting `_meta.tenant_id` (or passing an empty / whitespace string) yields
a **shared-only** query — the client still gets the public diet KG, but
sees no tenant-private data.

## 4. Tenant ID format

Tenant IDs are **3–64 char lowercase slugs** matching:

```
/^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/
```

| Rule | Rejected examples | Reason |
|---|---|---|
| Lowercase only | `Clinic-A` | Normalisation and Cypher safety |
| Alphanumeric + hyphen | `clinic_a`, `clinic.a`, `'; DROP TABLE` | Injection-safe |
| No leading/trailing hyphen | `-clinic`, `clinic-` | Parser ambiguity |
| 3–64 chars | `ab`, `a` × 65 | Collision + readability |

Invalid tenant IDs make the tool return `{ isError: true, content: [{ text: "Invalid tenant_id ..." }] }` — the agent should surface the error, not retry blindly.

## 5. Clerk `org_id → tenant_id` mapping

Syntropy-Journals authenticates clinics via Clerk. A Clerk `organization.id`
looks like `org_2abc123XYZ` — uppercase + underscore, **fails** the tenant
regex above. Consumers **must** run every Clerk `org_id` through the
canonical slugifier before passing it into `_meta.tenant_id`.

### Canonical rule

1. Strip the `org_` prefix.
2. Lowercase.
3. Replace underscores with hyphens.
4. Cap at 60 chars (leaves headroom; most Clerk IDs are 24–28 chars).
5. Validate against the tenant regex; reject on mismatch (do **not** silently drop characters beyond the cap).

### Reference implementation

TypeScript reference (`src/clerkOrgMapping.ts` — landing in the enforcement plan):

```ts
export function slugifyClerkOrgId(orgId: string): string {
  const stripped = orgId.startsWith('org_') ? orgId.slice(4) : orgId;
  const slug = stripped.toLowerCase().replace(/_/g, '-').slice(0, 60);
  if (!/^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/.test(slug)) {
    throw new Error(`Cannot map Clerk org_id "${orgId}" to a valid tenant slug`);
  }
  return slug;
}
```

| Clerk `org_id` | Mapped `tenant_id` |
|---|---|
| `org_2abc123XYZ` | `2abc123xyz` |
| `org_CLINIC_MAYFIELD_01` | `clinic-mayfield-01` |
| `org_2x` *(too short after strip)* | **throws** |

The Python equivalent (for data-pipeline code that ingests clinic artifacts
directly) ships alongside the TS version with identical behaviour.

### Why this rule exists

- Clerk IDs are **immutable per organisation** — a clinic's tenant slug is stable for the life of the Clerk org.
- The Cypher filter only understands the slug, so every call site needs the same mapping or tenants split across two scopes and see half their data.
- One-way mapping: the TS utility is the **only** sanctioned path. Don't hand-slug in the UI layer and again on the server — re-derive from `org_id` at the call boundary.

## 6. Scope semantics

Two scope values exist on every Neo4j node and edge:

| Scope value | Meaning | Who can see it |
|---|---|---|
| `shared` | Public diet KG — herbs, compounds, foods, targets, diseases, symptoms | Everyone |
| `tenant:<id>` | Private clinic knowledge — protocols, interventions, outcomes, biomarkers | Only that tenant |

A query always filters with `scope IN ['shared', 'tenant:<caller-id>']`.

```
tenant clinic-mayfield sees:    shared ∪ tenant:clinic-mayfield
tenant clinic-northvale sees:   shared ∪ tenant:clinic-northvale
anonymous / missing tenant:     shared only
```

Tenant writes land **exclusively** on `tenant:<id>` — the ingestion API
refuses to tag writes as `shared` (that's reserved for the shared ETL
pipelines in `lightrag/ingest_unified.py`).

## 7. Enforcement — what's live vs planned

**Live today (client-side scoping):**
- `semantic-search` extracts `tenant_id` from `_meta`, validates, and forwards `scope_filter` to `POST /query` on LightRAG.
- The server also echoes `_tenant` back in `structuredContent` so the agent can audit what scope was applied.

**Planned (server-side enforcement, `multi-tenant-enforcement-bootstrap` plan):**
- Tag all ~7,722 legacy Neo4j nodes with `scope="shared"` + create property indexes.
- `ScopedNeo4JStorage` subclass injects `WHERE n.scope IN $scope_filter` into every read Cypher.
- FastAPI wrapper `scoped_server.py` replaces the upstream LightRAG binary on port 9621, plumbs `scope_filter` through `contextvars.ContextVar` into storage.
- Canary CI test: insert sentinel as `tenant:canary-a`, query as `tenant:canary-b`, assert empty.

**Until that lands, treat tenant isolation as best-effort** — the server
sends `scope_filter`, but the upstream LightRAG binary silently ignores
unknown fields. Don't put data you wouldn't want another clinic to see in
the graph yet.

## 8. Tenant-only entity types

The ingestion API (Phase 4 of the master PRD) accepts four tenant-scoped
entity types that are **not** part of the shared ETL:

| Entity | Meaning |
|---|---|
| `Protocol` | Clinic treatment plan with ordered phases (screening → treatment → validation) |
| `Intervention` | Therapeutic action: compound + route + dosage + frequency (unifies IV, oral, topical) |
| `Outcome` | Structured clinical observation with measurable direction + magnitude |
| `Biomarker` | Lab marker (hsCRP, HbA1c, cortisol, TSH, insulin, IL-6…) linking outcomes to targets |

And seven tenant relationship types: `INCLUDES`, `USES`, `RESULTED_IN`,
`MEASURED_BY`, `INDICATES`, `CONTRAINDICATES`, `SYNERGIZES_WITH`.

Entities/relationships of these types are what `tenant:<id>` scope is for.
Shared ETL skips them — see `lightrag/entity_schema.py` and the
`source_table=None` branch in `lightrag/ingest_unified.py`.

## 9. Example flow

```text
User (clinic practitioner)
  "Which of our anti-inflammation protocols pair well with curcumin for
   patients showing elevated hsCRP?"

ShrineAgent (Clerk session → org_2abcDEF)
  slugifyClerkOrgId('org_2abcDEF')          → '2abcdef'
  client.callTool({
    name: 'semantic-search',
    arguments: {
      query: 'anti-inflammation protocols with curcumin for elevated hsCRP',
      mode: 'hybrid',
    },
    _meta: { tenant_id: '2abcdef' },
  });

shrine-diet-bioactivity MCP
  tenant = extractTenantContext(_meta)      → { tenantId: '2abcdef',
                                                 scopeFilter: ['shared',
                                                               'tenant:2abcdef'] }
  POST /query { query, mode, top_k, scope_filter: ['shared','tenant:2abcdef'] }

LightRAG (post-enforcement)
  ScopedNeo4JStorage: WHERE n.scope IN $scope_filter
  returns: curcumin (shared) + tenant's Protocol/Intervention nodes
```

## 10. Further reading

- `../README.md` — server overview and tool catalog
- `../.claude/PRPs/prds/multi-tenant-diet-kg-mcp.prd.md` — product rationale, phases, success metrics
- `../.claude/PRPs/plans/multi-tenant-enforcement-bootstrap.plan.md` — server-side Cypher enforcement + Clerk mapping utility rollout
- `../.claude/PRPs/plans/shrine-diet-bioactivity-unification.plan.md` — merging OpenNutrition's 8 tools + the `search-foods` meta-tool
- `../src/tenant.ts` — the 55-line source of truth for tenant extraction
- `../src/__tests__/tenant.test.ts` — behavioural contract tests

/**
 * Throwaway inspector for SymMap v2.0 XLSX workbooks.
 *
 * Prints, for each XLSX in cfg.symmap.out_dir:
 *   - sheet names
 *   - column headers per sheet
 *   - first 3 rows per sheet
 *   - total row count per sheet
 *   - non-null counts for cross-reference columns (helpful for spotting
 *     embedded relationships like Link_*_id fields)
 *
 * Usage:
 *   npx tsx scripts/inspect-symmap.ts
 */

import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
// xlsx ships an ESM-friendly entry under /xlsx.mjs; use that to access readFile in node ESM
import * as XLSX from 'xlsx/xlsx.mjs';
import * as fs from 'fs';
// XLSX needs `set_fs` to enable readFile in node ESM mode
XLSX.set_fs(fs);
import { loadDataSources } from '../src/config';

const _dir = typeof __dirname !== 'undefined'
  ? __dirname
  : dirname(fileURLToPath(import.meta.url));

interface SheetSummary {
  name: string;
  rowCount: number;
  headers: string[];
  firstThree: Record<string, unknown>[];
  nonNullCounts: Record<string, number>;
}

function inspectWorkbook(path: string): SheetSummary[] {
  const wb = XLSX.readFile(path);
  return wb.SheetNames.map((name) => {
    const sheet = wb.Sheets[name];
    const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, { defval: null });
    const headers = rows.length > 0 ? Object.keys(rows[0]) : [];
    const nonNullCounts: Record<string, number> = {};
    for (const h of headers) {
      let count = 0;
      for (const r of rows) {
        const v = r[h];
        if (v !== null && v !== undefined && String(v).trim() !== '') count++;
      }
      nonNullCounts[h] = count;
    }
    return {
      name,
      rowCount: rows.length,
      headers,
      firstThree: rows.slice(0, 3),
      nonNullCounts,
    };
  });
}

function main(): void {
  const cfg = loadDataSources().symmap;
  const pkgRoot = resolve(_dir, '..');
  const outDir = resolve(pkgRoot, cfg.out_dir);

  for (const file of cfg.files) {
    const path = resolve(outDir, file);
    process.stdout.write(`\n========== ${file} ==========\n`);
    try {
      const summaries = inspectWorkbook(path);
      for (const s of summaries) {
        process.stdout.write(`\n--- sheet: ${s.name} (rows: ${s.rowCount}) ---\n`);
        process.stdout.write(`headers: ${JSON.stringify(s.headers)}\n`);
        process.stdout.write(`non-null counts: ${JSON.stringify(s.nonNullCounts)}\n`);
        process.stdout.write(`first 3 rows:\n`);
        for (const r of s.firstThree) {
          process.stdout.write(`  ${JSON.stringify(r)}\n`);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'unknown error';
      process.stderr.write(`error inspecting ${file}: ${msg}\n`);
    }
  }
}

main();

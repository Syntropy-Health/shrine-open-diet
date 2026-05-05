import { describe, it, expect } from 'vitest';
import { slugifyClerkOrgId, slugifyClerkOrgIdSafe } from '../clerkOrgMapping.js';

describe('slugifyClerkOrgId — canonical mapping', () => {
  it('strips org_ prefix and lowercases', () => {
    expect(slugifyClerkOrgId('org_2abc123XYZ')).toBe('2abc123xyz');
  });

  it('replaces underscores with hyphens', () => {
    expect(slugifyClerkOrgId('org_CLINIC_MAYFIELD_01')).toBe(
      'clinic-mayfield-01',
    );
  });

  it('is idempotent for already-slug-like input', () => {
    expect(slugifyClerkOrgId('org_clinic-a')).toBe('clinic-a');
    // running it twice: passing an already-clean slug without prefix
    expect(slugifyClerkOrgId('clinic-a')).toBe('clinic-a');
  });

  it('handles lowercase-only Clerk IDs', () => {
    expect(slugifyClerkOrgId('org_abcdefg123')).toBe('abcdefg123');
  });

  it('caps at 60 chars before revalidation', () => {
    const longId = 'org_' + 'a'.repeat(70);
    expect(slugifyClerkOrgId(longId)).toBe('a'.repeat(60));
  });
});

describe('slugifyClerkOrgId — rejections', () => {
  it('throws on empty string', () => {
    expect(() => slugifyClerkOrgId('')).toThrow(/empty/);
  });

  it('throws on whitespace-only', () => {
    expect(() => slugifyClerkOrgId('   ')).toThrow(/empty/);
  });

  it('throws when the slug would start or end with hyphen', () => {
    // Underscore prefix of the body would become a hyphen after mapping.
    expect(() => slugifyClerkOrgId('org__leading')).toThrow(
      /Cannot map Clerk org_id/,
    );
    expect(() => slugifyClerkOrgId('org_trailing_')).toThrow(
      /Cannot map Clerk org_id/,
    );
  });

  it('throws when the stripped body is too short (<3 chars)', () => {
    expect(() => slugifyClerkOrgId('org_2x')).toThrow(/Cannot map Clerk org_id/);
  });

  it('throws on disallowed characters', () => {
    expect(() => slugifyClerkOrgId('org_bad.name')).toThrow(
      /Cannot map Clerk org_id/,
    );
    expect(() => slugifyClerkOrgId("org_'; DROP")).toThrow(
      /Cannot map Clerk org_id/,
    );
  });

  it('throws on non-string input', () => {
    // @ts-expect-error testing invalid runtime input
    expect(() => slugifyClerkOrgId(undefined)).toThrow(/empty/);
    // @ts-expect-error testing invalid runtime input
    expect(() => slugifyClerkOrgId(42)).toThrow();
  });
});

describe('slugifyClerkOrgIdSafe', () => {
  it('returns null for null / undefined / empty', () => {
    expect(slugifyClerkOrgIdSafe(null)).toBeNull();
    expect(slugifyClerkOrgIdSafe(undefined)).toBeNull();
    expect(slugifyClerkOrgIdSafe('')).toBeNull();
  });

  it('returns null instead of throwing on invalid input', () => {
    expect(slugifyClerkOrgIdSafe('org_2x')).toBeNull();
    expect(slugifyClerkOrgIdSafe("org_bad!char")).toBeNull();
  });

  it('returns the slug for valid input', () => {
    expect(slugifyClerkOrgIdSafe('org_2abcDEF')).toBe('2abcdef');
  });
});

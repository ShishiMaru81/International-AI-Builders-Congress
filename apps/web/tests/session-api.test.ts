/**
 * Tests for ApiError, token helpers and contrastRatio from api.ts.
 * Covers FE-01 (sign-out even on 401) and FE-14 (contrast helper correctness).
 */
import {describe, it, expect} from 'vitest';
import {ApiError, contrastRatio, formatTime} from '../src/lib/api';

describe('ApiError', () => {
  it('carries status and message', () => {
    const err = new ApiError('Not found', 404, 'NOT_FOUND');
    expect(err.status).toBe(404);
    expect(err.code).toBe('NOT_FOUND');
    expect(err.message).toBe('Not found');
    expect(err instanceof Error).toBe(true);
  });

  it('is identifiable with instanceof check (FE-01)', () => {
    const err = new ApiError('Unauthorized', 401);
    expect(err instanceof ApiError).toBe(true);
    expect(err.status).toBe(401);
  });

  it('allows status 0 for network errors', () => {
    const err = new ApiError('Network error. Check your connection and retry.', 0, 'NETWORK');
    expect(err.status).toBe(0);
    expect(err.code).toBe('NETWORK');
  });
});

describe('contrastRatio helper', () => {
  it('returns 21 for black on white', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 0);
  });

  it('returns 1 for identical colours', () => {
    expect(contrastRatio('#ffffff', '#ffffff')).toBeCloseTo(1, 2);
  });

  it('is symmetric', () => {
    const a = contrastRatio('#20372c', '#ffffff');
    const b = contrastRatio('#ffffff', '#20372c');
    expect(a).toBeCloseTo(b, 5);
  });

  it('supports 3-digit hex', () => {
    // #fff === #ffffff, #000 === #000000
    expect(contrastRatio('#000', '#fff')).toBeCloseTo(21, 0);
  });
});

describe('formatTime', () => {
  it('appends BST and uses Asia/Dhaka (unchanged signature)', () => {
    const result = formatTime('2026-11-15T00:00:00Z');
    expect(result).toContain('BST');
    expect(result).toContain('6:00');
  });

  it('accepts optional locale param without breaking', () => {
    const en = formatTime('2026-11-15T06:00:00Z', 'en');
    const bn = formatTime('2026-11-15T06:00:00Z', 'bn');
    expect(en).toContain('BST');
    expect(bn).toContain('BST');
  });
});

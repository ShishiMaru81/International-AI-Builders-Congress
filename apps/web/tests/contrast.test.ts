/**
 * FE-14: Verify WCAG AA colour contrast (≥ 4.5:1) for updated design tokens.
 * Uses the contrastRatio helper from api.ts so there is no separate dependency.
 */
import {describe, it, expect} from 'vitest';
import {contrastRatio} from '../src/lib/api';

const WCAG_AA = 4.5;

describe('FE-14 colour contrast', () => {
  // ── App surfaces ──────────────────────────────────────────────
  it('--muted (#55665a) on --surface (#fff) ≥ 4.5:1', () => {
    expect(contrastRatio('#55665a', '#ffffff')).toBeGreaterThanOrEqual(WCAG_AA);
  });

  it('--muted (#55665a) on --canvas (#f5f8f3) ≥ 4.5:1', () => {
    expect(contrastRatio('#55665a', '#f5f8f3')).toBeGreaterThanOrEqual(WCAG_AA);
  });

  it('white text (#fff) on --primary (#0f6a47) ≥ 4.5:1 (primary button)', () => {
    expect(contrastRatio('#ffffff', '#0f6a47')).toBeGreaterThanOrEqual(WCAG_AA);
  });

  it('--text (#20372c) on --surface (#fff) ≥ 4.5:1', () => {
    expect(contrastRatio('#20372c', '#ffffff')).toBeGreaterThanOrEqual(WCAG_AA);
  });

  // ── Landing page text ─────────────────────────────────────────
  it('landing body text (#556555) on landing bg (#f7faf3) ≥ 4.5:1', () => {
    expect(contrastRatio('#556555', '#f7faf3')).toBeGreaterThanOrEqual(WCAG_AA);
  });

  it('landing trust/pillars/principles text (#55665a) on landing bg (#f7faf3) ≥ 4.5:1', () => {
    expect(contrastRatio('#55665a', '#f7faf3')).toBeGreaterThanOrEqual(WCAG_AA);
  });

  // ── Error state ───────────────────────────────────────────────
  it('error text (#a24035) on error bg (#fff0ed) ≥ 4.5:1', () => {
    expect(contrastRatio('#a24035', '#fff0ed')).toBeGreaterThanOrEqual(WCAG_AA);
  });
});

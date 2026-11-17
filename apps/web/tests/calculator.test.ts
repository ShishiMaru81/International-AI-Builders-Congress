import {describe,it,expect} from 'vitest';
import {netReturn,formatTime} from '../src/lib/api';
describe('presentation helpers',()=>{it('illustrates the proceeds formula',()=>{expect(netReturn(42,400,.1,600)).toBe(14520)});it('uses Bangladesh time',()=>{expect(formatTime('2026-11-15T00:00:00Z')).toContain('6:00');expect(formatTime('2026-11-15T00:00:00Z')).toContain('BST')})});

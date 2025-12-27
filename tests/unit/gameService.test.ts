import { describe, it, expect, vi } from 'vitest';
import { generateGameRound } from '../../src/flashtap/services/gameService.js';
import { GameMode } from '../../src/flashtap/types.js';

describe('gameService', () => {
  it('should generate a matching round', async () => {
    const round = await generateGameRound(GameMode.MATCHING, 4);
    expect(round).toBeDefined();
    expect(round.mode).toBe(GameMode.MATCHING);
    expect(round.options).toHaveLength(4);
    expect(round.options.find(o => o.id === round.correctOptionId)).toBeDefined();
  });

  it('should generate a counting round', async () => {
    const round = await generateGameRound(GameMode.COUNTING, 4);
    expect(round).toBeDefined();
    expect(round.mode).toBe(GameMode.COUNTING);
    expect(round.options).toHaveLength(4);
    expect(round.options.find(o => o.id === round.correctOptionId)).toBeDefined();
    expect(Number(round.options[0].content)).not.toBeNaN();
  });

  it('should generate a color round', async () => {
     // Colors mode relies on shapes, so we check if it falls back or returns colors
     const round = await generateGameRound(GameMode.COLORS, 4);
     // It might fallback to matching if no valid color shapes found, but our config has them
     expect(round).toBeDefined();
     // It might return COLORS or MATCHING (if fallback)
     expect([GameMode.COLORS, GameMode.MATCHING]).toContain(round.mode);
     expect(round.options).toHaveLength(4);
  });

  it('should generate a letters round', async () => {
    const round = await generateGameRound(GameMode.LETTERS, 4);
    expect(round).toBeDefined();
    expect(round.mode).toBe(GameMode.LETTERS);
    expect(round.options).toHaveLength(4);

    // Check if question display is a single letter
    expect(round.questionDisplay).toMatch(/^[A-Z]$/);
  });

  it('should generate a shapes round', async () => {
    const round = await generateGameRound(GameMode.SHAPES, 4);
    expect(round).toBeDefined();
    expect(round.mode).toBe(GameMode.SHAPES);
    expect(round.options).toHaveLength(4);
    // All options should be from shape category
    // In our mock/config, we don't have easy access to verify category of options without importing assets,
    // but we can check if content is defined.
  });

  it('should generate a mixed round', async () => {
     // Mixed returns one of the other modes
     const round = await generateGameRound(GameMode.MIXED, 4);
     expect(round).toBeDefined();
     expect([
         GameMode.MATCHING,
         GameMode.COLORS,
         GameMode.SHAPES,
         GameMode.LETTERS,
         GameMode.COUNTING
     ]).toContain(round.mode);
  });
});

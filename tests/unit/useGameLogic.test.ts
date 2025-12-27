import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGameLogic } from '../../src/flashtap/hooks/useGameLogic.js';
import { GameMode } from '../../src/flashtap/types.js';
import * as audioService from '../../src/flashtap/services/audioService.js';

// Mock generateGameRound
vi.mock('../../src/flashtap/services/gameService.js', () => ({
  generateGameRound: vi.fn(() => Promise.resolve({
    questionText: 'Test Question',
    questionDisplay: 'Q',
    successMessage: 'Success',
    options: [
        { id: '1', content: 'A', isCorrect: true },
        { id: '2', content: 'B', isCorrect: false },
        { id: '3', content: 'C', isCorrect: false },
        { id: '4', content: 'D', isCorrect: false }
    ],
    correctOptionId: '1',
    category: 'Test',
    mode: 'MATCHING'
  }))
}));

vi.mock('../../src/flashtap/services/audioService.js', () => ({
  speakText: vi.fn(),
}));

describe('useGameLogic Attempts Logic', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should allow infinite attempts when attempts is undefined', async () => {
        const { result } = renderHook(() => useGameLogic({ mode: GameMode.MATCHING, answerCount: 4 }));

        // Wait for round load
        await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });

        // Click wrong answer multiple times
        act(() => result.current.handleOptionClick('2'));
        expect(result.current.gameState.status).toBe('playing');

        act(() => result.current.handleOptionClick('3'));
        expect(result.current.gameState.status).toBe('playing');

        act(() => result.current.handleOptionClick('4'));
        expect(result.current.gameState.status).toBe('playing');
    });

    it('should fail immediately when attempts is 0 (Sudden Death)', async () => {
        const { result } = renderHook(() => useGameLogic({ mode: GameMode.MATCHING, answerCount: 4, attempts: 0 }));

        await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });

        // One wrong click -> Failure
        act(() => result.current.handleOptionClick('2'));
        expect(result.current.gameState.status).toBe('failure');
    });

    it('should fail after N attempts when attempts > 0', async () => {
        const { result } = renderHook(() => useGameLogic({ mode: GameMode.MATCHING, answerCount: 4, attempts: 2 }));

        await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });

        // 1st wrong click -> Still playing
        act(() => result.current.handleOptionClick('2'));
        expect(result.current.gameState.status).toBe('playing');

        // 2nd wrong click -> Failure
        act(() => result.current.handleOptionClick('3'));
        expect(result.current.gameState.status).toBe('failure');
    });

    it('should fail when remaining options < |attempts| when attempts is negative', async () => {
        // attempts = -2. Options = 4. Max Attempts = 4 - 2 = 2.
        const { result } = renderHook(() => useGameLogic({ mode: GameMode.MATCHING, answerCount: 4, attempts: -2 }));

        await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });

        // 1st wrong click -> Still playing
        act(() => result.current.handleOptionClick('2'));
        expect(result.current.gameState.status).toBe('playing');

        // 2nd wrong click -> Failure (because now only 2 options left: correct + 1 wrong)
        // Wait, logic check:
        // MaxAttempts = 2.
        // Click 1 (Used 1) < 2 -> OK.
        // Click 2 (Used 2) >= 2 -> Fail.
        act(() => result.current.handleOptionClick('3'));
        expect(result.current.gameState.status).toBe('failure');
    });
});

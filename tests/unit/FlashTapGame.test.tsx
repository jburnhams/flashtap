import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent, waitFor, waitForElementToBeRemoved } from '@testing-library/react';
import React from 'react';
import { FlashTapGame } from '../../src/flashtap/FlashTapGame.js';
import * as audioService from '../../src/flashtap/services/audioService.js';
import { GameMode } from '../../src/flashtap/types.js';

// Mock audio service
vi.mock('../../src/flashtap/services/audioService.js', () => ({
  speakText: vi.fn(),
}));

describe('FlashTapGame', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should render the game loading state initially', () => {
        render(<FlashTapGame />);
        expect(screen.getByText(/Loading next game/i)).toBeInTheDocument();
    });

    it('should load a round and display options', async () => {
        render(<FlashTapGame />);

        // Wait for loading to finish
        await waitForElementToBeRemoved(() => screen.queryByText(/Loading next game/i), { timeout: 3000 });

        // Should show options
        const options = await screen.findAllByRole('button');
        expect(options.length).toBeGreaterThanOrEqual(4);
    });

    it('should handle incorrect and correct answers', async () => {
        render(<FlashTapGame />);

        // Wait for loading to finish
        await waitForElementToBeRemoved(() => screen.queryByText(/Loading next game/i), { timeout: 3000 });

        // Get question
        const questionHeading = document.querySelector('h2.text-2xl');
        expect(questionHeading).toBeInTheDocument();
        const questionText = questionHeading?.textContent || '';
        const targetLabel = questionText.replace('Find the ', '');

        // Find correct button
        const buttons = screen.getAllByRole('button');
        const correctButton = buttons.find(b => b.textContent?.includes(targetLabel) || b.querySelector('span')?.textContent === targetLabel);
        expect(correctButton).toBeDefined();

        // Find an incorrect button
        const incorrectButton = buttons.find(b => b !== correctButton && b.querySelector('.text-5xl, .text-6xl'));
        expect(incorrectButton).toBeDefined();

        // Click incorrect
        fireEvent.click(incorrectButton!);

        // Should speak error (mocked)
        expect(audioService.speakText).toHaveBeenCalledWith(expect.stringContaining('No,'));
        expect(incorrectButton).toBeDisabled();

        // Click correct
        fireEvent.click(correctButton!);

        // Should speak success
        expect(audioService.speakText).toHaveBeenCalledWith(expect.stringContaining('correct'));

        // Success modal should appear
        expect(await screen.findByText('Great Job!')).toBeInTheDocument();

        // Score should increase
        expect(screen.getByText(/Score: 10/i)).toBeInTheDocument();
    });

    it('should allow changing configuration via sidebar', async () => {
        render(<FlashTapGame />);

        // Wait for initial load
        await waitForElementToBeRemoved(() => screen.queryByText(/Loading next game/i), { timeout: 3000 });

        // Find "Letters" mode button. It is in the sidebar.
        const lettersBtn = screen.getByText('Letters');
        fireEvent.click(lettersBtn);

        // Wait for the new round to load. The mode change should trigger a new round.
        // We wait for the question to update to match Letters mode pattern.
        await waitFor(() => {
            const heading = document.querySelector('h2.text-2xl');
            expect(heading?.textContent).toMatch(/starts with the letter/i);
        });
    });
});

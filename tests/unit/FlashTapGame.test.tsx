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
        // Options + Sidebar toggle + Volume? (Sidebar toggle only visible on mobile? Volume on hover?)
        // GameArea always renders at least the option buttons.
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

        // Ensure we are in Matching mode (default) and question format is expected
        // If random generator picked something else (unlikely with default config but possible if config changed), this test might need adjustment.
        // Assuming "Find the [Label]"
        expect(questionText).toMatch(/^Find the /);
        const targetLabel = questionText.replace('Find the ', '').trim();
        expect(targetLabel.length).toBeGreaterThan(0);

        // Find correct button - precise match on the label span
        const buttons = screen.getAllByRole('button');

        // Helper to find button by label
        const correctButton = buttons.find(b => {
             const labelSpan = b.querySelector('span.text-sm'); // The label span
             // Also check textContent if span not found, but be careful of content (emoji)
             if (labelSpan) {
                 return labelSpan.textContent === targetLabel;
             }
             // Fallback: check if button text *ends with* target label (assuming format "EMOJI LABEL")
             // But button flex layout might separate them. textContent is "EMOJILABEL".
             return b.textContent?.includes(targetLabel);
        });

        if (!correctButton) {
            console.error('Target Label:', targetLabel);
            console.error('Available Buttons:', buttons.map(b => b.textContent));
        }
        expect(correctButton).toBeDefined();

        // Find an incorrect button
        // Must NOT be the correct button.
        // Must be an option button (check for class or content structure)
        const incorrectButton = buttons.find(b =>
            b !== correctButton &&
            b.querySelector('.text-5xl, .text-6xl') // Has the large emoji class
        );
        expect(incorrectButton).toBeDefined();

        // Click incorrect
        fireEvent.click(incorrectButton!);

        // Should speak error (mocked)
        expect(audioService.speakText).toHaveBeenCalledWith(expect.stringContaining('No,'));
        expect(incorrectButton).toBeDisabled();

        // Clear mock to test success specifically
        vi.mocked(audioService.speakText).mockClear();

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
        // Depending on screen size, sidebar might be hidden or visible.
        // In test env (jsdom), width might be 1024px by default?
        // But regardless, Sidebar buttons are in the DOM.
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

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import React from 'react';
import { FlashTapGame } from '../../src/flashtap/FlashTapGame.js';
import * as audioService from '../../src/flashtap/services/audioService.js';

// Mock audio to avoid errors but we can spy on it
vi.mock('../../src/flashtap/services/audioService.js', () => ({
  speakText: vi.fn(),
}));

describe('Game Integration', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should play a full round of matching game', async () => {
        render(<FlashTapGame />);

        // 1. Initial Load
        expect(screen.getByText(/Loading next game/i)).toBeInTheDocument();

        // 2. Wait for options to appear
        const options = await screen.findAllByRole('button');
        expect(options.length).toBeGreaterThanOrEqual(4);

        // 3. Find the question text
        // The question text is in an h2
        const questionHeading = document.querySelector('h2.text-2xl');
        expect(questionHeading).toBeInTheDocument();
        const questionText = questionHeading?.textContent;
        expect(questionText).toMatch(/Find the/i); // Assuming Matching mode default

        // 4. Determine correct answer from DOM or State?
        // In a real integration test (black box), we have to guess or look at attributes.
        // Our components don't expose "data-correct" explicitly for cheating, but we can deduce it.
        // "Find the Sheep" -> Click button with "Sheep" label/emoji.

        // Let's parse the question "Find the [Label]"
        const label = questionText?.replace('Find the ', '');

        // Find the button with that label/content
        // The buttons contain the emoji (content) and label.

        // We need to find the button that contains the label text (if label is shown)
        // or we need to map label to emoji if only emoji is shown.
        // In Matching mode, we show label:
        // {option.label && <span ...>{option.label}</span>}

        const correctButton = screen.getByText(label!, { selector: 'span' }).closest('button');
        expect(correctButton).toBeInTheDocument();

        // 5. Click the correct answer
        fireEvent.click(correctButton!);

        // 6. Expect Success
        // Success modal appears
        await waitFor(() => {
            expect(screen.getByText('Great Job!')).toBeInTheDocument();
        });

        // 7. Verify Score increased (we can't easily see score without finding the element)
        expect(screen.getByText(/Score: 10/i)).toBeInTheDocument();

        // 8. Click Next Game
        const nextButton = screen.getByText('Next Game ➔');
        fireEvent.click(nextButton);

        // 9. Should go back to loading or new round
        // "Great Job!" should disappear
        await waitFor(() => {
            expect(screen.queryByText('Great Job!')).not.toBeInTheDocument();
        });
    });
});

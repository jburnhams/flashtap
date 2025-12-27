import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import App from '../App';

describe('App', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders the application with navigation tabs', () => {
    render(<App />);
    expect(screen.getByText('Full Game Demo')).toBeInTheDocument();
    expect(screen.getByText('Custom Integration')).toBeInTheDocument();
  });

  it('renders the FlashTap game by default', () => {
    render(<App />);
    // "FlashTap" is in the sidebar of the game
    expect(screen.getByText('FlashTap')).toBeInTheDocument();
  });

  it('switches to custom integration view', () => {
    render(<App />);
    const customTab = screen.getByText('Custom Integration');
    fireEvent.click(customTab);

    // Check if the tab became active
    expect(customTab).toHaveClass('border-purple-600');
  });
});

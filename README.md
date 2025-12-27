# FlashTap Game Library

FlashTap is a reusable React component library for the FlashTap game, designed to be easily embedded into existing React Single Page Applications (SPAs).

## Installation

```bash
npm install flashtap
# or
yarn add flashtap
```

## Basic Usage

To embed the full game experience with the default UI and settings, simply import the `FlashTapGame` component and render it.

```tsx
import { FlashTapGame } from 'flashtap';

function App() {
  return (
    <div style={{ height: '100vh', width: '100%' }}>
      <FlashTapGame />
    </div>
  );
}
```

The `FlashTapGame` component is responsive and will adapt to the container size.

## Custom Integration (Headless Mode)

For skilled developers who want full control over the UI or want to integrate the game mechanics into a custom interface, FlashTap exposes its core logic via the `useGameLogic` hook.

### `useGameLogic` Hook

This hook manages the game state, round generation, scoring, and audio feedback, allowing you to build your own visualization.

```tsx
import { useGameLogic, GameConfig } from 'flashtap';

function CustomGame() {
  // 1. Define initial configuration
  const initialConfig: GameConfig = {
    mode: 'matching', // 'matching' | 'ordering' | 'mixed'
    answerCount: 4,
    attempts: 0 // 0 = Sudden Death, >0 = Fixed attempts
  };

  // 2. Initialize hook
  const {
    gameState,
    handleOptionClick,
    loadRound,
    score
  } = useGameLogic(initialConfig);

  // 3. Render your custom UI
  if (gameState.status === 'loading') return <div>Loading...</div>;

  return (
    <div>
      <h2>Score: {gameState.score}</h2>
      <div className="grid">
        {gameState.currentRound?.options.map(option => (
          <button
            key={option.id}
            onClick={() => handleOptionClick(option.id)}
            className="custom-btn"
          >
            {option.content}
          </button>
        ))}
      </div>
    </div>
  );
}
```

### Types

The library exports TypeScript types to help with integration:

- `GameConfig`: Configuration for the game (mode, difficulty, etc.)
- `GameState`: Current state of the game (playing, success, failure, etc.)
- `GameMode`: Enum for game modes.

## Styling

The library uses Tailwind CSS internally. If you are using the pre-built components, ensure your project handles the CSS (or import the dist styles if provided, typically `import 'flashtap/dist/style.css'` depending on build setup).

If using the headless `useGameLogic` hook, you are responsible for all styling.

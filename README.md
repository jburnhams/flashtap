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

## Custom Integration

If you need to wrap the game in your own layout (e.g., inside a dashboard, or with custom surrounding controls) but still want to use the standard game visualization, you can combine the `useGameLogic` hook with the `GameArea` component.

This allows you to manage the configuration and container while delegating the complex game rendering to the library.

### Example: Custom Wrapper

```tsx
import { useGameLogic, GameArea, GameConfig } from 'flashtap';

function CustomGameWrapper() {
  // 1. Define configuration
  const config: GameConfig = {
    mode: 'matching', // 'matching' | 'ordering' | 'mixed'
    answerCount: 4,
    attempts: 0 // 0 = Sudden Death
  };

  // 2. Initialize logic
  const {
    gameState,
    handleOptionClick,
    loadRound
  } = useGameLogic(config);

  return (
    <div className="my-custom-container" style={{ height: '600px', border: '2px solid #333' }}>
      <header className="custom-header">
         <h2>My Custom Game Header</h2>
      </header>

      {/* 3. Render the GameArea with state from the hook */}
      <GameArea
        gameState={gameState}
        onOptionClick={handleOptionClick}
        onNextRound={loadRound}
      />
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

The library uses Tailwind CSS internally. If you are using the pre-built components (`FlashTapGame` or `GameArea`), ensure your project handles the CSS (or import the dist styles if provided, typically `import 'flashtap/dist/style.css'` depending on build setup).

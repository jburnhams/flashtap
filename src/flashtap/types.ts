export enum GameMode {
  MATCHING = 'MATCHING',
  COLORS = 'COLORS',
  SHAPES = 'SHAPES',
  LETTERS = 'LETTERS',
  COUNTING = 'COUNTING',
  MIXED = 'MIXED'
}

// Represents a static asset (image/emoji) in the config
export interface GameAsset {
  id: string;
  content: string; // URL to image or Emoji
  label: string;   // Spoken name (e.g., "Sheep")
  category: string;
  value?: string | number; // For specific logic
  tags?: string[]; // For filtering (e.g. ['red', 'circle'])
}

export interface GameOption {
  id: string;
  content: string;
  label?: string;
  isCorrect?: boolean;
}

export interface GameRound {
  questionText: string;
  questionDisplay: string;
  successMessage: string; // Spoken when answered correctly
  options: GameOption[];
  correctOptionId: string;
  category: string;
  mode: GameMode;
}

export interface GameConfig {
  mode: GameMode;
  answerCount: number; // 4 to 16 (was difficulty)
  attempts?: number; // 0 = 1 try, >0 = N tries, <0 = (Total - N) tries. Default to undefined (infinite) or handle explicitly.
  categoryFilter?: string; // Optional specific category
}

export interface GameState {
  currentRound: GameRound | null;
  status: 'loading' | 'playing' | 'success' | 'failure';
  score: number;
  streak: number;
  wrongAnswers: string[]; // Track IDs of incorrect guesses for the current round
}

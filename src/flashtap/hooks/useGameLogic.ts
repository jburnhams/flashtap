import { useState, useCallback, useEffect } from 'react';
import { GameConfig, GameState } from '../types.js';
import { generateGameRound } from '../services/gameService.js';
import { speakText } from '../services/audioService.js';

interface UseGameLogicReturn {
  config: GameConfig;
  setConfig: React.Dispatch<React.SetStateAction<GameConfig>>;
  gameState: GameState;
  handleOptionClick: (id: string) => void;
  loadRound: () => Promise<void>;
  attemptsUsed: number;
  maxAttempts: number | null; // null if infinite
}

export const useGameLogic = (initialConfig: GameConfig): UseGameLogicReturn => {
  const [config, setConfig] = useState<GameConfig>(initialConfig);

  const [gameState, setGameState] = useState<GameState>({
    currentRound: null,
    status: 'loading',
    score: 0,
    streak: 0,
    wrongAnswers: [],
  });

  const [attemptsUsed, setAttemptsUsed] = useState(0);

  // Calculate Max Attempts based on config
  // attempts: 0 (Sudden Death -> 1 try), >0 (N tries), <0 (Total - N tries)
  // If undefined, infinite.
  const calculateMaxAttempts = (totalOptions: number): number | null => {
    if (config.attempts === undefined) return null;
    if (config.attempts === 0) return 1;
    if (config.attempts > 0) return config.attempts;
    if (config.attempts < 0) {
      const max = totalOptions + config.attempts; // e.g. 4 + (-2) = 2
      return max > 0 ? max : 1; // Ensure at least 1
    }
    return null;
  };

  const loadRound = useCallback(async () => {
    setGameState(prev => ({ ...prev, status: 'loading', wrongAnswers: [] }));
    setAttemptsUsed(0);
    try {
      const round = await generateGameRound(config.mode, config.answerCount);
      setGameState(prev => ({
        ...prev,
        currentRound: round,
        status: 'playing',
        wrongAnswers: []
      }));
    } catch (error) {
      console.error("Failed to load round:", error);
      setGameState(prev => ({ ...prev, status: 'failure' }));
    }
  }, [config.mode, config.answerCount]);

  // Initial Load handled by consumer or useEffect here?
  // Let's keep it here for simplicity, but allow consumer to control if needed.
  // For the "Run" button case, we might want to trigger it manually.
  // But standard React pattern is "logic hook" just provides function.
  // However, existing Game loads on mount.
  useEffect(() => {
    loadRound();
  }, [loadRound]);


  const handleOptionClick = (id: string) => {
    if (gameState.status !== 'playing' || !gameState.currentRound || gameState.wrongAnswers.includes(id)) return;

    const totalOptions = gameState.currentRound.options.length;
    const max = calculateMaxAttempts(totalOptions);
    const newAttemptsUsed = attemptsUsed + 1;
    setAttemptsUsed(newAttemptsUsed);

    if (id === gameState.currentRound.correctOptionId) {
      // Correct
      speakText(gameState.currentRound.successMessage);
      setGameState(prev => ({
        ...prev,
        status: 'success',
        score: prev.score + 10,
        streak: prev.streak + 1
      }));
    } else {
      // Incorrect
      const clickedOption = gameState.currentRound.options.find(o => o.id === id);
      const correctOption = gameState.currentRound.options.find(o => o.id === gameState.currentRound?.correctOptionId);

      let speech = "No, try again.";
      if (clickedOption && correctOption) {
        const clickedLabel = clickedOption.label || clickedOption.content;
        const correctLabel = correctOption.label || correctOption.content;
        const isNum = !isNaN(Number(clickedLabel));
        const prefix = isNum ? "that's" : "that's a";
        const suffix = isNum ? "not" : "not the";
        speech = `No, ${prefix} ${clickedLabel}, ${suffix} ${correctLabel}`;
      }
      speakText(speech);

      // Check for Loss
      const isLoss = max !== null && newAttemptsUsed >= max;

      if (isLoss) {
         setGameState(prev => ({
            ...prev,
            status: 'failure',
            streak: 0,
            wrongAnswers: [...prev.wrongAnswers, id]
         }));
      } else {
         setGameState(prev => ({
            ...prev,
            streak: 0,
            wrongAnswers: [...prev.wrongAnswers, id]
         }));
      }
    }
  };

  return {
    config,
    setConfig,
    gameState,
    handleOptionClick,
    loadRound,
    attemptsUsed,
    maxAttempts: gameState.currentRound ? calculateMaxAttempts(gameState.currentRound.options.length) : null
  };
};

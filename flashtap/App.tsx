import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import GameArea from './components/GameArea';
import { GameConfig, GameMode, GameState } from './types';
import { generateGameRound } from './services/gameService';
import { speakText } from './services/audioService';

const App: React.FC = () => {
  // Config State
  const [config, setConfig] = useState<GameConfig>({
    mode: GameMode.MATCHING,
    difficulty: 4,
  });

  // Game State
  const [gameState, setGameState] = useState<GameState>({
    currentRound: null,
    status: 'loading',
    score: 0,
    streak: 0,
    wrongAnswers: [],
  });

  // UI State
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Load a new round
  const loadRound = useCallback(async () => {
    setGameState(prev => ({ ...prev, status: 'loading', wrongAnswers: [] }));
    try {
      // In the static version this is instant, but keeping async signature is good practice
      const round = await generateGameRound(config.mode, config.difficulty);
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
  }, [config.mode, config.difficulty]);

  // Initial Load
  useEffect(() => {
    loadRound();
  }, [loadRound]);

  // Handle User Answer
  const handleOptionClick = (id: string) => {
    // Only allow clicking if playing and not already clicked wrong
    if (gameState.status !== 'playing' || !gameState.currentRound || gameState.wrongAnswers.includes(id)) return;

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
      // Incorrect - Construct correction message
      // "No, that's [Clicked Label], not [Correct Label]"
      const clickedOption = gameState.currentRound.options.find(o => o.id === id);
      const correctOption = gameState.currentRound.options.find(o => o.id === gameState.currentRound?.correctOptionId);
      
      if (clickedOption && correctOption) {
        const clickedLabel = clickedOption.label || clickedOption.content;
        const correctLabel = correctOption.label || correctOption.content;
        
        // Simple heuristic to make sentence sound natural
        // If it's a number, say "That's 5, not 3"
        // If it's a thing, say "That's a Sheep, not the Cow"
        
        // Check if label is a number
        const isNum = !isNaN(Number(clickedLabel));
        const prefix = isNum ? "that's" : "that's a";
        const suffix = isNum ? "not" : "not the";

        // Clean up label if it repeats "Red Circle" -> "Red Circle"
        speakText(`No, ${prefix} ${clickedLabel}, ${suffix} ${correctLabel}`);
      } else {
        speakText("No, try again.");
      }

      setGameState(prev => ({
        ...prev,
        // Reset streak on error
        streak: 0, 
        wrongAnswers: [...prev.wrongAnswers, id]
      }));
    }
  };

  const handleNextRound = () => {
    loadRound();
  };

  const handleConfigChange = (newConfig: GameConfig) => {
    setConfig(newConfig);
  };

  return (
    <div className="flex flex-col md:flex-row h-screen w-full bg-slate-100 overflow-hidden">
      <Sidebar 
        config={config} 
        onConfigChange={handleConfigChange} 
        isOpen={isSidebarOpen}
        toggleOpen={() => setIsSidebarOpen(!isSidebarOpen)}
      />
      
      <div className="flex-1 flex flex-col relative w-full h-full">
         {/* Mobile overlay for sidebar */}
         {isSidebarOpen && (
            <div 
              className="absolute inset-0 bg-black/20 z-30 md:hidden"
              onClick={() => setIsSidebarOpen(false)}
            />
         )}

         <GameArea 
            gameState={gameState} 
            onOptionClick={handleOptionClick}
            onNextRound={handleNextRound}
         />
      </div>
    </div>
  );
};

export default App;
import React, { useState } from 'react';
import Sidebar from './components/Sidebar.js';
import GameArea from './components/GameArea.js';
import { GameMode } from './types.js';
import { useGameLogic } from './hooks/useGameLogic.js';

export const FlashTapGame: React.FC = () => {
  const { config, setConfig, gameState, handleOptionClick, loadRound } = useGameLogic({
    mode: GameMode.MATCHING,
    answerCount: 4,
    // Default attempts is undefined -> Infinite in original game
  });

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="flex flex-col md:flex-row h-screen w-full bg-slate-100 overflow-hidden">
      <Sidebar 
        config={config} 
        onConfigChange={setConfig}
        isOpen={isSidebarOpen}
        toggleOpen={() => setIsSidebarOpen(!isSidebarOpen)}
      />
      
      <div className="flex-1 flex flex-col relative w-full h-full">
         {isSidebarOpen && (
            <div 
              className="absolute inset-0 bg-black/20 z-30 md:hidden"
              onClick={() => setIsSidebarOpen(false)}
            />
         )}

         {/* Handle Failure State within Game Area or here?
             Original game didn't really have "Failure" state visible, it just kept going.
             But now 'failure' state is possible if network fails OR if attempts run out (though undefined attempts = infinite).
             For the infinite game, we probably want to auto-reset or show "Try Again" if failure happens?
             But with infinite attempts, 'failure' status only happens on load error.
         */}
         <GameArea 
            gameState={gameState} 
            onOptionClick={handleOptionClick}
            onNextRound={loadRound}
         />
      </div>
    </div>
  );
};

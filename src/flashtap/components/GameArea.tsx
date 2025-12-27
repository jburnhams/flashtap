import React, { useEffect, useState } from 'react';
import { GameState } from '../types.js';
import { Volume2, RefreshCw, Trophy, Star } from 'lucide-react';
import { speakText } from '../services/audioService.js';

interface GameAreaProps {
  gameState: GameState;
  onOptionClick: (id: string) => void;
  onNextRound: () => void;
}

const GameArea: React.FC<GameAreaProps> = ({ gameState, onOptionClick, onNextRound }) => {
  const [lastSpoken, setLastSpoken] = useState<string>("");
  const { currentRound, status, wrongAnswers } = gameState;

  // Auto-speak question when round loads
  useEffect(() => {
    if (status === 'playing' && currentRound && currentRound.questionText !== lastSpoken) {
      // Small delay to allow UI to settle
      const timer = setTimeout(() => {
        speakText(currentRound.questionText);
        setLastSpoken(currentRound.questionText);
      }, 500);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [currentRound, status, lastSpoken]);

  const handleSpeak = () => {
    if (currentRound) {
      speakText(currentRound.questionText);
    }
  };

  if (status === 'loading') {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center animate-pulse">
        <div className="w-24 h-24 rounded-full bg-violet-200 mb-6 flex items-center justify-center">
             <Star className="text-violet-500 animate-spin" size={40}/>
        </div>
        <h2 className="text-3xl font-bold text-slate-400">Loading next game...</h2>
      </div>
    );
  }

  if (!currentRound) return null;

  // Calculate grid columns based on option count
  const optionCount = currentRound.options.length;
  let gridClass = 'grid-cols-2'; // Default 4 (2x2)
  if (optionCount > 4) gridClass = 'grid-cols-3'; // 6 or 9
  if (optionCount > 9) gridClass = 'grid-cols-4'; // 12 or 16
  
  // Mobile adjustments
  const mobileGridClass = optionCount <= 4 ? 'grid-cols-2' : 'grid-cols-3';

  return (
    <div className="flex-1 h-full flex flex-col p-4 md:p-8 max-w-5xl mx-auto w-full overflow-y-auto">
      
      {/* Top Bar: Stats & Controls */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-2">
            <div className="bg-yellow-100 text-yellow-700 px-4 py-2 rounded-full font-bold flex items-center gap-2 shadow-sm">
                <Trophy size={18} />
                <span>Score: {gameState.score}</span>
            </div>
            {gameState.streak > 1 && (
                <div className="bg-orange-100 text-orange-600 px-3 py-1 rounded-full text-sm font-bold animate-bounce">
                    🔥 {gameState.streak} Streak!
                </div>
            )}
        </div>
        <button 
            onClick={onNextRound}
            className="p-3 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-full transition-colors"
            title="Skip Round"
        >
            <RefreshCw size={20} />
        </button>
      </div>

      {/* Question Section */}
      <div className="flex flex-col items-center justify-center mb-8 md:mb-12 relative group">
         <div className="relative">
            <div className="text-8xl md:text-9xl mb-6 filter drop-shadow-lg transition-transform hover:scale-110 cursor-pointer" onClick={handleSpeak}>
                {currentRound.questionDisplay}
            </div>
            <button 
                onClick={(e) => { e.stopPropagation(); handleSpeak(); }}
                className="absolute -bottom-2 -right-2 bg-violet-500 hover:bg-violet-600 text-white p-3 rounded-full shadow-lg transition-transform hover:scale-110 active:scale-95 z-10"
            >
                <Volume2 size={24} />
            </button>
         </div>
         <h2 className="text-2xl md:text-3xl font-bold text-slate-700 mt-4 text-center max-w-lg">
            {currentRound.questionText}
         </h2>
      </div>

      {/* Options Grid */}
      <div className={`grid ${mobileGridClass} md:${gridClass} gap-4 md:gap-6 w-full max-w-3xl mx-auto`}>
        {currentRound.options.map((option) => {
            const isCorrect = option.id === currentRound.correctOptionId;
            const isWrong = wrongAnswers.includes(option.id);
            const isRevealed = status === 'success';
            
            let btnColor = "bg-white hover:bg-slate-50 border-slate-200";
            let textColor = "text-slate-800";
            let stateClass = "";

            if (isWrong) {
                // Keep visually present but greyed out
                stateClass = "opacity-40 grayscale cursor-not-allowed transform-none shadow-none border-slate-100 bg-slate-100";
                btnColor = ""; // Override base color
            } else if (isRevealed) {
                if (isCorrect) {
                    btnColor = "bg-green-400 border-green-500 scale-105 shadow-xl ring-4 ring-green-200";
                    textColor = "text-white";
                } else {
                     // Fade out other remaining options when won
                    stateClass = "opacity-30 pointer-events-none";
                }
            }

            return (
                <button
                    key={option.id}
                    disabled={status !== 'playing' || isWrong}
                    onClick={() => onOptionClick(option.id)}
                    className={`
                        ${btnColor}
                        ${textColor}
                        ${stateClass}
                        aspect-square rounded-3xl border-b-8 active:border-b-0 active:translate-y-2
                        flex flex-col items-center justify-center
                        transition-all duration-300 cursor-pointer relative overflow-hidden
                        group
                    `}
                >
                    <span className="text-5xl md:text-6xl select-none transform transition-transform group-hover:scale-110">
                        {option.content}
                    </span>
                    {option.label && (
                        <span className="mt-2 text-sm font-bold opacity-60 uppercase tracking-wider">
                            {option.label}
                        </span>
                    )}
                </button>
            );
        })}
      </div>

      {/* Success Modal */}
      {status === 'success' && (
          <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
             <div className="absolute inset-0 bg-white/30 backdrop-blur-[2px]" />
             <div className="bg-white p-8 rounded-3xl shadow-2xl transform animate-bounce-short pointer-events-auto text-center border-4 border-green-400">
                <div className="text-6xl mb-4">🎉</div>
                <h3 className="text-4xl font-black text-green-500 mb-2">Great Job!</h3>
                <button 
                    onClick={onNextRound}
                    className="mt-6 bg-green-500 text-white px-8 py-4 rounded-2xl text-xl font-bold hover:bg-green-600 transition-colors shadow-lg active:scale-95"
                >
                    Next Game ➔
                </button>
             </div>
          </div>
      )}

    </div>
  );
};

export default GameArea;
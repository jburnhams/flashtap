import React, { useState, useEffect, useRef } from 'react';
import { GameMode, GameConfig, GameArea, useGameLogic } from 'flashtap';
import { Play, Maximize, RotateCcw } from 'lucide-react';

export const CustomGameRunner: React.FC = () => {
  // Config Form State
  const [config, setConfig] = useState<GameConfig>({
    mode: GameMode.MATCHING,
    answerCount: 4,
    attempts: 0 // Default to Sudden Death as per "Custom Version" feeling
  });
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Runner State
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [startTime, setStartTime] = useState<number>(0);

  // Game Logic Hook
  // We initialize it but don't "loadRound" until run is clicked
  const gameLogic = useGameLogic(config);

  // Refs for fullscreen
  const containerRef = useRef<HTMLDivElement>(null);

  // Sync config changes to hook (though we only really need it when round starts)
  useEffect(() => {
    gameLogic.setConfig(config);
  }, [config]);

  // Monitor Game Status for Win/Loss
  useEffect(() => {
    if (!isRunning) return;

    if (gameLogic.gameState.status === 'success') {
      finishGame(true);
    } else if (gameLogic.gameState.status === 'failure') {
      finishGame(false);
    }
  }, [gameLogic.gameState.status, isRunning]);


  const handleRun = async () => {
    setResult(null);
    setIsRunning(true);
    setStartTime(Date.now());

    // Trigger load round explicitly
    await gameLogic.loadRound();

    // Handle Fullscreen
    if (isFullscreen && containerRef.current) {
      try {
        await containerRef.current.requestFullscreen();
      } catch (e) {
        console.error("Fullscreen failed:", e);
      }
    }
  };

  const finishGame = (won: boolean) => {
    const timeTaken = Date.now() - startTime;
    setIsRunning(false);

    // Exit fullscreen if active
    if (document.fullscreenElement) {
       document.exitFullscreen().catch(() => {});
    }

    setResult({
      won,
      attempts: gameLogic.attemptsUsed,
      timeTaken,
      config: { ...config },
      attemptChoices: gameLogic.gameState.wrongAnswers
    });
  };

  return (
    <div className="flex flex-col h-full w-full bg-slate-50 overflow-y-auto" ref={containerRef}>

      {!isRunning && (
        <div className="bg-white p-6 shadow-md m-4 rounded-xl border border-slate-200">
           <h2 className="text-xl font-bold text-slate-800 mb-4 flex items-center gap-2">
             <RotateCcw className="text-purple-600" />
             Configure Round
           </h2>

           <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 items-end">

              {/* Mode */}
              <div>
                <label className="block text-sm font-bold text-slate-500 mb-2">Game Mode</label>
                <select
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg font-semibold text-slate-700"
                  value={config.mode}
                  onChange={e => setConfig({...config, mode: e.target.value as GameMode})}
                >
                  {Object.values(GameMode).map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              {/* Answer Count */}
              <div>
                <label className="block text-sm font-bold text-slate-500 mb-2">
                    Answer Count: {config.answerCount}
                </label>
                <input
                  type="range" min="4" max="16" step="2"
                  className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
                  value={config.answerCount}
                  onChange={e => setConfig({...config, answerCount: parseInt(e.target.value)})}
                />
              </div>

              {/* Attempts */}
              <div>
                <label className="block text-sm font-bold text-slate-500 mb-2">
                    Attempts
                    <span className="text-xs font-normal text-slate-400 ml-2">
                        (0=1 try, -N=sub from total)
                    </span>
                </label>
                <input
                  type="number"
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg font-semibold text-slate-700"
                  value={config.attempts}
                  onChange={e => setConfig({...config, attempts: parseInt(e.target.value)})}
                />
              </div>

               {/* Fullscreen & Run */}
               <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                     <input
                        type="checkbox"
                        className="w-5 h-5 rounded text-purple-600 focus:ring-purple-500 border-gray-300"
                        checked={isFullscreen}
                        onChange={e => setIsFullscreen(e.target.checked)}
                     />
                     <span className="font-semibold text-slate-600 flex items-center gap-1">
                        <Maximize size={16}/> Fullscreen
                     </span>
                  </label>

                  <button
                    onClick={handleRun}
                    className="flex-1 bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg transition-transform active:scale-95"
                  >
                    <Play fill="currentColor" />
                    RUN
                  </button>
               </div>
           </div>
        </div>
      )}

      {/* Result Container */}
      {!isRunning && result && (
          <div className={`mx-4 mb-4 p-6 bg-white rounded-xl border-l-8 shadow-sm animate-in fade-in slide-in-from-top-4 ${result.won ? 'border-green-500' : 'border-red-500'}`}>
             <h3 className={`text-2xl font-black mb-4 ${result.won ? 'text-green-600' : 'text-red-500'}`}>
                {result.won ? "Round Complete: WON" : "Round Complete: LOST"}
             </h3>
             <div className="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono text-sm bg-slate-50 p-4 rounded-lg">
                <div>
                    <span className="block text-slate-400 text-xs uppercase">Time</span>
                    <span className="font-bold text-slate-700">{result.timeTaken}ms</span>
                </div>
                <div>
                    <span className="block text-slate-400 text-xs uppercase">Attempts Used</span>
                    <span className="font-bold text-slate-700">{result.attempts}</span>
                </div>
                <div>
                    <span className="block text-slate-400 text-xs uppercase">Mode</span>
                    <span className="font-bold text-slate-700">{result.config.mode}</span>
                </div>
                <div>
                     <span className="block text-slate-400 text-xs uppercase">Config</span>
                     <span className="text-xs text-slate-500">{JSON.stringify(result.config)}</span>
                </div>
             </div>
          </div>
      )}

      {/* Game Play Area Container */}
      {isRunning && (
         <div className="flex-1 flex flex-col bg-slate-100 min-h-[500px]">
             <GameArea
                gameState={gameLogic.gameState}
                onOptionClick={gameLogic.handleOptionClick}
                onNextRound={() => {}}
             />
         </div>
      )}

    </div>
  );
};

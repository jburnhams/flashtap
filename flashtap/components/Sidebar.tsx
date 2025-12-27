import React from 'react';
import { GameMode, GameConfig } from '../types';
import { Brain, Palette, Shapes, Type, Calculator, Shuffle } from 'lucide-react';

interface SidebarProps {
  config: GameConfig;
  onConfigChange: (newConfig: GameConfig) => void;
  isOpen: boolean;
  toggleOpen: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ config, onConfigChange, isOpen, toggleOpen }) => {
  
  const handleModeChange = (mode: GameMode) => {
    onConfigChange({ ...config, mode });
  };

  const handleDifficultyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onConfigChange({ ...config, difficulty: parseInt(e.target.value) });
  };

  const modes = [
    { id: GameMode.MATCHING, label: 'Matching', icon: <Brain size={20} /> },
    { id: GameMode.COLORS, label: 'Colors', icon: <Palette size={20} /> },
    { id: GameMode.SHAPES, label: 'Shapes', icon: <Shapes size={20} /> },
    { id: GameMode.LETTERS, label: 'Letters', icon: <Type size={20} /> },
    { id: GameMode.COUNTING, label: 'Counting', icon: <Calculator size={20} /> },
    { id: GameMode.MIXED, label: 'Mixed', icon: <Shuffle size={20} /> },
  ];

  return (
    <>
       {/* Mobile Toggle */}
      <button 
        onClick={toggleOpen}
        className={`fixed top-4 left-4 z-50 p-3 bg-white rounded-full shadow-lg hover:bg-slate-50 transition-all md:hidden`}
      >
        <div className="text-slate-600">
             <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
        </div>
      </button>

      {/* Sidebar Container */}
      <div className={`
        fixed inset-y-0 left-0 z-40 w-80 bg-white/95 backdrop-blur-sm shadow-2xl transform transition-transform duration-300 ease-in-out border-r border-slate-200
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0 md:static md:h-screen md:w-80
      `}>
        <div className="flex flex-col h-full p-6 overflow-y-auto">
          <h1 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-500 mb-8 tracking-tight uppercase italic">
            FlashTap
          </h1>

          {/* Mode Selection */}
          <div className="mb-8">
            <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4">Game Mode</h2>
            <div className="space-y-2">
              {modes.map((m) => (
                <button
                  key={m.id}
                  onClick={() => handleModeChange(m.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 font-semibold text-lg
                    ${config.mode === m.id 
                      ? 'bg-slate-800 text-white shadow-md translate-x-1' 
                      : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'
                    }`}
                >
                  {m.icon}
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Difficulty Slider */}
          <div className="mb-8">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Difficulty</h2>
              <span className="px-3 py-1 bg-slate-100 rounded-lg text-slate-600 font-bold text-sm">
                {config.difficulty} items
              </span>
            </div>
            <input
              type="range"
              min="4"
              max="16"
              step="2"
              value={config.difficulty}
              onChange={handleDifficultyChange}
              className="w-full h-3 bg-slate-200 rounded-full appearance-none cursor-pointer accent-blue-600"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-2 font-medium">
              <span>Easy</span>
              <span>Expert</span>
            </div>
          </div>

          <div className="mt-auto">
             <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
                <p className="text-xs text-slate-500 leading-relaxed">
                   <strong>Tip:</strong> Try "Mixed" mode for a challenge!
                </p>
             </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default Sidebar;
import { useState } from 'react';
import { FlashTapGame } from 'flashtap';
import { CustomGameRunner } from './components/CustomGameRunner';

function App() {
  const [activeTab, setActiveTab] = useState<'full' | 'custom'>('full');

  return (
    <div className="flex flex-col h-screen bg-slate-100">
      {/* Tab Navigation */}
      <div className="bg-white shadow-sm border-b border-slate-200 z-50">
        <div className="max-w-5xl mx-auto flex">
          <button
            onClick={() => setActiveTab('full')}
            className={`flex-1 py-4 text-center font-bold text-lg transition-colors border-b-2
              ${activeTab === 'full'
                ? 'border-blue-600 text-blue-600 bg-blue-50/50'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
          >
            Full Game Demo
          </button>
          <button
            onClick={() => setActiveTab('custom')}
            className={`flex-1 py-4 text-center font-bold text-lg transition-colors border-b-2
              ${activeTab === 'custom'
                ? 'border-purple-600 text-purple-600 bg-purple-50/50'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
          >
            Custom Integration
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 relative overflow-hidden">
        {activeTab === 'full' ? (
          <FlashTapGame />
        ) : (
          <CustomGameRunner />
        )}
      </div>
    </div>
  )
}

export default App;

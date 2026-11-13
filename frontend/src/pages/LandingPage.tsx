import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Sparkles,
  LogIn,
  LogOut,
  History
} from 'lucide-react';
import { useStore } from '../store/useStore';

const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { learner, logout } = useStore();

  const handleTakeNewSession = () => {
    navigate('/roles');
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="w-full min-h-screen flex flex-col items-center justify-between overflow-hidden bg-transparent text-slate-100 relative">
      {/* Top Navbar */}
      <header className="w-full max-w-6xl px-6 py-5 flex items-center justify-between z-20">
        <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => navigate('/')}>
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-700 flex items-center justify-center text-white shadow-md shadow-indigo-600/30">
            <Sparkles size={18} />
          </div>
          <div>
            <span className="font-extrabold text-base tracking-tight text-white block leading-tight">
              Elevate
            </span>
            <span className="text-[10px] text-indigo-400 font-bold uppercase tracking-wider block leading-tight">
              AI Sales Simulator
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {learner ? (
            <div className="flex items-center gap-2">
              <button
                onClick={() => navigate('/dashboard')}
                title="View Past Session Reports"
                className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 shadow-sm text-xs font-semibold text-slate-200 transition-colors cursor-pointer backdrop-blur-md"
              >
                <div className={`w-6 h-6 rounded-full bg-gradient-to-tr ${learner.avatarColor || 'from-indigo-600 to-purple-600'} text-white font-bold text-[10px] flex items-center justify-center`}>
                  {learner.initials || 'AM'}
                </div>
                <span className="hidden sm:inline">{learner.name}</span>
                <span className="text-indigo-400 font-medium text-[10px]">• Dashboard</span>
              </button>

              <button
                onClick={handleLogout}
                title="Sign Out"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-900/80 hover:bg-rose-950/60 text-slate-400 hover:text-rose-300 border border-slate-700/80 shadow-sm text-xs font-semibold transition-colors cursor-pointer backdrop-blur-md"
              >
                <LogOut size={13} />
                <span className="hidden sm:inline">Sign Out</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => navigate('/login')}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-bold transition-all cursor-pointer shadow-sm"
            >
              <LogIn size={14} />
              <span>Learner Sign In</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Hero */}
      <main className="flex-1 flex flex-col items-center justify-center w-full max-w-5xl px-6 py-8 z-10 text-center my-auto">
        <motion.h1
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight mb-6 text-white"
        >
          Practice high-stakes sales. <br />
          <span className="bg-gradient-to-r from-indigo-400 via-purple-300 to-teal-300 bg-clip-text text-transparent">
            Master executive counterparts.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="text-base sm:text-lg text-slate-300 mb-10 max-w-2xl leading-relaxed"
        >
          Simulate realistic conversations with audio-reactive executive personas.
          Get instant tactical scorecards on discovery, objection handling, and walkout risks.
        </motion.p>

        {/* Action CTAs - 2 Buttons: Take New Session and Past Session */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="flex flex-col sm:flex-row gap-3.5 justify-center w-full max-w-md sm:max-w-none"
        >
          <button
            onClick={handleTakeNewSession}
            className="group flex items-center justify-center gap-2 px-8 py-4 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white rounded-2xl font-bold text-sm transition-all shadow-xl shadow-indigo-600/30 cursor-pointer"
          >
            <span>Take New Session</span>
            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </button>

          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center justify-center gap-2 px-7 py-4 bg-slate-900/80 hover:bg-slate-800 text-slate-200 border border-slate-700/80 hover:border-indigo-500/50 rounded-2xl font-bold text-sm transition-all shadow-lg backdrop-blur-md cursor-pointer"
          >
            <History size={16} className="text-indigo-400" />
            <span>Past Session</span>
          </button>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="w-full max-w-6xl px-6 py-4 text-center text-xs text-slate-400 border-t border-slate-800/80 flex items-center justify-between flex-wrap gap-2">
        <span>Elevate AI Sales Simulator • Voice-First Pressure Cooker Practice</span>
        {learner && (
          <button
            onClick={() => navigate('/dashboard')}
            className="text-indigo-400 hover:text-indigo-300 font-semibold cursor-pointer"
          >
            Learner Dashboard →
          </button>
        )}
      </footer>
    </div>
  );
};

export default LandingPage;

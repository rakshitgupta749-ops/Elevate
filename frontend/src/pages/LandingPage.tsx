import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { MessageSquare, ArrowRight, Zap, Shield, Users } from 'lucide-react';

const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden">
      {/* Background gradients */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-purple-900/20 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-cyan-900/20 blur-[120px]" />
      </div>

      <main className="flex-1 flex flex-col items-center justify-center w-full max-w-5xl px-6 py-12 z-10 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-6 inline-flex items-center gap-2 px-3 py-1 rounded-full glass border border-slate-200 text-sm text-slate-600"
        >
          <Zap size={16} className="text-[var(--color-accent)]" />
          <span>Elevate AI Prototype</span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-5xl md:text-7xl font-bold tracking-tight mb-6"
        >
          Practice conversations. <br />
          <span className="text-gradient">Improve professional confidence.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-xl text-slate-600 mb-10 max-w-2xl"
        >
          Simulate real-world conversations with AI-powered professional personas.
          Nail your next interview, pitch, or negotiation.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-col sm:flex-row gap-4"
        >
          <button
            onClick={() => navigate('/topics')}
            className="group flex items-center justify-center gap-2 px-8 py-4 bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white rounded-full font-medium transition-all shadow-lg shadow-purple-600/20"
          >
            Start Practice
            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </button>
          
          <button
            onClick={() => navigate('/history')}
            className="flex items-center justify-center gap-2 px-8 py-4 glass hover:bg-slate-50/10 rounded-full font-medium transition-all text-slate-200 border border-slate-700"
          >
            Past Sessions
          </button>

          <button
            onClick={() => navigate('/roles')}
            className="flex items-center justify-center gap-2 px-8 py-4 glass hover:bg-slate-50/10 rounded-full font-medium transition-all text-slate-300"
          >
            Explore Roles
          </button>
        </motion.div>

        {/* Feature Cards Showcase */}
        <motion.div 
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.5 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-20 w-full"
        >
          <div className="glass-card p-6 rounded-2xl flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-full bg-purple-500/20 flex items-center justify-center mb-4 text-[var(--color-primary)]">
              <MessageSquare size={24} />
            </div>
            <h3 className="text-lg font-semibold mb-2">Realistic Scenarios</h3>
            <p className="text-sm text-slate-600">Context-aware AI that adapts to your industry and experience level.</p>
          </div>
          
          <div className="glass-card p-6 rounded-2xl flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-full bg-cyan-500/20 flex items-center justify-center mb-4 text-[var(--color-accent)]">
              <Users size={24} />
            </div>
            <h3 className="text-lg font-semibold mb-2">Expert Personas</h3>
            <p className="text-sm text-slate-600">Practice with a CTO, CEO, HR Manager, or Sales Director.</p>
          </div>
          
          <div className="glass-card p-6 rounded-2xl flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mb-4 text-emerald-400">
              <Shield size={24} />
            </div>
            <h3 className="text-lg font-semibold mb-2">Safe Environment</h3>
            <p className="text-sm text-slate-600">Make mistakes and learn without real-world consequences.</p>
          </div>
        </motion.div>

      </main>
    </div>
  );
};

export default LandingPage;

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Sparkles,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  Zap,
  Trophy,
  History,
  Shield,
  UserCheck
} from 'lucide-react';
import { useStore } from '../store/useStore';
import type { LearnerProfile } from '../store/useStore';

const DEMO_ADMIN: LearnerProfile = {
  id: 'admin-1',
  name: 'Eleanor Vance',
  email: 'admin@elevate.ai',
  title: 'Lead Administrator & Curriculum Director',
  company: 'Elevate Platform Admin',
  avatarColor: 'from-amber-600 to-rose-600',
  initials: 'EV',
  role: 'admin',
};

const DEMO_LEARNERS: LearnerProfile[] = [
  {
    id: 'learner-1',
    name: 'Alex Morgan',
    email: 'alex.morgan@elevate.ai',
    title: 'Senior Account Executive',
    company: 'Enterprise SaaS Solutions',
    avatarColor: 'from-indigo-600 to-purple-600',
    initials: 'AM',
    role: 'learner',
  },
  {
    id: 'learner-2',
    name: 'Jordan Lee',
    email: 'jordan.lee@elevate.ai',
    title: 'Mid-Market Sales Rep',
    company: 'Cloud Security Systems',
    avatarColor: 'from-teal-600 to-emerald-600',
    initials: 'JL',
    role: 'learner',
  },
  {
    id: 'learner-3',
    name: 'Sarah Chen',
    email: 'sarah.chen@elevate.ai',
    title: 'Strategic Sales Lead',
    company: 'AI & Data Infrastructure',
    avatarColor: 'from-amber-500 to-rose-600',
    initials: 'SC',
    role: 'learner',
  },
];

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { learner, setLearner } = useStore();

  const [mode, setMode] = useState<'learner' | 'admin'>('learner');
  const [email, setEmail] = useState('alex.morgan@elevate.ai');
  const [password, setPassword] = useState('password123');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [selectedDemoId, setSelectedDemoId] = useState<string>('learner-1');

  // If already authenticated, redirect to appropriate page
  React.useEffect(() => {
    if (learner) {
      if (learner.role === 'admin') {
        navigate('/admin', { replace: true });
      } else {
        navigate('/', { replace: true });
      }
    }
  }, [learner, navigate]);

  const handleModeChange = (newMode: 'learner' | 'admin') => {
    setMode(newMode);
    if (newMode === 'admin') {
      setEmail(DEMO_ADMIN.email);
      setSelectedDemoId(DEMO_ADMIN.id);
    } else {
      setEmail(DEMO_LEARNERS[0].email);
      setSelectedDemoId(DEMO_LEARNERS[0].id);
    }
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setLoading(true);
    setTimeout(() => {
      let profile: LearnerProfile;
      if (mode === 'admin') {
        profile = {
          ...DEMO_ADMIN,
          email: email.trim(),
          role: 'admin',
        };
      } else {
        const matched = DEMO_LEARNERS.find(d => d.email.toLowerCase() === email.toLowerCase());
        profile = matched || {
          id: `learner-${Date.now()}`,
          name: email.split('@')[0].replace(/\./g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
          email: email.trim(),
          title: 'Sales Professional',
          company: 'Enterprise Account Team',
          avatarColor: 'from-indigo-600 to-purple-600',
          initials: email.slice(0, 2).toUpperCase(),
          role: 'learner',
        };
      }

      setLearner(profile);
      setLoading(false);
      if (profile.role === 'admin') {
        navigate('/admin');
      } else {
        navigate('/');
      }
    }, 350);
  };

  const handleSelectDemo = (demo: LearnerProfile) => {
    setSelectedDemoId(demo.id);
    setEmail(demo.email);
    setPassword('password123');
    setLearner(demo);
    if (demo.role === 'admin') {
      navigate('/admin');
    } else {
      navigate('/');
    }
  };

  return (
    <div className="w-full min-h-screen bg-transparent text-slate-100 flex flex-col justify-center items-center p-4 md:p-8 relative overflow-hidden select-none">
      {/* Main Container Card in Dark Glassmorphism style */}
      <motion.div
        initial={{ opacity: 0, y: 25, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-xl bg-slate-900/80 border border-slate-800 rounded-3xl p-6 md:p-10 shadow-2xl backdrop-blur-xl relative z-10"
      >
        {/* Portal Role Tabs */}
        <div className="flex p-1 mb-6 rounded-2xl bg-slate-950/80 border border-slate-800">
          <button
            type="button"
            onClick={() => handleModeChange('learner')}
            className={`flex-1 py-2 px-4 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 cursor-pointer ${mode === 'learner'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
              }`}
          >
            <UserCheck size={14} />
            <span>Learner Portal</span>
          </button>
          <button
            type="button"
            onClick={() => handleModeChange('admin')}
            className={`flex-1 py-2 px-4 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 cursor-pointer ${mode === 'admin'
                ? 'bg-amber-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
              }`}
          >
            <Shield size={14} />
            <span>Admin Console</span>
          </button>
        </div>

        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-bold uppercase tracking-wider mb-3 shadow-xs">
            <Sparkles size={14} className="text-indigo-400" />
            <span>Elevate AI Sales Simulator</span>
          </div>

          <h1 className="text-3xl md:text-4xl font-extrabold text-white tracking-tight">
            {mode === 'admin' ? 'Administrator Console' : 'Learner Sign In'}
          </h1>
          <p className="text-sm text-slate-400 mt-2 max-w-md leading-relaxed">
            {mode === 'admin'
              ? 'Configure stakeholder personas, behavioral traits, voice synthesis, and publish curated scenarios for all learners.'
              : 'Explore real-world executive scenarios, review consent disclosures, and launch interactive sales interviews.'}
          </p>
        </div>

        {/* Quick Demo Learner / Admin Switcher */}
        <div className="mb-6 p-4 rounded-2xl bg-slate-950/70 border border-slate-800/80 shadow-inner">
          <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center justify-between">
            <span>{mode === 'admin' ? 'Demo Administrator Profile' : 'Instant Demo Learner Profiles'}</span>
            <span className="text-[10px] text-indigo-400 font-semibold">Click to sign in instantly</span>
          </label>
          <div className={`grid gap-2.5 ${mode === 'admin' ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-3'}`}>
            {mode === 'admin' ? (
              <button
                type="button"
                onClick={() => handleSelectDemo(DEMO_ADMIN)}
                className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between ${selectedDemoId === DEMO_ADMIN.id
                    ? 'bg-amber-950/40 border-amber-500 ring-1 ring-amber-500/30 shadow-md'
                    : 'bg-slate-900/80 border-slate-800 hover:border-slate-700 hover:bg-slate-850 shadow-xs'
                  }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-9 h-9 rounded-xl bg-gradient-to-tr ${DEMO_ADMIN.avatarColor} text-white font-bold text-sm flex items-center justify-center shadow-xs shrink-0`}>
                    {DEMO_ADMIN.initials}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-white">{DEMO_ADMIN.name}</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold uppercase">
                        Admin
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-400 block">{DEMO_ADMIN.title}</span>
                  </div>
                </div>
                <span className="text-[11px] font-semibold text-amber-400">Launch Console →</span>
              </button>
            ) : (
              DEMO_LEARNERS.map((demo) => {
                const isSelected = selectedDemoId === demo.id;
                return (
                  <button
                    key={demo.id}
                    type="button"
                    onClick={() => handleSelectDemo(demo)}
                    className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between ${isSelected
                        ? 'bg-indigo-950/40 border-indigo-500 ring-1 ring-indigo-500/30 shadow-md'
                        : 'bg-slate-900/80 border-slate-800 hover:border-slate-700 hover:bg-slate-850 shadow-xs'
                      }`}
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <div className={`w-7 h-7 rounded-lg bg-gradient-to-tr ${demo.avatarColor} text-white font-bold text-xs flex items-center justify-center shadow-xs shrink-0`}>
                        {demo.initials}
                      </div>
                      <span className="font-bold text-xs text-white truncate">
                        {demo.name}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400 truncate block">
                      {demo.title}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Divider */}
        <div className="relative flex items-center justify-center my-6">
          <div className="border-t border-slate-800 w-full" />
          <span className="bg-slate-900 px-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wider absolute">
            Or sign in with email
          </span>
        </div>

        {/* Login Form */}
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              {mode === 'admin' ? 'Administrator Email' : 'Learner Email'}
            </label>
            <div className="relative flex items-center">
              <Mail size={16} className="absolute left-3.5 text-slate-500" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={mode === 'admin' ? 'admin@elevate.ai' : 'name@company.com'}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 focus:border-indigo-500 transition-all shadow-inner"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center justify-between">
              <span>Password</span>
              <span className="text-[11px] text-slate-500 font-normal">Default: any password</span>
            </label>
            <div className="relative flex items-center">
              <Lock size={16} className="absolute left-3.5 text-slate-500" />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-10 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 focus:border-indigo-500 transition-all shadow-inner"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs pt-1">
            <label className="flex items-center gap-2 cursor-pointer text-slate-400 hover:text-slate-300">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-indigo-500/20"
              />
              <span>Remember session profile</span>
            </label>
            <span className="text-indigo-400 hover:text-indigo-300 font-semibold cursor-pointer">
              Enterprise SSO
            </span>
          </div>

          {/* Submit CTA */}
          <button
            type="submit"
            disabled={loading}
            className={`w-full mt-3 py-3.5 px-6 rounded-xl font-bold text-sm shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 text-white ${mode === 'admin'
                ? 'bg-gradient-to-r from-amber-600 to-rose-600 hover:from-amber-500 hover:to-rose-500 shadow-amber-600/30'
                : 'bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 shadow-indigo-600/30'
              }`}
          >
            {loading ? (
              <span>Authenticating...</span>
            ) : (
              <>
                <span>{mode === 'admin' ? 'Open Admin Console' : 'Sign In & Continue to Home'}</span>
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        {/* Feature Highlights Footer */}
        <div className="grid grid-cols-3 gap-3 pt-6 mt-6 border-t border-slate-800 text-center text-[11px] text-slate-400">
          <div className="flex flex-col items-center gap-1">
            <History size={16} className="text-indigo-400" />
            <span className="font-medium">Past Reports</span>
          </div>
          <div className="flex flex-col items-center gap-1">
            <Trophy size={16} className="text-amber-400" />
            <span className="font-medium">Executive Scores</span>
          </div>
          <div className="flex flex-col items-center gap-1">
            <Zap size={16} className="text-teal-400" />
            <span className="font-medium">Audio Blob Live</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default LoginPage;

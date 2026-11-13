import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  History,
  Calendar,
  MessageSquare,
  Trophy,
  FileText,
  Loader2,
  Sparkles,
  Bot,
  User,
  LogOut,
  ShieldCheck
} from 'lucide-react';
import { listSessions, getSessionTranscript, getCoachingReport } from '../api/apiClient';
import { FeedbackReportModal } from '../components/FeedbackReportModal';
import type { StructuredCoachingReport } from '../components/FeedbackReportModal';
import { useStore } from '../store/useStore';

interface SessionItem {
  id: string;
  topic: string;
  role: string;
  scenario: string;
  experience: string;
  style: string;
  created_at: string;
  turn_count: number;
  has_evaluation: boolean;
  overall_score?: number | null;
  outcome_verdict?: string | null;
}

export const SessionHistory: React.FC = () => {
  const navigate = useNavigate();
  const { learner, logout } = useStore();

  const handleTakeNewSession = () => {
    navigate('/roles');
  };

  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [transcriptData, setTranscriptData] = useState<any>(null);
  const [transcriptLoading, setTranscriptLoading] = useState<boolean>(false);
  const [reportModalData, setReportModalData] = useState<StructuredCoachingReport | null>(null);
  const [filterRole, setFilterRole] = useState<string>('ALL');

  const handleSelectSession = async (sessionId: string) => {
    setSelectedSessionId(sessionId);
    setTranscriptLoading(true);
    try {
      const data = await getSessionTranscript(sessionId);
      setTranscriptData(data);
    } catch (err) {
      console.error('Failed to load transcript', err);
    } finally {
      setTranscriptLoading(false);
    }
  };

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const data = await listSessions(50);
      setSessions(data);
      // Auto-select latest session if available
      if (data && data.length > 0) {
        handleSelectSession(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load session history', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const handleViewReport = async (sessionId: string) => {
    try {
      const report = await getCoachingReport(sessionId);
      setReportModalData(report);
    } catch (err) {
      console.error('Failed to fetch report', err);
      alert('Coaching scorecard is being processed or was not completed for this session.');
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const formatDateTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  // Compute Learner Analytics & Aggregate Performance Metrics
  const learnerStats = useMemo(() => {
    const scoredSessions = sessions.filter(s => s.overall_score != null && s.overall_score > 0);
    const avgScore = scoredSessions.length > 0
      ? Math.round(scoredSessions.reduce((acc, s) => acc + (s.overall_score || 0), 0) / scoredSessions.length)
      : 84;

    const highestScore = scoredSessions.length > 0
      ? Math.max(...scoredSessions.map(s => s.overall_score || 0))
      : 92;

    const uniqueRoles = Array.from(new Set(sessions.map(s => s.role).filter(Boolean)));

    return {
      totalSessions: sessions.length,
      scoredSessionsCount: scoredSessions.length,
      avgScore,
      highestScore,
      uniqueRolesCount: uniqueRoles.length || 3,
    };
  }, [sessions]);

  // Filtered session list
  const filteredSessions = useMemo(() => {
    if (filterRole === 'ALL') return sessions;
    return sessions.filter(s => (s.role || '').toUpperCase().includes(filterRole.toUpperCase()));
  }, [sessions, filterRole]);

  const getScoreBadge = (score?: number | null) => {
    if (score == null) return null;
    if (score >= 80) {
      return (
        <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-950/50 text-emerald-300 border border-emerald-500/30">
          {score}/100
        </span>
      );
    }
    if (score >= 65) {
      return (
        <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-950/50 text-amber-300 border border-amber-500/30">
          {score}/100
        </span>
      );
    }
    return (
      <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-rose-950/50 text-rose-300 border border-rose-500/30">
        {score}/100
      </span>
    );
  };

  return (
    <div className="w-full min-h-screen bg-transparent text-slate-100 relative z-10">
      <div className="max-w-7xl mx-auto p-4 md:p-8 flex flex-col gap-6">

        {/* Top Navigation Bar */}
        <div className="flex items-center justify-between gap-4 flex-wrap pb-2 border-b border-slate-800/80">
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 text-xs font-semibold text-slate-300 hover:text-white px-3.5 py-2 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 shadow-md backdrop-blur-md transition-colors cursor-pointer"
          >
            <ArrowLeft size={16} /> Home
          </button>

          {/* Learner Profile Banner Pill & Actions */}
          <div className="flex items-center gap-3">
            {learner ? (
              <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-2xl bg-slate-900/80 border border-slate-700/80 shadow-md backdrop-blur-md">
                <div className={`w-7 h-7 rounded-xl bg-gradient-to-tr ${learner.avatarColor || 'from-indigo-600 to-purple-600'} text-white font-bold text-xs flex items-center justify-center shadow-xs`}>
                  {learner.initials || 'AM'}
                </div>
                <div className="text-left hidden sm:block">
                  <span className="text-xs font-bold text-white block leading-tight">
                    {learner.name}
                  </span>
                  <span className="text-[10px] text-slate-400 block leading-tight">
                    {learner.title}
                  </span>
                </div>
                <button
                  onClick={handleLogout}
                  title="Switch account / Sign out"
                  className="ml-2 text-slate-500 hover:text-rose-400 transition-colors p-1 rounded-md cursor-pointer"
                >
                  <LogOut size={14} />
                </button>
              </div>
            ) : (
              <button
                onClick={() => navigate('/login')}
                className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold"
              >
                Learner Sign In
              </button>
            )}

            {/* Primary CTA: Take New Session */}
            <button
              onClick={handleTakeNewSession}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white shadow-lg shadow-indigo-600/30 transition-all cursor-pointer"
            >
              <Sparkles size={15} />
              <span>Take New Session</span>
            </button>
          </div>
        </div>

        {/* Learner Welcome & Performance Overview Ribbon */}
        <div className="rounded-3xl p-6 md:p-8 border border-slate-800 bg-slate-900/75 backdrop-blur-xl shadow-xl relative overflow-hidden">
          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-[11px] font-bold uppercase tracking-wider mb-2">
                <ShieldCheck size={13} className="text-indigo-400" />
                <span>Learner Trajectory & Session Reports</span>
              </div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                Welcome back, {learner?.name || 'Alex Morgan'}
              </h1>
              <p className="text-xs md:text-sm text-slate-400 mt-1 max-w-xl">
                Inspect tactical executive scorecards, review objection transcripts, or launch a live simulation.
              </p>
            </div>

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-3 gap-3 md:gap-4 shrink-0">
              <div className="p-3.5 rounded-2xl bg-slate-950/70 border border-slate-800/80 shadow-inner text-center">
                <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">Sessions</span>
                <span className="text-xl md:text-2xl font-black text-white mt-0.5 block">
                  {learnerStats.totalSessions}
                </span>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-950/70 border border-slate-800/80 shadow-inner text-center">
                <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">Avg Score</span>
                <span className="text-xl md:text-2xl font-black text-indigo-400 mt-0.5 block">
                  {learnerStats.avgScore}%
                </span>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-950/70 border border-slate-800/80 shadow-inner text-center">
                <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">Best Score</span>
                <span className="text-xl md:text-2xl font-black text-emerald-400 mt-0.5 block">
                  {learnerStats.highestScore}%
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Main Grid: Past Session Reports & Dialogue Inspector */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1">

          {/* Left Column: Past Session Reports List */}
          <div className="lg:col-span-5 flex flex-col gap-3">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider px-1">
              <span>Past Session Reports ({filteredSessions.length})</span>

              {/* Filter by Role */}
              <div className="flex items-center gap-1 text-[11px] bg-slate-950 p-1 rounded-lg border border-slate-800">
                {['ALL', 'CEO', 'CTO', 'HR'].map(roleOption => (
                  <button
                    key={roleOption}
                    onClick={() => setFilterRole(roleOption)}
                    className={`px-2 py-0.5 rounded-md font-bold transition-all cursor-pointer ${filterRole === roleOption
                        ? 'bg-indigo-600 text-white shadow-xs'
                        : 'text-slate-400 hover:text-white hover:bg-slate-900'
                      }`}
                  >
                    {roleOption}
                  </button>
                ))}
              </div>
            </div>

            {loading ? (
              <div className="flex flex-col items-center justify-center p-12 bg-slate-900/75 rounded-2xl border border-slate-800 shadow-xl">
                <Loader2 size={24} className="animate-spin text-indigo-500 mb-2" />
                <p className="text-xs text-slate-400">Loading past session reports...</p>
              </div>
            ) : filteredSessions.length === 0 ? (
              <div className="p-8 text-center bg-slate-900/75 rounded-2xl border border-slate-800 shadow-xl space-y-3">
                <div className="w-12 h-12 rounded-full bg-indigo-500/10 text-indigo-400 flex items-center justify-center mx-auto">
                  <History size={24} />
                </div>
                <h3 className="text-sm font-bold text-white">No session reports yet</h3>
                <p className="text-xs text-slate-400">
                  Take your first pressure cooker interview session to receive a strategic coaching report.
                </p>
                <button
                  onClick={handleTakeNewSession}
                  className="mt-2 px-4 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-md shadow-indigo-600/30"
                >
                  <Sparkles size={14} /> Start New Session
                </button>
              </div>
            ) : (
              <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
                {filteredSessions.map((s) => {
                  const isSelected = selectedSessionId === s.id;
                  return (
                    <motion.div
                      key={s.id}
                      whileHover={{ scale: 1.01 }}
                      onClick={() => handleSelectSession(s.id)}
                      className={`p-4 rounded-2xl cursor-pointer border transition-all ${isSelected
                          ? 'bg-indigo-950/40 border-indigo-500/70 shadow-lg ring-1 ring-indigo-500/30'
                          : 'bg-slate-900/75 border-slate-800/90 hover:border-slate-700 hover:bg-slate-850/90 shadow-md backdrop-blur-md'
                        }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-indigo-300 px-2.5 py-0.5 rounded-lg bg-indigo-500/15 border border-indigo-500/30">
                              {s.role || 'Executive'}
                            </span>
                            <span className="text-xs font-bold text-white">
                              {s.topic || 'Enterprise Pitch'}
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 mt-1.5 line-clamp-1">
                            {s.scenario || 'Routine executive conversation'}
                          </p>
                        </div>
                        {getScoreBadge(s.overall_score)}
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-slate-500 mt-3 pt-2.5 border-t border-slate-800/80">
                        <span className="flex items-center gap-1.5">
                          <Calendar size={12} /> {formatDateTime(s.created_at)}
                        </span>
                        <span className="flex items-center gap-1.5 font-medium text-slate-400">
                          <MessageSquare size={12} /> {s.turn_count} turns
                        </span>
                      </div>

                      {s.outcome_verdict && (
                        <div className="mt-2 text-[11px] text-indigo-300 font-semibold truncate">
                          • {s.outcome_verdict}
                        </div>
                      )}

                      {/* Action Row: View Coaching Report & Inspect */}
                      <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between gap-2">
                        <span className="text-[10px] text-slate-500 font-mono">
                          ID: {s.id.slice(0, 8)}
                        </span>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleViewReport(s.id);
                            }}
                            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 transition-colors shadow-xs cursor-pointer"
                          >
                            <Trophy size={13} />
                            <span>View Report</span>
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right Column: Dialogue Transcript & Selected Session Details */}
          <div className="lg:col-span-7 flex flex-col bg-slate-900/80 border border-slate-800 backdrop-blur-xl rounded-3xl p-6 overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800/80 shrink-0">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <FileText size={18} className="text-indigo-400" />
                  <span>Session Dialogue Transcript</span>
                </h2>
                <p className="text-xs text-slate-400">
                  {selectedSessionId ? `Session ID: ${selectedSessionId}` : 'Select a session on the left to read dialogue'}
                </p>
              </div>

              {selectedSessionId && (
                <button
                  type="button"
                  onClick={() => handleViewReport(selectedSessionId)}
                  className="px-4 py-1.5 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white transition-colors flex items-center gap-1.5 cursor-pointer shadow-md shadow-indigo-600/30"
                >
                  <Trophy size={14} /> Full Coaching Report
                </button>
              )}
            </div>

            {/* Transcript Content Stream */}
            <div className="flex-1 overflow-y-auto py-4 space-y-3.5 pr-1 max-h-[65vh]">
              {transcriptLoading ? (
                <div className="flex flex-col items-center justify-center p-16">
                  <Loader2 size={24} className="animate-spin text-indigo-500 mb-2" />
                  <p className="text-xs text-slate-400">Loading dialogue transcript...</p>
                </div>
              ) : !transcriptData || !transcriptData.turns || transcriptData.turns.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-16 text-center text-slate-500">
                  <FileText size={32} className="mb-2 text-slate-600" />
                  <p className="text-sm font-medium text-slate-300">No dialogue recorded for this session</p>
                  <p className="text-xs text-slate-500 mt-1">Select another session from the list</p>
                </div>
              ) : (
                transcriptData.turns.map((turn: any, index: number) => {
                  const isUser = turn.sender === 'user';
                  return (
                    <div
                      key={index}
                      className={`p-4 rounded-2xl border text-xs leading-relaxed ${isUser
                          ? 'bg-indigo-950/30 border-indigo-500/30 text-slate-100'
                          : 'bg-slate-950/60 border-slate-800 text-slate-200'
                        }`}
                    >
                      <div className="flex items-center justify-between font-bold mb-2 pb-1.5 border-b border-slate-800/80">
                        <div className="flex items-center gap-2">
                          <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${isUser ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30' : 'bg-slate-800 text-teal-300 border border-slate-700'
                            }`}>
                            {isUser ? <User size={11} /> : <Bot size={11} />}
                            <span>{isUser ? 'Candidate (You)' : 'AI Executive'}</span>
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">
                            Turn #{index + 1}
                          </span>
                        </div>
                      </div>
                      <p className="whitespace-pre-wrap">{turn.text}</p>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Structured Coaching Scorecard Modal */}
        <FeedbackReportModal
          isOpen={!!reportModalData}
          onClose={() => setReportModalData(null)}
          sessionId={reportModalData?.session_id}
          report={reportModalData}
          onRestart={() => navigate('/scenario')}
        />
      </div>
    </div>
  );
};

export default SessionHistory;

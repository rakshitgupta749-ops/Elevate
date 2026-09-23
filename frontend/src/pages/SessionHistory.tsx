import React, { useEffect, useState } from 'react';
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
  X
} from 'lucide-react';
import { listSessions, getSessionTranscript, getCoachingReport } from '../api/apiClient';
import { FeedbackReportModal } from '../components/FeedbackReportModal';
import type { StructuredCoachingReport } from '../components/FeedbackReportModal';

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
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [transcriptData, setTranscriptData] = useState<any>(null);
  const [transcriptLoading, setTranscriptLoading] = useState<boolean>(false);
  const [reportModalData, setReportModalData] = useState<StructuredCoachingReport | null>(null);

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const data = await listSessions(50);
      setSessions(data);
    } catch (err) {
      console.error('Failed to load session history', err);
    } finally {
      setLoading(false);
    }
  };

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

  const handleViewReport = async (sessionId: string) => {
    try {
      const report = await getCoachingReport(sessionId);
      setReportModalData(report);
    } catch (err) {
      console.error('Failed to fetch report', err);
      alert('Coaching report is not yet generated for this session.');
    }
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

  const getScoreBadge = (score?: number | null) => {
    if (score == null) return null;
    if (score >= 80) {
      return <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">{score}/100</span>;
    }
    if (score >= 65) {
      return <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">{score}/100</span>;
    }
    return <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">{score}/100</span>;
  };

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-text-main)] p-4 md:p-8 max-w-7xl mx-auto">
      
      {/* Top Bar */}
      <div className="flex items-center justify-between mb-8">
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft size={18} /> Back to Home
        </button>

        <button
          onClick={() => navigate('/topics')}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-lg shadow-purple-600/20 transition-all"
        >
          <Sparkles size={14} /> Start New Practice
        </button>
      </div>

      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight text-white flex items-center gap-3">
          <History className="text-purple-400" /> Practice History & Performance
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Review past mock conversations, track progress across stakeholder personas, and inspect tactical coaching reports.
        </p>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Session List (Left Column) */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider px-1">
            <span>Past Sessions ({sessions.length})</span>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center p-12 glass-card rounded-2xl">
              <Loader2 size={24} className="animate-spin text-purple-400 mb-2" />
              <p className="text-xs text-slate-400">Loading session history...</p>
            </div>
          ) : sessions.length === 0 ? (
            <div className="p-8 text-center glass-card rounded-2xl space-y-3">
              <div className="w-12 h-12 rounded-full bg-purple-500/10 text-purple-400 flex items-center justify-center mx-auto">
                <History size={24} />
              </div>
              <h3 className="text-sm font-bold text-white">No practice sessions found</h3>
              <p className="text-xs text-slate-400">
                Complete your first mock interview to view scores and tactical feedback reports here.
              </p>
              <button
                onClick={() => navigate('/topics')}
                className="mt-2 px-4 py-2 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-500 text-white transition-colors"
              >
                Start Practice Session
              </button>
            </div>
          ) : (
            <div className="space-y-2.5 max-h-[75vh] overflow-y-auto pr-1">
              {sessions.map((s) => {
                const isSelected = selectedSessionId === s.id;
                return (
                  <motion.div
                    key={s.id}
                    whileHover={{ scale: 1.01 }}
                    onClick={() => handleSelectSession(s.id)}
                    className={`p-4 rounded-2xl cursor-pointer border transition-all ${
                      isSelected
                        ? 'bg-purple-950/30 border-purple-500/50 shadow-lg shadow-purple-900/20'
                        : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-white px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700">
                            {s.role}
                          </span>
                          <span className="text-sm font-semibold text-slate-200">
                            {s.topic}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-1 line-clamp-1">
                          {s.scenario || 'Routine executive conversation'}
                        </p>
                      </div>
                      {getScoreBadge(s.overall_score)}
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 mt-3 pt-2 border-t border-slate-800/80">
                      <span className="flex items-center gap-1.5">
                        <Calendar size={12} /> {formatDateTime(s.created_at)}
                      </span>
                      <span className="flex items-center gap-1.5 font-medium">
                        <MessageSquare size={12} /> {s.turn_count} turns
                      </span>
                    </div>

                    {s.outcome_verdict && (
                      <div className="mt-2 text-[11px] text-purple-300 font-medium truncate">
                        • {s.outcome_verdict}
                      </div>
                    )}

                    {s.has_evaluation && (
                      <div className="mt-2 pt-2 border-t border-slate-800/60 flex justify-end">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleViewReport(s.id);
                          }}
                          className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-purple-400 hover:text-purple-300 bg-purple-950/40 hover:bg-purple-900/50 px-2.5 py-1 rounded-lg border border-purple-500/30 transition-colors"
                        >
                          <Trophy size={11} /> View Scorecard
                        </button>
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </div>
          )}
        </div>

        {/* Selected Session Detail / Transcript (Right Column) */}
        <div className="lg:col-span-7">
          {!selectedSessionId ? (
            <div className="h-full min-h-[400px] flex flex-col items-center justify-center p-8 glass-card rounded-2xl border border-slate-800 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center">
                <FileText size={24} />
              </div>
              <h3 className="text-sm font-bold text-white">Select a session to inspect</h3>
              <p className="text-xs text-slate-400 max-w-sm">
                Click any session on the left to replay the conversation transcript and view the evaluation scorecard.
              </p>
            </div>
          ) : transcriptLoading ? (
            <div className="h-full min-h-[400px] flex flex-col items-center justify-center p-8 glass-card rounded-2xl border border-slate-800">
              <Loader2 size={24} className="animate-spin text-purple-400 mb-2" />
              <p className="text-xs text-slate-400">Loading transcript...</p>
            </div>
          ) : (
            <div className="glass-card rounded-2xl border border-slate-800 flex flex-col h-full max-h-[78vh] overflow-hidden">
              
              {/* Detail Header */}
              <div className="p-4 md:p-5 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    {transcriptData?.role} • {transcriptData?.topic}
                  </h3>
                  <p className="text-xs text-slate-400">
                    {formatDateTime(transcriptData?.created_at)} • {transcriptData?.interactions?.length || 0} messages
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {transcriptData?.evaluation && (
                    <button
                      onClick={() => setReportModalData(transcriptData.evaluation)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-500 text-white shadow-sm transition-colors"
                    >
                      <Trophy size={14} /> View Scorecard
                    </button>
                  )}
                  <button
                    onClick={() => setSelectedSessionId(null)}
                    className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>

              {/* Transcript Messages List */}
              <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
                {transcriptData?.interactions?.length === 0 ? (
                  <p className="text-xs text-slate-400 text-center py-8">No messages recorded in this session.</p>
                ) : (
                  transcriptData?.interactions?.map((msg: any, idx: number) => {
                    const isUser = msg.sender === 'user';
                    return (
                      <div
                        key={idx}
                        className={`flex gap-3 max-w-[85%] ${isUser ? 'ml-auto flex-row-reverse' : ''}`}
                      >
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                          isUser ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300 border border-slate-700'
                        }`}>
                          {isUser ? <User size={14} /> : <Bot size={14} />}
                        </div>
                        <div className={`p-3.5 rounded-2xl text-xs leading-relaxed ${
                          isUser
                            ? 'bg-purple-600 text-white rounded-tr-none'
                            : 'bg-slate-800/80 text-slate-200 border border-slate-700/60 rounded-tl-none'
                        }`}>
                          <p className="whitespace-pre-wrap">{msg.message}</p>
                          <span className="block text-[10px] text-right mt-1 opacity-60">
                            {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Post-Session Coaching Modal */}
      <FeedbackReportModal
        isOpen={!!reportModalData}
        onClose={() => setReportModalData(null)}
        report={reportModalData}
        onRestart={() => navigate('/scenario')}
      />
    </div>
  );
};
export default SessionHistory;

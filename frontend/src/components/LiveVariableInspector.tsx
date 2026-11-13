import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Activity, 
  Sliders, 
  Zap, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  X, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  Cpu,
  Layers,
  FileText
} from 'lucide-react';
import { getSessionLiveState } from '../api/apiClient';

interface LiveVariableInspectorProps {
  sessionId: string | null;
  isOpen: boolean;
  onClose: () => void;
  lastTurnTrigger?: number; // increments when a turn finishes to auto-refresh
  messages?: Array<{ id: string; sender: 'user' | 'ai'; text: string }>;
}

const PERCEPTION_METRICS = [
  { key: 'trust', label: 'Trust', color: 'bg-emerald-500', text: 'text-emerald-700', bg: 'bg-emerald-50' },
  { key: 'skepticism', label: 'Skepticism', color: 'bg-amber-500', text: 'text-amber-700', bg: 'bg-amber-50' },
  { key: 'patience', label: 'Patience', color: 'bg-sky-500', text: 'text-sky-700', bg: 'bg-sky-50' },
  { key: 'engagement', label: 'Engagement', color: 'bg-indigo-500', text: 'text-indigo-700', bg: 'bg-indigo-50' },
  { key: 'interest', label: 'Interest', color: 'bg-purple-500', text: 'text-purple-700', bg: 'bg-purple-50' },
  { key: 'perceived_risk', label: 'Perceived Risk', color: 'bg-rose-500', text: 'text-rose-700', bg: 'bg-rose-50' },
  { key: 'frustration', label: 'Frustration', color: 'bg-red-500', text: 'text-red-700', bg: 'bg-red-50' },
  { key: 'confidence_in_candidate', label: 'Confidence', color: 'bg-teal-500', text: 'text-teal-700', bg: 'bg-teal-50' },
];

export const LiveVariableInspector: React.FC<LiveVariableInspectorProps> = ({
  sessionId,
  isOpen,
  onClose,
  lastTurnTrigger = 0,
  messages = [],
}) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'perception' | 'traits' | 'stages' | 'history' | 'transcript'>('perception');
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  const fetchLiveState = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const state = await getSessionLiveState(sessionId);
      setData(state);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error('Failed to fetch live session state', err);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (isOpen) {
      fetchLiveState();
    }
  }, [isOpen, fetchLiveState, lastTurnTrigger]);

  // Auto poll every 4 seconds when open
  useEffect(() => {
    if (!isOpen) return;
    const interval = setInterval(() => {
      fetchLiveState();
    }, 4000);
    return () => clearInterval(interval);
  }, [isOpen, fetchLiveState]);

  if (!isOpen) return null;

  const currentState = data?.current_state || {};
  const deltas = data?.deltas || {};
  const configuredTraits = data?.persona_configuration?.traits || {};
  const interviewState = data?.interview_state || {};
  const criteria = interviewState?.criteria || {};
  const stateHistory = data?.state_history || [];
  const latestDecision = data?.latest_decision;

  const formatStageName = (stageStr: string = '') => {
    return stageStr
      .replace(/^STAGE_\d+_/, '')
      .replace(/_/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <AnimatePresence>
      <div 
        className="fixed inset-0 z-50 flex items-center justify-end bg-black/50 backdrop-blur-xs"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, x: 350 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 350 }}
          transition={{ type: 'spring', damping: 25, stiffness: 280 }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-xl h-full bg-white shadow-2xl flex flex-col border-l border-slate-200 overflow-hidden"
        >
          {/* Header */}
          <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-[var(--color-primary)] text-white flex items-center justify-center shadow-xs">
                <Activity size={18} className="animate-pulse" />
              </div>
              <div>
                <h3 className="font-bold text-base text-slate-900 flex items-center gap-2">
                  Live Variable Inspector
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                    LIVE
                  </span>
                </h3>
                <p className="text-xs text-slate-500">
                  Real-time stakeholder perception & configured traits
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={fetchLiveState}
                disabled={loading}
                title="Refresh variables"
                className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 transition-colors"
              >
                <RefreshCw size={15} className={loading ? 'animate-spin text-[var(--color-primary)]' : ''} />
              </button>
              <button
                onClick={onClose}
                className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Quick Status Pill Bar */}
          <div className="px-5 py-3 bg-white border-b border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <div className="flex items-center gap-4">
              <div>
                <span className="text-slate-400 font-medium">Stage:</span>{' '}
                <span className="font-semibold text-slate-800">
                  {formatStageName(interviewState.current_stage) || 'Opening Rapport'}
                </span>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Turn:</span>{' '}
                <span className="font-semibold text-slate-800">
                  {interviewState.stage_turn_count ?? 0} (Total: {data?.turn_count ?? 0})
                </span>
              </div>
            </div>
            <span className="text-[11px] text-slate-400">
              Updated {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-slate-200 px-5 bg-slate-50/50">
            <button
              onClick={() => setActiveTab('perception')}
              className={`py-3 px-3.5 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === 'perception'
                  ? 'border-[var(--color-primary)] text-[var(--color-primary)] bg-white'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <Zap size={14} /> Perception State (8)
            </button>
            <button
              onClick={() => setActiveTab('traits')}
              className={`py-3 px-3.5 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === 'traits'
                  ? 'border-[var(--color-primary)] text-[var(--color-primary)] bg-white'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <Sliders size={14} /> Configured Traits ({Object.keys(configuredTraits).length})
            </button>
            <button
              onClick={() => setActiveTab('stages')}
              className={`py-3 px-3.5 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === 'stages'
                  ? 'border-[var(--color-primary)] text-[var(--color-primary)] bg-white'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <Layers size={14} /> Stage & Decisions
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`py-3 px-3.5 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === 'history'
                  ? 'border-[var(--color-primary)] text-[var(--color-primary)] bg-white'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <Clock size={14} /> Trajectory ({stateHistory.length})
            </button>
            <button
              onClick={() => setActiveTab('transcript')}
              className={`py-3 px-3.5 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === 'transcript'
                  ? 'border-[var(--color-primary)] text-[var(--color-primary)] bg-white'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <FileText size={14} /> Transcript ({messages.length})
            </button>
          </div>

          {/* Tab Contents */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            
            {/* TAB 1: Real-time Perception State */}
            {activeTab === 'perception' && (
              <div className="space-y-4">
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 flex items-center justify-between text-xs text-slate-600">
                  <span>How the AI stakeholder evaluates your responses across turns:</span>
                  <span className="font-semibold text-slate-800">Range: 0.00 – 1.00</span>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {PERCEPTION_METRICS.map((item) => {
                    const rawVal = currentState[item.key] ?? 0.5;
                    const numVal = typeof rawVal === 'number' ? rawVal : parseFloat(rawVal) || 0;
                    const percent = Math.round(numVal * 100);
                    const delta = deltas[item.key];

                    return (
                      <div 
                        key={item.key}
                        className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-2 hover:border-slate-300 transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm text-slate-800">{item.label}</span>
                            <span className="text-xs text-slate-400 font-mono">({item.key})</span>
                          </div>

                          <div className="flex items-center gap-2">
                            {delta !== undefined && delta !== 0 && (
                              <span className={`inline-flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded ${
                                delta > 0 
                                  ? (['trust', 'engagement', 'interest', 'patience', 'confidence_in_candidate'].includes(item.key) ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700')
                                  : (['trust', 'engagement', 'interest', 'patience', 'confidence_in_candidate'].includes(item.key) ? 'bg-rose-50 text-rose-700' : 'bg-emerald-50 text-emerald-700')
                              }`}>
                                {delta > 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                                {delta > 0 ? `+${delta}` : delta}
                              </span>
                            )}
                            <span className="font-bold text-sm text-slate-900 font-mono">
                              {numVal.toFixed(2)}
                            </span>
                          </div>
                        </div>

                        {/* Animated Progress Bar */}
                        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }}
                            transition={{ duration: 0.4 }}
                            className={`h-full rounded-full ${item.color}`}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                {latestDecision && (
                  <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
                      <Cpu size={14} /> Latest Policy Engine Reaction
                    </h4>
                    <div className="text-xs space-y-1 text-slate-700">
                      <div>
                        <span className="font-semibold text-slate-900">Action:</span>{' '}
                        <span className="px-2 py-0.5 rounded bg-[var(--color-primary)]/10 text-[var(--color-primary)] font-bold">
                          {latestDecision?.primary_action?.action_type || 'PROBE'}
                        </span>
                      </div>
                      {latestDecision?.primary_action?.reason && (
                        <div>
                          <span className="font-semibold text-slate-900">Reason:</span>{' '}
                          {latestDecision.primary_action.reason}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: Configured Traits */}
            {activeTab === 'traits' && (
              <div className="space-y-4">
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 text-xs text-slate-600">
                  Persona baseline configuration applied for{' '}
                  <strong className="text-slate-900">{data?.role || 'Stakeholder'}</strong>{' '}
                  (Preset:{' '}
                  <span className="px-2 py-0.5 rounded bg-slate-200 text-slate-800 font-semibold">
                    {data?.persona_configuration?.preset || 'BALANCED'}
                  </span>
                  ):
                </div>

                {Object.keys(configuredTraits).length === 0 ? (
                  <div className="text-center py-8 text-slate-400 text-sm">
                    No custom traits loaded for this session.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-3">
                    {Object.entries(configuredTraits).map(([traitKey, traitValue]: [string, any]) => {
                      const numVal = typeof traitValue === 'number' ? traitValue : parseFloat(traitValue) || 0;
                      const percent = Math.round(numVal * 100);

                      return (
                        <div 
                          key={traitKey}
                          className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-2"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-sm text-slate-800 capitalize">
                              {traitKey.replace(/_/g, ' ')}
                            </span>
                            <span className="font-bold text-sm text-slate-900 font-mono">
                              {numVal.toFixed(2)}
                            </span>
                          </div>

                          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                            <div
                              style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }}
                              className="h-full rounded-full bg-[var(--color-primary)]"
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-1.5">
                  <div className="font-semibold text-slate-800 mb-1">Session Parameters</div>
                  <div><strong>Topic:</strong> {data?.topic || 'N/A'}</div>
                  <div><strong>Scenario:</strong> {data?.scenario || 'N/A'}</div>
                  <div><strong>Style:</strong> {data?.style || 'N/A'}</div>
                  <div><strong>Experience:</strong> {data?.experience || 'N/A'}</div>
                </div>
              </div>
            )}

            {/* TAB 3: Stage Machine & Criteria */}
            {activeTab === 'stages' && (
              <div className="space-y-4">
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Active Lifecycle Stage
                  </div>
                  <div className="text-lg font-bold text-slate-900">
                    {formatStageName(interviewState.current_stage)}
                  </div>
                  <div className="text-xs text-slate-500 mt-1 flex items-center gap-3">
                    <span>Stage Turns: <strong>{interviewState.stage_turn_count ?? 0}</strong></span>
                    <span>Total Turns: <strong>{interviewState.total_turn_count ?? 0} / {interviewState.max_total_turns ?? 15}</strong></span>
                    <span>Status: <strong className="text-emerald-600">{interviewState.status ?? 'ACTIVE'}</strong></span>
                  </div>
                </div>

                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 pt-2">
                  Stage Exit Criteria
                </h4>
                {Object.keys(criteria).length === 0 ? (
                  <div className="text-xs text-slate-400 p-4 bg-slate-50 rounded-xl">
                    No criteria defined for the current stage.
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {Object.entries(criteria).map(([critId, crit]: [string, any]) => (
                      <div 
                        key={critId}
                        className={`p-3 rounded-xl border text-xs flex items-start justify-between gap-3 ${
                          crit.satisfied 
                            ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900' 
                            : 'bg-white border-slate-200 text-slate-700'
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          {crit.satisfied ? (
                            <CheckCircle2 size={16} className="text-emerald-600 flex-shrink-0 mt-0.5" />
                          ) : (
                            <AlertCircle size={16} className="text-slate-400 flex-shrink-0 mt-0.5" />
                          )}
                          <div>
                            <div className="font-semibold text-slate-900">{crit.name || critId}</div>
                            <div className="text-slate-500 mt-0.5">{crit.description}</div>
                          </div>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase flex-shrink-0 ${
                          crit.satisfied ? 'bg-emerald-200 text-emerald-800' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {crit.satisfied ? 'MET' : crit.required ? 'MANDATORY' : 'OPTIONAL'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: Trajectory History */}
            {activeTab === 'history' && (
              <div className="space-y-3">
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 text-xs text-slate-600">
                  Audit trail of how stakeholder variables shifted turn by turn:
                </div>

                {stateHistory.length === 0 ? (
                  <div className="text-center py-8 text-slate-400 text-sm">
                    No state snapshots recorded yet.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {stateHistory.map((snap: any, idx: number) => {
                      const snapState = typeof snap.state_json === 'string' 
                        ? JSON.parse(snap.state_json) 
                        : (snap.state || {});

                      return (
                        <div 
                          key={idx}
                          className="bg-white p-3.5 rounded-xl border border-slate-200 text-xs flex flex-col gap-2"
                        >
                          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                            <span className="font-bold text-slate-900">
                              Turn {snap.turn_number ?? idx}
                            </span>
                            <span className="text-slate-400 text-[11px]">
                              {snap.event_type || 'Turn Transition'}
                            </span>
                          </div>

                          {snap.event_reason && (
                            <div className="text-slate-600 text-[11px] italic">
                              "{snap.event_reason}"
                            </div>
                          )}

                          <div className="grid grid-cols-4 gap-1.5 pt-1 text-[11px] font-mono">
                            <div>Trust: <span className="font-bold text-slate-800">{Number(snapState.trust ?? 0).toFixed(2)}</span></div>
                            <div>Skep: <span className="font-bold text-slate-800">{Number(snapState.skepticism ?? 0).toFixed(2)}</span></div>
                            <div>Pat: <span className="font-bold text-slate-800">{Number(snapState.patience ?? 0).toFixed(2)}</span></div>
                            <div>Eng: <span className="font-bold text-slate-800">{Number(snapState.engagement ?? 0).toFixed(2)}</span></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB 5: Transcript */}
            {activeTab === 'transcript' && (
              <div className="space-y-3">
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 flex items-center justify-between text-xs text-slate-600">
                  <span>Session turns stream & candidate talk logs:</span>
                  <span className="font-semibold text-slate-800">{messages.length} turns</span>
                </div>
                {messages.length === 0 ? (
                  <p className="text-xs text-slate-400 text-center py-8">No transcript messages recorded yet.</p>
                ) : (
                  messages.map((m, i) => (
                    <div
                      key={m.id || i}
                      className={`p-3.5 rounded-xl border text-xs ${
                        m.sender === 'user'
                          ? 'bg-sky-50/70 border-sky-200 text-slate-800'
                          : 'bg-purple-50/70 border-purple-200 text-slate-800'
                      }`}
                    >
                      <div className="flex items-center justify-between font-bold mb-1.5 text-[11px]">
                        <span className={m.sender === 'user' ? 'text-sky-700' : 'text-purple-700'}>
                          Turn #{i + 1} - {m.sender === 'user' ? 'Candidate' : 'AI Executive'}
                        </span>
                        <span className="text-slate-400 font-normal font-mono">
                          {m.text.trim().split(/\s+/).filter(Boolean).length} words
                        </span>
                      </div>
                      <p className="leading-relaxed whitespace-pre-wrap">{m.text}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
            <span>Session: <code className="font-mono text-slate-700">{sessionId ? `${sessionId.slice(0, 8)}...` : 'Active'}</code></span>
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium transition-colors"
            >
              Close Inspector
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

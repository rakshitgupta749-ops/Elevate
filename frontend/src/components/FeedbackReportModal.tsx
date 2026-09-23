import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Trophy, 
  CheckCircle2, 
  AlertTriangle, 
  Download, 
  RotateCcw, 
  History, 
  X, 
  Target, 
  Sparkles, 
  TrendingUp, 
  ArrowRight,
  Mic,
  Gauge,
  Timer,
  Zap,
  Activity,
  MessageSquareQuote,
  Loader2
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getSalesScorecard } from '../api/apiClient';
import type { 
  SalesInterviewScorecardData, 
  DeliveryScorecardData, 
  StrategicScorecardData 
} from '../api/apiClient';

export interface FeedbackSubscore {
  name: string;
  score: number;
  description: string;
}

export interface FeedbackStrength {
  title: string;
  description: string;
  quote?: string | null;
}

export interface FeedbackWeakness {
  title: string;
  description: string;
  quote?: string | null;
  recommended_alternative?: string | null;
}

export interface StructuredCoachingReport {
  session_id: string;
  role: string;
  topic: string;
  scenario: string;
  overall_score: number;
  letter_grade: string;
  outcome_verdict: string;
  outcome_summary: string;
  subscores: FeedbackSubscore[];
  strengths: FeedbackStrength[];
  weaknesses: FeedbackWeakness[];
  tactical_takeaways: string[];
  markdown_report: string;
}

interface FeedbackReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId?: string;
  scorecard?: SalesInterviewScorecardData | null;
  report?: StructuredCoachingReport | null;
  onRestart?: () => void;
}

export const FeedbackReportModal: React.FC<FeedbackReportModalProps> = ({
  isOpen,
  onClose,
  sessionId: propSessionId,
  scorecard: propScorecard,
  report,
  onRestart,
}) => {
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<'two-track' | 'tactical'>('two-track');
  const [scorecard, setScorecard] = useState<SalesInterviewScorecardData | null>(propScorecard || null);
  const [loading, setLoading] = useState<boolean>(false);

  const targetSessionId = propSessionId || propScorecard?.session_id || report?.session_id;

  // Fetch consolidated scorecard from backend API whenever modal opens
  useEffect(() => {
    if (propScorecard) {
      setScorecard(propScorecard);
      return;
    }

    if (isOpen && targetSessionId) {
      setLoading(true);
      getSalesScorecard(targetSessionId)
        .then((data) => {
          setScorecard(data);
        })
        .catch((err) => {
          console.warn('Could not fetch consolidated scorecard, falling back to report data:', err);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [isOpen, targetSessionId, propScorecard]);

  if (!isOpen) return null;

  // Fallback delivery scorecard if not yet populated
  const delivery: DeliveryScorecardData = scorecard?.delivery_scorecard || {
    talk_listen_ratio: 0.50,
    talk_ratio_verdict: 'Balanced',
    avg_response_latency_sec: 1.20,
    latency_verdict: 'Crisp',
    average_wpm: 140.0,
    pace_verdict: 'Optimal',
    interruption_count: 0,
  };

  // Fallback strategic scorecard if not yet populated
  const strategic: StrategicScorecardData = scorecard?.strategic_scorecard || {
    discovery_score: report?.subscores.find(s => s.name.toLowerCase().includes('clarity'))?.score || 75,
    objection_handling_score: report?.subscores.find(s => s.name.toLowerCase().includes('objection'))?.score || 70,
    value_proposition_score: report?.subscores.find(s => s.name.toLowerCase().includes('value'))?.score || 72,
    strengths: report?.strengths.map(s => `${s.title}: ${s.description}`) || [
      'Maintained consistent executive engagement and clear professional tone.'
    ],
    critical_misses: report?.weaknesses.map(w => `${w.title}: ${w.description}`) || [
      'Could sharpen quantifiable business metrics earlier in the conversation.'
    ],
    key_coaching_quote: report?.weaknesses.find(w => w.quote)?.quote || 'N/A',
  };

  const readinessScore = scorecard?.overall_readiness_score ?? report?.overall_score ?? 75;

  const getReadinessColor = (score: number) => {
    if (score >= 80) return {
      text: 'text-emerald-400',
      border: 'border-emerald-500/30',
      bg: 'bg-emerald-500/10',
      bar: 'bg-emerald-500',
      label: 'Executive Ready / Strong Pitch',
    };
    if (score >= 65) return {
      text: 'text-amber-400',
      border: 'border-amber-500/30',
      bg: 'bg-amber-500/10',
      bar: 'bg-amber-500',
      label: 'Conditional Readiness / Minor Gaps',
    };
    return {
      text: 'text-rose-400',
      border: 'border-rose-500/30',
      bg: 'bg-rose-500/10',
      bar: 'bg-rose-500',
      label: 'High Risk / Needs Delivery Coaching',
    };
  };

  const readinessTheme = getReadinessColor(readinessScore);

  const repTalkPct = Math.round(delivery.talk_listen_ratio * 100);
  const buyerListenPct = Math.max(0, 100 - repTalkPct);

  const downloadMarkdown = () => {
    if (report?.markdown_report) {
      const blob = new Blob([report.markdown_report], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Sales_Scorecard_${targetSessionId ? targetSessionId.slice(0, 8) : 'session'}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      return;
    }

    const mdContent = `# 📊 Unified Sales Interview Scorecard
Session: ${targetSessionId || 'N/A'}
Timestamp: ${scorecard?.timestamp || new Date().toISOString()}

## Overall Readiness Score: ${readinessScore}/100 (${readinessTheme.label})

### Track 1: Acoustic & Delivery Telemetry
- Talk-to-Listen Ratio: ${repTalkPct}% Rep / ${buyerListenPct}% Buyer (${delivery.talk_ratio_verdict})
- Average Speaking Pace: ${delivery.average_wpm} WPM (${delivery.pace_verdict}) [Target: 130-160 WPM]
- Average Response Latency: ${delivery.avg_response_latency_sec}s (${delivery.latency_verdict}) [Target: 0.8s-1.8s]
- Aggressive Interruptions: ${delivery.interruption_count}

### Track 2: Strategic Scorecard
- Discovery Score: ${strategic.discovery_score}/100
- Objection Handling Score: ${strategic.objection_handling_score}/100
- Value Proposition Score: ${strategic.value_proposition_score}/100
- Key Coaching Quote: "${strategic.key_coaching_quote}"

#### Strengths:
${strategic.strengths.map(s => `- ${s}`).join('\n')}

#### Critical Misses:
${strategic.critical_misses.map(m => `- ${m}`).join('\n')}
`;
    const blob = new Blob([mdContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Sales_Scorecard_${targetSessionId ? targetSessionId.slice(0, 8) : 'session'}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <AnimatePresence>
      <div 
        className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6 bg-black/85 backdrop-blur-md overflow-y-auto"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          transition={{ duration: 0.22, ease: 'easeOut' }}
          className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden my-auto"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-950/70">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400">
                <Trophy size={22} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  Sales Interview Scorecard
                  <span className="text-[11px] px-2.5 py-0.5 rounded-full font-semibold bg-purple-500/15 text-purple-300 border border-purple-500/30">
                    Two-Track Evaluation
                  </span>
                </h2>
                <p className="text-xs text-slate-400">
                  Track 1 Delivery Telemetry + Track 2 Strategic Rubric
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              {report && (
                <div className="flex bg-slate-800/80 p-0.5 rounded-xl border border-slate-700/60 text-xs">
                  <button
                    onClick={() => setActiveTab('two-track')}
                    className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                      activeTab === 'two-track'
                        ? 'bg-purple-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Consolidated Scorecard
                  </button>
                  <button
                    onClick={() => setActiveTab('tactical')}
                    className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                      activeTab === 'tactical'
                        ? 'bg-purple-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Tactical Feedback
                  </button>
                </div>
              )}
              <button
                onClick={onClose}
                className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800/60 transition-colors ml-2"
              >
                <X size={20} />
              </button>
            </div>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 space-y-3">
                <Loader2 size={32} className="animate-spin text-purple-400" />
                <p className="text-sm text-slate-400 font-medium">Computing consolidated sales telemetry & strategic scorecard...</p>
              </div>
            ) : activeTab === 'two-track' ? (
              <>
                {/* 1. Hero Header: Overall Readiness Score */}
                <div className={`p-6 rounded-2xl border ${readinessTheme.bg} ${readinessTheme.border} flex flex-col md:flex-row items-center justify-between gap-6 shadow-inner`}>
                  <div className="space-y-2 flex-1 text-center md:text-left">
                    <div className="flex items-center justify-center md:justify-start gap-2">
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${readinessTheme.bg} ${readinessTheme.text} border ${readinessTheme.border}`}>
                        <Sparkles size={14} /> Overall Sales Readiness
                      </span>
                      {report?.letter_grade && (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                          Grade {report.letter_grade}
                        </span>
                      )}
                    </div>
                    <h3 className="text-xl font-extrabold text-white tracking-tight">
                      {readinessTheme.label}
                    </h3>
                    <p className="text-xs text-slate-300 leading-relaxed max-w-xl">
                      {report?.outcome_summary || (
                        readinessScore >= 80 
                          ? 'Candidate demonstrated confident executive presence, well-paced delivery, and strong strategic discovery alignment.'
                          : readinessScore >= 65
                          ? 'Candidate showed solid value articulation, but response hesitation or talk-to-listen imbalance requires coaching.'
                          : 'High delivery friction detected: significant pacing, barge-in, or value articulation issues impacted executive credibility.'
                      )}
                    </p>
                  </div>

                  {/* Readiness Score Visual */}
                  <div className="flex items-center gap-4 shrink-0">
                    <div className={`flex flex-col items-center justify-center w-28 h-28 rounded-2xl border ${readinessTheme.border} ${readinessTheme.bg} shadow-lg`}>
                      <span className={`text-4xl font-black tracking-tight ${readinessTheme.text}`}>
                        {readinessScore}
                      </span>
                      <span className="text-[10px] uppercase font-bold tracking-widest text-slate-400">
                        Readiness / 100
                      </span>
                    </div>
                  </div>
                </div>

                {/* 2. Track 1: Delivery Telemetry Cards (4-Card Grid) */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs uppercase font-extrabold text-slate-400 tracking-wider flex items-center gap-2">
                      <Activity size={14} className="text-cyan-400" /> Track 1: Acoustic & Delivery Telemetry
                    </h3>
                    <span className="text-[11px] text-slate-500 font-medium">Deterministic zero-latency engine</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                    {/* Card A: Talk-to-Listen Ratio */}
                    <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                          <Mic size={14} className="text-purple-400" /> Talk-to-Listen
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                          delivery.talk_ratio_verdict === 'Balanced'
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                            : delivery.talk_ratio_verdict === 'Pitch Slapping'
                            ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                        }`}>
                          {delivery.talk_ratio_verdict}
                        </span>
                      </div>

                      <div className="flex items-baseline justify-between">
                        <span className="text-2xl font-black text-white">{repTalkPct}%</span>
                        <span className="text-xs text-slate-400 font-medium">Buyer: {buyerListenPct}%</span>
                      </div>

                      {/* Dual-Color Ratio Progress Bar */}
                      <div className="w-full h-2 bg-slate-700/50 rounded-full overflow-hidden flex">
                        <div 
                          style={{ width: `${repTalkPct}%` }}
                          className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-500" 
                          title={`Rep Talk: ${repTalkPct}%`}
                        />
                        <div 
                          style={{ width: `${buyerListenPct}%` }}
                          className="h-full bg-slate-600/70 transition-all duration-500" 
                          title={`Buyer Listen: ${buyerListenPct}%`}
                        />
                      </div>
                      <p className="text-[10px] text-slate-400 font-medium">Benchmark: 45%–55% rep talk</p>
                    </div>

                    {/* Card B: Pace / Speaking Rate (WPM) */}
                    <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                          <Gauge size={14} className="text-blue-400" /> Pace (WPM)
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                          delivery.pace_verdict === 'Optimal'
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                            : delivery.pace_verdict === 'Rushing'
                            ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                        }`}>
                          {delivery.pace_verdict}
                        </span>
                      </div>

                      <div className="flex items-baseline justify-between">
                        <span className="text-2xl font-black text-white">{Math.round(delivery.average_wpm)}</span>
                        <span className="text-xs text-slate-400 font-medium">WPM</span>
                      </div>

                      <div className="w-full h-2 bg-slate-700/50 rounded-full overflow-hidden">
                        <div 
                          style={{ width: `${Math.min(100, Math.max(10, (delivery.average_wpm / 200) * 100))}%` }}
                          className={`h-full transition-all duration-500 ${
                            delivery.pace_verdict === 'Optimal' ? 'bg-emerald-500' : 'bg-amber-500'
                          }`}
                        />
                      </div>
                      <p className="text-[10px] text-slate-400 font-medium">Target range: 130–160 WPM</p>
                    </div>

                    {/* Card C: Response Latency (Hesitation) */}
                    <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                          <Timer size={14} className="text-emerald-400" /> Latency
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                          delivery.latency_verdict === 'Crisp'
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                            : delivery.latency_verdict === 'Hesitant'
                            ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                        }`}>
                          {delivery.latency_verdict}
                        </span>
                      </div>

                      <div className="flex items-baseline justify-between">
                        <span className="text-2xl font-black text-white">{delivery.avg_response_latency_sec.toFixed(1)}</span>
                        <span className="text-xs text-slate-400 font-medium">seconds pause</span>
                      </div>

                      <div className="w-full h-2 bg-slate-700/50 rounded-full overflow-hidden">
                        <div 
                          style={{ width: `${Math.min(100, Math.max(10, (delivery.avg_response_latency_sec / 4.0) * 100))}%` }}
                          className={`h-full transition-all duration-500 ${
                            delivery.latency_verdict === 'Crisp' ? 'bg-emerald-500' : 'bg-amber-500'
                          }`}
                        />
                      </div>
                      <p className="text-[10px] text-slate-400 font-medium">Benchmark: 0.8s–1.8s confident</p>
                    </div>

                    {/* Card D: Barge-ins & Interruptions */}
                    <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                          <Zap size={14} className="text-amber-400" /> Barge-ins
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                          delivery.interruption_count === 0
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                            : delivery.interruption_count <= 2
                            ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                            : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                        }`}>
                          {delivery.interruption_count === 0 ? 'Clean Flow' : `${delivery.interruption_count} Overlaps`}
                        </span>
                      </div>

                      <div className="flex items-baseline justify-between">
                        <span className="text-2xl font-black text-white">{delivery.interruption_count}</span>
                        <span className="text-xs text-slate-400 font-medium">interruptions</span>
                      </div>

                      <div className="w-full h-2 bg-slate-700/50 rounded-full overflow-hidden">
                        <div 
                          style={{ width: `${Math.min(100, delivery.interruption_count * 25)}%` }}
                          className={`h-full transition-all duration-500 ${
                            delivery.interruption_count === 0 ? 'bg-emerald-500' : 'bg-rose-500'
                          }`}
                        />
                      </div>
                      <p className="text-[10px] text-slate-400 font-medium truncate" title="Backchannels (<700ms) filtered">
                        Backchannels (&lt;700ms) filtered out
                      </p>
                    </div>
                  </div>
                </div>

                {/* 3. Track 2: Strategic Scorecard */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs uppercase font-extrabold text-slate-400 tracking-wider flex items-center gap-2">
                      <Target size={14} className="text-purple-400" /> Track 2: Strategic LLM Rubric Evaluation
                    </h3>
                    <span className="text-[11px] text-slate-500 font-medium">Content & technique evaluation</span>
                  </div>

                  {/* 3 Strategic Dimension Bars */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                    <div className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-700/50 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-200">Needs Discovery</span>
                        <span className="font-bold text-white">{strategic.discovery_score} / 100</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
                        <div 
                          style={{ width: `${strategic.discovery_score}%` }}
                          className="h-full bg-purple-500 rounded-full" 
                        />
                      </div>
                      <p className="text-[11px] text-slate-400">Diagnosis, qualification & pain points</p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-700/50 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-200">Objection Handling</span>
                        <span className="font-bold text-white">{strategic.objection_handling_score} / 100</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
                        <div 
                          style={{ width: `${strategic.objection_handling_score}%` }}
                          className="h-full bg-blue-500 rounded-full" 
                        />
                      </div>
                      <p className="text-[11px] text-slate-400">Defusing skepticism & validating risk</p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-700/50 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-200">Value Proposition & ROI</span>
                        <span className="font-bold text-white">{strategic.value_proposition_score} / 100</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
                        <div 
                          style={{ width: `${strategic.value_proposition_score}%` }}
                          className="h-full bg-emerald-500 rounded-full" 
                        />
                      </div>
                      <p className="text-[11px] text-slate-400">Business impact & metric alignment</p>
                    </div>
                  </div>

                  {/* Key Coaching Quote Callout */}
                  {strategic.key_coaching_quote && strategic.key_coaching_quote !== 'N/A' && (
                    <div className="p-4 rounded-xl bg-purple-950/20 border border-purple-500/30 space-y-1.5">
                      <div className="flex items-center gap-2 text-xs font-bold text-purple-300">
                        <MessageSquareQuote size={15} className="text-purple-400" />
                        Pivotal Candidate Quote for Coaching:
                      </div>
                      <p className="text-xs text-purple-100 italic leading-relaxed pl-5 border-l-2 border-purple-500/50">
                        "{strategic.key_coaching_quote}"
                      </p>
                    </div>
                  )}

                  {/* Strengths & Critical Misses Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Strengths */}
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase text-emerald-400 tracking-wider flex items-center gap-1.5">
                        <CheckCircle2 size={14} /> Key Strategic Strengths
                      </h4>
                      <div className="space-y-2">
                        {strategic.strengths.map((str, i) => (
                          <div key={i} className="p-3 rounded-xl bg-emerald-950/15 border border-emerald-500/20 text-xs text-slate-300 flex items-start gap-2">
                            <span className="text-emerald-400 font-bold mt-0.5">•</span>
                            <span className="leading-relaxed">{str}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Critical Misses */}
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase text-amber-400 tracking-wider flex items-center gap-1.5">
                        <AlertTriangle size={14} /> Critical Sales Misses
                      </h4>
                      <div className="space-y-2">
                        {strategic.critical_misses.map((miss, i) => (
                          <div key={i} className="p-3 rounded-xl bg-amber-950/15 border border-amber-500/20 text-xs text-slate-300 flex items-start gap-2">
                            <span className="text-amber-400 font-bold mt-0.5">•</span>
                            <span className="leading-relaxed">{miss}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              /* Tactical Tab: Legacy Detailed Analysis & Rewritten Alternatives */
              report && (
                <div className="space-y-6">
                  {/* Detailed Weakness Alternatives */}
                  <div>
                    <h3 className="text-xs uppercase font-bold text-amber-400 tracking-wider mb-3 flex items-center gap-2">
                      <AlertTriangle size={14} /> Improvement Areas & Rewritten Responses
                    </h3>
                    <div className="space-y-3">
                      {report.weaknesses.map((wk, i) => (
                        <div key={i} className="p-4 rounded-xl bg-amber-950/15 border border-amber-500/25 space-y-2.5">
                          <span className="text-xs font-bold text-amber-300 block">{wk.title}</span>
                          <p className="text-xs text-slate-300 leading-relaxed">{wk.description}</p>
                          {wk.quote && (
                            <div className="p-2.5 rounded-lg bg-black/40 border border-slate-800 text-xs text-slate-400 italic">
                              <span className="text-[10px] font-semibold uppercase text-slate-500 block not-italic mb-1">Your response:</span>
                              "{wk.quote}"
                            </div>
                          )}
                          {wk.recommended_alternative && (
                            <div className="p-3 rounded-lg bg-purple-950/30 border border-purple-500/30 text-xs text-purple-200 space-y-1">
                              <span className="text-[11px] font-bold text-purple-400 flex items-center gap-1">
                                💡 What you should have said instead:
                              </span>
                              <p className="font-medium italic leading-relaxed text-purple-100">
                                "{wk.recommended_alternative}"
                              </p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Tactical Takeaways */}
                  {report.tactical_takeaways.length > 0 && (
                    <div className="p-4 rounded-xl bg-slate-800/30 border border-slate-700/40 space-y-2">
                      <h3 className="text-xs uppercase font-bold text-purple-400 tracking-wider flex items-center gap-2">
                        <TrendingUp size={14} /> Actionable Next Steps
                      </h3>
                      <ul className="space-y-1.5">
                        {report.tactical_takeaways.map((t, i) => (
                          <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                            <ArrowRight size={13} className="text-purple-400 mt-0.5 shrink-0" />
                            <span>{t}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )
            )}

          </div>

          {/* Footer Actions */}
          <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-t border-slate-800/80 bg-slate-950/70">
            <div className="flex items-center gap-2">
              <button
                onClick={downloadMarkdown}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition-colors cursor-pointer"
              >
                <Download size={14} /> Download Scorecard (.md)
              </button>
              <button
                onClick={() => {
                  onClose();
                  navigate('/history');
                }}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors cursor-pointer"
              >
                <History size={14} /> View History
              </button>
            </div>

            <div className="flex items-center gap-2">
              {onRestart && (
                <button
                  onClick={() => {
                    onClose();
                    onRestart();
                  }}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-lg shadow-purple-600/20 transition-all cursor-pointer"
                >
                  <RotateCcw size={14} /> Practice Again
                </button>
              )}
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-700/60 hover:bg-slate-700 text-white transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

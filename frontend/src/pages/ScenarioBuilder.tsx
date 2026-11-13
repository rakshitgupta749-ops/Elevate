import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useStore } from '../store/useStore';
import { createSession, getAdminRoleConfiguration, getAdminPersonasByRole } from '../api/apiClient';
import { warmUpAudioContext } from '../utils/audioQueue';
import {
  Progress,
  ProgressLabel,
  ProgressTrack,
  ProgressValue,
} from '@/components/animate-ui/components/base/progress';
import {
  ArrowRight,
  ArrowLeft,
  Home,
  Loader2,
  Sparkles,
  Cloud,
  ShieldCheck,
  Check,
  User,
  AlertCircle,
  BookOpen,
  FileText,
  Shield,
  X,
  ChevronRight
} from 'lucide-react';

interface ScenarioTemplate {
  id: string;
  number: number;
  title: string;
  badge: string;
  category: string;
  icon: any;
  summary: string;
  fullText: string;
  challengeTags: string[];
  persona?: any;
}

const ROLE_SCENARIOS: Record<string, ScenarioTemplate[]> = {
  CTO: [
    {
      id: 'cto-kafka',
      number: 1,
      title: 'High-Throughput Architecture Migration',
      badge: 'Distributed Systems • 20k TPS',
      category: 'System Design & Scalability',
      icon: Cloud,
      summary: 'Propose replacing a bottlenecked relational database with an event-driven Kafka and distributed cache architecture.',
      fullText: "You are the Chief Technology Officer (CTO) of a high-growth fintech enterprise processing 20,000 transactions per second. Your core relational database is suffering connection saturation and latency spikes during market open. The candidate is meeting with you to pitch a zero-downtime event-driven architecture using Kafka, distributed caching, and read-replica segregation. You must rigorously scrutinize technical risk, operational complexity, data consistency guarantees, disaster recovery failover, and maintenance overhead. Challenge vague claims and demand concrete architectural proofs.",
      challengeTags: ['20k TPS Latency', 'Eventual Consistency', 'Disaster Recovery']
    },
    {
      id: 'cto-tech-debt',
      number: 2,
      title: 'Monolith Decomposition & CI/CD Velocity',
      badge: 'Architecture • 7-Year Monolith',
      category: 'Engineering Governance',
      icon: Sparkles,
      summary: 'Pitch a phased domain-driven decomposition of a legacy monolith to eliminate 45-minute build cycles and deployment fragility.',
      fullText: "You are the Chief Technology Officer (CTO) of an enterprise logistics platform. Your engineering organization is struggling with 45-minute CI/CD build cycles and deployment fragility across a 7-year-old monolithic codebase. The candidate is meeting with you to propose a phased domain-driven decomposition into microservices. You expect concrete plans for service boundary isolation, shared database dependency untangling, zero-downtime rollback strategies, and measurable developer velocity gains. Press them on deployment risks and operational complexity.",
      challengeTags: ['Domain Boundaries', 'Database Coupling', 'Rollback SLAs']
    },
    {
      id: 'cto-security',
      number: 3,
      title: 'Multi-Region Failover & Zero-Trust Governance',
      badge: 'Cloud Security • 99.995% SLA',
      category: 'Cloud Infrastructure & Security',
      icon: ShieldCheck,
      summary: 'Evaluate an active-active multi-region Kubernetes deployment under strict HIPAA and SOC2 Type II compliance.',
      fullText: "You are the Chief Technology Officer (CTO) of a healthcare technology company operating under strict HIPAA and SOC2 Type II compliance. Your platform mandates a 99.995% uptime SLA with active-active multi-region failover and zero-trust mutual TLS service mesh. The candidate is meeting with you to pitch a Kubernetes-based multi-cloud deployment. You must rigorously scrutinize replication lag, split-brain failure handling, ingress security, compliance auditability, and multi-region network egress costs. Challenge their resilience proofs.",
      challengeTags: ['Zero-Trust mTLS', 'Replication Lag', 'Split-Brain Risk']
    }
  ],
  CEO: [
    {
      id: 'ceo-ai-platform',
      number: 1,
      title: 'Enterprise AI Workflow Automation',
      badge: 'Enterprise SaaS • 500 Employees',
      category: 'Operational Transformation',
      icon: Sparkles,
      summary: 'Pitch an enterprise AI workflow platform to automate manual cross-department operations and accelerate time-to-market.',
      fullText: "You are the Chief Executive Officer (CEO) of a 500-employee enterprise technology company. The candidate is meeting with you to pitch an AI workflow automation platform to streamline disconnected operations across departments. You care strictly about strategic business ROI, enterprise valuation multiple expansion, security governance, workforce adoption speed, and timeline to break-even. Probe the commercial payback timeline, total cost of ownership, and measurable productivity lift.",
      challengeTags: ['Valuation Impact', 'Payback Timeline', 'Employee Adoption']
    },
    {
      id: 'ceo-cloud-spend',
      number: 2,
      title: 'Gross Margin Defense & Cloud Cost Control',
      badge: 'E-Commerce • Margin Pressure',
      category: 'Capital Allocation',
      icon: Cloud,
      summary: 'Address skyrocketing infrastructure spend eroding company margins before high-volume seasonal revenue spikes.',
      fullText: "You are the Chief Executive Officer (CEO) of a rapidly growing e-commerce company experiencing unpredictable cloud infrastructure surges that are severely eroding gross margins before peak season. The candidate is meeting with you to propose an infrastructure right-sizing and automated cost governance strategy. You want to understand exact gross margin improvement, multi-year vendor contract lock-ins, operational downtime risks, and customer experience safeguards during peak revenue events.",
      challengeTags: ['Margin Expansion', 'Contract Lock-in', 'Peak Availability']
    },
    {
      id: 'ceo-security-risk',
      number: 3,
      title: 'Institutional Audit & Brand Defense',
      badge: 'Finance • Pre-IPO / Funding',
      category: 'Risk Mitigation',
      icon: ShieldCheck,
      summary: 'Upgrade corporate cybersecurity and zero-trust posture ahead of an institutional funding round or enterprise audit.',
      fullText: "You are the Chief Executive Officer (CEO) of a 300-employee financial services firm preparing for international market expansion and institutional regulatory audits. The candidate is presenting an enterprise zero-trust security defense suite. You must ensure corporate brand reputation protection, strict regulatory compliance, executive liability mitigation, and smooth employee productivity without adding crippling organizational bureaucracy.",
      challengeTags: ['Regulatory Fines', 'Executive Liability', 'Operational Friction']
    }
  ],
  HR: [
    {
      id: 'hr-culture-friction',
      number: 1,
      title: 'Cross-Functional Leadership Alignment',
      badge: 'Org Health • Scale-up',
      category: 'Culture & Retention',
      icon: Sparkles,
      summary: 'Resolve strategic friction between aggressive product timelines and engineering delivery burnout.',
      fullText: "You are the VP of People & Culture (HR Director) at a high-growth scale-up experiencing severe velocity friction and burnout between aggressive product leads and engineering delivery teams. The candidate is meeting with you to discuss organizational restructuring, retention safeguards for critical senior talent, and improved communication governance. Probe their emotional intelligence, empathy, and practical management frameworks.",
      challengeTags: ['Burnout Mitigation', 'Senior Retention', 'Executive Friction']
    },
    {
      id: 'hr-talent-scaling',
      number: 2,
      title: 'Leveling Framework & High-Growth Retention',
      badge: 'Talent Strategy • Doubling Team',
      category: 'Talent Calibration',
      icon: ShieldCheck,
      summary: 'Calibrate leveling frameworks and competitive retention equity packages during rapid headcount expansion.',
      fullText: "You are the Head of Talent & Total Rewards (HR) at a technology company doubling in headcount this year. The candidate is meeting with you to address market compensation compression, career leveling consistency, and retention packages for high-performing key contributors. You need to ensure internal pay equity, prevent team morale fractures, and protect the organization from key person risk.",
      challengeTags: ['Comp Compression', 'Leveling Consistency', 'Key Contributor Equity']
    },
    {
      id: 'hr-performance-reset',
      number: 3,
      title: 'Performance Reset & Culture Accountability',
      badge: 'Performance • Accountability',
      category: 'Performance Governance',
      icon: ShieldCheck,
      summary: 'Enforce high delivery standards while maintaining team psychological safety during an operational reset.',
      fullText: "You are the Chief People Officer (HR Executive) navigating sensitive team restructuring and underperforming division turnarounds. The candidate is meeting with you to establish performance accountability frameworks and department resets. You must ensure team morale is safeguarded, performance evaluations remain objective and defensible, legal severance policies are respected, and core cultural pillars are preserved.",
      challengeTags: ['Fair Standards', 'Psychological Safety', 'PIP Governance']
    }
  ],
  SALES_MANAGER: [
    {
      id: 'sales-incumbent',
      number: 1,
      title: 'Competitive Incumbent Displacement',
      badge: 'Enterprise Deal • Established Vendor',
      category: 'Value Defense',
      icon: Sparkles,
      summary: 'Convince an enterprise buyer to rip-and-replace an entrenched incumbent software suite.',
      fullText: "You are the VP of Commercial Enterprise Sales. Your company has been using an established competitor for 6 years and your team is accustomed to it. The candidate is meeting with you to pitch their product as a replacement. You must relentlessly probe and push back on switching friction, staff retraining downtime, contract termination costs, integration headaches, and aggressive pricing discount demands.",
      challengeTags: ['Switching Costs', 'Retraining Friction', 'ROI Justification']
    },
    {
      id: 'sales-discount-defense',
      number: 2,
      title: 'End-of-Quarter Discount Pushback',
      badge: 'Procurement • 35% Discount Request',
      category: 'Contract Negotiation',
      icon: ShieldCheck,
      summary: 'Defend gross margin and license value against aggressive enterprise procurement concession demands.',
      fullText: "You are the Commercial Sales Director & Procurement Committee Lead negotiating an enterprise contract before end-of-quarter sign-off. The candidate is presenting their commercial contract. You are pushing for a 35% across-the-board price discount, extended payment terms, and punitive custom SLA guarantees. Test how well the candidate defends their pricing, articulates business ROI, and trades concessions.",
      challengeTags: ['Procurement Pushback', 'Margin Protection', 'Milestone Packaging']
    },
    {
      id: 'sales-committee-pitch',
      number: 3,
      title: 'Multi-Stakeholder Executive Committee',
      badge: 'C-Suite Alignment • 6-Figure Deal',
      category: 'Consensus Building',
      icon: Sparkles,
      summary: 'Present an enterprise solution aligning the competing objectives of the CFO, CTO, and Business Operations.',
      fullText: "You are the Executive Sales Director evaluating whether the candidate can successfully lead and close a complex 6-figure enterprise transaction. You are assessing how the candidate manages competing stakeholder demands across the CFO (budget cuts), CTO (infosec & integration), and Head of Operations (implementation disruption). Probe their ability to navigate conflicting internal agendas and drive executive consensus.",
      challengeTags: ['Conflicting Priorities', 'Timeline Guarantees', 'Executive Sign-off']
    }
  ]
};

const DEFAULT_SCENARIOS: ScenarioTemplate[] = [
  {
    id: 'default-strategic',
    number: 1,
    title: 'Strategic Initiative Alignment',
    badge: 'Enterprise • High Stakes',
    category: 'Executive Strategy',
    icon: Sparkles,
    summary: 'Align strategic priorities, resource allocation, and key deliverables with an executive stakeholder.',
    fullText: "You are meeting with a senior executive to align on strategic priorities for an upcoming major corporate initiative. You must present a clear vision, establish measurable KPIs, address operational dependencies, and secure executive sponsorship and resource allocation.",
    challengeTags: ['Resource Allocation', 'Executive Buy-in', 'Measurable KPIs']
  },
  {
    id: 'default-problem-solving',
    number: 2,
    title: 'Crisis Mitigation & Operational Roadmap',
    badge: 'Operations • Fast-Paced',
    category: 'Problem Solving',
    icon: Cloud,
    summary: 'Present a comprehensive root-cause analysis and mitigation roadmap following an operational roadblock.',
    fullText: "You are meeting with a decision-maker following an unforeseen operational challenge. You need to walk them through what went wrong, your immediate containment actions, a structured long-term prevention plan, and how you will protect key business deliverables.",
    challengeTags: ['Root Cause Analysis', 'Containment Action', 'Risk Defense']
  },
  {
    id: 'default-negotiation',
    number: 3,
    title: 'High-Impact Project Scope Negotiation',
    badge: 'Project Governance • Deadlines',
    category: 'Stakeholder Negotiation',
    icon: ShieldCheck,
    summary: 'Negotiate project scope, resource constraints, and delivery deadlines with demanding stakeholders.',
    fullText: "You are meeting with a key enterprise stakeholder who is pushing for expanded project scope without extending delivery deadlines or increasing budget. You need to present pragmatic tradeoff options, defend engineering quality, and negotiate an acceptable phased milestone plan.",
    challengeTags: ['Scope Creep', 'Fixed Deadlines', 'Tradeoff Analysis']
  }
];

export const ScenarioBuilder: React.FC = () => {
  const navigate = useNavigate();
  const {
    role,
    scenario,
    setScenario,
    setTopic,
    setSessionId,
    setInitialMessage,
    setInitialAudio,
    setVoiceProfile,
  } = useStore();

  const [loading, setLoading] = useState(false);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);
  const [selectedScenarioTemplate, setSelectedScenarioTemplate] = useState<ScenarioTemplate | null>(null);

  // Modal flow state: null | 'description' | 'consent'
  const [activeModal, setActiveModal] = useState<'description' | 'consent' | null>(null);
  const [isConsentGiven, setIsConsentGiven] = useState(false);
  const [adminConfig, setAdminConfig] = useState<any | null>(null);
  const [publishedPersonas, setPublishedPersonas] = useState<any[]>([]);
  const [loadingPersonas, setLoadingPersonas] = useState(false);

  // Launching Progress State using Animate UI Progress
  const [isLaunching, setIsLaunching] = useState(false);
  const [launchProgress, setLaunchProgress] = useState(0);
  const [launchStage, setLaunchStage] = useState('Initializing simulation environment...');

  // Redirect if persona role is missing
  useEffect(() => {
    if (!role) {
      navigate('/roles');
    }
  }, [role, navigate]);

  // Fetch all personas published by admin for this role
  useEffect(() => {
    if (!role?.id) return;
    setLoadingPersonas(true);
    getAdminPersonasByRole(role.id)
      .then((personas) => {
        if (personas && Array.isArray(personas) && personas.length > 0) {
          setPublishedPersonas(personas);
        }
      })
      .catch((err) => {
        console.error('Failed to load published personas for role', err);
      })
      .finally(() => {
        setLoadingPersonas(false);
      });
  }, [role?.id]);

  // Determine role-relevant scenario cards (from published personas or fallback default templates)
  const activeScenarios = useMemo(() => {
    if (publishedPersonas.length > 0) {
      const iconList = [Cloud, Sparkles, ShieldCheck];
      return publishedPersonas.map((p, idx) => ({
        id: p.id || `persona-${idx}`,
        number: idx + 1,
        title: p.title || `${role?.name} Persona ${idx + 1}`,
        badge: `${p.preset || 'BALANCED'} • ${p.experience || 'Intermediate'} • ${p.style || 'Professional'}`,
        category: role?.name || 'Simulation',
        icon: iconList[idx % iconList.length],
        summary: p.conversation_overview || p.custom_scenario || 'Executive interview scenario calibrated by administrator.',
        fullText: p.custom_scenario || p.conversation_overview || 'Executive interview scenario.',
        challengeTags: p.challenge_tags && p.challenge_tags.length > 0 ? p.challenge_tags : [`${p.preset || 'BALANCED'} Rigor`, p.style || 'Executive'],
        persona: p,
      }));
    }

    const roleKey = (role?.id || '').toUpperCase();
    if (roleKey.includes('CTO')) return ROLE_SCENARIOS.CTO;
    if (roleKey.includes('CEO')) return ROLE_SCENARIOS.CEO;
    if (roleKey.includes('HR')) return ROLE_SCENARIOS.HR;
    if (roleKey.includes('SALES')) return ROLE_SCENARIOS.SALES_MANAGER;
    return DEFAULT_SCENARIOS;
  }, [role?.id, role?.name, publishedPersonas]);

  // Auto-select first scenario template by default
  useEffect(() => {
    if (activeScenarios.length > 0 && !selectedScenarioTemplate) {
      setSelectedScenarioTemplate(activeScenarios[0]);
      setScenario(activeScenarios[0].fullText);
    }
  }, [activeScenarios]);

  // Fetch admin configuration info to apply canonical settings
  useEffect(() => {
    if (!role?.id) return;
    getAdminRoleConfiguration(role.id)
      .then((cfg) => {
        setAdminConfig(cfg);
        if (cfg?.custom_scenario && (!scenario || scenario === activeScenarios[0]?.fullText)) {
          setScenario(cfg.custom_scenario);
        }
      })
      .catch((err) => {
        console.log('Using default admin configuration for role', err);
      });
  }, [role?.id]);

  const handleOpenScenarioBriefing = (template: ScenarioTemplate) => {
    setSelectedScenarioTemplate(template);
    setScenario(template.fullText);
    setErrorNotice(null);
    setActiveModal('description'); // Open Complete Description Modal
  };

  const handleStart = async () => {
    if (!scenario.trim()) {
      setErrorNotice('Please select a scenario briefing before starting.');
      return;
    }

    if (!isConsentGiven) {
      setErrorNotice('Please acknowledge and check the consent box to proceed.');
      return;
    }

    setErrorNotice(null);
    warmUpAudioContext();
    setLoading(true);
    setIsLaunching(true);
    setLaunchProgress(0);
    setLaunchStage('Loading administrator-published persona configuration...');

    const timeouts: any[] = [];
    timeouts.push(setTimeout(() => {
      setLaunchProgress(30);
      setLaunchStage(`Calibrating ${role.name} AI persona & behavioral policy...`);
    }, 250));

    timeouts.push(setTimeout(() => {
      setLaunchProgress(60);
      setLaunchStage('Configuring audio stream & neural evaluation engine...');
    }, 700));

    timeouts.push(setTimeout(() => {
      setLaunchProgress(85);
      setLaunchStage('Establishing duplex stream & preparing opening turn...');
    }, 1300));

    try {
      const chosenTemplate = selectedScenarioTemplate || activeScenarios[0];
      const derivedTopic =
        chosenTemplate?.persona?.scenario_title ||
        chosenTemplate?.title ||
        adminConfig?.scenario_title ||
        `${role.name} Executive Session`;

      setTopic({ id: chosenTemplate?.id || role.id, title: derivedTopic });

      // Pass selected persona ID and calibrated parameters to createSession!
      const data = await createSession({
        topic: derivedTopic,
        role: role.id,
        scenario,
        admin_configuration_id: chosenTemplate?.id,
        experience: chosenTemplate?.persona?.experience || adminConfig?.experience || 'Intermediate',
        style: chosenTemplate?.persona?.style || adminConfig?.style || 'Professional',
        voice: chosenTemplate?.persona?.voice || adminConfig?.voice || 'am_onyx',
      });

      timeouts.forEach(clearTimeout);

      setLaunchProgress(100);
      setLaunchStage('Ready! Entering executive interview room...');

      setSessionId(data.session_id);
      if (data.voice) {
        setVoiceProfile(data.voice);
      }
      if (data.initial_message) {
        setInitialMessage(data.initial_message);
      }
      if (data.initial_audio) {
        setInitialAudio(data.initial_audio);
      }

      setTimeout(() => {
        navigate('/conversation');
      }, 500);
    } catch (error: any) {
      timeouts.forEach(clearTimeout);
      setIsLaunching(false);
      setLaunchProgress(0);
      console.error('Failed to create session', error);
      const detail = error.response?.data?.detail || 'Please ensure backend is running.';
      setErrorNotice(typeof detail === 'string' ? detail : 'Failed to launch interview session. Please check backend connection.');
    } finally {
      setLoading(false);
    }
  };

  if (!role) {
    return null;
  }

  const activeTemplate = selectedScenarioTemplate || activeScenarios[0];

  return (
    <div className="min-h-screen bg-transparent text-slate-100 flex flex-col relative z-10 pb-16">
      {/* Top Header Bar */}
      <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-900/90 backdrop-blur-xl px-4 lg:px-8 py-3.5">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/roles')}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 transition-colors cursor-pointer"
            >
              <ArrowLeft size={13} /> Back
            </button>
            <button
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 transition-colors cursor-pointer"
            >
              <Home size={13} /> Home
            </button>

            {/* Breadcrumb pill */}
            <div className="hidden sm:flex items-center gap-2 text-xs border-l border-slate-800 pl-3">
              <span className="px-2.5 py-1 rounded-md bg-teal-500/10 text-teal-400 border border-teal-500/20 font-medium flex items-center gap-1.5">
                <User size={12} /> {role.name}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Learner Portal
            </span>
          </div>
        </div>
      </header>

      {/* Main Container - Focused Purely on Scenario Selection */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 lg:px-8 py-8 space-y-8">
        {/* Title & Introduction */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <BookOpen size={13} /> Stage 2 • Select Your Scenario
            </div>
            <h1 className="text-2xl md:text-4xl font-extrabold tracking-tight text-white mb-2">
              Choose Interview Scenario
            </h1>
            <p className="text-sm md:text-base text-slate-400 max-w-2xl">
              Select an executive challenge below. You will be able to review the full scenario briefing before agreeing to evaluation consent and starting the simulation.
            </p>
          </div>

          {/* Active Stakeholder Counterpart Badge */}
          <div className="shrink-0 p-4 rounded-2xl bg-slate-900/70 border border-slate-800 flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-indigo-500/20 to-teal-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 shrink-0">
              <User size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-white">{role.name}</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono">
                  {role.id}
                </span>
              </div>
              <span className="text-[11px] text-slate-400 block mt-0.5">
                Calibrated by Curriculum Admin
              </span>
            </div>
          </div>
        </div>

        {errorNotice && (
          <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-sm flex items-start gap-3 shadow-lg">
            <AlertCircle size={18} className="shrink-0 mt-0.5 text-rose-400" />
            <div className="flex-1 font-medium">{errorNotice}</div>
          </div>
        )}

        {/* Clean Scenario Selection Cards Grid */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <BookOpen size={14} className="text-indigo-400" />
              Available Scenarios for {role.name}
            </h2>
            <span className="text-xs text-slate-500">
              {loadingPersonas ? 'Fetching latest administrator personas...' : 'Click any card to read briefing & proceed'}
            </span>
          </div>

          {loadingPersonas ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-400">
              <Loader2 size={28} className="animate-spin text-indigo-400" />
              <span className="text-xs font-medium">Loading published personas for {role.name}...</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {activeScenarios.map((sc) => {
                const IconComp = sc.icon;
                const isSelected = activeTemplate?.id === sc.id;

                return (
                  <div
                    key={sc.id}
                    onClick={() => handleOpenScenarioBriefing(sc)}
                    className={`group p-6 rounded-3xl border transition-all duration-200 cursor-pointer flex flex-col justify-between hover:-translate-y-1 ${isSelected
                      ? 'bg-slate-900/90 border-indigo-500/70 shadow-2xl shadow-indigo-950/50 ring-1 ring-indigo-500/40'
                      : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-900/80'
                      }`}
                  >
                    <div className="space-y-4">
                      {/* Top Badges */}
                      <div className="flex items-center justify-between gap-2">
                        <span className="shrink-0 whitespace-nowrap text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          Scenario {sc.number}
                        </span>
                        <span className="min-w-0 text-[11px] text-slate-400 font-medium truncate">
                          {sc.badge}
                        </span>
                      </div>

                      {/* Icon & Title */}
                      <div className="flex items-start gap-3.5">
                        <div className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 transition-colors ${isSelected
                          ? 'bg-indigo-500/20 text-indigo-300'
                          : 'bg-slate-800 text-slate-400 group-hover:text-slate-200 group-hover:bg-slate-750'
                          }`}>
                          <IconComp size={22} />
                        </div>
                        <div className="min-w-0">
                          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                            {sc.category}
                          </span>
                          <h3 className="text-base font-bold text-white group-hover:text-indigo-200 transition-colors mt-0.5">
                            {sc.title}
                          </h3>
                        </div>
                      </div>

                      {/* Summary */}
                      <p className="text-xs text-slate-400 leading-relaxed line-clamp-3">
                        {sc.summary}
                      </p>

                      {/* Challenge Tags */}
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {sc.challengeTags.map((tag: string, idx: number) => (
                          <span
                            key={idx}
                            className="text-[10px] px-2 py-0.5 rounded-lg bg-slate-950/70 text-slate-400 border border-slate-800"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Card Footer Button */}
                    <div className="pt-6 mt-4 border-t border-slate-800/80 flex items-center justify-between gap-2">
                      <span className="shrink-0 whitespace-nowrap text-xs font-semibold text-indigo-400 group-hover:text-indigo-300 flex items-center gap-1.5">
                        Review Briefing <ChevronRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                      </span>
                      {isSelected && (
                        <span className="shrink-0 whitespace-nowrap inline-flex items-center gap-1 text-[11px] font-bold text-emerald-400 bg-emerald-950/60 border border-emerald-500/30 px-2.5 py-0.5 rounded-md">
                          <Check size={12} /> Selected
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      {/* ========================================================================= */}
      {/* POPUP MODAL 1: COMPLETE SCENARIO DESCRIPTION MODAL */}
      {/* ========================================================================= */}
      <AnimatePresence>
        {activeModal === 'description' && activeTemplate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-2xl bg-slate-900/95 border border-slate-800 rounded-3xl shadow-2xl backdrop-blur-2xl overflow-hidden flex flex-col max-h-[90vh]"
            >
              {/* Modal Header */}
              <div className="p-6 border-b border-slate-800/80 flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <span className="shrink-0 whitespace-nowrap text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-indigo-500/15 text-indigo-400 border border-indigo-500/25">
                      Scenario {activeTemplate.number} • {activeTemplate.category}
                    </span>
                    <span className="text-xs text-slate-400 font-medium">
                      {activeTemplate.badge}
                    </span>
                  </div>
                  <h2 className="text-xl md:text-2xl font-extrabold text-white">
                    {activeTemplate.title}
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer shrink-0"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Modal Body - Full Description & Dossier */}
              <div className="p-6 overflow-y-auto space-y-6 flex-1 text-sm">
                {/* Counterpart Information Banner */}
                <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-teal-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 shrink-0">
                    <User size={20} />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-white block">
                      Meeting Counterpart: {role.name} ({role.id})
                    </span>
                    <span className="text-xs text-slate-400 block leading-tight">
                      Simulation persona parameters configured by Curriculum Administrator.
                    </span>
                  </div>
                </div>

                {/* Admin-Defined Conversation Overview: "What is this conversation about?" */}
                <div className="p-4 rounded-2xl bg-gradient-to-br from-indigo-950/40 via-slate-950 to-slate-900 border border-indigo-500/30 space-y-2 shadow-inner">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-1.5">
                      <Sparkles size={13} className="text-indigo-400" />
                      What is this conversation about?
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold uppercase">
                      Overview
                    </span>
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed font-medium">
                    {activeTemplate.persona?.conversation_overview || activeTemplate.summary || adminConfig?.conversation_overview}
                  </p>
                </div>

                {/* Complete Scenario Directives Text */}
                <div className="space-y-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <FileText size={14} className="text-indigo-400" />
                    Full Meeting Mandate & Scenario Directives
                  </h3>
                  <div className="p-5 rounded-2xl bg-slate-950/90 border border-slate-800/90 text-sm text-slate-200 leading-relaxed whitespace-pre-line shadow-inner">
                    {activeTemplate.persona?.custom_scenario || activeTemplate.persona?.conversation_overview || scenario || activeTemplate.fullText}
                  </div>
                </div>

                {/* Challenge Tags */}
                {activeTemplate.challengeTags && activeTemplate.challengeTags.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">
                      Key Technical & Commercial Evaluation Dimensions
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {activeTemplate.challengeTags.map((tag: string, idx: number) => (
                        <span
                          key={idx}
                          className="text-xs px-3 py-1.5 rounded-xl bg-slate-800 text-slate-300 border border-slate-700/60 font-medium"
                        >
                          🎯 {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Modal Footer - Forward to Consent */}
              <div className="p-6 border-t border-slate-800/80 bg-slate-950/50 flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition-colors cursor-pointer"
                >
                  Back to Scenarios
                </button>
                <button
                  type="button"
                  onClick={() => setActiveModal('consent')}
                  className="px-6 py-3 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 shadow-lg shadow-indigo-950/40 transition-all flex items-center gap-2 cursor-pointer"
                >
                  <span>Proceed to Evaluation Consent</span>
                  <ArrowRight size={16} />
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ========================================================================= */}
      {/* POPUP MODAL 2: INFORMATION DISCLOSURE & CONSENT MODAL */}
      {/* ========================================================================= */}
      <AnimatePresence>
        {activeModal === 'consent' && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-xl bg-slate-900/95 border border-slate-800 rounded-3xl shadow-2xl backdrop-blur-2xl overflow-hidden flex flex-col max-h-[90vh]"
            >
              {/* Modal Header */}
              <div className="p-6 border-b border-slate-800/80 flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
                    <Shield size={20} />
                  </div>
                  <div>
                    <h2 className="text-xl font-extrabold text-white">
                      Information Disclosure & Consent
                    </h2>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Required evaluation terms prior to launching interview
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer shrink-0"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 overflow-y-auto space-y-5 text-sm">
                <p className="text-xs text-slate-300 leading-relaxed">
                  To provide accurate, objective performance feedback, audio delivery metrics, and strategic competency scoring, Elevate securely captures and evaluates session interaction data.
                </p>

                {/* Disclosure Checklist */}
                <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2 text-xs text-slate-300">
                  <span className="font-bold text-white text-[11px] uppercase tracking-wider block">
                    What we collect and evaluate:
                  </span>
                  <ul className="list-disc pl-5 space-y-1.5 text-slate-400 text-[11px]">
                    <li>Real-time microphone audio recordings and transcriptions.</li>
                    <li>Delivery metrics: talk-to-listen ratio, speech pace, and response latency.</li>
                    <li>Strategic metrics: discovery probing, objection handling, and executive alignment.</li>
                    <li>A comprehensive post-interview scorecard will be generated for your learner dashboard.</li>
                  </ul>
                </div>

                {/* Mandatory Consent Checkbox */}
                <div className="pt-1">
                  <label className="flex items-start gap-3 p-4 rounded-2xl bg-indigo-950/30 border border-indigo-500/40 hover:border-indigo-500 transition-colors cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={isConsentGiven}
                      onChange={(e) => setIsConsentGiven(e.target.checked)}
                      className="mt-0.5 w-4 h-4 rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-indigo-500/30 cursor-pointer shrink-0"
                    />
                    <span className="text-xs text-slate-200 leading-snug font-medium">
                      I have read the complete scenario briefing and <strong className="text-white">agree to have my audio recordings and responses stored and processed</strong> by Elevate's AI evaluation engine.
                    </span>
                  </label>
                </div>
              </div>

              {/* Modal Footer - Start Interview CTA */}
              <div className="p-6 border-t border-slate-800/80 bg-slate-950/50 flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setActiveModal('description')}
                  className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition-colors cursor-pointer"
                >
                  ← Back to Briefing
                </button>

                <button
                  type="button"
                  onClick={handleStart}
                  disabled={!isConsentGiven || loading}
                  className="px-6 py-3 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-indigo-600 via-indigo-500 to-teal-500 hover:from-indigo-500 hover:to-teal-400 disabled:opacity-40 disabled:cursor-not-allowed shadow-xl shadow-indigo-950/40 transition-all flex items-center gap-2 cursor-pointer"
                >
                  {loading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" /> Starting...
                    </>
                  ) : (
                    <>
                      <span>Start Interview</span>
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Simulation Launch Overlay with Animate UI Progress */}
      <AnimatePresence>
        {isLaunching && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 15 }}
              transition={{ duration: 0.25 }}
              className="w-full max-w-lg bg-slate-900/95 border border-slate-800 rounded-3xl p-6 md:p-8 shadow-2xl backdrop-blur-2xl relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute bottom-0 left-0 w-48 h-48 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />

              <div className="relative z-10 space-y-6">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-md shadow-indigo-500/20 shrink-0">
                    <Sparkles size={24} className="animate-spin text-indigo-400" style={{ animationDuration: '6s' }} />
                  </div>
                  <div>
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-[10px] font-bold uppercase tracking-wider mb-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Simulation Calibration
                    </div>
                    <h2 className="text-lg md:text-xl font-extrabold text-white tracking-tight">
                      Preparing Interview Environment
                    </h2>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-950/70 border border-slate-800/80 space-y-3 shadow-inner">
                  <Progress value={launchProgress} className="w-full space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <ProgressLabel className="text-xs text-slate-200 font-semibold truncate">
                        {launchStage}
                      </ProgressLabel>
                      <span className="text-xs font-mono text-indigo-400 font-bold shrink-0">
                        <ProgressValue /> %
                      </span>
                    </div>
                    <ProgressTrack indicatorClassName="bg-gradient-to-r from-indigo-500 via-purple-500 to-teal-400 shadow-lg shadow-indigo-500/40" />
                  </Progress>
                </div>

                <div className="grid grid-cols-2 gap-2.5 text-center text-xs">
                  <div className="p-2.5 rounded-xl bg-slate-950/50 border border-slate-800/60">
                    <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider block">Counterpart</span>
                    <span className="text-xs font-semibold text-slate-200 truncate block mt-0.5">{role.name}</span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-950/50 border border-slate-800/60">
                    <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider block">Consent Status</span>
                    <span className="text-xs font-semibold text-emerald-400 truncate block mt-0.5">Verified & Consented</span>
                  </div>
                </div>

                <p className="text-[11px] text-center text-slate-500 flex items-center justify-center gap-1.5">
                  <Loader2 size={12} className="animate-spin text-indigo-400" />
                  Synthesizing persona & establishing duplex WebSocket session...
                </p>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ScenarioBuilder;

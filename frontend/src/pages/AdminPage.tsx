import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useStore } from '../store/useStore';
import {
  getPersonaConfigurationSchema,
  getAllAdminPersonas,
  getAdminPersonasByRole,
  saveAdminPersona,
  deleteAdminPersona,
  type AdminRoleConfiguration
} from '../api/apiClient';
import {
  Shield,
  Sliders,
  Mic,
  Briefcase,
  Zap,
  Sparkles,
  Flame,
  Award,
  SlidersHorizontal,
  Check,
  Play,
  Square,
  Loader2,
  Save,
  RotateCcw,
  AlertCircle,
  CheckCircle2,
  LogOut,
  Eye,
  MessageSquare,
  X,
  AlertTriangle,
  Layers,
  Trash2,
  Edit3,
  Search,
  RefreshCw,
  FolderOpen,
  Plus
} from 'lucide-react';

interface VoiceOption {
  id: string;
  name: string;
  gender: 'Male' | 'Female';
  tone: string;
  accent: string;
  bestFor: string;
}

const VOICE_OPTIONS: VoiceOption[] = [
  { id: 'am_onyx', name: 'Onyx', gender: 'Male', tone: 'Authoritative & Poised', accent: 'American', bestFor: 'C-Suite, Leadership, Directing' },
  { id: 'am_michael', name: 'Michael', gender: 'Male', tone: 'Technical & Inquisitive', accent: 'American', bestFor: 'CTO, Architecture, Technical Q&A' },
  { id: 'af_bella', name: 'Bella', gender: 'Female', tone: 'Confident & Assertive', accent: 'American', bestFor: 'Negotiations, High-Impact Pitches' },
  { id: 'bf_emma', name: 'Emma', gender: 'Female', tone: 'Elegant & Articulate', accent: 'British', bestFor: 'Global C-Suite, Board, Talent & Strategy' },
];

const EXPERIENCE_OPTIONS = [
  { id: 'Beginner', label: 'Beginner', badge: 'Foundations', description: 'Fundamental concepts, exploratory questions, and constructive guidance' },
  { id: 'Intermediate', label: 'Intermediate', badge: 'Applied Skills', description: 'Practical execution, standard industry rigor, and real-world scenarios' },
  { id: 'Advanced', label: 'Advanced', badge: 'Architecture', description: 'Deep technical tradeoffs, failure mode proofs, and cross-functional impact' },
  { id: 'Expert', label: 'Executive', badge: 'Strategic C-Suite', description: 'Macro business valuation, strategic risk governance, and board-level ROI' },
];

const STYLE_OPTIONS = [
  { id: 'Professional', label: 'Professional', icon: Briefcase, color: 'text-indigo-400', description: 'Objective, structured, balanced corporate dialogue' },
  { id: 'Challenging', label: 'Challenging', icon: Zap, color: 'text-amber-400', description: 'Deep analytical probing, questioning assumptions and edge cases' },
  { id: 'Stress Interview', label: 'Stress Interview', icon: Flame, color: 'text-rose-400', description: 'Rapid pushback, skeptical scrutiny, and high-pressure cross-examination' },
  { id: 'Executive', label: 'Executive', icon: Award, color: 'text-purple-400', description: 'Concise, high-velocity, strictly focused on commercial metrics' },
  { id: 'Friendly', label: 'Collaborative', icon: Sparkles, color: 'text-teal-400', description: 'Supportive, developmental, and exploratory exchange' },
];

const ROLES = [
  { id: 'CTO', name: 'Chief Technology Officer', short: 'CTO', icon: '💻', desc: 'Evaluates architectural depth, scalability tradeoffs, and technical rigor.' },
  { id: 'CEO', name: 'Chief Executive Officer', short: 'CEO', icon: '👔', desc: 'Focuses on valuation impact, ROI payback timelines, and commercial strategy.' },
  { id: 'HR', name: 'Head of People & Culture', short: 'HR', icon: '👥', desc: 'Scrutinizes organizational dynamics, leadership fit, and team retention.' },
  { id: 'SALES_MANAGER', name: 'VP of Commercial Sales', short: 'Sales Dir', icon: '📈', desc: 'Challenges procurement pushback, vendor displacement, and margin defense.' },
];

const DEFAULT_CONVERSATION_OVERVIEWS: Record<string, string> = {
  CTO: "In this executive simulation, the candidate is pitching a high-throughput architectural migration to the CTO, who will rigorously scrutinize system latency, zero-downtime consistency, disaster recovery failover, and operational complexity.",
  CEO: "In this executive simulation, the candidate is presenting an enterprise platform strategy to the CEO, who focuses strictly on commercial ROI, gross margin protection, workforce adoption timeline, and valuation impact.",
  HR: "In this leadership simulation, the candidate is meeting with the Head of People to align cross-functional engineering and product governance, mitigate burnout, and structure fair retention leveling frameworks.",
  SALES_MANAGER: "In this commercial simulation, the candidate is pitching against an entrenched incumbent vendor to the VP of Sales, who will aggressively probe switching costs, procurement discounts, and gross margin defense.",
};

const DEFAULT_AGENT_CONTEXTS: Record<string, string> = {
  CTO: "You are the Chief Technology Officer evaluating a candidate's high-scale technical pitch. Your company infrastructure processes heavy production load (20,000 TPS). Scrutinize system latency, eventual consistency, disaster recovery failover mechanisms, database connection pooling limits, and operational support overhead. Push back firmly if the candidate provides vague or superficial architectural explanations.",
  CEO: "You are the Chief Executive Officer evaluating an enterprise strategic initiative. Focus strictly on top-line and bottom-line commercial impact, ROI payback timelines, workforce adoption friction, vendor lock-in risk, and overall valuation increase. Demand concrete numbers and strategic clarity.",
  HR: "You are the Head of People & Culture conducting an executive leadership interview. Probe the candidate's conflict resolution ability, burnout prevention tactics, cross-functional communication governance between engineering and product, and fair leveling/retention frameworks.",
  SALES_MANAGER: "You are the VP of Commercial Enterprise Sales. You have an entrenched incumbent vendor relationship of 6 years. Challenge switching friction, user migration downtime, procurement contract terms, price discounts, and measurable value proposition.",
};

export const AdminPage: React.FC = () => {
  const navigate = useNavigate();
  const { logout } = useStore();

  // Top Tabs: 'studio' | 'published'
  const [adminTab, setAdminTab] = useState<'studio' | 'published'>('studio');

  // Studio Selection State
  const [selectedRole, setSelectedRole] = useState<string>('CTO');
  const [rolePersonas, setRolePersonas] = useState<AdminRoleConfiguration[]>([]);
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(null);

  // Studio Form State
  const [personaTitle, setPersonaTitle] = useState<string>('');
  const [preset, setPreset] = useState<string>('BALANCED');
  const [traits, setTraits] = useState<Record<string, number>>({});
  const [voice, setVoice] = useState<string>('am_onyx');
  const [experience, setExperience] = useState<string>('Intermediate');
  const [style, setStyle] = useState<string>('Professional');
  const [conversationOverview, setConversationOverview] = useState<string>('');
  const [customScenario, setCustomScenario] = useState<string>('');
  const [scenarioTitle, setScenarioTitle] = useState<string>('');
  const [challengeTags, setChallengeTags] = useState<string[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  const [schema, setSchema] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Validation Popup Modal State
  const [validationModalOpen, setValidationModalOpen] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Published Scenarios Manager State
  const [allPersonas, setAllPersonas] = useState<AdminRoleConfiguration[]>([]);
  const [loadingPublished, setLoadingPublished] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilterRole, setSelectedFilterRole] = useState<string>('ALL');
  const [personaToDelete, setPersonaToDelete] = useState<AdminRoleConfiguration | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteSuccessNotice, setDeleteSuccessNotice] = useState<string | null>(null);

  // Audio preview state
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [voiceLoading, setVoiceLoading] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  // Load all published personas for Published Scenarios Manager tab
  const fetchAllPersonas = useCallback(async () => {
    setLoadingPublished(true);
    try {
      const data = await getAllAdminPersonas();
      setAllPersonas(data || []);
    } catch (err) {
      console.error('Failed to load published personas:', err);
    } finally {
      setLoadingPublished(false);
    }
  }, []);

  useEffect(() => {
    fetchAllPersonas();
  }, [fetchAllPersonas]);

  // Load schema and role personas whenever selectedRole changes
  const fetchRoleData = useCallback(async (roleKey: string, preferPersonaId?: string | null) => {
    setLoading(true);
    setSaveSuccess(null);
    setErrorMessage(null);

    try {
      const [schemaData, personasList] = await Promise.all([
        getPersonaConfigurationSchema(roleKey),
        getAdminPersonasByRole(roleKey)
      ]);

      setSchema(schemaData);
      setRolePersonas(personasList || []);

      if (personasList && personasList.length > 0) {
        // Find preferred persona or first one in list
        const activePersona = preferPersonaId
          ? personasList.find(p => p.id === preferPersonaId) || personasList[0]
          : personasList[0];

        setSelectedPersonaId(activePersona.id || null);
        setPersonaTitle(activePersona.title || `${roleKey} Persona`);
        setPreset(activePersona.preset || 'BALANCED');
        setTraits(activePersona.traits || {});
        setVoice(activePersona.voice || (roleKey === 'CTO' || roleKey === 'CEO' ? 'am_onyx' : 'af_bella'));
        setExperience(activePersona.experience || 'Intermediate');
        setStyle(activePersona.style || 'Professional');
        setConversationOverview(activePersona.conversation_overview || DEFAULT_CONVERSATION_OVERVIEWS[roleKey] || '');
        setCustomScenario(activePersona.custom_scenario || DEFAULT_AGENT_CONTEXTS[roleKey] || '');
        setScenarioTitle(activePersona.scenario_title || activePersona.title || '');
        setChallengeTags(activePersona.challenge_tags || []);
        setLastUpdatedAt(activePersona.updated_at || null);
      } else {
        // Initialize blank new persona draft
        const initTraits: Record<string, number> = {};
        schemaData.traits?.forEach((t: any) => {
          initTraits[t.id] = schemaData.default_traits?.[t.id] ?? t.default;
        });

        setSelectedPersonaId(null);
        setPersonaTitle(`${roleKey} Persona`);
        setPreset('BALANCED');
        setTraits(initTraits);
        setVoice(roleKey === 'CTO' || roleKey === 'CEO' ? 'am_onyx' : 'af_bella');
        setExperience('Intermediate');
        setStyle('Professional');
        setConversationOverview(DEFAULT_CONVERSATION_OVERVIEWS[roleKey] || '');
        setCustomScenario(DEFAULT_AGENT_CONTEXTS[roleKey] || '');
        setScenarioTitle('');
        setChallengeTags([]);
        setLastUpdatedAt(null);
      }
    } catch (err) {
      console.error('Failed to load role schema & personas:', err);
      setErrorMessage('Failed to load role configuration. Please check backend connection.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRoleData(selectedRole);
  }, [selectedRole, fetchRoleData]);

  // Select an existing persona to edit
  const handleSelectPersona = (p: AdminRoleConfiguration) => {
    setSelectedPersonaId(p.id || null);
    setPersonaTitle(p.title || `${selectedRole} Persona`);
    setPreset(p.preset || 'BALANCED');
    setTraits(p.traits || {});
    setVoice(p.voice || (selectedRole === 'CTO' || selectedRole === 'CEO' ? 'am_onyx' : 'af_bella'));
    setExperience(p.experience || 'Intermediate');
    setStyle(p.style || 'Professional');
    setConversationOverview(p.conversation_overview || DEFAULT_CONVERSATION_OVERVIEWS[selectedRole] || '');
    setCustomScenario(p.custom_scenario || DEFAULT_AGENT_CONTEXTS[selectedRole] || '');
    setScenarioTitle(p.scenario_title || p.title || '');
    setChallengeTags(p.challenge_tags || []);
    setLastUpdatedAt(p.updated_at || null);
    setSaveSuccess(null);
    setErrorMessage(null);
  };

  // Start a new persona draft under the current role
  const handleCreateNewPersona = () => {
    if (!schema) return;
    const initTraits: Record<string, number> = {};
    schema.traits?.forEach((t: any) => {
      initTraits[t.id] = schema.default_traits?.[t.id] ?? t.default;
    });

    setSelectedPersonaId(null);
    setPersonaTitle('');
    setPreset('BALANCED');
    setTraits(initTraits);
    setVoice(selectedRole === 'CTO' || selectedRole === 'CEO' ? 'am_onyx' : 'af_bella');
    setExperience('Intermediate');
    setStyle('Professional');
    setConversationOverview(DEFAULT_CONVERSATION_OVERVIEWS[selectedRole] || '');
    setCustomScenario(DEFAULT_AGENT_CONTEXTS[selectedRole] || '');
    setScenarioTitle('');
    setChallengeTags([]);
    setLastUpdatedAt(null);
    setSaveSuccess(null);
    setErrorMessage(null);
  };

  // Audio preview cleanup
  const stopVoiceAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.removeAttribute('src');
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    setPlayingVoiceId(null);
    setVoiceLoading(null);
  }, []);

  const handlePreviewVoice = async (voiceId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setVoice(voiceId);

    if (playingVoiceId === voiceId) {
      stopVoiceAudio();
      return;
    }

    stopVoiceAudio();
    setVoiceLoading(voiceId);

    try {
      const res = await fetch(`/api/voice/preview?voice_id=${encodeURIComponent(voiceId)}`);
      if (!res.ok) throw new Error(`Preview failed: ${res.status}`);

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;

      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => stopVoiceAudio();
      audio.onerror = () => stopVoiceAudio();

      await audio.play();
      setPlayingVoiceId(voiceId);
      setVoiceLoading(null);
    } catch (err) {
      console.error('Failed to preview voice:', err);
      stopVoiceAudio();
    }
  };

  useEffect(() => {
    return () => stopVoiceAudio();
  }, [stopVoiceAudio]);

  const handlePresetSelect = (presetObj: any) => {
    if (!schema) return;
    setPreset(presetObj.id);
    const newTraits: Record<string, number> = {};
    schema.traits?.forEach((t: any) => {
      const baseDefault = schema.default_traits?.[t.id] ?? t.default;
      const modValue = presetObj.trait_modifiers?.[t.id];
      newTraits[t.id] = modValue !== undefined ? modValue : baseDefault;
    });
    setTraits(newTraits);
  };

  const handleResetDefaults = () => {
    if (!schema) return;
    setPreset('BALANCED');
    const initTraits: Record<string, number> = {};
    schema.traits?.forEach((t: any) => {
      initTraits[t.id] = schema.default_traits?.[t.id] ?? t.default;
    });
    setTraits(initTraits);
  };

  const handleTraitChange = (traitId: string, value: number) => {
    setTraits(prev => ({
      ...prev,
      [traitId]: value,
    }));
  };

  // Validate that all configuration options are selected and set
  const validateAllOptions = (): string[] => {
    const missing: string[] = [];

    if (!selectedRole) {
      missing.push('Stakeholder Role selection');
    }
    if (!personaTitle || !personaTitle.trim()) {
      missing.push('Persona Title / Specialization Name');
    }
    if (!conversationOverview || !conversationOverview.trim()) {
      missing.push('Learner-Facing Description ("What is this conversation about?")');
    }
    if (!customScenario || !customScenario.trim()) {
      missing.push('Agent Interview Context (Passed to the AI Interviewer)');
    }
    if (!preset || !preset.trim()) {
      missing.push('Behavioral Preset Template');
    }
    if (!voice || !voice.trim()) {
      missing.push('Executive Voice Engine Profile');
    }
    if (!experience || !experience.trim()) {
      missing.push('Target Candidate Experience Level');
    }
    if (!style || !style.trim()) {
      missing.push('Meeting Rigor & Atmosphere');
    }

    if (schema?.traits) {
      const uncalibrated = schema.traits.filter(
        (t: any) => t.configurable && (typeof traits[t.id] !== 'number' || isNaN(traits[t.id]))
      );
      if (uncalibrated.length > 0) {
        missing.push(`Trait Sliders (${uncalibrated.map((t: any) => t.display_name).join(', ')})`);
      }
    }

    return missing;
  };

  const handleSaveConfiguration = async () => {
    setErrorMessage(null);
    setSaveSuccess(null);

    // Validate that all options are selected
    const errors = validateAllOptions();
    if (errors.length > 0) {
      setValidationErrors(errors);
      setValidationModalOpen(true);
      return;
    }

    setSaving(true);
    try {
      const payload: AdminRoleConfiguration = {
        id: selectedPersonaId || undefined,
        role: selectedRole,
        title: personaTitle.trim(),
        preset,
        traits,
        experience,
        style,
        voice,
        conversation_overview: conversationOverview.trim(),
        custom_scenario: customScenario.trim(),
        scenario_title: scenarioTitle || personaTitle.trim(),
        challenge_tags: challengeTags,
      };

      const result = await saveAdminPersona(payload);
      setSelectedPersonaId(result.id || null);
      setSaveSuccess(`Successfully published persona "${result.title}" for ${selectedRole}! Learners can now choose this persona in their scenario selection.`);
      setLastUpdatedAt(result.updated_at || new Date().toISOString());

      // Refresh both role-specific and global lists
      await Promise.all([
        fetchRoleData(selectedRole, result.id),
        fetchAllPersonas()
      ]);
    } catch (err: any) {
      console.error('Failed to save admin persona:', err);
      setErrorMessage(err.response?.data?.detail || 'Failed to save configuration. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  // Edit action from Published Scenarios tab: switches directly to Studio with that persona selected
  const handleEditPublishedPersona = (p: AdminRoleConfiguration) => {
    setSelectedRole(p.role.toUpperCase());
    setSelectedPersonaId(p.id || null);
    setPersonaTitle(p.title || `${p.role} Persona`);
    setPreset(p.preset || 'BALANCED');
    setTraits(p.traits || {});
    setVoice(p.voice || (p.role === 'CTO' || p.role === 'CEO' ? 'am_onyx' : 'af_bella'));
    setExperience(p.experience || 'Intermediate');
    setStyle(p.style || 'Professional');
    setConversationOverview(p.conversation_overview || '');
    setCustomScenario(p.custom_scenario || '');
    setScenarioTitle(p.scenario_title || p.title || '');
    setChallengeTags(p.challenge_tags || []);
    setAdminTab('studio');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Delete confirmation handler
  const handleConfirmDelete = async () => {
    if (!personaToDelete || !personaToDelete.id) return;
    setDeleting(true);
    try {
      await deleteAdminPersona(personaToDelete.id);
      setDeleteSuccessNotice(`Persona "${personaToDelete.title || personaToDelete.id}" has been deleted.`);
      setPersonaToDelete(null);
      await Promise.all([
        fetchAllPersonas(),
        fetchRoleData(selectedRole)
      ]);
      setTimeout(() => setDeleteSuccessNotice(null), 5000);
    } catch (err: any) {
      console.error('Failed to delete persona:', err);
      alert('Failed to delete persona: ' + (err.response?.data?.detail || err.message));
    } finally {
      setDeleting(false);
    }
  };

  const activeRoleMeta = ROLES.find(r => r.id === selectedRole) || ROLES[0];

  // Filter published personas based on search and role tab
  const filteredPersonas = allPersonas.filter(p => {
    const q = searchQuery.toLowerCase();
    const matchesSearch =
      !q ||
      (p.title && p.title.toLowerCase().includes(q)) ||
      (p.role && p.role.toLowerCase().includes(q)) ||
      (p.preset && p.preset.toLowerCase().includes(q)) ||
      (p.conversation_overview && p.conversation_overview.toLowerCase().includes(q)) ||
      (p.challenge_tags && p.challenge_tags.some(t => t.toLowerCase().includes(q)));

    const matchesRole = selectedFilterRole === 'ALL' || p.role.toUpperCase() === selectedFilterRole;
    return matchesSearch && matchesRole;
  });

  return (
    <div className="min-h-screen bg-transparent text-slate-100 flex flex-col relative z-10 pb-16">
      {/* Top Admin Bar */}
      <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-900/90 backdrop-blur-xl px-4 lg:px-8 py-3.5">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-amber-600 to-rose-600 flex items-center justify-center text-white shadow-md shadow-amber-600/30">
              <Shield size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-base tracking-tight text-white block leading-tight">
                  Admin Configuration Studio
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold uppercase tracking-wider">
                  Admin Console
                </span>
              </div>
              <span className="text-[11px] text-slate-400 block leading-tight">
                Multi-Persona Scenario Engineering & Global Governance
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-300 hover:text-white px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 border border-slate-700/80 transition-colors cursor-pointer"
            >
              <Eye size={13} />
              <span>Learner View</span>
            </button>
            <button
              onClick={() => {
                logout();
                navigate('/login');
              }}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-rose-300 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-rose-950/40 border border-slate-700/60 transition-colors cursor-pointer"
            >
              <LogOut size={13} />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Sub-Header Navigation Tabs */}
      <div className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md px-4 lg:px-8 sticky top-[61px] z-20 shadow-sm">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2 sm:gap-6">
            <button
              type="button"
              onClick={() => setAdminTab('studio')}
              className={`py-3.5 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
                adminTab === 'studio'
                  ? 'border-amber-500 text-amber-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <SlidersHorizontal size={15} />
              <span>Persona & Simulation Studio</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setAdminTab('published');
                fetchAllPersonas();
              }}
              className={`py-3.5 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
                adminTab === 'published'
                  ? 'border-amber-500 text-amber-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers size={15} />
              <span>Published Scenarios Manager</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] bg-slate-800 text-slate-300 border border-slate-700 font-mono">
                {allPersonas.length}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Workspace Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 lg:p-8">

        {/* ========================================================================= */}
        {/* TAB 1: PERSONA & SIMULATION STUDIO */}
        {/* ========================================================================= */}
        {adminTab === 'studio' && (
          <div className="space-y-6">

            {/* Studio Header Banner */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-3xl bg-slate-900/60 border border-slate-800 backdrop-blur-md shadow-xl">
              <div>
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/25 text-amber-400 text-xs font-bold uppercase tracking-wider mb-2">
                  <Sliders size={13} /> Multi-Persona Configuration Studio
                </div>
                <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                  Calibrate AI Stakeholder Personas & Agendas
                </h1>
                <p className="text-sm text-slate-400 mt-1 max-w-2xl leading-relaxed">
                  Build and publish multiple personas per role with distinct personality traits, meeting agendas, and executive voices.
                  {lastUpdatedAt && (
                    <span className="block text-[11px] text-slate-500 font-mono mt-1">
                      Last published: {new Date(lastUpdatedAt).toLocaleTimeString()}
                    </span>
                  )}
                </p>
              </div>

              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
                <button
                  type="button"
                  onClick={handleCreateNewPersona}
                  className="px-4 py-2.5 rounded-xl border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-xs font-bold flex items-center justify-center gap-2 transition-all cursor-pointer shadow-sm"
                >
                  <Plus size={15} />
                  <span>+ New Persona</span>
                </button>
                <button
                  type="button"
                  disabled={saving}
                  onClick={handleSaveConfiguration}
                  className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-rose-600 hover:from-amber-500 hover:to-rose-500 text-white text-xs font-bold shadow-lg shadow-amber-900/30 flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-50"
                >
                  {saving ? (
                    <>
                      <Loader2 size={16} className="animate-spin" /> Publishing...
                    </>
                  ) : (
                    <>
                      <Save size={16} /> Publish Persona
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Success / Error Alerts */}
            {saveSuccess && (
              <div className="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-sm flex items-start gap-3 shadow-lg">
                <CheckCircle2 size={18} className="shrink-0 mt-0.5 text-emerald-400" />
                <div className="flex-1 font-medium">{saveSuccess}</div>
              </div>
            )}

            {errorMessage && (
              <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-sm flex items-start gap-3 shadow-lg">
                <AlertCircle size={18} className="shrink-0 mt-0.5 text-rose-400" />
                <div className="flex-1 font-medium">{errorMessage}</div>
              </div>
            )}

            {/* 1. Stakeholder Role Switcher Tabs */}
            <div className="space-y-3">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
                <span>Step 1: Select Stakeholder Role</span>
                <span className="text-[11px] text-amber-400 font-medium">Configure multiple personas for any role</span>
              </label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {ROLES.map((r) => {
                  const isSelected = selectedRole === r.id;
                  const personaCount = allPersonas.filter(p => p.role === r.id).length;
                  return (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => setSelectedRole(r.id)}
                      className={`p-4 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                        isSelected
                          ? 'bg-amber-950/30 border-amber-500 ring-1 ring-amber-500/30 shadow-lg text-white'
                          : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:border-slate-700 hover:bg-slate-850'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-2xl">{r.icon}</span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-bold">
                            {personaCount} {personaCount === 1 ? 'Persona' : 'Personas'}
                          </span>
                          {isSelected && <Check size={14} className="text-amber-400" />}
                        </div>
                      </div>
                      <div>
                        <span className="text-sm font-bold text-white block">{r.short}</span>
                        <span className="text-xs text-slate-300 block font-medium truncate">{r.name}</span>
                        <p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-tight">{r.desc}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 2. Personas List / Selector under this Role */}
            <div className="p-4 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                    <Layers size={13} />
                    Personas for {activeRoleMeta.name} ({rolePersonas.length})
                  </span>
                  <span className="text-[11px] text-slate-400 hidden md:inline">
                    — Click any persona to edit, or create a new combination
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleCreateNewPersona}
                  className="px-3 py-1.5 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer self-start sm:self-auto"
                >
                  <Plus size={13} />
                  <span>+ Create New {activeRoleMeta.short} Persona</span>
                </button>
              </div>

              <div className="flex flex-wrap gap-2 pt-1">
                {rolePersonas.map((p) => {
                  const isSelected = selectedPersonaId === p.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handleSelectPersona(p)}
                      className={`px-3.5 py-2 rounded-xl text-xs font-semibold border transition-all flex items-center gap-2 cursor-pointer ${
                        isSelected
                          ? 'bg-amber-950/70 border-amber-500 text-white ring-1 ring-amber-500/50 shadow-md'
                          : 'bg-slate-950/80 border-slate-800 text-slate-300 hover:border-slate-700 hover:text-white'
                      }`}
                    >
                      <span>{activeRoleMeta.icon}</span>
                      <span className="truncate max-w-[220px] font-medium">{p.title || p.id}</span>
                      {isSelected ? (
                        <Check size={13} className="text-amber-400 shrink-0" />
                      ) : (
                        <span className="text-[10px] text-slate-500 font-mono">({p.preset})</span>
                      )}
                    </button>
                  );
                })}

                {selectedPersonaId === null && (
                  <div className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-950/50 border border-emerald-500 text-emerald-300 flex items-center gap-2 animate-pulse">
                    <Sparkles size={13} className="text-emerald-400" />
                    <span>Creating New Persona Draft</span>
                  </div>
                )}
              </div>
            </div>

            {loading ? (
              <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
                <Loader2 size={32} className="animate-spin text-amber-400" />
                <span className="text-sm font-medium">Loading configuration for {selectedRole}...</span>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Left 2 Cols: Persona Title, Overview, Presets & Trait Sliders */}
                <div className="lg:col-span-2 space-y-6">

                  {/* Persona Title / Specialization Field */}
                  <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md shadow-2xl space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold uppercase tracking-wider text-amber-300 flex items-center gap-2">
                        <Edit3 size={14} className="text-amber-400" />
                        Persona Title / Specialization <span className="text-rose-400 text-xs">*</span>
                      </label>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                        {selectedPersonaId ? `ID: ${selectedPersonaId}` : 'New Persona Draft'}
                      </span>
                    </div>
                    <input
                      type="text"
                      value={personaTitle}
                      onChange={(e) => setPersonaTitle(e.target.value)}
                      placeholder={`e.g., ${selectedRole} - High-Throughput & Scalability Architect`}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500 transition-all font-semibold"
                    />
                    <p className="text-[11px] text-slate-400 leading-tight">
                      Learners will see this title on scenario selection cards to choose between multiple {selectedRole} personas.
                    </p>
                  </div>

                  {/* 1. Learner-Facing Description ("What is this conversation about?") */}
                  <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md shadow-2xl space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <label className="text-xs font-bold uppercase tracking-wider text-amber-300 flex items-center gap-2">
                          <MessageSquare size={14} className="text-amber-400" />
                          Learner Description: "What is this conversation about?" <span className="text-rose-400 text-xs">*</span>
                        </label>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold uppercase tracking-wider">
                          Visible to Learner
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500 font-mono">
                        {conversationOverview.length} chars
                      </span>
                    </div>

                    <textarea
                      rows={3}
                      value={conversationOverview}
                      onChange={(e) => setConversationOverview(e.target.value)}
                      placeholder={`Describe the high-level meeting topic, goal, and what the learner is pitching...`}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500 transition-all leading-relaxed"
                    />

                    <p className="text-[11px] text-slate-400 leading-tight">
                      This text is shown to the <strong className="text-slate-200">learner</strong> on scenario selection cards and in the Description Modal so they understand what the meeting is about before giving consent.
                    </p>
                  </div>

                  {/* 2. Agent Interview Context (Passed to the AI Interviewer) */}
                  <div className="p-6 rounded-2xl bg-slate-900/80 border border-indigo-500/30 backdrop-blur-md shadow-2xl space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <label className="text-xs font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-2">
                          <Sparkles size={14} className="text-indigo-400" />
                          Agent Interview Context (Passed to the AI Interviewer) <span className="text-rose-400 text-xs">*</span>
                        </label>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-bold uppercase tracking-wider">
                          Injected into AI Agent
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500 font-mono">
                        {customScenario.length} chars
                      </span>
                    </div>

                    <textarea
                      rows={5}
                      value={customScenario}
                      onChange={(e) => setCustomScenario(e.target.value)}
                      placeholder={`Enter the internal simulation context, technical parameters, company background, and hidden objections that the AI interviewer must probe...`}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-all leading-relaxed font-mono"
                    />

                    <p className="text-[11px] text-indigo-300/80 leading-tight">
                      This context is passed directly to the <strong className="text-indigo-200">AI agent</strong> during the interview. It governs the agent's background, internal motivations, technical expectations, and what the agent will scrutinize and challenge.
                    </p>
                  </div>

                  {/* Preset Behavioral Profiles */}
                  <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md shadow-2xl space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
                            <Award size={15} className="text-amber-400" />
                            Step 2: Behavioral Archetype Preset <span className="text-rose-400 text-xs">*</span>
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold font-mono">
                            Active: {preset}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-1">
                          Select an archetype to automatically calibrate baseline traits, skepticism, and interview rigor.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={handleResetDefaults}
                        className="text-xs font-semibold text-slate-400 hover:text-amber-300 flex items-center gap-1.5 transition-colors cursor-pointer self-start sm:self-auto px-2.5 py-1.5 rounded-lg bg-slate-950/60 border border-slate-800 hover:border-slate-700"
                      >
                        <RotateCcw size={12} />
                        <span>Reset Defaults</span>
                      </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
                      {schema?.presets?.map((p: any) => {
                        const isSelected = preset === p.id;
                        const displayName = p.display_name || p.name || p.id;
                        return (
                          <button
                            key={p.id}
                            type="button"
                            onClick={() => handlePresetSelect(p)}
                            className={`p-4 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between group ${
                              isSelected
                                ? 'bg-gradient-to-b from-amber-950/70 via-slate-900 to-slate-950 border-amber-500 text-white ring-1 ring-amber-500/40 shadow-xl shadow-amber-950/40'
                                : 'bg-slate-950/90 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-900/90 hover:text-white'
                            }`}
                          >
                            <div>
                              <div className="flex items-center justify-between mb-1.5 gap-2">
                                <span className={`text-sm font-bold block ${isSelected ? 'text-amber-300' : 'text-slate-100 group-hover:text-amber-200 transition-colors'}`}>
                                  {displayName}
                                </span>
                                {isSelected ? (
                                  <span className="px-1.5 py-0.5 rounded-md bg-amber-500/20 text-amber-300 text-[10px] font-bold border border-amber-500/30 flex items-center gap-1 shrink-0">
                                    <Check size={11} /> Selected
                                  </span>
                                ) : (
                                  <span className="text-[10px] font-mono text-slate-500 uppercase px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 shrink-0">
                                    {p.id}
                                  </span>
                                )}
                              </div>

                              <p className="text-xs text-slate-400 leading-relaxed font-normal mt-1">
                                {p.description}
                              </p>
                            </div>

                            {p.trait_modifiers && Object.keys(p.trait_modifiers).length > 0 && (
                              <div className="flex flex-wrap gap-1 pt-2.5 mt-3 border-t border-slate-800/80">
                                {Object.entries(p.trait_modifiers).slice(0, 3).map(([k, v]) => (
                                  <span key={k} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 text-slate-400 font-mono border border-slate-800/80">
                                    {k}: <strong className="text-amber-400">{Math.round((v as number) * 100)}%</strong>
                                  </span>
                                ))}
                              </div>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Dynamic Trait Calibration Sliders */}
                  <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md shadow-2xl space-y-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">
                          Step 3: Fine-Tune Stakeholder Personality Sliders <span className="text-rose-400 text-xs">*</span>
                        </span>
                        <p className="text-xs text-slate-400 mt-0.5">
                          Directly governs the LLM behavioral policy engine and pushback frequency.
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {schema?.traits?.map((t: any) => {
                        const val = traits[t.id] ?? schema.default_traits?.[t.id] ?? t.default ?? 0.5;
                        const pct = Math.round(val * 100);

                        return (
                          <div
                            key={t.id}
                            className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-2 hover:border-slate-700 transition-colors"
                          >
                            <div className="flex items-center justify-between text-xs">
                              <div>
                                <span className="font-bold text-slate-200 block">{t.display_name}</span>
                                <span className="text-[10px] text-slate-500 font-mono">{t.id}</span>
                              </div>
                              <span className="font-mono font-bold text-amber-400 text-xs bg-amber-950/50 px-2 py-0.5 rounded border border-amber-500/20">
                                {pct}%
                              </span>
                            </div>

                            <input
                              type="range"
                              min={t.min ?? 0.0}
                              max={t.max ?? 1.0}
                              step={t.step ?? 0.05}
                              value={val}
                              onChange={(e) => handleTraitChange(t.id, parseFloat(e.target.value))}
                              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
                            />

                            <div className="flex items-center justify-between text-[10px] text-slate-500">
                              <span>Low Pushback</span>
                              <p className="truncate max-w-[150px] text-slate-400 text-center">{t.description}</p>
                              <span>Extreme Rigor</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                </div>

                {/* Right Col: Voice, Experience, Style & Publishing */}
                <div className="space-y-6">

                  {/* Executive Voice Profile Engine */}
                  <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md shadow-2xl space-y-4">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <Mic size={13} className="text-amber-400" />
                        Executive Voice Engine Profile <span className="text-rose-400 text-xs">*</span>
                      </span>
                    </span>

                    <div className="space-y-2.5">
                      {VOICE_OPTIONS.map((v) => {
                        const isSelected = voice === v.id;
                        const isPlaying = playingVoiceId === v.id;
                        const isLoadingAudio = voiceLoading === v.id;

                        return (
                          <div
                            key={v.id}
                            onClick={() => setVoice(v.id)}
                            className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                              isSelected
                                ? 'bg-amber-950/40 border-amber-500 ring-1 ring-amber-500/30 text-white'
                                : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700 hover:bg-slate-900'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <div className="flex items-center gap-1.5">
                                <span className="text-xs font-bold text-slate-200">{v.name}</span>
                                <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                                  {v.gender}
                                </span>
                              </div>
                              {isSelected && <Check size={12} className="text-amber-400" />}
                            </div>

                            <p className="text-[10px] text-slate-400 mb-2 leading-tight">
                              {v.tone}
                            </p>

                            <button
                              type="button"
                              onClick={(e) => handlePreviewVoice(v.id, e)}
                              className={`w-full py-1 px-2 rounded-lg text-[11px] font-medium transition-all flex items-center justify-center gap-1.5 border cursor-pointer ${
                                isPlaying
                                  ? 'bg-rose-950/80 border-rose-500/60 text-rose-300'
                                  : 'bg-slate-800/80 hover:bg-slate-800 border-slate-700/60 text-slate-300 hover:text-white'
                              }`}
                            >
                              {isLoadingAudio ? (
                                <Loader2 size={11} className="animate-spin" />
                              ) : isPlaying ? (
                                <>
                                  <Square size={10} className="fill-current" /> Stop
                                </>
                              ) : (
                                <>
                                  <Play size={10} className="fill-current" /> Listen Preview
                                </>
                              )}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Target Candidate Experience Calibration */}
                  <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md shadow-2xl space-y-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">
                      Target Candidate Experience Level <span className="text-rose-400 text-xs">*</span>
                    </span>
                    <div className="grid grid-cols-2 gap-2">
                      {EXPERIENCE_OPTIONS.map((exp) => {
                        const isSelected = experience === exp.id;
                        return (
                          <button
                            key={exp.id}
                            type="button"
                            onClick={() => setExperience(exp.id)}
                            className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                              isSelected
                                ? 'bg-amber-950/40 border-amber-500 text-white ring-1 ring-amber-500/30'
                                : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-0.5">
                              <span className={`text-xs font-bold ${isSelected ? 'text-amber-300' : 'text-slate-300'}`}>
                                {exp.label}
                              </span>
                              {isSelected && <Check size={12} className="text-amber-400" />}
                            </div>
                            <span className="text-[10px] text-slate-500 block leading-tight truncate">
                              {exp.badge}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Meeting Rigor & Atmosphere */}
                  <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md shadow-2xl space-y-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">
                      Meeting Rigor & Atmosphere <span className="text-rose-400 text-xs">*</span>
                    </span>
                    <div className="space-y-2">
                      {STYLE_OPTIONS.map((st) => {
                        const isSelected = style === st.id;
                        const IconComponent = st.icon;
                        return (
                          <button
                            key={st.id}
                            type="button"
                            onClick={() => setStyle(st.id)}
                            className={`w-full p-2.5 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between ${
                              isSelected
                                ? 'bg-amber-950/40 border-amber-500 text-white ring-1 ring-amber-500/30'
                                : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <IconComponent size={14} className={st.color} />
                              <div>
                                <span className="text-xs font-bold text-slate-200 block">{st.label}</span>
                                <span className="text-[10px] text-slate-400 block leading-tight">{st.description}</span>
                              </div>
                            </div>
                            {isSelected && <Check size={13} className="text-amber-400 shrink-0" />}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Action Button Pad */}
                  <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md shadow-2xl space-y-3">
                    <button
                      type="button"
                      disabled={saving}
                      onClick={handleSaveConfiguration}
                      className="w-full py-4 px-6 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-amber-600 via-amber-500 to-rose-600 hover:from-amber-500 hover:to-rose-500 shadow-xl shadow-amber-950/50 hover:shadow-amber-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                    >
                      {saving ? (
                        <>
                          <Loader2 size={16} className="animate-spin" /> Publishing Persona...
                        </>
                      ) : (
                        <>
                          <Save size={16} /> Publish Persona to Learners
                        </>
                      )}
                    </button>
                    <p className="text-[11px] text-center text-slate-400 leading-tight">
                      Saves this persona configuration to SQLite database. It will immediately appear in the Learner Scenario selection list for <span className="text-amber-300 font-semibold">{selectedRole}</span>.
                    </p>
                  </div>

                </div>

              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: PUBLISHED SCENARIOS MANAGER (LIST ALL PERSONAS, EDIT & DELETE) */}
        {/* ========================================================================= */}
        {adminTab === 'published' && (
          <div className="space-y-6">
            {/* Header with Search and Stats */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-3xl bg-slate-900/60 border border-slate-800 backdrop-blur-md shadow-xl">
              <div>
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-indigo-400 text-xs font-bold uppercase tracking-wider mb-2">
                  <Layers size={13} /> Active Catalog ({allPersonas.length} Personas)
                </div>
                <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                  Published Personas & Scenario Governance
                </h1>
                <p className="text-sm text-slate-400 mt-1 max-w-2xl leading-relaxed">
                  Review all active personas published for learners across roles. You can edit any persona's traits and agenda, or delete old scenarios.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    handleCreateNewPersona();
                    setAdminTab('studio');
                  }}
                  className="px-4 py-2.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 text-xs font-bold flex items-center gap-2 transition-colors cursor-pointer"
                >
                  <Plus size={15} />
                  <span>+ Create Persona</span>
                </button>
                <button
                  type="button"
                  onClick={fetchAllPersonas}
                  disabled={loadingPublished}
                  className="px-4 py-2.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer"
                >
                  <RefreshCw size={14} className={loadingPublished ? 'animate-spin' : ''} />
                  <span>Refresh</span>
                </button>
              </div>
            </div>

            {/* Notification Alert */}
            {deleteSuccessNotice && (
              <div className="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-sm flex items-start gap-3 shadow-lg">
                <CheckCircle2 size={18} className="shrink-0 mt-0.5 text-emerald-400" />
                <div className="flex-1 font-medium">{deleteSuccessNotice}</div>
              </div>
            )}

            {/* Role Filter Chips & Search Filter Bar */}
            <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
              <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
                {/* Role Tabs Filter */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  <button
                    type="button"
                    onClick={() => setSelectedFilterRole('ALL')}
                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                      selectedFilterRole === 'ALL'
                        ? 'bg-amber-500 text-slate-950 font-bold'
                        : 'bg-slate-950 border border-slate-800 text-slate-300 hover:border-slate-700'
                    }`}
                  >
                    All Roles ({allPersonas.length})
                  </button>

                  {ROLES.map(r => {
                    const count = allPersonas.filter(p => p.role.toUpperCase() === r.id).length;
                    const isSelected = selectedFilterRole === r.id;
                    return (
                      <button
                        key={r.id}
                        type="button"
                        onClick={() => setSelectedFilterRole(r.id)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 cursor-pointer ${
                          isSelected
                            ? 'bg-amber-500 text-slate-950 font-bold'
                            : 'bg-slate-950 border border-slate-800 text-slate-300 hover:border-slate-700'
                        }`}
                      >
                        <span>{r.icon}</span>
                        <span>{r.short}</span>
                        <span className="text-[10px] opacity-75 font-mono">({count})</span>
                      </button>
                    );
                  })}
                </div>

                {/* Search input */}
                <div className="relative max-w-xs w-full">
                  <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search title, agenda, traits..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500 transition-all"
                  />
                </div>
              </div>
            </div>

            {/* Published Personas Cards List */}
            {loadingPublished ? (
              <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
                <Loader2 size={32} className="animate-spin text-amber-400" />
                <span className="text-sm font-medium">Loading published personas...</span>
              </div>
            ) : filteredPersonas.length === 0 ? (
              <div className="py-16 text-center rounded-3xl border border-dashed border-slate-800 bg-slate-900/30 p-8 space-y-3">
                <FolderOpen size={36} className="mx-auto text-slate-500" />
                <h3 className="text-base font-bold text-slate-200">No personas match your filter</h3>
                <p className="text-xs text-slate-400 max-w-sm mx-auto">
                  Try clearing your search query or create a new persona in the Studio tab.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    handleCreateNewPersona();
                    setAdminTab('studio');
                  }}
                  className="px-4 py-2 rounded-xl bg-amber-500 text-slate-950 font-bold text-xs inline-flex items-center gap-1.5"
                >
                  <Plus size={14} />
                  <span>Create New Persona</span>
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-5">
                {filteredPersonas.map((persona) => {
                  const roleMeta = ROLES.find(r => r.id === persona.role) || {
                    id: persona.role,
                    name: persona.role,
                    short: persona.role,
                    icon: '👤',
                    desc: 'Executive stakeholder'
                  };

                  return (
                    <div
                      key={persona.id}
                      className="p-6 rounded-3xl border border-slate-800 bg-slate-900/80 hover:border-slate-700 shadow-xl transition-all space-y-4"
                    >
                      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
                        {/* Left Side: Persona Identity & Overview */}
                        <div className="space-y-3.5 flex-1">
                          <div className="flex items-center gap-3">
                            <span className="text-3xl">{roleMeta.icon}</span>
                            <div>
                              <div className="flex items-center gap-2 flex-wrap">
                                <h3 className="text-lg font-bold text-white">
                                  {persona.title || `${persona.role} Persona`}
                                </h3>
                                <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                  Live for Learners
                                </span>
                                <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                                  {persona.role}
                                </span>
                              </div>
                              <p className="text-xs text-slate-400 mt-0.5 leading-tight">
                                {roleMeta.name} • ID: <span className="font-mono text-slate-500">{persona.id}</span>
                              </p>
                            </div>
                          </div>

                          {/* 1. "What is this conversation about?" Box (Learner-Facing) */}
                          <div className="p-4 rounded-2xl bg-slate-950/90 border border-slate-800/90 space-y-1.5 shadow-inner">
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] font-bold uppercase tracking-wider text-amber-300 flex items-center gap-1.5">
                                <MessageSquare size={13} className="text-amber-400" />
                                Learner Description: What is this conversation about?
                              </span>
                              <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-bold uppercase">
                                Visible to Learner
                              </span>
                            </div>
                            <p className="text-xs text-slate-200 leading-relaxed font-normal">
                              {persona.conversation_overview || 'No learner description provided.'}
                            </p>
                          </div>

                          {/* 2. Agent Interview Context Box (Injected into Agent) */}
                          <div className="p-4 rounded-2xl bg-indigo-950/20 border border-indigo-500/30 space-y-1.5 shadow-inner">
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-1.5">
                                <Sparkles size={13} className="text-indigo-400" />
                                Agent Interview Context (Passed to AI Interviewer)
                              </span>
                              <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-bold uppercase">
                                Injected into AI Agent
                              </span>
                            </div>
                            <p className="text-xs text-slate-300 leading-relaxed font-mono">
                              {persona.custom_scenario || persona.conversation_overview || 'No agent context configured.'}
                            </p>
                          </div>

                          {/* Parameters Grid */}
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-xs">
                            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/60">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Archetype</span>
                              <span className="text-xs font-semibold text-amber-300 truncate block mt-0.5">
                                {persona.preset || 'BALANCED'}
                              </span>
                            </div>
                            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/60">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Voice Engine</span>
                              <span className="text-xs font-semibold text-indigo-300 truncate block mt-0.5 capitalize">
                                {(persona.voice || 'am_onyx').replace('am_', '').replace('af_', '')}
                              </span>
                            </div>
                            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/60">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Candidate Level</span>
                              <span className="text-xs font-semibold text-teal-300 truncate block mt-0.5">
                                {persona.experience || 'Intermediate'}
                              </span>
                            </div>
                            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/60">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Atmosphere / Rigor</span>
                              <span className="text-xs font-semibold text-rose-300 truncate block mt-0.5">
                                {persona.style || 'Professional'}
                              </span>
                            </div>
                          </div>

                          {/* Top Traits Preview */}
                          {persona.traits && Object.keys(persona.traits).length > 0 && (
                            <div className="flex flex-wrap gap-1.5 pt-1">
                              {Object.entries(persona.traits).map(([traitKey, val]) => (
                                <span
                                  key={traitKey}
                                  className="text-[10px] px-2 py-0.5 rounded-lg bg-slate-800 text-slate-300 border border-slate-700/60 font-mono"
                                >
                                  {traitKey}: <strong className="text-amber-300">{Math.round((val as number) * 100)}%</strong>
                                </span>
                              ))}
                            </div>
                          )}

                          {/* Challenge Tags */}
                          {persona.challenge_tags && persona.challenge_tags.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 pt-0.5">
                              {persona.challenge_tags.map((tag, idx) => (
                                <span
                                  key={idx}
                                  className="text-[10px] px-2 py-0.5 rounded-md bg-indigo-950/40 text-indigo-300 border border-indigo-500/20"
                                >
                                  #{tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Right Side: Edit & Delete Actions */}
                        <div className="flex flex-row lg:flex-col items-center gap-2.5 shrink-0 pt-2 lg:pt-0">
                          <button
                            type="button"
                            onClick={() => handleEditPublishedPersona(persona)}
                            className="flex-1 lg:flex-initial px-4 py-2.5 rounded-xl bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/40 text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer shadow-xs"
                          >
                            <Edit3 size={14} />
                            <span>Edit in Studio</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => setPersonaToDelete(persona)}
                            className="flex-1 lg:flex-initial px-4 py-2.5 rounded-xl bg-rose-950/30 hover:bg-rose-900/50 text-rose-300 border border-rose-500/30 hover:border-rose-500/60 text-xs font-semibold transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                          >
                            <Trash2 size={14} />
                            <span>Delete Persona</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

      </main>

      {/* ========================================================================= */}
      {/* POPUP MODAL: VALIDATION ALERT MODAL (SET ALL OPTIONS) */}
      {/* ========================================================================= */}
      <AnimatePresence>
        {validationModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-md bg-slate-900 border border-amber-500/40 rounded-3xl shadow-2xl p-6 space-y-4"
            >
              <div className="flex items-start gap-3.5">
                <div className="w-10 h-10 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
                  <AlertTriangle size={20} />
                </div>
                <div className="flex-1">
                  <h3 className="text-base font-bold text-white">
                    Set All Configuration Options
                  </h3>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                    Please ensure all required persona parameters are configured before publishing to learners:
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setValidationModalOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-rose-400 block">
                  Missing or Incomplete Parameters:
                </span>
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {validationErrors.map((err, idx) => (
                    <li key={idx} className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-400 shrink-0" />
                      <span>{err}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="button"
                  onClick={() => setValidationModalOpen(false)}
                  className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs transition-colors cursor-pointer"
                >
                  Review & Fix Options
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ========================================================================= */}
      {/* POPUP MODAL: DELETE CONFIRMATION MODAL */}
      {/* ========================================================================= */}
      <AnimatePresence>
        {personaToDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-md bg-slate-900 border border-rose-500/40 rounded-3xl shadow-2xl p-6 space-y-4"
            >
              <div className="flex items-start gap-3.5">
                <div className="w-10 h-10 rounded-2xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400 shrink-0">
                  <Trash2 size={20} />
                </div>
                <div className="flex-1">
                  <h3 className="text-base font-bold text-white">
                    Delete Persona Configuration?
                  </h3>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                    Are you sure you want to delete persona <strong className="text-white">"{personaToDelete.title}"</strong> ({personaToDelete.role})? Learners will no longer see this persona scenario.
                  </p>
                </div>
              </div>

              <div className="pt-2 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setPersonaToDelete(null)}
                  disabled={deleting}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmDelete}
                  disabled={deleting}
                  className="px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  {deleting ? (
                    <>
                      <Loader2 size={13} className="animate-spin" /> Deleting...
                    </>
                  ) : (
                    <span>Confirm Delete</span>
                  )}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
};

export default AdminPage;

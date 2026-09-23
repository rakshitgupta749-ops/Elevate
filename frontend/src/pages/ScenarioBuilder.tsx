import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useStore } from '../store/useStore';
import { createSession } from '../api/apiClient';
import { ArrowRight, Loader2, Sparkles, Cloud, ShieldCheck, X, Check, Eye } from 'lucide-react';
import { PersonaConfigurator } from '../components/PersonaConfigurator';

interface ExampleScenario {
  id: string;
  number: number;
  title: string;
  badge: string;
  icon: any;
  summary: string;
  fullText: string;
}

const EXAMPLE_SCENARIOS: ExampleScenario[] = [
  {
    id: 'ai-platform',
    number: 1,
    title: 'AI Software Platform',
    badge: 'Technology • 500 Employees',
    icon: Sparkles,
    summary: 'A salesperson sells an AI workflow automation platform to a tech CEO with multiple disconnected tools and manual processes.',
    fullText: "You are the CEO of a 500-employee technology company. A salesperson is contacting you to sell an AI-powered workflow automation platform. The company currently uses multiple software tools for managing internal operations, but several processes are still manual. The salesperson needs to understand the company's challenges, explain how their platform can help, address questions about integration, security, implementation, and ROI, and attempt to schedule a product demonstration.",
  },
  {
    id: 'cloud-infra',
    number: 2,
    title: 'Cloud Infrastructure Solution',
    badge: 'E-Commerce • High Traffic',
    icon: Cloud,
    summary: 'A salesperson pitches cloud cost optimization and infrastructure management to an e-commerce CEO managing traffic spikes.',
    fullText: "You are the CEO of a growing e-commerce company experiencing increasing cloud infrastructure costs and occasional performance issues during periods of high traffic. A salesperson is contacting you to sell a cloud optimization and infrastructure management solution. The salesperson needs to understand the company's current infrastructure, identify operational and cost-related challenges, explain the potential benefits of the solution, address concerns about migration, downtime, security, and pricing, and attempt to schedule a technical discussion or product demonstration.",
  },
  {
    id: 'cybersecurity',
    number: 3,
    title: 'Cybersecurity Solution',
    badge: 'Finance • 300 Employees',
    icon: ShieldCheck,
    summary: 'A salesperson pitches an enterprise cybersecurity platform to a financial services CEO upgrading from basic protection tools.',
    fullText: "You are the CEO of a 300-employee financial services company. The company currently uses basic cybersecurity tools but is looking to improve its protection against phishing, ransomware, unauthorized access, and data breaches. A salesperson is contacting you to sell an enterprise cybersecurity platform. The salesperson needs to understand the company's current security requirements, explain how the platform addresses those requirements, discuss integration with existing systems, compliance, deployment, pricing, and ROI, and attempt to schedule a security assessment or product demonstration.",
  },
];

const ScenarioBuilder: React.FC = () => {
  const navigate = useNavigate();
  const { topic, role, scenario, experience, style, selectedPreset, customTraits, setScenario, setExperience, setStyle, setSessionId, setInitialMessage } = useStore();
  const [loading, setLoading] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState<ExampleScenario | null>(null);

  React.useEffect(() => {
    if (!topic || !role) {
      navigate('/topics');
    }
  }, [topic, role, navigate]);

  if (!topic || !role) {
    return null;
  }

  const handleStart = async () => {
    if (!scenario.trim()) return;
    
    setLoading(true);
    try {
      const data = await createSession({
        topic: topic.title,
        role: role.id,
        scenario,
        experience,
        style,
        persona_configuration: {
          role: role.id,
          preset: selectedPreset || 'BALANCED',
          traits: customTraits,
          persona_schema_version: '1.0',
        },
      });
      setSessionId(data.session_id);
      if (data.initial_message) {
        setInitialMessage(data.initial_message);
      }
      navigate('/conversation');
    } catch (error: any) {
      console.error('Failed to create session', error);
      const detail = error.response?.data?.detail || 'Please ensure backend is running and TCS_API_KEY is correctly set.';
      alert(`Failed to start session: ${detail}`);
    } finally {
      setLoading(false);
    }
  };

  const handleApplyScenario = (text: string) => {
    setScenario(text);
    setSelectedScenario(null);
  };

  return (
    <div className="min-h-screen p-8 md:p-16 max-w-4xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-10"
      >
        <h1 className="text-3xl md:text-5xl font-bold mb-4">Build your Scenario</h1>
        <p className="text-slate-600 text-lg">
          You are preparing for a <span className="text-slate-900 font-medium">{topic.title}</span> with a <span className="text-slate-900 font-medium">{role.name}</span>.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card p-8 rounded-2xl space-y-8"
      >
        {/* Step 1: Example Scenarios (3 Cards) */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div>
              <label className="block text-sm font-semibold text-slate-800">
                Example Scenarios
              </label>
              <p className="text-xs text-slate-500 mt-0.5">
                Click any card to preview full details and load into your scenario.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {EXAMPLE_SCENARIOS.map((ex) => {
              const IconComponent = ex.icon;
              const isSelected = scenario === ex.fullText;
              return (
                <motion.div
                  key={ex.id}
                  whileHover={{ y: -3, scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={() => setSelectedScenario(ex)}
                  className={`cursor-pointer rounded-xl p-4 transition-all duration-200 border flex flex-col justify-between ${
                    isSelected
                      ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/5 shadow-md ring-2 ring-[var(--color-primary)]/20'
                      : 'border-slate-200 hover:border-slate-300 bg-[var(--color-surface)] hover:shadow-sm'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div className="w-8 h-8 rounded-lg bg-[var(--color-primary)]/10 text-[var(--color-primary)] flex items-center justify-center">
                        <IconComponent size={16} />
                      </div>
                      <span className="text-[11px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                        Scenario {ex.number}
                      </span>
                    </div>

                    <h3 className="font-semibold text-sm text-slate-900 mb-1 line-clamp-1">
                      {ex.title}
                    </h3>
                    <p className="text-[11px] font-medium text-[var(--color-accent)] mb-2">
                      {ex.badge}
                    </p>
                    <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                      {ex.summary}
                    </p>
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-xs font-medium text-[var(--color-primary)]">
                    <span className="flex items-center gap-1">
                      <Eye size={13} /> View Details
                    </span>
                    {isSelected && (
                      <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                        <Check size={13} /> Selected
                      </span>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* Step 2: Scenario Description Textarea */}
        <div className="border-t border-slate-200 pt-6">
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium text-slate-700">
              Scenario Description
            </label>
            {scenario && (
              <button
                type="button"
                onClick={() => setScenario('')}
                className="text-xs text-slate-400 hover:text-red-500 transition-colors"
              >
                Clear text
              </button>
            )}
          </div>
          <textarea
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            placeholder="Select one of the example scenarios above, or describe your own custom conversation scenario..."
            className="w-full bg-[var(--color-surface)] border border-slate-200 rounded-xl p-4 text-slate-900 focus:outline-none focus:border-[var(--color-primary)] transition-colors resize-none h-32 text-sm leading-relaxed"
          />
        </div>

        {/* Step 2: Persona Configuration Builder */}
        <div className="border-t border-slate-200 pt-6">
          <PersonaConfigurator />
        </div>

        {/* Step 3: Experience & Conversation Style */}
        <div className="border-t border-slate-200 pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-2">
              Your Experience Level
            </label>
            <select
              value={experience}
              onChange={(e) => setExperience(e.target.value)}
              className="w-full bg-[var(--color-surface)] border border-slate-200 rounded-xl p-4 text-slate-900 focus:outline-none focus:border-[var(--color-primary)] transition-colors appearance-none"
            >
              <option value="Beginner">Beginner</option>
              <option value="Intermediate">Intermediate</option>
              <option value="Advanced">Advanced</option>
              <option value="Expert">Expert</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 mb-2">
              Conversation Style
            </label>
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              className="w-full bg-[var(--color-surface)] border border-slate-200 rounded-xl p-4 text-slate-900 focus:outline-none focus:border-[var(--color-primary)] transition-colors appearance-none"
            >
              <option value="Friendly">Friendly</option>
              <option value="Professional">Professional</option>
              <option value="Challenging">Challenging</option>
              <option value="Stress Interview">Stress Interview</option>
              <option value="Executive">Executive</option>
            </select>
          </div>
        </div>
      </div>

      <div className="pt-6">
          <button
            onClick={handleStart}
            disabled={!scenario.trim() || loading}
            className="w-full flex items-center justify-center gap-2 py-4 bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-all"
          >
            {loading ? <Loader2 className="animate-spin" /> : 'Begin Conversation'}
            {!loading && <ArrowRight size={18} />}
          </button>
        </div>
      </motion.div>

      {/* Scenario Detail Modal Popup */}
      <AnimatePresence>
        {selectedScenario && (
          <div 
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            onClick={() => setSelectedScenario(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              transition={{ duration: 0.2 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-6 md:p-8 relative border border-slate-200 overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-[var(--color-primary)]/10 text-[var(--color-primary)] flex items-center justify-center flex-shrink-0">
                    {React.createElement(selectedScenario.icon, { size: 20 })}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-[var(--color-primary)]/10 text-[var(--color-primary)]">
                        Scenario {selectedScenario.number}
                      </span>
                      <span className="text-xs text-slate-500 font-medium">
                        {selectedScenario.badge}
                      </span>
                    </div>
                    <h2 className="text-xl font-bold text-slate-900">
                      {selectedScenario.title}
                    </h2>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setSelectedScenario(null)}
                  className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Body */}
              <div className="my-5">
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
                  Full Scenario Context
                </label>
                <div className="bg-slate-50 rounded-xl p-5 border border-slate-200 text-slate-800 text-sm leading-relaxed max-h-72 overflow-y-auto">
                  {selectedScenario.fullText}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setSelectedScenario(null)}
                  className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors text-sm font-medium"
                >
                  Close
                </button>
                <button
                  type="button"
                  onClick={() => handleApplyScenario(selectedScenario.fullText)}
                  className="px-5 py-2.5 rounded-xl bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white transition-all text-sm font-medium flex items-center gap-2 shadow-sm"
                >
                  <Check size={16} />
                  Use this Scenario
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ScenarioBuilder;

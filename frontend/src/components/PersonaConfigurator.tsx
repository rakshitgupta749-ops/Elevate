import React, { useEffect, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Sliders, Sparkles, RotateCcw, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { getPersonaConfigurationSchema } from '../api/apiClient';
import { useStore } from '../store/useStore';

interface TraitDefinition {
  id: string;
  display_name: string;
  description: string;
  category: string;
  default: number;
  min_value: number;
  max_value: number;
  configurable: boolean;
  affects: string[];
}

interface PresetDefinition {
  id: string;
  display_name: string;
  description: string;
  trait_modifiers: Record<string, number>;
}

interface RoleSchema {
  role: string;
  display_name: string;
  description: string;
  traits: TraitDefinition[];
  presets: PresetDefinition[];
  default_traits: Record<string, number>;
  schema_version: string;
}

export const PersonaConfigurator: React.FC = () => {
  const { role, selectedPreset, customTraits, setSelectedPreset, setCustomTrait, setCustomTraits } = useStore();
  const [schema, setSchema] = useState<RoleSchema | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!role?.id) return;
    let isMounted = true;
    setLoading(true);
    setError(null);

    getPersonaConfigurationSchema(role.id)
      .then((data: RoleSchema) => {
        if (!isMounted) return;
        setSchema(data);

        // Initialize traits if empty
        if (Object.keys(customTraits).length === 0) {
          const initialTraits: Record<string, number> = {};
          data.traits.forEach((t) => {
            initialTraits[t.id] = data.default_traits[t.id] ?? t.default;
          });
          setCustomTraits(initialTraits);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error('Failed to load persona schema', err);
        setError('Failed to load role trait schema. Falling back to default configuration.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [role?.id]);

  // Handle Preset selection
  const handleSelectPreset = (preset: PresetDefinition) => {
    if (!schema) return;
    setSelectedPreset(preset.id);

    // Apply preset modifiers on top of role defaults
    const newTraits: Record<string, number> = {};
    schema.traits.forEach((t) => {
      const baseDefault = schema.default_traits[t.id] ?? t.default;
      const modValue = preset.trait_modifiers[t.id];
      newTraits[t.id] = modValue !== undefined ? modValue : baseDefault;
    });

    setCustomTraits(newTraits);
  };

  // Reset to role defaults
  const handleResetDefaults = () => {
    if (!schema) return;
    setSelectedPreset('BALANCED');
    const resetTraits: Record<string, number> = {};
    schema.traits.forEach((t) => {
      resetTraits[t.id] = schema.default_traits[t.id] ?? t.default;
    });
    setCustomTraits(resetTraits);
  };

  // Dynamically compute live persona summary
  const liveSummary = useMemo(() => {
    if (!schema) return 'Loading persona characteristics...';

    const strictness = customTraits['strictness'] ?? 0.50;
    const skepticism = customTraits['skepticism'] ?? 0.50;
    const kindness = customTraits['kindness'] ?? 0.50;
    const patience = customTraits['patience'] ?? 0.50;
    const directness = customTraits['directness'] ?? 0.50;
    const techDepth = customTraits['technical_depth'] ?? 0.50;
    const finScrutiny = customTraits['financial_scrutiny'] ?? 0.50;

    let tone = 'pragmatic and professional';
    if (kindness >= 0.70) tone = 'supportive, constructive, and warm';
    else if (kindness <= 0.35) tone = 'demanding, direct, and unsparing';

    let evaluation = 'balanced in scrutiny';
    if (skepticism >= 0.80 && strictness >= 0.80) {
      evaluation = 'highly skeptical, demanding verifiable proof and zero hand-waving';
    } else if (skepticism >= 0.80) {
      evaluation = 'rigorously skeptical toward vendor claims and metrics';
    } else if (strictness >= 0.80) {
      evaluation = 'exacting, rejecting vague or incomplete answers';
    } else if (skepticism <= 0.35 && strictness <= 0.40) {
      evaluation = 'open-minded, exploratory, and receptive to new paradigms';
    }

    let cadence = 'structured in cadence';
    if (directness >= 0.80 && patience <= 0.40) {
      cadence = 'fast-paced and terse with minimal patience for filler';
    } else if (directness >= 0.80) {
      cadence = 'explicit and direct in questioning';
    } else if (patience >= 0.75) {
      cadence = 'patient, allowing thorough elaboration of complex points';
    }

    let focus = `focused on standard enterprise ${schema.role} criteria.`;
    if (schema.role === 'CTO') {
      focus = techDepth >= 0.85
        ? 'demanding deep architectural precision, latency mechanics, and failure mode proofs.'
        : 'focused on engineering governance and high-level delivery feasibility.';
    } else if (schema.role === 'CFO') {
      focus = finScrutiny >= 0.85
        ? 'scrutinizing total cost of ownership, variable fees, and verified ROI payback schedules.'
        : 'focused on budget alignment and contract predictability.';
    } else if (schema.role === 'SALES_MANAGER') {
      focus = 'focused on pipeline velocity, rep adoption, and clear competitive differentiation.';
    } else if (schema.role === 'CEO') {
      focus = 'focused on strategic enterprise valuation, disruptive vision, and urgency.';
    } else if (schema.role === 'HR') {
      focus = 'prioritizing team well-being, culture resonance, and ethical compliance.';
    }

    return `A ${tone} ${schema.display_name} who is ${evaluation}, ${cadence}, ${focus}`;
  }, [schema, customTraits]);

  if (loading && !schema) {
    return (
      <div className="p-6 rounded-2xl border border-slate-200 bg-slate-50/50 flex items-center justify-center gap-3 text-slate-500">
        <span className="w-4 h-4 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin" />
        <span>Loading role trait configuration schema...</span>
      </div>
    );
  }

  if (error && !schema) {
    return (
      <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 flex items-center gap-3 text-sm">
        <ShieldAlert size={18} />
        <span>{error}</span>
      </div>
    );
  }

  if (!schema) return null;

  return (
    <div className="space-y-6 pt-2">
      {/* Header & Preset Selector */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Sliders size={20} className="text-[var(--color-primary)]" />
            <h2 className="text-lg font-semibold text-slate-900">Persona Configuration</h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-50 text-[var(--color-primary)] font-medium">
              Phase 9
            </span>
          </div>
          <button
            onClick={handleResetDefaults}
            type="button"
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 transition-colors px-2.5 py-1 rounded-lg hover:bg-slate-100"
          >
            <RotateCcw size={13} />
            <span>Reset Defaults</span>
          </button>
        </div>
        <p className="text-sm text-slate-600 mb-4">
          Select a persona preset or customize individual behavioral traits. Configuration directly governs stakeholder policy thresholds, reaction intensity, and initial perception state.
        </p>

        {/* Preset Pills */}
        <div className="flex flex-wrap gap-2 mb-6">
          {schema.presets.map((preset) => {
            const isSelected = selectedPreset === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => handleSelectPreset(preset)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-medium transition-all flex items-center gap-1.5 border ${
                  isSelected
                    ? 'bg-[var(--color-primary)] text-white border-[var(--color-primary)] shadow-sm'
                    : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                {isSelected && <CheckCircle2 size={13} />}
                <span>{preset.display_name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Live Persona Preview Card */}
      <motion.div
        layout
        className="p-5 rounded-xl bg-gradient-to-br from-slate-900 to-indigo-950 text-white shadow-sm border border-slate-800"
      >
        <div className="flex items-center gap-2 mb-2">
          <Sparkles size={16} className="text-indigo-400" />
          <span className="text-xs font-semibold tracking-wider text-indigo-300 uppercase">
            Live Persona Preview
          </span>
          <span className="text-xs text-slate-400 ml-auto">
            Preset: <span className="text-white font-medium">{selectedPreset || 'BALANCED'}</span>
          </span>
        </div>
        <p className="text-sm text-slate-200 leading-relaxed italic">
          "{liveSummary}"
        </p>
      </motion.div>

      {/* Trait Sliders Grid */}
      <div className="space-y-4 pt-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Role-Specific Behavioral Sliders ({schema.display_name})
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {schema.traits
            .filter((t) => t.configurable)
            .map((trait) => {
              const currentValue = customTraits[trait.id] ?? schema.default_traits[trait.id] ?? trait.default;
              const percentValue = Math.round(currentValue * 100);

              // Color badge calculation
              let badgeColor = 'bg-slate-100 text-slate-700';
              if (percentValue >= 80) badgeColor = 'bg-indigo-100 text-indigo-800 font-semibold';
              else if (percentValue <= 35) badgeColor = 'bg-slate-200 text-slate-700';

              return (
                <div
                  key={trait.id}
                  className="p-4 rounded-xl border border-slate-200 bg-white/80 hover:border-slate-300 transition-colors space-y-2.5"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-slate-900 block">
                        {trait.display_name}
                      </span>
                      <span className="text-xs text-slate-500 block leading-tight mt-0.5">
                        {trait.description}
                      </span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-md ${badgeColor} ml-2 shrink-0`}>
                      {percentValue}%
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={1}
                      value={percentValue}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) / 100.0;
                        setCustomTrait(trait.id, val);
                      }}
                      className="w-full accent-[var(--color-primary)] cursor-pointer h-1.5 bg-slate-200 rounded-lg appearance-none"
                    />
                    <div className="flex justify-between text-[10px] text-slate-400">
                      <span>Low (0%)</span>
                      <span>Moderate (50%)</span>
                      <span>High (100%)</span>
                    </div>
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
};

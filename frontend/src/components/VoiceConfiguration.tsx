import React, { useState, useRef, useCallback } from 'react';
import { useStore } from '../store/useStore';
import { Play, Square, Loader2, Mic } from 'lucide-react';

export interface VoiceOption {
  id: string;
  label: string;
  name: string;
  tone: string;
  gender: 'Male' | 'Female';
  description: string;
}

export const VOICE_OPTIONS: VoiceOption[] = [
  { id: 'am_onyx',    label: 'Onyx',    name: 'Onyx',    tone: 'Authoritative', gender: 'Male',   description: 'Authoritative executive tone, best for C-Suite & leadership roles' },
  { id: 'am_michael', label: 'Michael', name: 'Michael', tone: 'Direct',        gender: 'Male',   description: 'Direct, focused delivery, best for technical & engineering interviews' },
  { id: 'af_bella',   label: 'Bella',   name: 'Bella',   tone: 'Confident',     gender: 'Female', description: 'Confident, assertive presence, ideal for stakeholder negotiations' },
  { id: 'bf_emma',    label: 'Emma',    name: 'Emma',    tone: 'Articulate',    gender: 'Female', description: 'Polished British English executive tone, ideal for global stakeholder communications' },
];

const API_BASE = '/api';

const VoiceConfiguration: React.FC = () => {
  const { voiceProfile, setVoiceProfile } = useStore();
  const [previewState, setPreviewState] = useState<'idle' | 'loading' | 'playing'>('idle');
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const cleanupAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.removeAttribute('src');
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  const handleStop = useCallback(() => {
    cleanupAudio();
    setPreviewState('idle');
  }, [cleanupAudio]);

  const handlePlayPreview = useCallback(async () => {
    if (previewState === 'playing') {
      handleStop();
      return;
    }

    cleanupAudio();
    setPreviewState('loading');

    try {
      const res = await fetch(`${API_BASE}/voice/preview?voice_id=${encodeURIComponent(voiceProfile)}`);
      if (!res.ok) throw new Error(`Preview failed: ${res.status}`);

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;

      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => {
        setPreviewState('idle');
        cleanupAudio();
      };
      audio.onerror = () => {
        console.error('[VoicePreview] Audio playback error');
        setPreviewState('idle');
        cleanupAudio();
      };

      await audio.play();
      setPreviewState('playing');
    } catch (err) {
      console.error('[VoicePreview] Failed to fetch preview:', err);
      setPreviewState('idle');
      cleanupAudio();
    }
  }, [voiceProfile, previewState, cleanupAudio, handleStop]);

  const selectedVoice = VOICE_OPTIONS.find((v) => v.id === voiceProfile) || VOICE_OPTIONS[0];

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-7 h-7 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
          <Mic size={14} />
        </div>
        <div>
          <label className="block text-sm font-semibold text-white">
            AI Executive Voice
          </label>
          <p className="text-xs text-slate-400 mt-0.5">
            Choose the voice profile for your AI interviewer.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Voice Dropdown */}
        <div className="flex-1 relative">
          <select
            id="voice-profile-select"
            value={voiceProfile}
            onChange={(e) => {
              if (previewState !== 'idle') handleStop();
              setVoiceProfile(e.target.value);
            }}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 pr-10 text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 transition-colors appearance-none text-sm"
          >
            {VOICE_OPTIONS.map((v) => (
              <option key={v.id} value={v.id} className="bg-slate-900 text-white">
                {v.label} — {v.tone} {v.gender}
              </option>
            ))}
          </select>

          {/* Badges */}
          <div className="flex items-center gap-2 mt-2">
            <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
              selectedVoice.gender === 'Male'
                ? 'bg-blue-950/60 text-blue-400 border border-blue-800/60'
                : 'bg-purple-950/60 text-purple-400 border border-purple-800/60'
            }`}>
              {selectedVoice.gender}
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-800/80 text-slate-300 border border-slate-700/60">
              {selectedVoice.tone}
            </span>
            <span className="text-[10px] font-medium text-slate-400 tracking-wide">
              Kokoro-82M
            </span>
          </div>
        </div>

        {/* Preview Button */}
        <button
          id="voice-preview-button"
          type="button"
          onClick={handlePlayPreview}
          disabled={previewState === 'loading'}
          className={`flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-200 cursor-pointer ${
            previewState === 'playing'
              ? 'bg-rose-600 hover:bg-rose-700 text-white shadow-md shadow-rose-900/40'
              : previewState === 'loading'
                ? 'bg-slate-800 text-slate-500 cursor-wait'
                : 'bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 border border-indigo-500/30'
          }`}
          title={previewState === 'playing' ? 'Stop preview' : 'Play voice preview'}
        >
          {previewState === 'loading' ? (
            <Loader2 size={18} className="animate-spin" />
          ) : previewState === 'playing' ? (
            <Square size={16} />
          ) : (
            <Play size={18} />
          )}
        </button>
      </div>
    </div>
  );
};

export default VoiceConfiguration;

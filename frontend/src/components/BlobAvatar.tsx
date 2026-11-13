import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { 
  Mic, 
  MicOff,
  AlertTriangle, 
  ShieldAlert, 
  Activity, 
  Loader2,
  Sparkles, 
  User, 
  Volume2 
} from 'lucide-react';

export type BlobMood = 'listening' | 'neutral' | 'agitated' | 'hostile';
export type BlobActivityState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface BlobAvatarProps {
  mood: BlobMood;
  audioLevel: number; // 0.0 to 1.0 normalized
  isSpeaking?: boolean;
  isThinking?: boolean;
  isTranscribing?: boolean;
  avatarState?: BlobActivityState;
  roleName?: string;
  roleTitle?: string;
  isCandidateSpeaking?: boolean;
  interruptionCount?: number;
}

export const BlobAvatar: React.FC<BlobAvatarProps> = ({
  mood = 'listening',
  audioLevel = 0,
  isSpeaking = false,
  isThinking = false,
  isTranscribing = false,
  avatarState,
  roleName = 'CEO',
  roleTitle,
  isCandidateSpeaking = false,
  interruptionCount = 0,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const [lookOffset, setLookOffset] = useState({ x: 0, y: 0 });

  // Clamp audioLevel between 0 and 1
  const clampedLevel = Math.min(1, Math.max(0, audioLevel));
  // Active speaking indicator MUST reflect genuine AI speech/audio playback only (never mood/mic-closed idle)
  const speakingActive = Boolean(isSpeaking || avatarState === 'speaking' || audioLevel > 0.03);
  const thinkingActive = Boolean(!speakingActive && (isThinking || avatarState === 'thinking'));
  const transcribingActive = Boolean(!speakingActive && !thinkingActive && isTranscribing);
  const isActiveTurn = speakingActive || thinkingActive || transcribingActive || isCandidateSpeaking;
  // Controlled dynamic scale: gentle, elegant expansion (at most +8% on peak volume)
  const currentScale = 1 + (clampedLevel * 0.08);

  // Subtle interactive eye-tracking on hover (lightweight)
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * 8;
    const y = ((e.clientY - rect.top) / rect.height - 0.5) * 6;
    setLookOffset({ x, y });
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    setLookOffset({ x: 0, y: 0 });
  };

  // Configuration matrix for the 4 mood states & accurate activity labels
  const moodConfig = useMemo(() => {
    const resolveStatus = (speakingLabel: string, thinkingLabel: string, idleLabel: string, listeningLabel: string, emotionIcon: any) => {
      if (speakingActive) {
        return { label: speakingLabel, icon: emotionIcon };
      }
      if (thinkingActive) {
        return { label: thinkingLabel, icon: Loader2 };
      }
      if (transcribingActive) {
        return { label: 'MIC PAUSED • TRANSCRIBING DRAFT', icon: Loader2 };
      }
      if (isCandidateSpeaking) {
        return { label: listeningLabel, icon: Mic };
      }
      return { label: idleLabel, icon: MicOff };
    };

    switch (mood) {
      case 'listening': {
        const status = resolveStatus(
          'EXECUTIVE SPEAKING • COMPOSED',
          'THINKING • FORMULATING RESPONSE',
          'STANDBY • MIC CLOSED',
          'LISTENING TO YOU',
          Volume2
        );
        return {
          gradient: 'bg-gradient-to-tr from-slate-900 via-slate-800 to-sky-900',
          innerGlow: 'radial-gradient(circle at 35% 30%, rgba(186, 230, 253, 0.4), transparent 65%)',
          animationStyle: speakingActive 
            ? 'blob-talk-smooth 2.2s ease-in-out infinite' 
            : 'blob-breathe 6s ease-in-out infinite alternate',
          auraColor: 'rgba(56, 189, 248, 0.25)',
          ringColor: 'rgba(56, 189, 248, 0.4)',
          waveBarColor: 'bg-sky-400',
          borderColor: 'border-sky-500/40',
          badgeText: status.label,
          badgeBg: 'bg-sky-950/90 border-sky-500/50 text-sky-300',
          dotColor: 'bg-sky-400',
          icon: status.icon,
          // Eyes styling
          eyeSocket: 'bg-slate-950/95 border border-sky-400/50 shadow-[0_0_12px_rgba(56,189,248,0.4)]',
          pupil: 'bg-gradient-to-b from-sky-300 to-cyan-400 shadow-[0_0_10px_#38bdf8]',
          leftSlant: 'rotate-0 scale-y-100',
          rightSlant: 'rotate-0 scale-y-100',
        };
      }
      case 'neutral': {
        const status = resolveStatus(
          'EXECUTIVE SPEAKING • COMPOSED',
          'THINKING • FORMULATING RESPONSE',
          'STANDBY • MIC CLOSED',
          'LISTENING TO YOU',
          Activity
        );
        return {
          gradient: 'bg-gradient-to-tr from-indigo-600 via-blue-500 to-cyan-400',
          innerGlow: 'radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.5), transparent 60%)',
          animationStyle: speakingActive
            ? 'blob-talk-smooth 2.2s ease-in-out infinite'
            : 'blob-breathe 5s ease-in-out infinite alternate',
          auraColor: 'rgba(99, 102, 241, 0.35)',
          ringColor: 'rgba(34, 211, 238, 0.45)',
          waveBarColor: 'bg-cyan-300',
          borderColor: 'border-cyan-300/50',
          badgeText: status.label,
          badgeBg: 'bg-indigo-950/90 border-indigo-500/50 text-cyan-300',
          dotColor: 'bg-cyan-400',
          icon: status.icon,
          // Eyes styling
          eyeSocket: 'bg-indigo-950/95 border border-cyan-300/60 shadow-[0_0_14px_rgba(34,211,238,0.5)]',
          pupil: 'bg-gradient-to-b from-white to-cyan-300 shadow-[0_0_12px_#22d3ee]',
          leftSlant: 'rotate-0 scale-y-100',
          rightSlant: 'rotate-0 scale-y-100',
        };
      }
      case 'agitated': {
        const status = resolveStatus(
          'EXECUTIVE SPEAKING • SKEPTICAL',
          'SKEPTICAL • EVALUATING YOUR POINT',
          'SKEPTICAL • MIC CLOSED',
          'LISTENING • SKEPTICAL',
          AlertTriangle
        );
        return {
          gradient: 'bg-gradient-to-tr from-amber-600 via-orange-500 to-rose-500',
          innerGlow: 'radial-gradient(circle at 35% 30%, rgba(254, 243, 199, 0.55), transparent 60%)',
          animationStyle: speakingActive
            ? 'blob-talk-smooth 1.8s ease-in-out infinite'
            : 'blob-breathe 4.5s ease-in-out infinite alternate',
          auraColor: 'rgba(249, 115, 22, 0.45)',
          ringColor: 'rgba(249, 115, 22, 0.55)',
          waveBarColor: 'bg-amber-300',
          borderColor: 'border-amber-300/60',
          badgeText: status.label,
          badgeBg: 'bg-amber-950/95 border-amber-500/60 text-amber-200',
          dotColor: 'bg-amber-400',
          icon: status.icon,
          // Eyes styling: skeptical slant & narrower socket
          eyeSocket: 'bg-amber-950 border border-amber-400/70 shadow-[0_0_16px_rgba(251,191,36,0.6)]',
          pupil: 'bg-gradient-to-b from-amber-200 to-orange-500 shadow-[0_0_14px_#f59e0b]',
          leftSlant: 'rotate-[14deg] scale-y-85',
          rightSlant: '-rotate-[14deg] scale-y-85',
        };
      }
      case 'hostile': {
        const status = resolveStatus(
          interruptionCount > 0 ? `BARGE-IN / HOSTILE (#${interruptionCount})` : 'HIGH PRESSURE • HOSTILE EMOTION',
          interruptionCount > 0 ? `BARGE-IN • RECALIBRATING (#${interruptionCount})` : 'HIGH PRESSURE • EVALUATING',
          interruptionCount > 0 ? `BARGE-IN (#${interruptionCount}) • MIC CLOSED` : 'HIGH PRESSURE • MIC CLOSED',
          interruptionCount > 0 ? `LISTENING • BARGE-IN (#${interruptionCount})` : 'LISTENING • HIGH PRESSURE',
          ShieldAlert
        );
        return {
          gradient: 'bg-gradient-to-tr from-rose-700 via-red-600 to-red-950',
          innerGlow: 'radial-gradient(circle at 35% 30%, rgba(254, 202, 202, 0.65), transparent 50%)',
          animationStyle: speakingActive
            ? 'blob-talk-smooth 1.4s ease-in-out infinite'
            : 'blob-breathe 4s ease-in-out infinite alternate',
          auraColor: 'rgba(239, 68, 68, 0.55)',
          ringColor: 'rgba(239, 68, 68, 0.65)',
          waveBarColor: 'bg-rose-400',
          borderColor: 'border-red-400/80',
          badgeText: status.label,
          badgeBg: 'bg-rose-950 border border-rose-500/80 text-rose-200',
          dotColor: 'bg-rose-500',
          icon: status.icon,
          // Eyes styling: intense sharp glare
          eyeSocket: 'bg-red-950 border-2 border-red-500 shadow-[0_0_20px_rgba(239,68,68,0.8)]',
          pupil: 'bg-gradient-to-b from-white to-red-600 shadow-[0_0_16px_#ef4444]',
          leftSlant: 'rotate-[22deg] scale-y-70',
          rightSlant: '-rotate-[22deg] scale-y-70',
        };
      }
    }
  }, [mood, isCandidateSpeaking, interruptionCount, speakingActive, thinkingActive, transcribingActive]);

  const MoodIcon = moodConfig.icon;

  return (
    <div className="relative flex flex-col items-center justify-center w-full h-full select-none overflow-hidden py-3">
      {/* Strict Constraints: Pure CSS @keyframes for silky smooth, organic morphing & fluid breathing */}
      <style>{`
        @keyframes blob-breathe {
          0% { 
            border-radius: 46% 54% 58% 42% / 46% 52% 48% 54%; 
            transform: scale(1);
          }
          50% { 
            border-radius: 54% 46% 42% 58% / 54% 48% 52% 46%; 
            transform: scale(1.02);
          }
          100% { 
            border-radius: 46% 54% 58% 42% / 46% 52% 48% 54%; 
            transform: scale(1);
          }
        }
        @keyframes blob-talk-smooth {
          0% { 
            border-radius: 48% 52% 54% 46% / 48% 52% 48% 52%; 
            transform: scale(1);
          }
          50% { 
            border-radius: 53% 47% 45% 55% / 52% 48% 52% 48%; 
            transform: scale(1.045);
          }
          100% { 
            border-radius: 48% 52% 54% 46% / 48% 52% 48% 52%; 
            transform: scale(1);
          }
        }
        @keyframes soft-pulse-ring {
          0% {
            transform: scale(0.98);
            opacity: 0.4;
          }
          60% {
            transform: scale(1.18);
            opacity: 0.12;
          }
          100% {
            transform: scale(1.25);
            opacity: 0;
          }
        }
        @keyframes blob-blink {
          0%, 92%, 100% { transform: scaleY(1); }
          96% { transform: scaleY(0.08); }
        }
        @keyframes blob-float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-5px); }
        }
        @keyframes voice-bar-smooth {
          0% { height: 6px; opacity: 0.4; }
          50% { height: 16px; opacity: 0.9; }
          100% { height: 8px; opacity: 0.55; }
        }
      `}</style>

      {/* Prominent High-Contrast Executive Heading: CEO is clearly visible */}
      <div className="text-center z-20 mb-2 sm:mb-4 max-w-md px-3 sm:px-4">
        <div className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-0.5 rounded-full bg-purple-500/15 border border-purple-500/35 text-purple-300 text-[10px] sm:text-[11px] font-bold uppercase tracking-wider mb-1.5 sm:mb-2">
          <User size={11} className="text-purple-400" />
          <span>Executive Counterpart</span>
        </div>
        
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-black tracking-tight text-white drop-shadow-md">
          {roleName || 'CEO'}
        </h1>

        {roleTitle && (
          <p className="text-xs sm:text-sm font-medium text-slate-300 mt-0.5 sm:mt-1 max-w-xs md:max-w-sm mx-auto line-clamp-2">
            {roleTitle}
          </p>
        )}

        {/* Dynamic Mood Status Pill */}
        <div className="mt-2 sm:mt-2.5 flex items-center justify-center">
          <div className={`inline-flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3.5 py-1 sm:py-1.5 rounded-full border text-[11px] sm:text-xs font-bold backdrop-blur-md shadow-lg transition-all duration-500 ${moodConfig.badgeBg}`}>
            <span className={`w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full ${moodConfig.dotColor} ${isActiveTurn ? 'animate-pulse' : 'opacity-60'}`} />
            <MoodIcon size={12} className={`shrink-0 ${thinkingActive || transcribingActive ? 'animate-spin' : ''}`} />
            <span className="tracking-wide">{moodConfig.badgeText}</span>
          </div>
        </div>
      </div>

      {/* Central Interactive Blob Stage with Hover & Floating Effects */}
      <div 
        onMouseEnter={() => setIsHovered(true)}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        className="relative flex items-center justify-center w-48 h-48 sm:w-60 sm:h-60 md:w-76 md:h-76 my-auto cursor-pointer group"
        style={{
          animation: 'blob-float 6s ease-in-out infinite',
        }}
      >
        {/* Soft, Fluid Sound Wave Ring when Speaking */}
        {speakingActive && (
          <div 
            className="absolute -inset-4 rounded-full border pointer-events-none"
            style={{
              borderColor: moodConfig.ringColor,
              animation: 'soft-pulse-ring 2.8s cubic-bezier(0.2, 0.6, 0.3, 1) infinite',
            }}
          />
        )}

        {/* Outer Audio-Reactive Halo Glow: Silky Smooth Ease */}
        <div 
          className="absolute inset-0 rounded-full transition-all duration-500 ease-out pointer-events-none"
          style={{
            transform: `scale(${1 + (speakingActive ? 0.08 : 0) + (clampedLevel * 0.15) + (isHovered ? 0.05 : 0)})`,
            backgroundColor: moodConfig.auraColor,
            filter: 'blur(35px)',
            opacity: 0.3 + (speakingActive ? 0.15 : 0) + (clampedLevel * 0.2) + (isHovered ? 0.15 : 0),
          }}
        />

        {/* Dynamic Container Scale: Expands gently on speech volume with smooth 300ms glide */}
        <div 
          className="relative w-36 h-36 sm:w-44 sm:h-44 md:w-56 md:h-56 flex items-center justify-center z-10 transition-transform duration-300 ease-out"
          style={{
            transform: `scale(${currentScale * (isHovered ? 1.03 : 1.0)})`,
          }}
        >
          {/* Layer 1: Ambient Outer Backing Blob for Depth (Harmonious with Layer 2) */}
          <div 
            className={`absolute inset-0 opacity-40 filter blur-md transition-all duration-700 ${moodConfig.gradient}`}
            style={{
              animation: moodConfig.animationStyle,
            }}
          />

          {/* Layer 2: Main Primary CSS-Morphing Blob Body */}
          <div 
            className={`relative w-full h-full shadow-2xl transition-all duration-700 border ${moodConfig.borderColor} ${moodConfig.gradient} overflow-hidden`}
            style={{
              animation: moodConfig.animationStyle,
              boxShadow: isHovered 
                ? `0 0 50px ${moodConfig.auraColor}, inset 0 0 30px rgba(255,255,255,0.3)`
                : `0 0 35px ${moodConfig.auraColor}, inset 0 0 20px rgba(255,255,255,0.2)`,
            }}
          >
            {/* Organic Specular Inner Highlight / Glass Sheen */}
            <div 
              className="absolute inset-0 pointer-events-none"
              style={{
                background: moodConfig.innerGlow,
                mixBlendMode: 'overlay',
              }}
            />

            {/* Expressive Voice Frequency Wave Bars: Smooth, Subtle & Elegant */}
            <div className="absolute bottom-6 md:bottom-8 inset-x-0 flex items-center justify-center gap-1.5 pointer-events-none z-20">
              {[0.6, 0.9, 1.1, 0.9, 0.6].map((multiplier, idx) => (
                <div 
                  key={idx}
                  className={`w-1 md:w-1.5 rounded-full transition-all duration-300 ease-out ${moodConfig.waveBarColor}`}
                  style={{
                    height: speakingActive 
                      ? `${Math.max(5, Math.min(18, (clampedLevel > 0.03 ? clampedLevel * multiplier * 20 : multiplier * 10)))}px`
                      : '4px',
                    opacity: speakingActive ? 0.85 : 0.2,
                    animation: speakingActive ? `voice-bar-smooth ${1.8 + idx * 0.2}s ease-in-out infinite alternate` : 'none',
                    boxShadow: speakingActive ? `0 0 6px ${moodConfig.ringColor}` : 'none',
                  }}
                />
              ))}
            </div>

            {/* ============================================================ */}
            {/* Expressive AI Executive Eyes: Animated, Blinking & Reactive */}
            {/* ============================================================ */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
              <div 
                className="flex items-center gap-6 md:gap-7 transition-transform duration-300 ease-out"
                style={{
                  transform: `translate(${lookOffset.x * 0.5}px, ${lookOffset.y * 0.5 - 6}px)`,
                }}
              >
                {/* Left Eye */}
                <div className={`transition-all duration-500 ${moodConfig.leftSlant}`}>
                  <div 
                    className={`w-6 h-8.5 md:w-7 md:h-10 rounded-full flex items-center justify-center transition-all duration-500 ${moodConfig.eyeSocket}`}
                    style={{ animation: 'blob-blink 4.2s infinite ease-in-out' }}
                  >
                    {/* Pupil with subtle audio-reactive dilation & mouse tracking */}
                    <div 
                      className={`w-3 h-4.5 md:w-3.5 md:h-5 rounded-full transition-transform duration-300 ease-out ${moodConfig.pupil}`}
                      style={{
                        transform: `scale(${1 + (clampedLevel * 0.12) + (speakingActive ? 0.05 : 0) + (isHovered ? 0.08 : 0)}) translate(${lookOffset.x * 0.5}px, ${lookOffset.y * 0.5}px)`,
                      }}
                    >
                      {/* Specular Light Reflection Glint */}
                      <div className="w-1 h-1 bg-white rounded-full mt-0.5 ml-0.5 opacity-90 shadow-sm" />
                    </div>
                  </div>
                </div>

                {/* Right Eye */}
                <div className={`transition-all duration-500 ${moodConfig.rightSlant}`}>
                  <div 
                    className={`w-6 h-8.5 md:w-7 md:h-10 rounded-full flex items-center justify-center transition-all duration-500 ${moodConfig.eyeSocket}`}
                    style={{ animation: 'blob-blink 4.2s infinite ease-in-out' }}
                  >
                    {/* Pupil with subtle audio-reactive dilation & mouse tracking */}
                    <div 
                      className={`w-3 h-4.5 md:w-3.5 md:h-5 rounded-full transition-transform duration-300 ease-out ${moodConfig.pupil}`}
                      style={{
                        transform: `scale(${1 + (clampedLevel * 0.12) + (speakingActive ? 0.05 : 0) + (isHovered ? 0.08 : 0)}) translate(${lookOffset.x * 0.5}px, ${lookOffset.y * 0.5}px)`,
                      }}
                    >
                      {/* Specular Light Reflection Glint */}
                      <div className="w-1 h-1 bg-white rounded-full mt-0.5 ml-0.5 opacity-90 shadow-sm" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Hover Cue Tag */}
        {isHovered && (
          <motion.div 
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="absolute -bottom-7 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-700/80 text-[11px] font-semibold text-slate-300 shadow-md flex items-center gap-1.5 pointer-events-none backdrop-blur-xs"
          >
            <Sparkles size={11} className="text-purple-400" />
            <span>Executive is observing your proposal</span>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default BlobAvatar;

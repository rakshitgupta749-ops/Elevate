import React, { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import avatarVideo from '../../../avatar_video/Create_a_highly_realistic_prof.mp4';

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface RobotAvatarProps {
  state: AvatarState;
  speechText?: string;
}

const RobotAvatar: React.FC<RobotAvatarProps> = ({ state, speechText }) => {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (state === 'speaking') {
      // Do the math to set avatar pace
      // Estimate speech duration based on word count (approx 2.5 words per sec)
      const wordCount = speechText ? speechText.split(/\s+/).length : 0;
      const estimatedSpeechDuration = Math.max(wordCount / 2.5, 1);

      // Calculate pace so video finishes around the time speech finishes
      const videoDuration = video.duration || 5;
      const calculatedPace = videoDuration / estimatedSpeechDuration;

      // Clamp between 0.2x and 3.0x speed
      video.playbackRate = Math.min(Math.max(calculatedPace, 0.2), 3.0);

      video.currentTime = 0;
      video.play().catch(e => console.log('Playback error:', e));
    } else {
      video.pause();
      video.currentTime = 0;
    }
  }, [state, speechText]);
  // Determine ring animation based on state
  let ringAnimation = {};
  if (state === 'listening') {
    ringAnimation = {
      scale: [1, 1.02, 1],
      opacity: [0.3, 0.8, 0.3],
      transition: { repeat: Infinity, duration: 1.5, ease: "easeInOut" }
    };
  } else if (state === 'thinking') {
    ringAnimation = {
      opacity: [0.4, 0.8, 0.4],
      transition: { repeat: Infinity, duration: 2, ease: "easeInOut" }
    };
  } else if (state === 'speaking') {
    ringAnimation = {
      scale: [1, 1.01, 1],
      transition: { repeat: Infinity, duration: 0.5, ease: "easeInOut" }
    };
  }

  return (
    <div className="relative w-full mx-auto mb-6">
      {/* Inner Avatar Body */}
      <div className="relative w-full bg-slate-900 rounded-xl overflow-hidden shadow-inner z-10">
        <video
          ref={videoRef}
          src={avatarVideo}
          className="w-full h-auto block"
          muted
          playsInline
        />
        
        {/* Status Label */}
        <div className="absolute bottom-3 left-3 flex items-center gap-2 bg-black/60 backdrop-blur-sm text-white px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wider z-20">
          <div className={`w-2 h-2 rounded-full ${
            state === 'listening' ? 'bg-red-500 animate-pulse' :
            state === 'thinking' ? 'bg-yellow-400' :
            state === 'speaking' ? 'bg-green-400 animate-pulse' :
            'bg-[var(--color-primary)]'
          }`} />
          {state}
        </div>
      </div>

      {/* Outer Ring */}
      <motion.div
        className={`absolute -inset-1.5 rounded-2xl border-4 z-0 pointer-events-none ${
          state === 'listening' ? 'border-red-500' :
          state === 'thinking' ? 'border-yellow-400 border-dashed' :
          state === 'speaking' ? 'border-green-400' :
          'border-[var(--color-primary)] opacity-30'
        }`}
        animate={ringAnimation}
      />
    </div>
  );
};

export default RobotAvatar;

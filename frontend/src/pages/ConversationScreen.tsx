import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useStore } from '../store/useStore';
import {
  streamChatWithAgent,
  streamOpeningWithAgent,
  concludeSession,
  rewindTurn,
  getCoachingHint,
  getSessionLiveState,
  speakVoiceText,
  transcribeVoiceAudio,
} from '../api/apiClient';
import {
  Send,
  Loader2,
  ArrowLeft,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Activity,
  RotateCcw,
  Lightbulb,
  Trophy,
  ShieldAlert,
  X,
  Radio,
  FileText,
  Clock,
  Bot,
  User
} from 'lucide-react';
import BlobAvatar from '../components/BlobAvatar';
import type { BlobMood } from '../components/BlobAvatar';
import { LiveVariableInspector } from '../components/LiveVariableInspector';
import { FeedbackReportModal } from '../components/FeedbackReportModal';
import type { StructuredCoachingReport } from '../components/FeedbackReportModal';
import DebugTranscriptDrawer from '../components/DebugTranscriptDrawer';
import { AudioQueue } from '../utils/audioQueue';
import { InterviewWebSocketClient } from '../utils/interviewWebSocket';
import { VOICE_OPTIONS } from '../components/VoiceConfiguration';

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'speaking';

let audioIdCounter = 0;
const getNextAudioId = (prefix: string) => {
  audioIdCounter += 1;
  return `${prefix}-${audioIdCounter}`;
};

/**
 * =====================================================================
 * STT ENGINE TOGGLE:
 * 'whisper'   - Server-side Azure Whisper (Zero mobile duplicates, cross-platform audio streaming)
 * 'webspeech' - Client-side browser Web Speech API (Local browser recognition)
 * Change this value to 'webspeech' to switch back to Web Speech API anytime.
 * =====================================================================
 */
export const STT_ENGINE: 'whisper' | 'webspeech' = 'whisper';

const getSupportedAudioMimeType = (): string => {
  if (typeof MediaRecorder === 'undefined') return '';
  const candidateTypes = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
    'audio/wav',
  ];
  for (const t of candidateTypes) {
    if (MediaRecorder.isTypeSupported(t)) {
      return t;
    }
  }
  return '';
};

const normalizeTranscript = (text: string) => {
  const cleaned = text.toLowerCase().replace(/[^\w\s]/g, ' ');
  return cleaned.split(/\s+/).filter(Boolean).join(' ');
};

const mergeTranscripts = (textA: string, textB: string): string => {
  const a = (textA || '').trim();
  const b = (textB || '').trim();
  if (!a) return b;
  if (!b) return a;

  const normA = normalizeTranscript(a);
  const normB = normalizeTranscript(b);

  if (normA === normB) {
    return b;
  }

  // Containment and prefix/suffix superset checks (handles mobile Chrome cumulative results)
  if (normB.startsWith(normA) || normB.endsWith(normA) || normB.includes(normA)) {
    return b;
  }
  if (normA.startsWith(normB) || normA.endsWith(normB) || normA.includes(normB)) {
    return a;
  }

  // Token overlap check (suffix of a matches prefix of b)
  const wordsA = a.split(/\s+/);
  const wordsB = b.split(/\s+/);
  const normWordsA = normA.split(' ');
  const normWordsB = normB.split(' ');

  let overlap = 0;
  const maxLen = Math.min(normWordsA.length, normWordsB.length);
  for (let l = maxLen; l > 0; l--) {
    if (normWordsA.slice(-l).join(' ') === normWordsB.slice(0, l).join(' ')) {
      overlap = l;
      break;
    }
  }

  if (overlap > 0) {
    return `${wordsA.join(' ')} ${wordsB.slice(overlap).join(' ')}`;
  }

  return `${a} ${b}`;
};

interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
}

const ConversationScreen: React.FC = () => {
  const navigate = useNavigate();
  const { role, sessionId, initialMessage, initialAudio, resetSession, voiceProfile, setVoiceProfile } = useStore();

  const getFallbackGreeting = (roleId?: string) => {
    const id = (roleId || '').toUpperCase();
    if (id.includes('CEO')) {
      return "Thanks for taking the time to meet today. We have high expectations for this initiative and its strategic impact on enterprise valuation. To kick us off, please introduce yourself and give me a high-level overview of your background.";
    }
    if (id.includes('CTO')) {
      return "Thanks for jumping on today. From an architectural standpoint, I care about scalability, reliability, and technical tradeoffs. To kick us off, please introduce yourself and walk me through your technical background.";
    }
    if (id.includes('HR')) {
      return "Hello, thanks for joining me today. I'm looking forward to learning more about your journey. To get started, could you briefly introduce yourself and tell me about your background?";
    }
    if (id.includes('SALES')) {
      return "Good to connect today. Our pipeline and ROI requirements are aggressive. Before we dive into the details, please introduce yourself and give me a brief overview of your background.";
    }
    return "Thanks for joining today's session. To get us started, please introduce yourself and give me a brief overview of your background and role.";
  };

  const initialGreeting = initialMessage || getFallbackGreeting(role?.id);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'initial',
      sender: 'ai',
      text: initialGreeting
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isAudioEnabled, setIsAudioEnabled] = useState(true);
  const [avatarState, setAvatarState] = useState<AvatarState>(
    initialAudio ? 'speaking' : (!initialMessage ? 'thinking' : 'idle')
  );
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [mood, setMood] = useState<BlobMood>(
    initialAudio ? 'neutral' : 'listening'
  );
  const [isListening, setIsListening] = useState(false);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [isTranscriptOpen, setIsTranscriptOpen] = useState(false);
  const [isTranscriptDocked, setIsTranscriptDocked] = useState(false);
  const [turnTrigger, setTurnTrigger] = useState(0);

  // Priority P0 & P1 States
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [coachingReport, setCoachingReport] = useState<StructuredCoachingReport | null>(null);
  const [concludeLoading, setConcludeLoading] = useState(false);
  const [rewindLoading, setRewindLoading] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [currentHint, setCurrentHint] = useState<{ hint: string; focus_area: string; current_stakeholder_perception: string } | null>(null);
  const [isTerminated, setIsTerminated] = useState(false);
  const [terminationReason, setTerminationReason] = useState<string | null>(null);
  const [bargeInNotice, setBargeInNotice] = useState<{ visible: boolean; count: number }>({ visible: false, count: 0 });
  const [autoSendCountdown, setAutoSendCountdown] = useState<number | null>(null);
  const [isTranscribingToInput, setIsTranscribingToInput] = useState(false);
  const [isMobilePersonaOpen, setIsMobilePersonaOpen] = useState(false);
  const [isAudioUnlocked, setIsAudioUnlocked] = useState(true);
  const hasInterviewerStartedSpeakingRef = useRef<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);
  const audioQueueRef = useRef<AudioQueue | null>(null);
  const wsClientRef = useRef<InterviewWebSocketClient | null>(null);
  const synthTimerRef = useRef<any>(null);
  const silenceTimerRef = useRef<any>(null);
  const countdownIntervalRef = useRef<any>(null);
  const autoSendCountdownRef = useRef<number | null>(null);
  const voiceProfileRef = useRef<string>(voiceProfile || 'am_onyx');
  const speakingSessionSeqRef = useRef<number>(0);
  const initialGreetingSpokenRef = useRef<boolean>(false);

  // Refs to prevent stale closures in WebSocket / AudioQueue callbacks and manage auto-mic lifecycle
  const isAudioEnabledRef = useRef<boolean>(isAudioEnabled);
  const isListeningRef = useRef<boolean>(false);
  const shouldKeepListeningRef = useRef<boolean>(false);
  const isTerminatedRef = useRef<boolean>(false);
  const isConcludingRef = useRef<boolean>(false);
  const loadingRef = useRef<boolean>(false);
  const inputRef = useRef<string>('');
  const baseInputRef = useRef<string>('');
  const speechStartedForTurnRef = useRef<boolean>(false);
  const speechStartTimeRef = useRef<number | null>(null);
  const lastSpeechTimeRef = useRef<number | null>(null);

  // Whisper audio recording refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const vadIntervalRef = useRef<any>(null);
  const isWhisperRecordingRef = useRef<boolean>(false);
  const pendingWhisperUserMsgIdRef = useRef<string | null>(null);
  const turnAudioReceivedRef = useRef<boolean>(false);
  const recordingStartTimeRef = useRef<number>(0);
  const whisperWatchdogRef = useRef<any>(null);
  const isSendingWhisperRef = useRef<boolean>(false);
  const vadInitializedRef = useRef<boolean>(false);
  const recordingHasSpeechRef = useRef<boolean>(false);
  const autoSendSuppressedRef = useRef<boolean>(false);
  const isManuallyClosedRef = useRef<boolean>(false);

  const clearSilenceTimers = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    autoSendCountdownRef.current = null;
    setAutoSendCountdown(null);
  };

  const setCountdownValue = (val: number | null) => {
    if (autoSendCountdownRef.current !== val) {
      autoSendCountdownRef.current = val;
      setAutoSendCountdown(val);
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollH = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(Math.max(scrollH, 48), 140)}px`;
    }
  }, [input]);

  const latestAiMessage = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].sender === 'ai' && messages[i].text.trim()) {
        return messages[i];
      }
    }
    return null;
  }, [messages]);

  useEffect(() => {
    isAudioEnabledRef.current = isAudioEnabled;
  }, [isAudioEnabled]);

  useEffect(() => {
    isTerminatedRef.current = isTerminated;
  }, [isTerminated]);

  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  useEffect(() => {
    inputRef.current = input;
  }, [input]);

  useEffect(() => {
    voiceProfileRef.current = voiceProfile || 'am_onyx';
    if (wsClientRef.current && voiceProfile) {
      wsClientRef.current.setVoice(voiceProfile);
    }
  }, [voiceProfile]);

  // =====================================================================
  // 1. WHISPER AUDIO RECORDING ENGINE (Server-side Azure Whisper STT)
  // Audio is recorded via MediaRecorder and sent to backend over WebSocket.
  // =====================================================================
  const handleTranscriptionFailure = () => {
    isSendingWhisperRef.current = false;
    if (whisperWatchdogRef.current) {
      clearTimeout(whisperWatchdogRef.current);
      whisperWatchdogRef.current = null;
    }
    const targetMsgId = pendingWhisperUserMsgIdRef.current;
    pendingWhisperUserMsgIdRef.current = null;
    loadingRef.current = false;
    setLoading(false);
    setAvatarState('idle');
    setMood('listening');

    // Remove empty AI placeholder and "Transcribing with Whisper..." placeholder
    setMessages((prev) =>
      prev.filter((m) => {
        if (m.sender === 'ai' && !m.text.trim()) return false;
        if (targetMsgId && m.id === targetMsgId) return false;
        if (m.sender === 'user' && m.text.includes('Transcribing with Whisper')) return false;
        return true;
      })
    );

    // Auto-restart listening so candidate can speak again unless mic was closed manually
    if (!isTerminatedRef.current && !isConcludingRef.current && !isManuallyClosedRef.current) {
      setTimeout(() => {
        startListening(true);
      }, 300);
    }
  };

  const stopWhisperRecording = () => {
    clearSilenceTimers();
    shouldKeepListeningRef.current = false;
    isWhisperRecordingRef.current = false;
    isListeningRef.current = false;
    setIsListening(false);
    isSendingWhisperRef.current = false;
    recordingHasSpeechRef.current = false;
    vadInitializedRef.current = false;
    autoSendSuppressedRef.current = false;

    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch {
        // ignore close errors
      }
      audioContextRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.onstop = null;
        mediaRecorderRef.current.ondataavailable = null;
        mediaRecorderRef.current.stop();
      } catch {
        // ignore stop errors
      }
      mediaRecorderRef.current = null;
    }
    if (mediaStreamRef.current) {
      try {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      } catch {
        // ignore track stop errors
      }
      mediaStreamRef.current = null;
    }
  };

  // Manual microphone close: stops recording WITHOUT sending reply automatically to AI.
  // If speech was captured, transcribes it into the chat input box so user can manually click Send.
  const stopWhisperRecordingManual = () => {
    clearSilenceTimers();
    isManuallyClosedRef.current = true;
    shouldKeepListeningRef.current = false;
    isWhisperRecordingRef.current = false;
    isListeningRef.current = false;
    setIsListening(false);
    if (!audioQueueRef.current?.isAudioActive() && !window.speechSynthesis?.speaking) {
      setAvatarState('idle');
      setMood((prev) => (prev === 'hostile' || prev === 'agitated' ? prev : 'listening'));
    }

    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch {
        // ignore close errors
      }
      audioContextRef.current = null;
    }

    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      recordingHasSpeechRef.current = false;
      vadInitializedRef.current = false;
      mediaRecorderRef.current = null;
      if (mediaStreamRef.current) {
        try {
          mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        } catch {
          // ignore track stop errors
        }
        mediaStreamRef.current = null;
      }
      return;
    }

    const mimeType = getSupportedAudioMimeType() || 'audio/webm';
    const hadSpeech = recordingHasSpeechRef.current || !vadInitializedRef.current;
    recordingHasSpeechRef.current = false;
    vadInitializedRef.current = false;
    autoSendSuppressedRef.current = false;

    recorder.onstop = async () => {
      const chunks = [...audioChunksRef.current];
      audioChunksRef.current = [];

      if (mediaStreamRef.current) {
        try {
          mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        } catch {
          // ignore track stop errors
        }
        mediaStreamRef.current = null;
      }
      mediaRecorderRef.current = null;

      if (!hadSpeech || chunks.length === 0) {
        return;
      }

      const audioBlob = new Blob(chunks, { type: mimeType });
      if (audioBlob.size < 2000) {
        console.info(`[ConversationScreen] Manual mic close fragment too small (${audioBlob.size} bytes). Skipping transcription.`);
        return;
      }

      setIsTranscribingToInput(true);
      try {
        const base64Data = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            const resultStr = reader.result as string;
            resolve(resultStr.includes(',') ? resultStr.split(',')[1] : resultStr);
          };
          reader.onerror = () => reject(new Error('Failed to read recorded audio'));
          reader.readAsDataURL(audioBlob);
        });

        if (!base64Data) return;

        const res = await transcribeVoiceAudio(base64Data, mimeType);
        const transcript = (res?.text || '').trim();
        if (transcript) {
          const existing = (inputRef.current || '').trim();
          const combined = existing ? `${existing} ${transcript}` : transcript;
          inputRef.current = combined;
          baseInputRef.current = combined;
          setInput(combined);
          setTimeout(() => {
            textareaRef.current?.focus();
          }, 50);
        }
      } catch (err) {
        console.warn('[ConversationScreen] Transcribe-to-input failed:', err);
      } finally {
        setIsTranscribingToInput(false);
      }
    };

    try {
      recorder.stop();
    } catch {
      mediaRecorderRef.current = null;
      if (mediaStreamRef.current) {
        try {
          mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        } catch {
          // ignore track stop errors
        }
        mediaStreamRef.current = null;
      }
    }
  };

  const sendWhisperRecording = () => {
    // Atomic check to prevent double-invocation race conditions
    if (isSendingWhisperRef.current || loadingRef.current || !sessionId) return;

    const existingInputPrefix = (inputRef.current || '').trim();
    const hadSpeechInRecorder = recordingHasSpeechRef.current || !vadInitializedRef.current;

    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      isSendingWhisperRef.current = false;
      stopWhisperRecording();
      if (existingInputPrefix) {
        sendTextTurn(existingInputPrefix);
      }
      return;
    }

    // If user already has text in input and did not speak during this mic open, send existing text directly
    if (existingInputPrefix && !hadSpeechInRecorder) {
      stopWhisperRecording();
      sendTextTurn(existingInputPrefix);
      return;
    }

    if (audioQueueRef.current?.isAudioActive() || window.speechSynthesis?.speaking) {
      audioQueueRef.current?.flushAudio();
      wsClientRef.current?.sendBargeIn();
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel();

    isSendingWhisperRef.current = true;
    isManuallyClosedRef.current = false;
    loadingRef.current = true;
    setLoading(true);
    setAvatarState('thinking');
    clearSilenceTimers();

    const mimeType = getSupportedAudioMimeType() || 'audio/webm';

    // Stop listening & VAD monitoring
    clearSilenceTimers();
    shouldKeepListeningRef.current = false;
    isWhisperRecordingRef.current = false;
    isListeningRef.current = false;
    setIsListening(false);
    recordingHasSpeechRef.current = false;
    vadInitializedRef.current = false;
    autoSendSuppressedRef.current = false;

    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch { }
      audioContextRef.current = null;
    }

    // Capture complete audio in onstop callback (W3C standard pattern for full data flush)
    recorder.onstop = async () => {
      const chunks = [...audioChunksRef.current];
      audioChunksRef.current = [];

      if (mediaStreamRef.current) {
        try {
          mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        } catch { }
        mediaStreamRef.current = null;
      }
      mediaRecorderRef.current = null;

      if (chunks.length === 0) {
        isSendingWhisperRef.current = false;
        loadingRef.current = false;
        setLoading(false);
        if (existingInputPrefix) {
          sendTextTurn(existingInputPrefix);
        } else {
          setAvatarState('idle');
        }
        return;
      }

      const audioBlob = new Blob(chunks, { type: mimeType });

      // In WebM, metadata headers take ~600-800 bytes. Real speech is > 2000 bytes.
      // Dropping sub-2KB stubs prevents Azure Whisper 400 'could not be decoded' errors.
      if (audioBlob.size < 2000) {
        console.info(`[ConversationScreen] Audio fragment too small (${audioBlob.size} bytes). Discarding.`);
        isSendingWhisperRef.current = false;
        loadingRef.current = false;
        setLoading(false);
        if (existingInputPrefix) {
          sendTextTurn(existingInputPrefix);
        } else {
          handleTranscriptionFailure();
        }
        return;
      }

      // If input already contains text (e.g. from prior manual mic pause/typing) plus new speech,
      // transcribe new audio and merge before submitting unified turn.
      if (existingInputPrefix) {
        try {
          const base64Data = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
              const resultStr = reader.result as string;
              resolve(resultStr.includes(',') ? resultStr.split(',')[1] : resultStr);
            };
            reader.onerror = () => reject(new Error('Failed to read audio blob'));
            reader.readAsDataURL(audioBlob);
          });

          let newSpeechText = '';
          if (base64Data) {
            const res = await transcribeVoiceAudio(base64Data, mimeType);
            newSpeechText = (res?.text || '').trim();
          }
          const combinedText = newSpeechText ? `${existingInputPrefix} ${newSpeechText}` : existingInputPrefix;
          isSendingWhisperRef.current = false;
          loadingRef.current = false;
          setLoading(false);
          sendTextTurn(combinedText);
        } catch (err) {
          console.warn('[ConversationScreen] Combined audio transcription error, falling back to input text:', err);
          isSendingWhisperRef.current = false;
          loadingRef.current = false;
          setLoading(false);
          sendTextTurn(existingInputPrefix);
        }
        return;
      }

      turnAudioReceivedRef.current = false;
      hasInterviewerStartedSpeakingRef.current = false;
      speechStartedForTurnRef.current = false;
      speechStartTimeRef.current = null;
      lastSpeechTimeRef.current = null;

      const userMsgId = `user-${Date.now()}`;
      const aiMsgId = `ai-${Date.now()}`;
      pendingWhisperUserMsgIdRef.current = userMsgId;

      setMessages((prev) => [
        ...prev,
        { id: userMsgId, sender: 'user', text: '🎙️ Transcribing with Whisper...' },
        { id: aiMsgId, sender: 'ai', text: '' },
      ]);

      setAvatarState('thinking');
      audioQueueRef.current?.startTurn();

      // Start 8-second watchdog timer to prevent getting stuck
      if (whisperWatchdogRef.current) clearTimeout(whisperWatchdogRef.current);
      whisperWatchdogRef.current = setTimeout(() => {
        if (loadingRef.current && pendingWhisperUserMsgIdRef.current === userMsgId) {
          console.warn('[ConversationScreen] Whisper transcription timed out (watchdog fired).');
          handleTranscriptionFailure();
        }
      }, 8000);

      const reader = new FileReader();
      reader.readAsDataURL(audioBlob);
      reader.onloadend = () => {
        const resultStr = reader.result as string;
        const base64Data = resultStr.includes(',') ? resultStr.split(',')[1] : resultStr;
        if (base64Data && wsClientRef.current?.isConnected()) {
          wsClientRef.current.sendAudio(base64Data);
        } else {
          console.warn('[ConversationScreen] WebSocket not connected when sending audio.');
          handleTranscriptionFailure();
        }
      };
    };

    try {
      recorder.stop();
    } catch {
      isSendingWhisperRef.current = false;
      loadingRef.current = false;
      setLoading(false);
      stopWhisperRecording();
    }
  };

  const startWhisperRecording = (autoTriggered: boolean = false) => {
    if (isTerminatedRef.current || isConcludingRef.current || loadingRef.current) {
      return;
    }
    if (autoTriggered && isManuallyClosedRef.current) {
      return;
    }
    if (autoTriggered && !hasInterviewerStartedSpeakingRef.current) {
      return;
    }
    if (
      autoTriggered &&
      (audioQueueRef.current?.isTurnInProgress() ||
        audioQueueRef.current?.isAudioActive() ||
        window.speechSynthesis?.speaking)
    ) {
      return;
    }
    if (isListeningRef.current || isWhisperRecordingRef.current) {
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      if (!autoTriggered) {
        alert('Microphone recording is not supported in this browser.');
      }
      return;
    }

    if (!autoTriggered) {
      isManuallyClosedRef.current = false;
    }
    recordingHasSpeechRef.current = false;
    vadInitializedRef.current = false;
    autoSendSuppressedRef.current = false;
    shouldKeepListeningRef.current = true;

    navigator.mediaDevices
      .getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      .then((stream) => {
        if (!shouldKeepListeningRef.current || loadingRef.current) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        mediaStreamRef.current = stream;
        const mimeType = getSupportedAudioMimeType();
        const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
        mediaRecorderRef.current = recorder;
        audioChunksRef.current = [];

        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };

        recorder.onstart = () => {
          isWhisperRecordingRef.current = true;
          isListeningRef.current = true;
          setIsListening(true);
          recordingStartTimeRef.current = Date.now();
          const isAiSpeaking = audioQueueRef.current?.isAudioActive() || window.speechSynthesis?.speaking;
          if (!isAiSpeaking) {
            setMood((prev) => (prev === 'hostile' || prev === 'agitated' ? prev : 'listening'));
          }
        };

        recorder.start(200);

        // Acoustic volume monitoring for barge-in and silence-based auto-send
        try {
          const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
          if (AudioContextClass) {
            const ctx = new AudioContextClass();
            audioContextRef.current = ctx;
            const source = ctx.createMediaStreamSource(stream);
            const analyser = ctx.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);

            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            let silenceCount = 0;
            vadInitializedRef.current = true;

            vadIntervalRef.current = setInterval(() => {
              if (!isListeningRef.current) return;
              analyser.getByteFrequencyData(dataArray);
              let sum = 0;
              for (let i = 0; i < bufferLength; i++) {
                sum += dataArray[i];
              }
              const avg = sum / bufferLength;

              // Sound detected (> 8 / 255)
              if (avg > 8) {
                silenceCount = 0;
                autoSendSuppressedRef.current = false;
                clearSilenceTimers();

                recordingHasSpeechRef.current = true;
                if (!speechStartedForTurnRef.current) {
                  speechStartedForTurnRef.current = true;
                  speechStartTimeRef.current = Date.now();
                  wsClientRef.current?.sendSpeechStart();
                }
                lastSpeechTimeRef.current = Date.now();

                // Candidate spoke during AI speech -> trigger barge in!
                // Ignore transient mic-activation pops within the first 600ms of recording
                const isGracePeriod = Date.now() - recordingStartTimeRef.current < 600;
                const isAiSpeaking = !isGracePeriod && (audioQueueRef.current?.isAudioActive() || window.speechSynthesis?.speaking);
                if (isAiSpeaking) {
                  audioQueueRef.current?.flushAudio();
                  wsClientRef.current?.sendBargeIn();
                  loadingRef.current = false;
                  setLoading(false);
                  setMood('hostile');
                  setBargeInNotice({ visible: true, count: 1 });
                  setTimeout(() => {
                    setBargeInNotice((prev) => ({ ...prev, visible: false }));
                    setMood('agitated');
                  }, 2500);
                }
              } else if (recordingHasSpeechRef.current && !autoSendSuppressedRef.current) {
                // Speech occurred earlier in this recording and now candidate is silent
                silenceCount += 1;
                const elapsedSilenceMs = lastSpeechTimeRef.current
                  ? Date.now() - lastSpeechTimeRef.current
                  : silenceCount * 100;

                // If candidate has stayed silent for 3.0 seconds, close mic and send response to LLM
                if (elapsedSilenceMs >= 3000) {
                  clearSilenceTimers();
                  if (!loadingRef.current && !isTerminatedRef.current && !isConcludingRef.current) {
                    sendWhisperRecording();
                  }
                } else if (elapsedSilenceMs >= 500) {
                  // After 500ms of pause, display live countdown (3s -> 2s -> 1s)
                  const remainingSec = Math.max(1, Math.ceil((3000 - elapsedSilenceMs) / 1000));
                  setCountdownValue(remainingSec);
                }
              }
            }, 100);
          }
        } catch (vadErr) {
          console.warn('[ConversationScreen] AudioContext VAD error:', vadErr);
        }
      })
      .catch((err) => {
        console.error('[ConversationScreen] Microphone stream failed:', err);
        if (!autoTriggered) {
          alert('Could not access microphone: ' + err.message);
        }
        isWhisperRecordingRef.current = false;
        isListeningRef.current = false;
        setIsListening(false);
      });
  };

  // =====================================================================
  // 2. PRESERVED WEB SPEECH API IMPLEMENTATION (for easy rollback)
  // Set STT_ENGINE = 'webspeech' at top of file to restore browser transcription.
  // =====================================================================
  const stopWebSpeechRecognition = () => {
    clearSilenceTimers();
    shouldKeepListeningRef.current = false;
    isListeningRef.current = false;
    setIsListening(false);
    if (!audioQueueRef.current?.isAudioActive() && !window.speechSynthesis?.speaking) {
      setAvatarState('idle');
      setMood((prev) => (prev === 'hostile' || prev === 'agitated' ? prev : 'listening'));
    }
    if (recognitionRef.current) {
      const rec = recognitionRef.current;
      recognitionRef.current = null;
      try {
        rec.onresult = null;
        rec.onerror = null;
        rec.onend = null;
        rec.abort();
      } catch {
        // ignore stop/abort errors
      }
    }
  };

  const startWebSpeechRecognition = (autoTriggered: boolean = false) => {
    if (isTerminatedRef.current || isConcludingRef.current || loadingRef.current) {
      return;
    }
    if (autoTriggered && isManuallyClosedRef.current) {
      return;
    }
    if (autoTriggered && !hasInterviewerStartedSpeakingRef.current) {
      return;
    }
    if (!autoTriggered) {
      isManuallyClosedRef.current = false;
    }
    if (
      autoTriggered &&
      (audioQueueRef.current?.isTurnInProgress() ||
        audioQueueRef.current?.isAudioActive() ||
        window.speechSynthesis?.speaking)
    ) {
      return;
    }
    if (isListeningRef.current && recognitionRef.current) {
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      if (!autoTriggered) {
        alert("Speech recognition is not supported in this browser. Please use Google Chrome or Edge.");
      }
      return;
    }

    try {
      shouldKeepListeningRef.current = true;
      if (!autoTriggered) {
        baseInputRef.current = inputRef.current.trim();
      }

      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        isListeningRef.current = true;
        setIsListening(true);
        const isAiSpeaking = audioQueueRef.current?.isAudioActive() || window.speechSynthesis?.speaking;
        if (!isAiSpeaking) {
          setMood((prev) => (prev === 'hostile' || prev === 'agitated' ? prev : 'listening'));
        }
      };

      recognition.onresult = (event: any) => {
        if (!isListeningRef.current || loadingRef.current) {
          return;
        }

        let fullSpoken = '';
        for (let i = 0; i < event.results.length; ++i) {
          const text = (event.results[i][0]?.transcript || '').trim();
          if (!text) continue;
          fullSpoken = mergeTranscripts(fullSpoken, text);
        }
        if (!fullSpoken || !isListeningRef.current || loadingRef.current) return;

        const words = fullSpoken.split(/\s+/);
        const dedupedWords: string[] = [];
        for (let i = 0; i < words.length; i++) {
          const w = words[i];
          if (
            dedupedWords.length >= 1 &&
            dedupedWords[dedupedWords.length - 1].toLowerCase() === w.toLowerCase()
          ) {
            continue;
          }
          dedupedWords.push(w);
        }
        fullSpoken = dedupedWords.join(' ').trim();

        if (!speechStartedForTurnRef.current) {
          speechStartedForTurnRef.current = true;
          speechStartTimeRef.current = Date.now();
          wsClientRef.current?.sendSpeechStart();
        }
        lastSpeechTimeRef.current = Date.now();

        const isAiSpeaking = audioQueueRef.current?.isAudioActive() || window.speechSynthesis?.speaking;
        if (isAiSpeaking) {
          audioQueueRef.current?.flushAudio();
          wsClientRef.current?.sendBargeIn();
          loadingRef.current = false;
          setLoading(false);
          setMood('hostile');
          setBargeInNotice({ visible: true, count: 1 });
          setTimeout(() => {
            setBargeInNotice(prev => ({ ...prev, visible: false }));
            setMood('agitated');
          }, 2500);
        }

        const base = (baseInputRef.current || '').trim();
        let combined = mergeTranscripts(base, fullSpoken);

        if (combined.length > 2500) {
          combined = combined.slice(0, 2500).trim();
        }

        inputRef.current = combined;
        setInput(combined);

        clearSilenceTimers();
        let remaining = 3;
        setCountdownValue(remaining);
        countdownIntervalRef.current = setInterval(() => {
          remaining -= 1;
          if (remaining > 0) {
            setCountdownValue(remaining);
          } else {
            if (countdownIntervalRef.current) {
              clearInterval(countdownIntervalRef.current);
              countdownIntervalRef.current = null;
            }
          }
        }, 1000);

        silenceTimerRef.current = setTimeout(() => {
          clearSilenceTimers();
          const textToSend = inputRef.current.trim();
          if (textToSend && !loadingRef.current && !isTerminatedRef.current && !isConcludingRef.current) {
            handleSend();
          }
        }, 3000);
      };

      recognition.onerror = (event: any) => {
        if (event.error === 'no-speech' || event.error === 'aborted') {
          return;
        }
        console.warn("[ConversationScreen] Speech recognition notice:", event.error);
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
          clearSilenceTimers();
          shouldKeepListeningRef.current = false;
          isListeningRef.current = false;
          setIsListening(false);
          setLoading(false);
        }
      };

      recognition.onend = () => {
        isListeningRef.current = false;
        recognitionRef.current = null;

        if (silenceTimerRef.current !== null || autoSendCountdownRef.current !== null) {
          return;
        }

        const isAiSpeaking = audioQueueRef.current?.isAudioActive() || window.speechSynthesis?.speaking;
        if (
          shouldKeepListeningRef.current &&
          !loadingRef.current &&
          !isTerminatedRef.current &&
          !isConcludingRef.current &&
          !isAiSpeaking
        ) {
          setTimeout(() => {
            if (
              shouldKeepListeningRef.current &&
              !loadingRef.current &&
              !isTerminatedRef.current &&
              !isConcludingRef.current &&
              silenceTimerRef.current === null &&
              autoSendCountdownRef.current === null
            ) {
              startWebSpeechRecognition(true);
            }
          }, 200);
        } else {
          setIsListening(false);
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (e) {
      console.error("Failed to start speech recognition:", e);
      clearSilenceTimers();
      isListeningRef.current = false;
      setIsListening(false);
    }
  };

  // =====================================================================
  // 3. UNIFIED LISTENING INTERFACES
  // Automatically routes according to STT_ENGINE configuration.
  // =====================================================================
  const stopListening = () => {
    if (STT_ENGINE === 'whisper') {
      stopWhisperRecording();
    } else {
      stopWebSpeechRecognition();
    }
  };

  const startListening = (autoTriggered: boolean = false) => {
    if (STT_ENGINE === 'whisper') {
      startWhisperRecording(autoTriggered);
    } else {
      startWebSpeechRecognition(autoTriggered);
    }
  };

  // Priority P0: Conclude and show scorecard
  const handleConclude = async () => {
    if (!sessionId) return;
    isConcludingRef.current = true;
    stopListening();
    setConcludeLoading(true);
    try {
      const report = await concludeSession(sessionId);
      setCoachingReport(report);
      setIsReportOpen(true);
    } catch (err) {
      console.error('Failed to conclude session', err);
      alert('Failed to generate coaching evaluation. Please try again.');
    } finally {
      setConcludeLoading(false);
    }
  };

  const speakMessage = async (text: string) => {
    if (!isAudioEnabledRef.current) {
      startListening(true);
      return;
    }
    const cleanText = text.replace(/#/g, '').replace(/\*/g, '').replace(/\[END_INTERVIEW\]/g, '').trim();
    if (!cleanText) {
      if (!loadingRef.current && !isTerminatedRef.current && !isConcludingRef.current) {
        startListening(true);
      }
      return;
    }

    const currentVoice = voiceProfileRef.current || voiceProfile || 'am_onyx';

    audioQueueRef.current?.flushAudio();
    if (synthTimerRef.current) {
      clearInterval(synthTimerRef.current);
      synthTimerRef.current = null;
    }
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    speakingSessionSeqRef.current += 1;
    const currentSeq = speakingSessionSeqRef.current;

    // Split into natural sentences for fast incremental playback (< 1.5s TTFA)
    const sentenceRegex = /[^.!?]+(?:[.!?]+(?:\s+|$)|$)/g;
    const rawSentences = cleanText.match(sentenceRegex) || [cleanText];
    const sentences = rawSentences.map(s => s.trim()).filter(Boolean);

    if (sentences.length === 0) return;

    try {
      setAvatarState('thinking');
      // Synthesize Sentence 0 first for ultra-fast first-audio latency without gateway timeouts
      const firstSentence = sentences[0];
      const firstData = await speakVoiceText(firstSentence, currentVoice, sessionId);
      if (speakingSessionSeqRef.current !== currentSeq) {
        return;
      }
      if (firstData?.audio && audioQueueRef.current) {
        audioQueueRef.current.startTurn();
        audioQueueRef.current.enqueue({
          id: getNextAudioId('tts-0'),
          audioBase64: firstData.audio,
          text: firstSentence,
          durationSec: firstData.duration_sec,
        });

        // Asynchronously stream the remaining sentences in background
        if (sentences.length > 1) {
          (async () => {
            for (let i = 1; i < sentences.length; i++) {
              if (speakingSessionSeqRef.current !== currentSeq) {
                return;
              }
              const sentenceText = sentences[i];
              try {
                const chunkData = await speakVoiceText(sentenceText, currentVoice, sessionId);
                if (speakingSessionSeqRef.current !== currentSeq) {
                  return;
                }
                if (chunkData?.audio && audioQueueRef.current) {
                  audioQueueRef.current.enqueue({
                    id: getNextAudioId(`tts-${i}`),
                    audioBase64: chunkData.audio,
                    text: sentenceText,
                    durationSec: chunkData.duration_sec,
                  });
                }
              } catch (chunkErr) {
                console.warn(`[ConversationScreen] Chunk ${i} synthesis failed:`, chunkErr);
              }
            }
            if (speakingSessionSeqRef.current === currentSeq) {
              audioQueueRef.current?.notifyTurnComplete();
            }
          })();
        } else {
          audioQueueRef.current.notifyTurnComplete();
        }
        return;
      }
    } catch (err) {
      console.warn('[ConversationScreen] Kokoro TTS synthesis request failed, using browser speech synthesis:', err);
    }

    // Graceful fallback to browser speech synthesis only if Kokoro TTS is unreachable
    if (!window.speechSynthesis) {
      setAvatarState('idle');
      setMood('listening');
      startListening(true);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(cleanText);
    const voices = window.speechSynthesis.getVoices();
    const isFemale = (currentVoice || '').startsWith('af_') || (currentVoice || '').startsWith('bf_');
    const matched = voices.find(v => isFemale ? (v.name.includes('Female') || v.name.includes('Zira') || v.name.includes('Samantha')) : (v.name.includes('Male') || v.name.includes('David')));
    if (matched) utterance.voice = matched;

    utterance.onstart = () => {
      hasInterviewerStartedSpeakingRef.current = true;
      setAvatarState('speaking');
      setMood((prev) => (prev === 'hostile' || prev === 'agitated' ? prev : 'neutral'));
      synthTimerRef.current = setInterval(() => {
        if (window.speechSynthesis && window.speechSynthesis.speaking) {
          const t = Date.now() / 500;
          const smoothLevel = 0.20 + (Math.sin(t) + 1) * 0.12;
          setAudioLevel(smoothLevel);
        } else {
          if (synthTimerRef.current) {
            clearInterval(synthTimerRef.current);
            synthTimerRef.current = null;
          }
          setAudioLevel(0);
        }
      }, 50);
    };
    utterance.onend = () => {
      if (synthTimerRef.current) {
        clearInterval(synthTimerRef.current);
        synthTimerRef.current = null;
      }
      setAvatarState('idle');
      setMood((prev) => (prev === 'hostile' || prev === 'agitated' ? prev : 'listening'));
      setAudioLevel(0);
      loadingRef.current = false;
      setLoading(false);
      if (!isTerminatedRef.current && !isConcludingRef.current) {
        startListening(true);
      }
    };
    utterance.onerror = () => {
      if (synthTimerRef.current) {
        clearInterval(synthTimerRef.current);
        synthTimerRef.current = null;
      }
      setAvatarState('idle');
      setMood((prev) => (prev === 'hostile' || prev === 'agitated' ? prev : 'listening'));
      setAudioLevel(0);
      loadingRef.current = false;
      setLoading(false);
      if (!isTerminatedRef.current && !isConcludingRef.current) {
        startListening(true);
      }
    };
    window.speechSynthesis.speak(utterance);
  };

  useEffect(() => {
    if (!sessionId) {
      navigate('/');
      return;
    }

    // 1. Initialize Web Audio queue
    const audioQueue = new AudioQueue();
    audioQueueRef.current = audioQueue;

    audioQueue.onVolumeChange = (level) => {
      setAudioLevel(level);
    };

    audioQueue.onPlaybackStart = () => {
      hasInterviewerStartedSpeakingRef.current = true;
      wsClientRef.current?.sendPlaybackStart();
      setAvatarState('speaking');
      setMood(prev => (prev === 'hostile' || prev === 'agitated' ? prev : 'neutral'));
    };

    audioQueue.onPlaybackEnd = () => {
      wsClientRef.current?.sendPlaybackEnd();
      setAvatarState('idle');
      setMood(prev => (prev === 'hostile' || prev === 'agitated' ? prev : 'listening'));
      setAudioLevel(0);
      loadingRef.current = false;
      setLoading(false);
      // Automatically activate candidate microphone when AI finishes speaking
      if (!isTerminatedRef.current && !isConcludingRef.current) {
        startListening(true);
      }
    };

    audioQueue.onAvatarStateChange = (state) => {
      setAvatarState(state);
      if (state === 'idle' || state === 'listening') {
        setMood(prev => (prev === 'hostile' || prev === 'agitated' ? prev : 'listening'));
      } else if (state === 'speaking') {
        setMood(prev => (prev === 'hostile' || prev === 'agitated' ? prev : 'neutral'));
      }
    };

    audioQueue.onFlush = (count) => {
      if (synthTimerRef.current) {
        clearInterval(synthTimerRef.current);
        synthTimerRef.current = null;
      }
      setAvatarState('listening');
      setAudioLevel(0);
      if (count !== undefined && count > 0) {
        setMood('hostile');
        setBargeInNotice({ visible: true, count });
        setTimeout(() => {
          setBargeInNotice(prev => ({ ...prev, visible: false }));
          setMood('agitated');
        }, 3000);
      } else {
        setMood('listening');
      }
    };

    // 2. Initialize duplex WebSocket
    const wsClient = new InterviewWebSocketClient(sessionId, {
      onAudioChunk: (chunk) => {
        if (isAudioEnabledRef.current && chunk.audio) {
          turnAudioReceivedRef.current = true;
          audioQueue.enqueue({
            id: `chunk-${Date.now()}-${Math.random()}`,
            audioBase64: chunk.audio,
            text: chunk.text,
            durationSec: chunk.duration_sec,
            isFinal: chunk.is_final,
          });
        }
      },
      onTextDelta: (deltaData) => {
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last && last.sender === 'ai') {
            return prev.map((m, idx) => idx === prev.length - 1 ? { ...m, text: m.text + deltaData.delta } : m);
          }
          return prev;
        });
      },
      onTurnComplete: (data) => {
        loadingRef.current = false;
        setLoading(false);
        setTurnTrigger(prev => prev + 1);
        if (data.full_text) {
          const cleanDisplay = data.full_text.replace(/\[END_INTERVIEW\]/g, '').trim();
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last && last.sender === 'ai') {
              return prev.map((m, idx) => idx === prev.length - 1 ? { ...m, text: cleanDisplay } : m);
            }
            return [...prev, { id: `ai-${Date.now()}`, sender: 'ai', text: cleanDisplay }];
          });
          if (data.full_text.includes("### 📊 Interview Complete") || data.full_text.includes("[END_INTERVIEW]")) {
            audioQueueRef.current?.notifyTurnComplete();
            isConcludingRef.current = true;
            stopListening();
            handleConclude();
            return;
          }

          // Fallback: If audio is enabled, but NO audio chunks were received from the server
          // (e.g. Kokoro synthesis failed on server), fall back to speakMessage so the candidate always hears speech!
          if (isAudioEnabledRef.current && !turnAudioReceivedRef.current && cleanDisplay) {
            console.warn('[ConversationScreen] No server audio chunks received for turn. Triggering fallback speech.');
            speakMessage(cleanDisplay);
            return;
          }
        }
        audioQueueRef.current?.notifyTurnComplete();
        // If audio is muted, ensure avatar returns to idle and start user's mic immediately.
        // Otherwise, microphone will be activated by audioQueue.onPlaybackEnd or fallback speech onend.
        if (!isAudioEnabledRef.current) {
          setAvatarState('idle');
          startListening(true);
        }
      },
      onTranscript: (data) => {
        isSendingWhisperRef.current = false;
        if (whisperWatchdogRef.current) {
          clearTimeout(whisperWatchdogRef.current);
          whisperWatchdogRef.current = null;
        }
        if (data.role === 'user' && data.text) {
          const whisperText = data.text.trim();
          const targetMsgId = pendingWhisperUserMsgIdRef.current;
          if (targetMsgId) {
            setMessages((prev) =>
              prev.map((m) => (m.id === targetMsgId ? { ...m, text: whisperText } : m))
            );
            pendingWhisperUserMsgIdRef.current = null;
          } else {
            setMessages((prev) => {
              for (let i = prev.length - 1; i >= 0; i--) {
                if (prev[i].sender === 'user' && prev[i].text.includes('Transcribing with Whisper')) {
                  const updated = [...prev];
                  updated[i] = { ...updated[i], text: whisperText };
                  return updated;
                }
              }
              return prev;
            });
          }
        }
      },
      onTranscriptEmpty: () => {
        console.warn('[ConversationScreen] Server reported empty or non-speech transcript.');
        handleTranscriptionFailure();
      },
      onBargeInFlush: (data) => {
        console.warn(`[ConversationScreen] Received barge_in_flush from server! Interruption count: ${data.interruption_count}`);
        audioQueue.flushAudio(data.interruption_count);
        loadingRef.current = false;
        setLoading(false); // Clear loading state so input and buttons are immediately interactive
        setAvatarState('listening');
        setMood('hostile');
        setBargeInNotice({ visible: true, count: data.interruption_count });
        startListening(true);
        setTimeout(() => {
          setBargeInNotice(prev => ({ ...prev, visible: false }));
          setMood('agitated');
        }, 3500);
      },
      onSessionTerminated: (data) => {
        isTerminatedRef.current = true;
        setIsTerminated(true);
        stopListening();
        setMood('hostile');
        if (data.reason) setTerminationReason(data.reason);
      },
      onError: (err) => {
        console.warn('[ConversationScreen] WebSocket notice:', err);
        if (whisperWatchdogRef.current) {
          clearTimeout(whisperWatchdogRef.current);
          whisperWatchdogRef.current = null;
        }
        if (pendingWhisperUserMsgIdRef.current) {
          handleTranscriptionFailure();
          return;
        }
        loadingRef.current = false;
        setLoading(false);
        setAvatarState('idle');
        audioQueue.flushAudio();
        const errMessage = typeof err === 'string' ? err : (err?.message || 'Connection or streaming issue. Please try again.');
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last && last.sender === 'ai' && !last.text) {
            return prev.map((m, idx) => idx === prev.length - 1 ? { ...m, text: `⚠️ ${errMessage}` } : m);
          }
          return prev;
        });
      }
    }, voiceProfile);

    wsClient.connect();
    wsClientRef.current = wsClient;

    let streamSub: EventSource | null = null;

    if (!initialMessage && sessionId) {
      setAvatarState('thinking');
      let streamed = '';
      streamSub = streamOpeningWithAgent(
        sessionId,
        (chunk) => {
          streamed += chunk;
          setMessages([{ id: 'initial', sender: 'ai', text: streamed }]);
        },
        () => {
          setTurnTrigger(prev => prev + 1);
          if (isAudioEnabledRef.current && streamed) {
            speakMessage(streamed);
          } else {
            setAvatarState('idle');
            setMood('listening');
            startListening(true);
          }
        },
        (err) => {
          console.error("Stream opening error:", err);
          const fallback = getFallbackGreeting(role?.id);
          setMessages([{ id: 'initial', sender: 'ai', text: fallback }]);
          if (isAudioEnabledRef.current) {
            speakMessage(fallback);
          } else {
            startListening(true);
          }
        }
      );
    } else if (isAudioEnabledRef.current && initialGreeting) {
      if (!initialGreetingSpokenRef.current) {
        initialGreetingSpokenRef.current = true;
        if (initialAudio) {
          setAvatarState('speaking');
          setMood('neutral');
          audioQueue.startTurn();
          audioQueue.enqueue({
            id: getNextAudioId('initial-greeting'),
            audioBase64: initialAudio,
            text: initialGreeting,
          });
          audioQueue.notifyTurnComplete();
        } else {
          speakMessage(initialGreeting);
        }
      }
    } else {
      startListening(true);
    }

    // User-gesture autounlock listener to ensure audio plays even under strict browser autoplay policies
    const unlockUserAudio = () => {
      audioQueue.resume();
      setIsAudioUnlocked(true);
    };
    window.addEventListener('click', unlockUserAudio, { passive: true });
    window.addEventListener('keydown', unlockUserAudio, { passive: true });
    window.addEventListener('touchstart', unlockUserAudio, { passive: true });
    window.addEventListener('pointerdown', unlockUserAudio, { passive: true });

    const ctx = audioQueue.getAudioContext();
    if (ctx && ctx.state === 'suspended') {
      setIsAudioUnlocked(false);
    }

    return () => {
      window.removeEventListener('click', unlockUserAudio);
      window.removeEventListener('keydown', unlockUserAudio);
      window.removeEventListener('touchstart', unlockUserAudio);
      window.removeEventListener('pointerdown', unlockUserAudio);
      if (streamSub) streamSub.close();
      if (synthTimerRef.current) clearInterval(synthTimerRef.current);
      if (whisperWatchdogRef.current) clearTimeout(whisperWatchdogRef.current);
      audioQueue.close();
      wsClient.disconnect();
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      stopListening();
    };
  }, [sessionId, navigate]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Check live session status for dynamic interviewer emotion & early termination
  useEffect(() => {
    if (!sessionId) return;
    const updateInterviewerEmotion = async () => {
      try {
        const live = await getSessionLiveState(sessionId);
        const currentState = live?.current_state || {};
        const interviewStatus = live?.interview_state?.status;

        if (interviewStatus === 'TERMINATED') {
          setIsTerminated(true);
          setMood('hostile');
          if (live?.interview_state?.termination_reason) {
            setTerminationReason(live.interview_state.termination_reason);
          }
          return;
        }

        const frustration = currentState.frustration ?? 0.1;
        const skepticism = currentState.skepticism ?? 0.5;
        const patience = currentState.patience ?? 0.7;

        // Dynamic interviewer emotion mapping:
        // Hostile: Critical frustration (>= 0.65) or exhausted patience (<= 0.18)
        if (frustration >= 0.65 || patience <= 0.18) {
          setMood('hostile');
        }
        // Agitated: High skepticism (>= 0.70), elevated frustration (>= 0.40), or draining patience (<= 0.35)
        else if (frustration >= 0.40 || skepticism >= 0.70 || patience <= 0.35) {
          setMood('agitated');
        }
        // Neutral: Composed speaking state only when audio is actually playing
        else if (audioQueueRef.current?.isAudioActive() || window.speechSynthesis?.speaking) {
          setMood('neutral');
        }
        // Listening: Calm, receptive state while candidate speaks or AI is thinking/idle
        else {
          setMood('listening');
        }
      } catch {
        // non-blocking
      }
    };
    updateInterviewerEmotion();
  }, [sessionId, turnTrigger]);

  const toggleListening = () => {
    if (isListening || isListeningRef.current) {
      isManuallyClosedRef.current = true;
      if (STT_ENGINE === 'whisper') {
        stopWhisperRecordingManual();
      } else {
        stopWebSpeechRecognition();
      }
      return;
    }
    isManuallyClosedRef.current = false;
    startListening(false);
  };

  const sendTextTurn = async (userTextRaw: string) => {
    let userText = userTextRaw.trim();
    if (!userText || loadingRef.current || !sessionId) return;

    // Hard ceiling safety: prevent runaway repeated transcripts from browser speech recognition
    if (userText.length > 4000) {
      userText = userText.slice(0, 4000).trim();
    }

    if (audioQueueRef.current?.isAudioActive() || window.speechSynthesis?.speaking) {
      audioQueueRef.current?.flushAudio();
      wsClientRef.current?.sendBargeIn();
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel();

    // Calculate candidate spoken duration if voice dictation was used
    const speechDurationSec =
      speechStartTimeRef.current && lastSpeechTimeRef.current
        ? Math.max(0.5, (lastSpeechTimeRef.current - speechStartTimeRef.current) / 1000.0)
        : undefined;

    isManuallyClosedRef.current = false;
    loadingRef.current = true;
    setLoading(true);
    turnAudioReceivedRef.current = false;

    // Reset interviewer speaking status for the upcoming AI turn (Turn 2+)
    hasInterviewerStartedSpeakingRef.current = false;
    speechStartedForTurnRef.current = false;
    recordingHasSpeechRef.current = false;
    speechStartTimeRef.current = null;
    lastSpeechTimeRef.current = null;
    baseInputRef.current = '';

    stopListening();

    inputRef.current = '';
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.value = '';
      textareaRef.current.style.height = '48px';
    }
    setCurrentHint(null);

    const userMsgId = `user-${Date.now()}`;
    const aiMsgId = `ai-${Date.now()}`;

    setMessages(prev => [
      ...prev,
      { id: userMsgId, sender: 'user', text: userText },
      { id: aiMsgId, sender: 'ai', text: '' }
    ]);

    setAvatarState('thinking');
    audioQueueRef.current?.startTurn();

    // Prefer WebSocket if connected
    if (wsClientRef.current?.isConnected()) {
      wsClientRef.current.sendText(userText, speechDurationSec);
      return;
    }

    // Fallback: SSE streaming
    let accumulatedText = "";

    streamChatWithAgent(
      sessionId,
      userText,
      (chunk: string) => {
        accumulatedText += chunk;
        setMessages(prev =>
          prev.map(msg => msg.id === aiMsgId ? { ...msg, text: accumulatedText } : msg)
        );
      },
      () => {
        setTurnTrigger(prev => prev + 1);

        // If completed naturally, prompt evaluation
        if (accumulatedText.includes("### 📊 Interview Complete") || accumulatedText.includes("[END_INTERVIEW]")) {
          loadingRef.current = false;
          setLoading(false);
          isConcludingRef.current = true;
          stopListening();
          handleConclude();
          return;
        }

        if (isAudioEnabledRef.current) {
          // Do not prematurely complete turn or lower loading state while preparing speech.
          // speakMessage enqueues audio chunks and audioQueue.onPlaybackEnd handles turn completion!
          speakMessage(accumulatedText).finally(() => {
            loadingRef.current = false;
            setLoading(false);
          });
        } else {
          loadingRef.current = false;
          setLoading(false);
          setAvatarState('idle');
          audioQueueRef.current?.notifyTurnComplete();
          startListening(true);
        }
      },
      (err: any) => {
        console.error('Chat error', err);
        loadingRef.current = false;
        setLoading(false);
        setAvatarState('idle');
        audioQueueRef.current?.flushAudio();
        setMessages(prev =>
          prev.map(msg => msg.id === aiMsgId ? { ...msg, text: '*System Error: Stream failed. Check connection.*' } : msg)
        );
      }
    );
  };

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    clearSilenceTimers();

    if (isTranscribingToInput) return;

    // If using Whisper and voice recording is active when candidate manually presses Send:
    if (STT_ENGINE === 'whisper' && isWhisperRecordingRef.current) {
      const hasInputText = Boolean((inputRef.current || input).trim());
      const hasLiveSpeech = recordingHasSpeechRef.current || !vadInitializedRef.current;
      if (!hasInputText || hasLiveSpeech) {
        sendWhisperRecording();
        return;
      }
      // Candidate typed text and did not speak into open mic -> close mic and send typed text
      stopWhisperRecording();
    }

    const userText = (inputRef.current || input).trim();
    if (!userText || loadingRef.current || !sessionId) return;
    await sendTextTurn(userText);
  };

  // Priority P1: "Take 2" Rewind Turn
  const handleRewind = async () => {
    if (!sessionId || rewindLoading) return;
    setRewindLoading(true);
    try {
      const res = await rewindTurn(sessionId);
      if (res.messages && res.messages.length > 0) {
        setMessages(res.messages.map((m: any) => ({
          id: `msg-${m.id}`,
          sender: m.sender as 'user' | 'ai',
          text: m.message,
        })));
      } else {
        setMessages([{ id: 'initial', sender: 'ai', text: initialGreeting }]);
      }
      setTurnTrigger(prev => prev + 1);
      isTerminatedRef.current = false;
      isConcludingRef.current = false;
      isManuallyClosedRef.current = false;
      setIsTerminated(false);
      setTerminationReason(null);
      setCurrentHint(null);
      inputRef.current = '';
      baseInputRef.current = '';
      setInput('');
      if (textareaRef.current) {
        textareaRef.current.value = '';
        textareaRef.current.style.height = '48px';
      }
      startListening(true);
    } catch (err) {
      console.error('Failed to rewind turn', err);
      alert('Could not rewind turn.');
    } finally {
      setRewindLoading(false);
    }
  };

  // Priority P1: Coaching Hint
  const handleFetchHint = async () => {
    if (!sessionId || hintLoading) return;
    setHintLoading(true);
    try {
      const hintData = await getCoachingHint(sessionId);
      setCurrentHint(hintData);
    } catch (err) {
      console.error('Failed to get coaching hint', err);
    } finally {
      setHintLoading(false);
    }
  };

  const handleExit = () => {
    stopListening();
    audioQueueRef.current?.flushAudio();
    wsClientRef.current?.disconnect();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    resetSession();
    navigate('/');
  };

  if (!role) return null;

  return (
    <div className="w-full min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between">
      <div className="flex flex-col md:flex-row p-2 sm:p-4 md:p-6 lg:p-8 max-w-[1600px] w-full mx-auto gap-3 md:gap-6 flex-1 md:overflow-hidden min-h-[100dvh] md:min-h-screen">

        {/* Left Sidebar - Desktop Only Persona Card */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="hidden md:flex md:w-80 lg:w-96 flex-col gap-4"
        >
          <div className="flex items-center justify-between py-1">
            <button
              onClick={handleExit}
              className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-xs font-semibold py-1.5 w-fit cursor-pointer"
            >
              <ArrowLeft size={16} /> Exit Practice
            </button>

            <button
              onClick={() => navigate('/history')}
              className="text-slate-400 hover:text-white transition-colors text-xs font-semibold py-1.5 cursor-pointer"
            >
              History
            </button>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 flex-1 overflow-y-auto flex flex-col shadow-2xl backdrop-blur-xl">
            <div className="flex flex-col items-center text-center mb-6 pt-0 w-full">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-purple-900/60 to-indigo-900/60 border border-purple-500/30 flex items-center justify-center shadow-lg relative mb-2">
                <Radio size={36} className="text-purple-400 animate-pulse" />
                <span className="absolute -bottom-2 px-2 py-0.5 rounded-full bg-purple-600 text-[10px] font-bold text-white uppercase tracking-wider">
                  {avatarState === 'speaking' ? 'Speaking' : avatarState === 'thinking' ? 'Thinking' : 'Live Voice'}
                </span>
              </div>

              <h2 className="text-2xl font-black mt-4 text-white tracking-tight drop-shadow-sm">{role?.name || 'CEO'}</h2>
              <span className="text-xs px-3 py-1 bg-purple-500/20 border border-purple-500/40 text-purple-300 rounded-full font-bold mt-1.5">
                {role?.description || 'Executive Counterpart'}
              </span>
            </div>

            <div className="space-y-4 text-sm flex-1">
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl space-y-1">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Persona Archetype</span>
                <p className="text-xs text-slate-300 font-medium">
                  {role.traits ? role.traits.join(" • ") : "Executive Counterpart"}
                </p>
              </div>

              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl space-y-1">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Meeting Directives</span>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Evaluates clarity, evidence, and ROI. Low tolerance for vague or evasive statements.
                </p>
              </div>

              {/* AI Voice Profile Indicator & Dynamic Selector */}
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">AI Voice Profile</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold border border-purple-500/30">
                    Kokoro-82M
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    aria-label="Select AI Voice Profile"
                    value={voiceProfile || 'am_onyx'}
                    onChange={(e) => {
                      const nextVoice = e.target.value;
                      setVoiceProfile(nextVoice);
                      wsClientRef.current?.setVoice(nextVoice);
                    }}
                    className="flex-1 bg-slate-900 border border-slate-700/80 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-purple-500 cursor-pointer"
                  >
                    {VOICE_OPTIONS.map((opt) => (
                      <option key={opt.id} value={opt.id} className="bg-slate-900 text-white">
                        {opt.name} ({opt.gender} • {opt.tone})
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    title="Test Voice Preview"
                    aria-label="Test Voice Preview"
                    onClick={async () => {
                      const currentOpt = VOICE_OPTIONS.find(v => v.id === (voiceProfile || 'am_onyx'));
                      const previewPhrase = currentOpt ? `Hello, I'm ${currentOpt.name}. I'm ready.` : "Hello, I am ready.";
                      try {
                        const data = await speakVoiceText(previewPhrase, voiceProfile || 'am_onyx', sessionId);
                        if (data?.audio && audioQueueRef.current) {
                          audioQueueRef.current.startTurn();
                          audioQueueRef.current.enqueue({
                            id: getNextAudioId('preview'),
                            audioBase64: data.audio,
                            text: previewPhrase,
                            durationSec: data.duration_sec,
                          });
                          audioQueueRef.current.notifyTurnComplete();
                        }
                      } catch (e) {
                        console.warn('Voice preview error:', e);
                      }
                    }}
                    className="p-1.5 bg-purple-600/30 hover:bg-purple-600/50 border border-purple-500/40 text-purple-300 hover:text-white rounded-lg transition-colors cursor-pointer"
                  >
                    <Volume2 size={14} />
                  </button>
                </div>
                <p className="text-[10px] text-slate-400">
                  {VOICE_OPTIONS.find(v => v.id === (voiceProfile || 'am_onyx'))?.description || 'Active AI voice profile'}
                </p>
              </div>
            </div>

            {/* Audio & Status controls */}
            <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between">
              <button
                type="button"
                onClick={() => {
                  const next = !isAudioEnabled;
                  isAudioEnabledRef.current = next;
                  setIsAudioEnabled(next);
                  if (!next) {
                    audioQueueRef.current?.flushAudio();
                    if (window.speechSynthesis) {
                      window.speechSynthesis.cancel();
                    }
                    setAvatarState('idle');
                    startListening(true);
                  }
                }}
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors cursor-pointer"
              >
                {isAudioEnabled ? <Volume2 size={15} className="text-emerald-400" /> : <VolumeX size={15} />}
                <span>{isAudioEnabled ? 'Audio On' : 'Muted'}</span>
              </button>

              <span className="text-[11px] text-slate-400 font-medium">
                Turns: {Math.max(0, messages.filter(m => m.sender === 'user').length)}
              </span>
            </div>
          </div>
        </motion.div>

        {/* Right Side - Main Interface */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex-1 flex flex-col bg-slate-900/90 rounded-2xl overflow-hidden border border-slate-800 shadow-2xl backdrop-blur-xl"
        >
          {/* Chat Header Bar */}
          <div className="px-3 sm:px-6 py-2 sm:py-3 border-b border-slate-800 bg-slate-950/60 backdrop-blur-xs flex items-center justify-between z-10 flex-shrink-0 gap-2">
            <div className="flex items-center gap-1.5 sm:gap-2.5 min-w-0">
              {/* Mobile Back Button */}
              <button
                type="button"
                onClick={handleExit}
                className="md:hidden p-1.5 -ml-1 text-slate-400 hover:text-white rounded-lg transition-colors cursor-pointer shrink-0"
                title="Exit Practice"
              >
                <ArrowLeft size={16} />
              </button>

              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
              <div className="flex flex-col sm:flex-row sm:items-center sm:gap-1.5 min-w-0">
                <span className="text-xs font-bold text-white tracking-wide truncate">
                  {role?.name || 'Executive'}
                </span>
                <span className="hidden sm:inline-block text-[10px] text-purple-300 font-medium truncate">
                  • {role?.description || 'Interviewer'}
                </span>
              </div>

              <AnimatePresence>
                {bargeInNotice.visible && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9, x: -10 }}
                    animate={{ opacity: 1, scale: 1, x: 0 }}
                    exit={{ opacity: 0, scale: 0.9, x: -10 }}
                    className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[10px] sm:text-[11px] font-semibold shrink-0"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                    <span>Barge-in</span>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
              {/* Mobile Persona Sheet Button */}
              <button
                type="button"
                onClick={() => setIsMobilePersonaOpen(true)}
                className="md:hidden flex items-center gap-1 px-2 py-1.5 rounded-xl bg-slate-800 text-purple-300 hover:text-white border border-slate-700 text-xs font-semibold cursor-pointer"
                title="Persona Info"
              >
                <User size={13} />
                <span className="text-[10px]">Persona</span>
              </button>

              {/* Priority P0: End & Evaluate Button */}
              <button
                type="button"
                onClick={handleConclude}
                disabled={concludeLoading || loading}
                className="flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3.5 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-sm cursor-pointer"
              >
                {concludeLoading ? <Loader2 size={13} className="animate-spin" /> : <Trophy size={13} />}
                <span className="hidden sm:inline">End & Evaluate</span>
                <span className="sm:hidden text-[11px]">End</span>
              </button>

              {/* Debug Transcript Button */}
              <button
                type="button"
                onClick={() => setIsTranscriptOpen(prev => !prev)}
                className={`flex items-center gap-1 px-2 sm:px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${isTranscriptOpen
                  ? 'bg-purple-600/30 border-purple-500/60 text-purple-200'
                  : 'bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border-slate-700'
                  }`}
                title="Open Live Debug Transcript Console"
              >
                <FileText size={13} className="text-purple-400" />
                <span className="hidden sm:inline">Transcript</span>
                <span className="px-1 py-0.2 rounded-full bg-purple-500/20 text-purple-300 text-[10px] font-mono">
                  {messages.length}
                </span>
              </button>

              {/* Live Variable Inspector Button */}
              <button
                type="button"
                onClick={() => setIsInspectorOpen(true)}
                className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 text-xs font-semibold transition-all cursor-pointer"
              >
                <Activity size={14} className="text-indigo-400 animate-pulse" />
                <span>Inspector</span>
              </button>
            </div>
          </div>

          {/* Main Stage Area: Pressure Cooker Blob Avatar + Optional Docked Debug Transcript */}
          <div className="flex-1 flex overflow-hidden relative">
            <div className="flex-1 p-2 sm:p-4 md:p-6 flex flex-col items-center justify-center relative overflow-hidden">
              {/* Floating Mobile Audio Unlock Button */}
              {!isAudioUnlocked && (
                <motion.button
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  onClick={() => {
                    audioQueueRef.current?.resume();
                    setIsAudioUnlocked(true);
                  }}
                  className="absolute z-30 px-5 py-2.5 rounded-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-bold text-xs shadow-2xl border border-purple-400/40 animate-bounce flex items-center gap-2 cursor-pointer"
                >
                  <Volume2 size={16} /> Tap to start interview audio
                </motion.button>
              )}
              {/* Priority P0: Early Termination Banner */}
              {isTerminated && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="w-full max-w-xl mb-4 p-4 rounded-2xl bg-rose-950/70 border border-rose-500/60 text-rose-200 text-xs flex items-center justify-between gap-4 shadow-xl z-20"
                >
                  <div className="space-y-1">
                    <span className="font-bold flex items-center gap-1.5 text-rose-300 text-sm">
                      <ShieldAlert size={16} /> Stakeholder Walkout: Early Termination
                    </span>
                    <p className="text-xs text-rose-200/90 leading-relaxed">
                      {terminationReason || `The ${role.name}'s patience was exhausted and frustration reached critical limits.`}
                    </p>
                  </div>
                  <button
                    onClick={handleConclude}
                    className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shrink-0 transition-colors shadow-sm cursor-pointer"
                  >
                    View Report
                  </button>
                </motion.div>
              )}

              <BlobAvatar
                mood={mood}
                audioLevel={audioLevel}
                isSpeaking={avatarState === 'speaking'}
                isThinking={avatarState === 'thinking' || loading}
                isTranscribing={isTranscribingToInput}
                avatarState={avatarState}
                roleName={role?.name || 'CEO'}
                roleTitle={role?.description}
                isCandidateSpeaking={isListening}
                interruptionCount={bargeInNotice.count}
              />

              {/* Live Subtitle Card so dialogue is fully visible right on screen */}
              {latestAiMessage && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="w-full max-w-2xl mt-2 sm:mt-4 p-3 sm:p-4 rounded-xl sm:rounded-2xl bg-slate-900/85 border border-slate-800/90 shadow-xl backdrop-blur-md text-left z-10"
                >
                  <div className="flex items-center justify-between mb-1.5 sm:mb-2">
                    <div className="flex items-center gap-1.5 sm:gap-2">
                      <Bot size={14} className="text-purple-400 shrink-0" />
                      <span className="text-xs font-bold text-slate-300">
                        {role?.name || 'Interviewer'}
                      </span>
                      {avatarState === 'speaking' && (
                        <span className="flex items-center gap-1 text-[9px] sm:text-[10px] text-emerald-400 font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" /> Speaking
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => setIsTranscriptOpen(true)}
                      className="text-[10px] sm:text-[11px] text-purple-400 hover:text-purple-300 font-medium transition-colors cursor-pointer"
                    >
                      Transcript &rarr;
                    </button>
                  </div>
                  <p className="text-xs sm:text-sm text-slate-200 leading-relaxed max-h-20 sm:max-h-28 overflow-y-auto pr-1">
                    {latestAiMessage.text}
                  </p>
                </motion.div>
              )}
            </div>

            {/* Docked Debug Transcript Panel */}
            {isTranscriptDocked && isTranscriptOpen && (
              <DebugTranscriptDrawer
                isOpen={isTranscriptOpen}
                onClose={() => setIsTranscriptOpen(false)}
                messages={messages}
                roleName={role?.name || 'CEO'}
                sessionId={sessionId}
                isDocked={true}
                onToggleDock={() => setIsTranscriptDocked(false)}
                isLoading={loading}
              />
            )}
          </div>

          {/* Priority P1: Coaching Hint Popover */}
          <AnimatePresence>
            {currentHint && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                className="mx-4 mb-2 p-3.5 rounded-2xl bg-purple-950/95 border border-purple-500/40 text-xs shadow-2xl backdrop-blur-md flex items-start justify-between gap-3 text-purple-100"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 font-bold text-purple-300">
                    <Lightbulb size={14} className="text-amber-400 shrink-0" />
                    <span>Coach Hint: {currentHint.focus_area}</span>
                  </div>
                  <p className="text-xs text-purple-100 leading-relaxed font-medium">
                    "{currentHint.hint}"
                  </p>
                  <span className="inline-block text-[10px] text-purple-300/80 mt-0.5">
                    Stakeholder perception: {currentHint.current_stakeholder_perception}
                  </span>
                </div>
                <button
                  onClick={() => setCurrentHint(null)}
                  className="text-purple-300 hover:text-white p-1 rounded-md hover:bg-purple-900/50 transition-colors"
                >
                  <X size={14} />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Input Area */}
          <div className="p-2 sm:p-4 border-t border-slate-800 bg-slate-950/90 backdrop-blur-md">
            {/* Auto-send countdown & Transcribing-to-input badges */}
            <AnimatePresence>
              {isTranscribingToInput && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 6 }}
                  className="max-w-4xl mx-auto mb-2 px-3 py-1.5 sm:px-4 sm:py-2 rounded-xl bg-slate-900/95 border border-indigo-500/40 text-xs flex items-center gap-2 text-indigo-200 shadow-lg backdrop-blur-md"
                >
                  <Loader2 size={13} className="text-indigo-400 animate-spin shrink-0" />
                  <span className="font-medium text-[11px] sm:text-xs">
                    Microphone closed — converting speech to text for manual review & send...
                  </span>
                </motion.div>
              )}
              {autoSendCountdown !== null && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 6 }}
                  className="max-w-4xl mx-auto mb-2 px-3 py-1.5 sm:px-4 sm:py-2 rounded-xl bg-purple-950/90 border border-purple-500/40 text-xs flex items-center justify-between text-purple-200 shadow-lg backdrop-blur-md"
                >
                  <div className="flex items-center gap-1.5 sm:gap-2">
                    <Clock size={13} className="text-purple-400 animate-pulse shrink-0" />
                    <span className="font-medium text-[11px] sm:text-xs">
                      Sending response in <strong className="text-white font-bold">{autoSendCountdown}s</strong>
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        clearSilenceTimers();
                        if (STT_ENGINE === 'whisper') {
                          sendWhisperRecording();
                        } else {
                          handleSend();
                        }
                      }}
                      className="px-2 py-0.5 sm:px-2.5 sm:py-1 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-semibold text-[10px] sm:text-[11px] transition-colors cursor-pointer"
                    >
                      Send Now
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        autoSendSuppressedRef.current = true;
                        clearSilenceTimers();
                      }}
                      className="p-1 hover:bg-purple-900/50 rounded-md text-purple-300 hover:text-white transition-colors cursor-pointer"
                      title="Cancel auto-send"
                    >
                      <X size={13} />
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <form onSubmit={handleSend} className="relative flex items-end gap-1.5 sm:gap-2 max-w-4xl mx-auto">

              {/* Priority P1: "Take 2" (Rewind Turn) */}
              {messages.some(m => m.sender === 'user') && !loading && (
                <button
                  type="button"
                  onClick={handleRewind}
                  disabled={rewindLoading}
                  title="Take 2: Undo previous turn and try another answer"
                  className="p-2 sm:p-3 rounded-xl sm:rounded-full flex-shrink-0 bg-slate-900 border border-slate-800 hover:border-amber-500/50 hover:bg-amber-950/30 text-amber-400 transition-colors cursor-pointer mb-0.5"
                >
                  <RotateCcw size={16} className={rewindLoading ? "animate-spin text-amber-400 sm:w-[18px] sm:h-[18px]" : "sm:w-[18px] sm:h-[18px]"} />
                </button>
              )}

              {/* Priority P1: Ask Coach for Hint */}
              <button
                type="button"
                onClick={handleFetchHint}
                disabled={hintLoading || loading}
                title="Get a real-time tactical hint for this turn"
                className="p-2 sm:p-3 rounded-xl sm:rounded-full flex-shrink-0 bg-slate-900 border border-slate-800 hover:border-purple-500/50 hover:bg-purple-950/30 text-purple-400 transition-colors cursor-pointer mb-0.5"
              >
                {hintLoading ? <Loader2 size={16} className="animate-spin text-purple-400 sm:w-[18px] sm:h-[18px]" /> : <Lightbulb size={16} className="sm:w-[18px] sm:h-[18px]" />}
              </button>

              {/* Voice Dictation Toggle */}
              <button
                type="button"
                onClick={toggleListening}
                disabled={isTranscribingToInput || loading || isTerminated}
                title={isListening ? "Close microphone manually (won't auto-send; click Send when ready)" : "Open microphone"}
                className={`p-2 sm:p-3 rounded-xl sm:rounded-full flex-shrink-0 transition-colors cursor-pointer disabled:opacity-50 mb-0.5 ${isListening
                  ? 'bg-rose-500 text-white animate-pulse'
                  : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white hover:bg-slate-800'
                  }`}
              >
                {isListening ? <Mic size={16} className="sm:w-[18px] sm:h-[18px]" /> : <MicOff size={16} className="sm:w-[18px] sm:h-[18px]" />}
              </button>

              <div className="relative flex-1">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={input}
                  onChange={(e) => {
                    const val = e.target.value;
                    inputRef.current = val;
                    baseInputRef.current = val;
                    setInput(val);
                    autoSendSuppressedRef.current = true;
                    clearSilenceTimers();
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder={
                    isTranscribingToInput
                      ? "Transcribing recorded audio to text box..."
                      : isListening
                        ? "Listening... (auto-sends after 3s silence, or close mic to send manually)"
                        : "Type answer (Enter to send)..."
                  }
                  className="w-full bg-slate-900 border border-slate-800 rounded-2xl px-3.5 sm:px-5 py-2.5 sm:py-3.5 pr-11 sm:pr-14 text-xs md:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 transition-colors resize-none overflow-y-auto min-h-[44px] sm:min-h-[48px] max-h-[140px] leading-relaxed"
                  disabled={loading || isTerminated}
                />

                <button
                  type="submit"
                  disabled={(!input.trim() && !isListening) || loading || isTerminated || isTranscribingToInput}
                  className="absolute right-2 bottom-2 sm:right-2.5 sm:bottom-2.5 p-1.5 sm:p-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:bg-slate-800 text-white rounded-xl transition-colors flex items-center justify-center cursor-pointer shadow-md"
                  title="Send (Enter)"
                >
                  {loading || isTranscribingToInput ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                </button>
              </div>
            </form>
          </div>
        </motion.div>

        {/* Mobile Persona Sheet Drawer */}
        <AnimatePresence>
          {isMobilePersonaOpen && (
            <div
              className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/75 backdrop-blur-sm p-0 sm:p-4"
              onClick={() => setIsMobilePersonaOpen(false)}
            >
              <motion.div
                initial={{ opacity: 0, y: 120 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 120 }}
                transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                onClick={(e) => e.stopPropagation()}
                className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-t-3xl sm:rounded-2xl p-5 shadow-2xl flex flex-col max-h-[85vh] overflow-y-auto"
              >
                <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl bg-purple-600/25 border border-purple-500/40 text-purple-400 flex items-center justify-center">
                      <User size={18} />
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-white">{role?.name || 'Executive'}</h3>
                      <p className="text-[11px] text-purple-300 font-medium">{role?.description || 'Counterpart'}</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsMobilePersonaOpen(false)}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
                  >
                    <X size={18} />
                  </button>
                </div>

                <div className="space-y-3 text-xs">
                  {/* Archetype */}
                  <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Persona Archetype</span>
                    <p className="text-xs text-slate-300 font-medium">
                      {role.traits ? role.traits.join(" • ") : "Executive Counterpart"}
                    </p>
                  </div>

                  {/* Directives */}
                  <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Meeting Directives</span>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      Evaluates clarity, evidence, and ROI. Low tolerance for vague or evasive statements.
                    </p>
                  </div>

                  {/* AI Voice Profile Selector */}
                  <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">AI Voice Profile</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold border border-purple-500/30">
                        Kokoro-82M
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <select
                        aria-label="Select AI Voice Profile"
                        value={voiceProfile || 'am_onyx'}
                        onChange={(e) => {
                          const nextVoice = e.target.value;
                          setVoiceProfile(nextVoice);
                          wsClientRef.current?.setVoice(nextVoice);
                        }}
                        className="flex-1 bg-slate-900 border border-slate-700/80 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-purple-500 cursor-pointer"
                      >
                        {VOICE_OPTIONS.map((opt) => (
                          <option key={opt.id} value={opt.id} className="bg-slate-900 text-white">
                            {opt.name} ({opt.gender} • {opt.tone})
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        title="Test Voice Preview"
                        aria-label="Test Voice Preview"
                        onClick={async () => {
                          const currentOpt = VOICE_OPTIONS.find(v => v.id === (voiceProfile || 'am_onyx'));
                          const previewPhrase = currentOpt ? `Hello, I'm ${currentOpt.name}. I'm ready.` : "Hello, I am ready.";
                          try {
                            const data = await speakVoiceText(previewPhrase, voiceProfile || 'am_onyx', sessionId);
                            if (data?.audio && audioQueueRef.current) {
                              audioQueueRef.current.startTurn();
                              audioQueueRef.current.enqueue({
                                id: getNextAudioId('preview-mob'),
                                audioBase64: data.audio,
                                text: previewPhrase,
                                durationSec: data.duration_sec,
                              });
                              audioQueueRef.current.notifyTurnComplete();
                            }
                          } catch (e) {
                            console.warn('Voice preview error:', e);
                          }
                        }}
                        className="p-1.5 bg-purple-600/30 hover:bg-purple-600/50 border border-purple-500/40 text-purple-300 hover:text-white rounded-lg transition-colors cursor-pointer"
                      >
                        <Volume2 size={14} />
                      </button>
                    </div>
                  </div>

                  {/* Audio Mute / Unmute Toggle */}
                  <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Interviewer Audio</span>
                    <button
                      type="button"
                      onClick={() => {
                        const next = !isAudioEnabled;
                        isAudioEnabledRef.current = next;
                        setIsAudioEnabled(next);
                        if (!next) {
                          audioQueueRef.current?.flushAudio();
                          if (window.speechSynthesis) window.speechSynthesis.cancel();
                          setAvatarState('idle');
                          startListening(true);
                        }
                      }}
                      className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-900 border border-slate-700 text-xs font-semibold text-slate-200"
                    >
                      {isAudioEnabled ? <Volume2 size={14} className="text-emerald-400" /> : <VolumeX size={14} />}
                      <span>{isAudioEnabled ? 'Audio On' : 'Muted'}</span>
                    </button>
                  </div>

                  {/* Navigation / Actions */}
                  <div className="pt-2 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={handleExit}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors cursor-pointer"
                    >
                      <ArrowLeft size={14} /> Exit Practice
                    </button>
                    <button
                      type="button"
                      onClick={() => navigate('/history')}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors cursor-pointer"
                    >
                      History
                    </button>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setIsMobilePersonaOpen(false)}
                  className="mt-4 w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs transition-colors shadow-md cursor-pointer"
                >
                  Done
                </button>
              </motion.div>
            </div>
          )}
        </AnimatePresence>

        {/* Slide-over Debug Transcript Drawer (Overlay Mode) */}
        {!isTranscriptDocked && (
          <DebugTranscriptDrawer
            isOpen={isTranscriptOpen}
            onClose={() => setIsTranscriptOpen(false)}
            messages={messages}
            roleName={role?.name || 'CEO'}
            sessionId={sessionId}
            isDocked={false}
            onToggleDock={() => setIsTranscriptDocked(true)}
            isLoading={loading}
          />
        )}

        {/* Live Variable Inspector Panel */}
        <LiveVariableInspector
          sessionId={sessionId}
          isOpen={isInspectorOpen}
          onClose={() => setIsInspectorOpen(false)}
          lastTurnTrigger={turnTrigger}
          messages={messages}
        />

        {/* Concluding & Scorecard Generation Overlay */}
        <AnimatePresence>
          {concludeLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
            >
              <motion.div
                initial={{ scale: 0.92, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.92, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="bg-slate-900 border border-purple-500/30 rounded-3xl p-6 sm:p-8 max-w-sm w-full text-center shadow-2xl space-y-4"
              >
                <div className="relative w-16 h-16 mx-auto flex items-center justify-center">
                  <div className="absolute inset-0 rounded-full bg-purple-500/20 animate-ping" />
                  <div className="w-16 h-16 rounded-2xl bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 shadow-inner">
                    <Trophy size={30} className="animate-pulse" />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <h3 className="text-base sm:text-lg font-bold text-white">
                    Generating Sales Scorecard
                  </h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Analyzing conversation dynamics, acoustic delivery telemetry, and executive readiness...
                  </p>
                </div>

                <div className="flex items-center justify-center gap-2 text-xs font-semibold text-purple-300 bg-purple-950/40 border border-purple-500/30 py-2.5 px-3 rounded-xl">
                  <Loader2 size={14} className="animate-spin text-purple-400 shrink-0" />
                  <span>Synthesizing evaluation report...</span>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Priority P0: Structured Coaching Scorecard Modal */}
        <FeedbackReportModal
          isOpen={isReportOpen}
          onClose={() => setIsReportOpen(false)}
          sessionId={sessionId || coachingReport?.session_id}
          report={coachingReport}
          onRestart={() => navigate('/scenario')}
        />
      </div>
    </div>
  );
};

export default ConversationScreen;

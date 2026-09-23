import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useStore } from '../store/useStore';
import { 
  streamChatWithAgent, 
  streamOpeningWithAgent, 
  concludeSession, 
  rewindTurn, 
  getCoachingHint,
  getSessionLiveState 
} from '../api/apiClient';
import { 
  User, 
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
  X
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import RobotAvatar from '../components/RobotAvatar';
import type { AvatarState } from '../components/RobotAvatar';
import { LiveVariableInspector } from '../components/LiveVariableInspector';
import { FeedbackReportModal } from '../components/FeedbackReportModal';
import type { StructuredCoachingReport } from '../components/FeedbackReportModal';
import { AudioQueue } from '../utils/audioQueue';
import { InterviewWebSocketClient } from '../utils/interviewWebSocket';

interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
}

const ConversationScreen: React.FC = () => {
  const navigate = useNavigate();
  const { role, sessionId, initialMessage, resetSession } = useStore();

  const getFallbackGreeting = (roleId?: string) => {
    const id = (roleId || '').toUpperCase();
    if (id.includes('CEO')) {
      return "Thanks for taking the time to meet today. We have high expectations for this initiative, and my focus is strictly on strategic impact and enterprise valuation. Let's get straight to it—give me the high-level picture of how your approach moves the needle for our growth.";
    }
    if (id.includes('CTO')) {
      return "Thanks for jumping on. From an architectural standpoint, I care about scalability, reliability, and technical tradeoffs. To kick us off, walk me through your high-level architecture and the core decisions behind it.";
    }
    if (id.includes('HR')) {
      return "Hello, thanks for joining me today. I'm looking forward to learning more about your background and how you collaborate in team environments. To get started, could you tell me about a recent project you led and how you handled key stakeholder dynamics?";
    }
    if (id.includes('SALES')) {
      return "Good to connect today. We're evaluating solutions in this space, but our pipeline and ROI requirements are aggressive. Let's dive right in—what is the core differentiator of your offering, and why should we prioritize this now?";
    }
    return "Thanks for joining today's session. Let's dive right in—could you provide an overview of your strategy and how you plan to tackle this scenario?";
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
  const [avatarState, setAvatarState] = useState<AvatarState>('idle');
  const [isListening, setIsListening] = useState(false);
  const [isAudioEnabled, setIsAudioEnabled] = useState(true);
  const [currentSpeechText, setCurrentSpeechText] = useState('');
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
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
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const audioQueueRef = useRef<AudioQueue | null>(null);
  const wsClientRef = useRef<InterviewWebSocketClient | null>(null);

  useEffect(() => {
    if (!sessionId) {
      navigate('/');
      return;
    }

    // 1. Initialize Web Audio queue
    const audioQueue = new AudioQueue();
    audioQueueRef.current = audioQueue;

    audioQueue.onPlaybackStart = (_chunk) => {
      wsClientRef.current?.sendPlaybackStart();
      setAvatarState('speaking');
    };

    audioQueue.onPlaybackEnd = () => {
      wsClientRef.current?.sendPlaybackEnd();
      setAvatarState('idle');
      setCurrentSpeechText('');
    };

    audioQueue.onAvatarStateChange = (state) => {
      setAvatarState(state);
    };

    audioQueue.onFlush = (count) => {
      setAvatarState('listening');
      setCurrentSpeechText('');
      if (count !== undefined && count > 0) {
        setBargeInNotice({ visible: true, count });
        setTimeout(() => {
          setBargeInNotice(prev => ({ ...prev, visible: false }));
        }, 3000);
      }
    };

    // 2. Initialize duplex WebSocket
    const wsClient = new InterviewWebSocketClient(sessionId, {
      onAudioChunk: (chunk) => {
        if (isAudioEnabled && chunk.audio) {
          audioQueue.enqueue({
            id: `chunk-${Date.now()}-${Math.random()}`,
            audioBase64: chunk.audio,
            text: chunk.text,
            durationSec: chunk.duration_sec,
          });
          if (chunk.text) {
            setCurrentSpeechText(chunk.text);
          }
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
        setLoading(false);
        setTurnTrigger(prev => prev + 1);
        if (data.full_text) {
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last && last.sender === 'ai') {
              return prev.map((m, idx) => idx === prev.length - 1 ? { ...m, text: data.full_text } : m);
            }
            return [...prev, { id: `ai-${Date.now()}`, sender: 'ai', text: data.full_text }];
          });
          if (data.full_text.includes("### 📊 Interview Complete") || data.full_text.includes("[END_INTERVIEW]")) {
            handleConclude();
          }
        }
      },
      onTranscript: (data) => {
        if (data.role === 'user') {
          setInput(prev => prev ? prev : data.text);
        }
      },
      onBargeInFlush: (data) => {
        console.warn(`[ConversationScreen] Received barge_in_flush from server! Interruption count: ${data.interruption_count}`);
        audioQueue.flushAudio(data.interruption_count);
        setAvatarState('listening');
        setBargeInNotice({ visible: true, count: data.interruption_count });
        setTimeout(() => {
          setBargeInNotice(prev => ({ ...prev, visible: false }));
        }, 3500);
      },
      onSessionTerminated: (data) => {
        setIsTerminated(true);
        if (data.reason) setTerminationReason(data.reason);
      },
      onError: (err) => {
        console.debug('[ConversationScreen] WebSocket notice:', err);
      }
    });

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
          if (isAudioEnabled && streamed) {
            speakMessage(streamed);
          } else {
            setAvatarState('idle');
          }
        },
        (err) => {
          console.error("Stream opening error:", err);
          const fallback = getFallbackGreeting(role?.id);
          setMessages([{ id: 'initial', sender: 'ai', text: fallback }]);
          if (isAudioEnabled) speakMessage(fallback);
        }
      );
    } else if (isAudioEnabled && initialGreeting) {
      speakMessage(initialGreeting);
    }
    
    return () => {
      if (streamSub) streamSub.close();
      audioQueue.close();
      wsClient.disconnect();
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      if (recognitionRef.current) recognitionRef.current.stop();
    };
  }, [sessionId, navigate]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Check live session status for early termination
  useEffect(() => {
    if (!sessionId) return;
    const checkTermination = async () => {
      try {
        const live = await getSessionLiveState(sessionId);
        if (live?.interview_state?.status === 'TERMINATED') {
          setIsTerminated(true);
          if (live.interview_state.termination_reason) {
            setTerminationReason(live.interview_state.termination_reason);
          }
        }
      } catch (e) {
        // non-blocking
      }
    };
    checkTermination();
  }, [sessionId, turnTrigger]);

  const speakMessage = (text: string) => {
    if (!isAudioEnabled) return;
    audioQueueRef.current?.flushAudio();
    if (!window.speechSynthesis) return;
    
    const cleanText = text.replace(/#/g, '').replace(/\*/g, '').replace(/\[END_INTERVIEW\]/g, '');
    
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.onstart = () => {
      setCurrentSpeechText(cleanText);
      setAvatarState('speaking');
    };
    utterance.onend = () => {
      setAvatarState('idle');
      setCurrentSpeechText('');
    };
    utterance.onerror = () => {
      setAvatarState('idle');
      setCurrentSpeechText('');
    };
    
    window.speechSynthesis.speak(utterance);
  };

  const toggleListening = () => {
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in this browser. Please use Google Chrome or Edge.");
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
        // Instant Client-Side Flush on Candidate Speech
        if (audioQueueRef.current?.isAudioActive() || window.speechSynthesis?.speaking) {
          audioQueueRef.current?.flushAudio();
          wsClientRef.current?.sendBargeIn();
          setBargeInNotice({ visible: true, count: 1 });
          setTimeout(() => setBargeInNotice(prev => ({ ...prev, visible: false })), 2500);
        } else {
          wsClientRef.current?.sendSpeechStart();
        }
      };

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInput((prev) => prev ? `${prev} ${transcript}` : transcript);
      };

      recognition.onerror = (event: any) => {
        console.error("Speech recognition error", event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (e) {
      console.error("Failed to start speech recognition:", e);
      setIsListening(false);
    }
  };

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || loading || !sessionId) return;

    if (audioQueueRef.current?.isAudioActive() || window.speechSynthesis?.speaking) {
      audioQueueRef.current?.flushAudio();
      wsClientRef.current?.sendBargeIn();
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    }

    const userText = input;
    setInput('');
    setCurrentHint(null);
    
    const userMsgId = `user-${Date.now()}`;
    const aiMsgId = `ai-${Date.now()}`;

    setMessages(prev => [
      ...prev,
      { id: userMsgId, sender: 'user', text: userText },
      { id: aiMsgId, sender: 'ai', text: '' }
    ]);

    setLoading(true);
    setAvatarState('thinking');

    // Prefer WebSocket if connected
    if (wsClientRef.current?.isConnected()) {
      wsClientRef.current.sendText(userText);
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
        setLoading(false);
        setTurnTrigger(prev => prev + 1);
        speakMessage(accumulatedText);

        // If completed naturally, prompt evaluation
        if (accumulatedText.includes("### 📊 Interview Complete") || accumulatedText.includes("[END_INTERVIEW]")) {
          handleConclude();
        }
      },
      (err: any) => {
        console.error('Chat error', err);
        setLoading(false);
        setAvatarState('idle');
        setMessages(prev => 
          prev.map(msg => msg.id === aiMsgId ? { ...msg, text: '*System Error: Stream failed. Check connection.*' } : msg)
        );
      }
    );
  };

  // Priority P0: Conclude and show scorecard
  const handleConclude = async () => {
    if (!sessionId) return;
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
      setIsTerminated(false);
      setTerminationReason(null);
      setCurrentHint(null);
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
    audioQueueRef.current?.flushAudio();
    wsClientRef.current?.disconnect();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    resetSession();
    navigate('/');
  };

  if (!role) return null;

  // Find index of last user message for "Take 2" button
  const lastUserMsgIndex = messages.map(m => m.sender).lastIndexOf('user');

  return (
    <div className="h-screen flex flex-col md:flex-row p-4 md:p-8 max-w-[1600px] mx-auto gap-6 overflow-hidden">
      
      {/* Left Sidebar - Persona Card with Avatar */}
      <motion.div 
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        className="w-full md:w-80 lg:w-96 flex flex-col gap-4"
      >
        <div className="flex items-center justify-between py-1">
          <button 
            onClick={handleExit}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-xs font-semibold py-1.5 w-fit"
          >
            <ArrowLeft size={16} /> Exit Practice
          </button>

          <button
            onClick={() => navigate('/history')}
            className="text-slate-400 hover:text-white transition-colors text-xs font-semibold py-1.5"
          >
            History
          </button>
        </div>

        <div className="glass-card rounded-2xl p-6 flex-1 overflow-y-auto flex flex-col">
          <div className="flex flex-col items-center text-center mb-6 pt-0 w-full">
            <RobotAvatar state={avatarState} speechText={currentSpeechText} />
            
            <h2 className="text-xl font-bold mt-4 text-white">{role.name}</h2>
            <span className="text-xs px-3 py-1 bg-purple-500/10 border border-purple-500/30 text-purple-300 rounded-full font-medium mt-1">
              {role.description}
            </span>
          </div>

          <div className="space-y-4 text-sm flex-1">
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl space-y-1">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Persona Archetype</span>
              <p className="text-xs text-slate-300 font-medium">
                {role.traits ? role.traits.join(" • ") : "Executive Counterpart"}
              </p>
            </div>

            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl space-y-1">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Meeting Directives</span>
              <p className="text-xs text-slate-300 leading-relaxed">
                Evaluates clarity, evidence, and ROI. Low tolerance for vague or evasive statements.
              </p>
            </div>
          </div>

          {/* Audio & Status controls */}
          <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between">
            <button
              type="button"
              onClick={() => {
                const next = !isAudioEnabled;
                setIsAudioEnabled(next);
                if (!next) {
                  audioQueueRef.current?.flushAudio();
                  if (window.speechSynthesis) {
                    window.speechSynthesis.cancel();
                  }
                  setAvatarState('idle');
                }
              }}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors"
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

      {/* Right Side - Chat Interface */}
      <motion.div 
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        className="flex-1 flex flex-col glass-card rounded-2xl overflow-hidden border border-slate-800"
      >
        {/* Chat Header Bar */}
        <div className="px-6 py-3 border-b border-slate-800 bg-slate-950/60 backdrop-blur-xs flex items-center justify-between z-10 flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Live Roleplay Practice
            </span>
            <AnimatePresence>
              {bargeInNotice.visible && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9, x: -10 }}
                  animate={{ opacity: 1, scale: 1, x: 0 }}
                  exit={{ opacity: 0, scale: 0.9, x: -10 }}
                  className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[11px] font-semibold"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                  <span>Barge-in • Audio Flushed (#{bargeInNotice.count})</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Priority P0: End & Evaluate Button */}
            <button
              type="button"
              onClick={handleConclude}
              disabled={concludeLoading || loading}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-sm cursor-pointer"
            >
              {concludeLoading ? <Loader2 size={14} className="animate-spin" /> : <Trophy size={14} />}
              <span>End & Evaluate</span>
            </button>

            {/* Live Variable Inspector Button */}
            <button
              type="button"
              onClick={() => setIsInspectorOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 text-xs font-semibold transition-all cursor-pointer"
            >
              <Activity size={14} className="text-indigo-400 animate-pulse" />
              <span>Inspector</span>
            </button>
          </div>
        </div>

        {/* Messages Stream */}
        <div className="flex-1 p-6 overflow-y-auto flex flex-col gap-5">
          
          {/* Priority P0: Early Termination Banner */}
          {isTerminated && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="p-4 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-rose-200 text-xs flex items-center justify-between gap-4 shadow-lg shadow-rose-950/20"
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
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shrink-0 transition-colors shadow-sm"
              >
                View Coaching Report
              </button>
            </motion.div>
          )}

          {messages.map((msg, index) => {
            const isUser = msg.sender === 'user';
            const isLatestUserMsg = isUser && index === lastUserMsgIndex;

            return (
              <div 
                key={msg.id} 
                className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`flex max-w-[85%] gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                  {msg.sender === 'ai' && (
                    <div className="w-8 h-8 rounded-full bg-slate-800 flex-shrink-0 flex items-center justify-center border border-slate-700 mt-1 text-slate-300">
                      <User size={14} />
                    </div>
                  )}
                  
                  <div className="flex flex-col items-end">
                    <div 
                      className={`p-4 rounded-2xl text-xs md:text-sm leading-relaxed ${
                        isUser 
                          ? 'bg-purple-600 text-white rounded-tr-none' 
                          : 'bg-slate-800/80 border border-slate-700/60 text-slate-200 rounded-tl-none'
                      }`}
                    >
                      {msg.sender === 'ai' ? (
                        <div className="[&>p]:mb-2 [&>p:last-child]:mb-0 [&_strong]:font-semibold [&_strong]:text-purple-400">
                          <ReactMarkdown>{msg.text}</ReactMarkdown>
                          {msg.text.includes("### 📊 Interview Complete") && (
                            <button
                              onClick={handleConclude}
                              className="mt-4 flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-xl hover:bg-purple-500 transition-colors text-xs font-bold"
                            >
                              <Trophy size={14} /> View Scorecard & Report
                            </button>
                          )}
                        </div>
                      ) : (
                        msg.text
                      )}
                    </div>

                    {/* Priority P1: "Take 2" (Rewind Turn) on latest user turn */}
                    {isLatestUserMsg && !loading && (
                      <button
                        onClick={handleRewind}
                        disabled={rewindLoading}
                        title="Undo this turn and try a different answer"
                        className="mt-1.5 inline-flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800 px-2.5 py-1 rounded-lg border border-slate-700/60 transition-colors cursor-pointer"
                      >
                        <RotateCcw size={11} className={rewindLoading ? "animate-spin text-purple-400" : ""} />
                        <span>Take 2 (Rewind)</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          
          <div ref={messagesEndRef} />
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
        <div className="p-4 border-t border-slate-800 bg-slate-950/80">
          <form onSubmit={handleSend} className="relative flex items-center gap-2 max-w-4xl mx-auto">
            
            {/* Priority P1: Ask Coach for Hint */}
            <button
              type="button"
              onClick={handleFetchHint}
              disabled={hintLoading || loading}
              title="Get a real-time tactical hint for this turn"
              className="p-3 rounded-full flex-shrink-0 bg-slate-900 border border-slate-800 hover:border-purple-500/50 hover:bg-purple-950/30 text-purple-400 transition-colors cursor-pointer"
            >
              {hintLoading ? <Loader2 size={18} className="animate-spin text-purple-400" /> : <Lightbulb size={18} />}
            </button>

            {/* Voice Dictation Toggle */}
            <button
              type="button"
              onClick={toggleListening}
              className={`p-3 rounded-full flex-shrink-0 transition-colors cursor-pointer ${
                isListening 
                  ? 'bg-rose-500 text-white animate-pulse' 
                  : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white hover:bg-slate-800'
              }`}
            >
              {isListening ? <Mic size={18} /> : <MicOff size={18} />}
            </button>
            
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={isListening ? "Listening to your voice..." : "Type your answer or proposal..."}
              className="flex-1 bg-slate-900 border border-slate-800 rounded-full px-5 py-3.5 pr-12 text-xs md:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 transition-colors"
              disabled={loading || isTerminated}
            />
            
            <button
              type="submit"
              disabled={!input.trim() || loading || isTerminated}
              className="absolute right-2 p-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:bg-slate-800 text-white rounded-full transition-colors flex items-center justify-center cursor-pointer"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </button>
          </form>
        </div>
      </motion.div>

      {/* Live Variable Inspector Panel */}
      <LiveVariableInspector
        sessionId={sessionId}
        isOpen={isInspectorOpen}
        onClose={() => setIsInspectorOpen(false)}
        lastTurnTrigger={turnTrigger}
      />

      {/* Priority P0: Structured Coaching Scorecard Modal */}
      <FeedbackReportModal
        isOpen={isReportOpen}
        onClose={() => setIsReportOpen(false)}
        sessionId={sessionId || coachingReport?.session_id}
        report={coachingReport}
        onRestart={() => navigate('/scenario')}
      />
    </div>
  );
};

export default ConversationScreen;

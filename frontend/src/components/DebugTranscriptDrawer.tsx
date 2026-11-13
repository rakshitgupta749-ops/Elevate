import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  FileText, 
  Copy, 
  Check, 
  Download, 
  Search, 
  X, 
  Pin, 
  PinOff, 
  Terminal, 
  User, 
  Bot, 
  ArrowDown, 
  Activity
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export interface DebugTranscriptMessage {
  id: string;
  sender: 'user' | 'ai';
  text: string;
}

interface DebugTranscriptDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  messages: DebugTranscriptMessage[];
  roleName?: string;
  sessionId?: string | null;
  isDocked?: boolean;
  onToggleDock?: () => void;
  isLoading?: boolean;
}

export const DebugTranscriptDrawer: React.FC<DebugTranscriptDrawerProps> = ({
  isOpen,
  onClose,
  messages,
  roleName = 'CEO',
  sessionId,
  isDocked = false,
  onToggleDock,
  isLoading = false,
}) => {
  const [copiedAll, setCopiedAll] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    if (autoScroll && isOpen) {
      scrollEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, autoScroll, isOpen]);

  // Turn and word statistics
  const stats = useMemo(() => {
    let candidateWords = 0;
    let aiWords = 0;
    let userTurns = 0;
    let aiTurns = 0;

    messages.forEach((m) => {
      const words = m.text.trim().split(/\s+/).filter(Boolean).length;
      if (m.sender === 'user') {
        candidateWords += words;
        userTurns += 1;
      } else {
        aiWords += words;
        aiTurns += 1;
      }
    });

    const totalWords = candidateWords + aiWords;
    const candidateRatio = totalWords > 0 ? Math.round((candidateWords / totalWords) * 100) : 50;

    return {
      totalTurns: messages.length,
      userTurns,
      aiTurns,
      candidateWords,
      aiWords,
      totalWords,
      candidateRatio,
    };
  }, [messages]);

  // Filter messages by search query
  const filteredMessages = useMemo(() => {
    if (!searchQuery.trim()) return messages;
    const q = searchQuery.toLowerCase();
    return messages.filter(
      (m) => m.text.toLowerCase().includes(q) || m.sender.toLowerCase().includes(q)
    );
  }, [messages, searchQuery]);

  // Copy whole transcript
  const handleCopyAll = () => {
    const transcriptText = messages
      .map((m, idx) => {
        const senderLabel = m.sender === 'user' ? 'Candidate (You)' : `AI Executive (${roleName})`;
        return `### Turn #${idx + 1} - ${senderLabel}\n${m.text}\n`;
      })
      .join('\n---\n\n');

    const header = `# Roleplay Session Transcript (Debug Export)\nSession ID: ${sessionId || 'N/A'}\nRole: ${roleName}\nTotal Turns: ${messages.length}\nDate: ${new Date().toISOString()}\n\n---\n\n`;

    navigator.clipboard.writeText(header + transcriptText);
    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 2000);
  };

  // Copy single message
  const handleCopyMessage = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  // Download transcript as text file
  const handleDownload = () => {
    const transcriptText = messages
      .map((m, idx) => {
        const senderLabel = m.sender === 'user' ? 'Candidate (You)' : `AI Executive (${roleName})`;
        return `[Turn ${idx + 1}] ${senderLabel}:\n${m.text}\n`;
      })
      .join('\n----------------------------------------\n\n');

    const content = `ROLEPLAY DEBUG TRANSCRIPT\nSession ID: ${sessionId || 'N/A'}\nRole: ${roleName}\nExported: ${new Date().toLocaleString()}\nCandidate Words: ${stats.candidateWords} | AI Words: ${stats.aiWords}\n\n========================================\n\n${transcriptText}`;

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `transcript-${sessionId || 'session'}-${Date.now()}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!isOpen) return null;

  const content = (
    <div className="flex flex-col h-full bg-slate-900 text-slate-100 border-l border-slate-800 shadow-2xl overflow-hidden">
      {/* Header Bar */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-xl bg-purple-600/20 border border-purple-500/40 text-purple-400 flex items-center justify-center shrink-0">
            <Terminal size={16} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-sm text-white tracking-tight truncate">
                Debug Transcript
              </h3>
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                LIVE
              </span>
            </div>
            <p className="text-[11px] text-slate-400 truncate">
              {stats.totalTurns} turns • {stats.totalWords} words total
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={handleCopyAll}
            title="Copy full transcript to clipboard"
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/80 text-xs font-semibold transition-colors cursor-pointer"
          >
            {copiedAll ? (
              <>
                <Check size={13} className="text-emerald-400" />
                <span className="text-emerald-300">Copied!</span>
              </>
            ) : (
              <>
                <Copy size={13} className="text-purple-400" />
                <span>Copy</span>
              </>
            )}
          </button>

          <button
            onClick={handleDownload}
            title="Download transcript as .txt file"
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/80 transition-colors cursor-pointer"
          >
            <Download size={14} className="text-indigo-400" />
          </button>

          {onToggleDock && (
            <button
              onClick={onToggleDock}
              title={isDocked ? "Float window" : "Pin/Dock to side"}
              className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                isDocked 
                  ? 'bg-purple-600/30 border-purple-500/50 text-purple-300' 
                  : 'bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border-slate-700/80'
              }`}
            >
              {isDocked ? <PinOff size={14} /> : <Pin size={14} />}
            </button>
          )}

          <button
            onClick={onClose}
            title="Close transcript drawer"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer ml-1"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Stats Quick Ribbon */}
      <div className="px-4 py-2 bg-slate-950/40 border-b border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400 shrink-0">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-sky-400" />
            <span>You: <strong className="text-slate-200">{stats.candidateWords}w</strong> ({stats.candidateRatio}%)</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-purple-400" />
            <span>AI: <strong className="text-slate-200">{stats.aiWords}w</strong></span>
          </span>
        </div>

        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium transition-colors cursor-pointer ${
            autoScroll ? 'text-purple-300 bg-purple-950/50' : 'text-slate-500 hover:text-slate-400'
          }`}
          title="Toggle auto-scroll to latest turn"
        >
          <ArrowDown size={11} className={autoScroll ? 'animate-bounce' : ''} />
          <span>Auto-scroll {autoScroll ? 'ON' : 'OFF'}</span>
        </button>
      </div>

      {/* Search Input Bar */}
      <div className="p-3 border-b border-slate-800/80 bg-slate-900/60 shrink-0">
        <div className="relative flex items-center">
          <Search size={14} className="absolute left-3 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search dialogue, keywords, or turns..."
            className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-9 pr-8 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 text-slate-500 hover:text-slate-300"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div 
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-3.5 scroll-smooth"
      >
        {filteredMessages.length === 0 ? (
          <div className="h-48 flex flex-col items-center justify-center text-center p-6 text-slate-500">
            <FileText size={28} className="mb-2 text-slate-600" />
            <p className="text-xs font-medium">
              {searchQuery ? `No dialogue matching "${searchQuery}"` : 'Transcript is currently empty'}
            </p>
            <p className="text-[11px] text-slate-600 mt-1">
              Turns will stream in real-time during the conversation
            </p>
          </div>
        ) : (
          filteredMessages.map((msg, index) => {
            const isUser = msg.sender === 'user';
            const wordCount = msg.text.trim().split(/\s+/).filter(Boolean).length;
            const turnNumber = index + 1;

            return (
              <motion.div
                key={msg.id || index}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className={`rounded-2xl border p-3.5 transition-all text-xs ${
                  isUser 
                    ? 'bg-sky-950/20 border-sky-800/40 text-slate-200' 
                    : 'bg-purple-950/20 border-purple-800/40 text-slate-200'
                }`}
              >
                {/* Message Header */}
                <div className="flex items-center justify-between gap-2 mb-2 pb-2 border-b border-slate-800/60">
                  <div className="flex items-center gap-2">
                    <span className="flex items-center justify-center w-5 h-5 rounded-md bg-slate-800/90 text-slate-400 font-mono text-[10px] font-bold">
                      #{turnNumber}
                    </span>
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-bold text-[10px] uppercase tracking-wider ${
                      isUser 
                        ? 'bg-sky-500/20 border border-sky-500/40 text-sky-300' 
                        : 'bg-purple-500/20 border border-purple-500/40 text-purple-300'
                    }`}>
                      {isUser ? <User size={10} /> : <Bot size={10} />}
                      <span>{isUser ? 'Candidate (You)' : `AI Executive (${roleName})`}</span>
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {wordCount} words
                    </span>
                  </div>

                  {/* Copy Individual Turn Button */}
                  <button
                    onClick={() => handleCopyMessage(msg.id || String(index), msg.text)}
                    title="Copy this turn to clipboard"
                    className="p-1 rounded-md text-slate-500 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
                  >
                    {copiedId === (msg.id || String(index)) ? (
                      <Check size={12} className="text-emerald-400" />
                    ) : (
                      <Copy size={12} />
                    )}
                  </button>
                </div>

                {/* Message Content */}
                <div className="leading-relaxed font-normal text-slate-200 whitespace-pre-wrap break-words">
                  {msg.sender === 'ai' ? (
                    <div className="[&>p]:mb-1.5 [&>p:last-child]:mb-0 [&_strong]:font-semibold [&_strong]:text-purple-300">
                      <ReactMarkdown>{msg.text}</ReactMarkdown>
                    </div>
                  ) : (
                    msg.text
                  )}
                </div>
              </motion.div>
            );
          })
        )}

        {/* Live Loading Indicator */}
        {isLoading && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-purple-950/30 border border-purple-500/30 text-xs text-purple-300 animate-pulse">
            <Activity size={14} className="animate-spin text-purple-400" />
            <span>AI Executive is thinking / formulating response...</span>
          </div>
        )}

        <div ref={scrollEndRef} />
      </div>

      {/* Footer Info */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/80 text-[11px] text-slate-400 flex items-center justify-between shrink-0 font-mono">
        <span className="truncate">
          Session: {sessionId ? `${sessionId.slice(0, 8)}...` : 'Local Practice'}
        </span>
        <span className="text-slate-400 shrink-0">
          Pressure Cooker Mode
        </span>
      </div>
    </div>
  );

  // If docked, render inline container; otherwise render as slide-over drawer
  if (isDocked) {
    return (
      <div className="w-80 lg:w-96 h-full flex flex-col shrink-0 border-l border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
        {content}
      </div>
    );
  }

  return (
    <AnimatePresence>
      <div 
        className="fixed inset-0 z-50 flex items-center justify-end bg-black/60 backdrop-blur-xs"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, x: 400 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 400 }}
          transition={{ type: 'spring', damping: 26, stiffness: 300 }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-lg md:max-w-xl h-full shadow-2xl flex flex-col overflow-hidden"
        >
          {content}
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default DebugTranscriptDrawer;

/**
 * InterviewWebSocketClient: Real-time duplex WebSocket manager for live roleplay interview.
 * Handles audio chunks, TTS stream playback sync, candidate speech, and barge-in flush control frames.
 */

export interface WebSocketAudioChunk {
  type: 'audio_chunk';
  audio: string;
  text?: string;
  duration_sec?: number;
  sample_rate?: number;
  format?: string;
  is_final?: boolean;
}

export interface WebSocketTextDelta {
  type: 'text_delta';
  delta: string;
}

export interface WebSocketTurnComplete {
  type: 'turn_complete';
  full_text: string;
  is_final?: boolean;
}

export interface WebSocketTranscript {
  type: 'transcript';
  text: string;
  role: 'user' | 'ai';
}

export interface WebSocketBargeInFlush {
  type: 'barge_in_flush';
  timestamp: number;
  interruption_count: number;
}

export interface WebSocketSessionTerminated {
  type: 'session_terminated';
  status: string;
  reason?: string;
}

export interface InterviewWebSocketHandlers {
  onAudioChunk?: (data: WebSocketAudioChunk) => void;
  onTextDelta?: (data: WebSocketTextDelta) => void;
  onTurnComplete?: (data: WebSocketTurnComplete) => void;
  onTranscript?: (data: WebSocketTranscript) => void;
  onBargeInFlush?: (data: WebSocketBargeInFlush) => void;
  onSessionTerminated?: (data: WebSocketSessionTerminated) => void;
  onError?: (err: any) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export class InterviewWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers: InterviewWebSocketHandlers;
  private isExplicitlyClosed: boolean = false;
  private pingInterval: any = null;

  constructor(sessionId: string, handlers: InterviewWebSocketHandlers) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname || 'localhost';
    const port = '8000';
    this.url = `${protocol}//${host}:${port}/api/ws/interview/${encodeURIComponent(sessionId)}`;
    this.handlers = handlers;
  }

  public connect(): void {
    this.isExplicitlyClosed = false;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.info(`[InterviewWebSocket] Connected to ${this.url}`);
        this.handlers.onOpen?.();
        // Start ping heartbeat
        this.pingInterval = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 15000);
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const type = data.type;

          if (type === 'audio_chunk') {
            this.handlers.onAudioChunk?.(data);
          } else if (type === 'text_delta') {
            this.handlers.onTextDelta?.(data);
          } else if (type === 'turn_complete') {
            this.handlers.onTurnComplete?.(data);
          } else if (type === 'transcript') {
            this.handlers.onTranscript?.(data);
          } else if (type === 'barge_in_flush') {
            console.warn(`[InterviewWebSocket] Control Frame: BARGE-IN FLUSH received! Count: ${data.interruption_count}`);
            this.handlers.onBargeInFlush?.(data);
          } else if (type === 'session_terminated') {
            this.handlers.onSessionTerminated?.(data);
          } else if (type === 'error') {
            console.error('[InterviewWebSocket] Server error frame:', data.error);
            this.handlers.onError?.(data.error);
          }
        } catch (e) {
          console.debug('[InterviewWebSocket] Non-JSON message received:', event.data);
        }
      };

      this.ws.onerror = (event) => {
        console.warn('[InterviewWebSocket] Error event:', event);
        this.handlers.onError?.(event);
      };

      this.ws.onclose = () => {
        console.info('[InterviewWebSocket] Connection closed');
        if (this.pingInterval) clearInterval(this.pingInterval);
        if (!this.isExplicitlyClosed) {
          this.handlers.onClose?.();
        }
      };
    } catch (e) {
      console.error('[InterviewWebSocket] Connection failed:', e);
      this.handlers.onError?.(e);
    }
  }

  public send(payload: object): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  public sendText(message: string): boolean {
    return this.send({ type: 'text', message });
  }

  public sendPlaybackStart(): boolean {
    return this.send({ type: 'playback_start' });
  }

  public sendPlaybackEnd(): boolean {
    return this.send({ type: 'playback_end' });
  }

  public sendBargeIn(): boolean {
    return this.send({ type: 'barge_in' });
  }

  public sendSpeechStart(): boolean {
    return this.send({ type: 'user_speech_start' });
  }

  public isConnected(): boolean {
    return !!this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  public disconnect(): void {
    this.isExplicitlyClosed = true;
    if (this.pingInterval) clearInterval(this.pingInterval);
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

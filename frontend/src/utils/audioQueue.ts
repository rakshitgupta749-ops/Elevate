/**
 * AudioQueue: Manages Web Audio API sequential playback and instant flush for barge-in interruptions.
 */

export interface QueuedAudioChunk {
  id: string;
  audioBase64: string;
  durationSec?: number;
  text?: string;
}

export type AvatarStateCallback = (state: 'idle' | 'speaking' | 'listening') => void;

export class AudioQueue {
  private audioContext: AudioContext | null = null;
  private queue: QueuedAudioChunk[] = [];
  private currentSource: AudioBufferSourceNode | null = null;
  private isPlaying: boolean = false;
  private isProcessingQueue: boolean = false;

  public onPlaybackStart?: (chunk: QueuedAudioChunk) => void;
  public onPlaybackEnd?: () => void;
  public onFlush?: (interruptionCount?: number) => void;
  public onAvatarStateChange?: AvatarStateCallback;

  constructor() {
    // AudioContext will be initialized on first user interaction to comply with browser autoplay policies
  }

  private getAudioContext(): AudioContext {
    if (!this.audioContext || this.audioContext.state === 'closed') {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      this.audioContext = new AudioCtx();
    }
    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume().catch(() => {});
    }
    return this.audioContext;
  }

  /**
   * Enqueue a base64 encoded audio chunk (e.g. WAV from Kokoro TTS).
   */
  public async enqueue(chunk: QueuedAudioChunk): Promise<void> {
    this.queue.push(chunk);
    if (!this.isPlaying && !this.isProcessingQueue) {
      this.playNext();
    }
  }

  private async playNext(): Promise<void> {
    if (this.queue.length === 0) {
      this.isPlaying = false;
      this.currentSource = null;
      this.onPlaybackEnd?.();
      this.onAvatarStateChange?.('idle');
      return;
    }

    this.isProcessingQueue = true;
    const chunk = this.queue.shift()!;

    try {
      const ctx = this.getAudioContext();
      const binaryString = window.atob(chunk.audioBase64);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // decodeAudioData requires a fresh copy of buffer
      const audioBuffer = await ctx.decodeAudioData(bytes.buffer.slice(0));

      // If flushed while decoding
      if (!this.isProcessingQueue && this.queue.length === 0 && !this.isPlaying) {
        return;
      }

      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);
      this.currentSource = source;
      this.isPlaying = true;

      this.onPlaybackStart?.(chunk);
      this.onAvatarStateChange?.('speaking');

      source.onended = () => {
        if (this.currentSource === source) {
          this.currentSource = null;
          this.playNext();
        }
      };

      source.start(0);
    } catch (err) {
      console.error('[AudioQueue] Error decoding or playing audio chunk:', err);
      // Continue to next chunk if one fails
      this.currentSource = null;
      this.playNext();
    } finally {
      this.isProcessingQueue = false;
    }
  }

  /**
   * Immediately stops audio playback, cancels current Web Audio node,
   * flushes all queued chunks, and cancels any speech synthesis.
   */
  public flushAudio(interruptionCount?: number): boolean {
    const wasActive = this.isPlaying || this.queue.length > 0 || (typeof window !== 'undefined' && !!window.speechSynthesis?.speaking);

    // 1. Clear upcoming queue
    this.queue = [];
    this.isProcessingQueue = false;

    // 2. Stop current playing node immediately
    if (this.currentSource) {
      try {
        this.currentSource.onended = null;
        this.currentSource.stop(0);
        this.currentSource.disconnect();
      } catch (e) {
        // Node may have already ended
      }
      this.currentSource = null;
    }

    this.isPlaying = false;

    // 3. Cancel browser SpeechSynthesis fallback if active
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    // 4. Fire callbacks
    this.onFlush?.(interruptionCount);
    this.onAvatarStateChange?.('listening');

    console.info(`[AudioQueue] Audio buffer flushed (wasActive=${wasActive}, interruptionCount=${interruptionCount ?? 'N/A'})`);
    return wasActive;
  }

  /**
   * Check if audio is currently playing or queued.
   */
  public isAudioActive(): boolean {
    const isSpeechActive = typeof window !== 'undefined' && !!window.speechSynthesis?.speaking;
    return this.isPlaying || this.queue.length > 0 || isSpeechActive;
  }

  /**
   * Cleanup and close audio context.
   */
  public close(): void {
    this.flushAudio();
    if (this.audioContext && this.audioContext.state !== 'closed') {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }
  }
}

export const globalAudioQueue = new AudioQueue();

/**
 * AudioQueue: Manages Web Audio API pre-decoded, gapless sequential playback
 * and instant flush for barge-in interruptions.
 */

export interface QueuedAudioChunk {
  id: string;
  audioBase64: string;
  durationSec?: number;
  text?: string;
  isFinal?: boolean;
}

interface DecodedAudioItem {
  id: string;
  buffer: AudioBuffer;
  durationSec: number;
  text?: string;
  isFinal?: boolean;
}

export type AvatarStateCallback = (state: 'idle' | 'speaking' | 'listening') => void;

let sharedAudioContext: AudioContext | null = null;

export function getSharedAudioContext(): AudioContext {
  if (typeof window === 'undefined') return null as any;
  if (!sharedAudioContext || sharedAudioContext.state === 'closed') {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    sharedAudioContext = new AudioCtx();
  }
  if (sharedAudioContext.state === 'suspended') {
    sharedAudioContext.resume().catch(() => {});
  }
  return sharedAudioContext;
}

export function warmUpAudioContext(): void {
  try {
    const ctx = getSharedAudioContext();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
  } catch {
    // Non-blocking
  }
}

// User-gesture auto-unlock for modern browser autoplay restrictions
if (typeof window !== 'undefined') {
  const unlock = () => {
    warmUpAudioContext();
    window.removeEventListener('click', unlock);
    window.removeEventListener('keydown', unlock);
    window.removeEventListener('touchstart', unlock);
    window.removeEventListener('pointerdown', unlock);
  };
  window.addEventListener('click', unlock, { passive: true });
  window.addEventListener('keydown', unlock, { passive: true });
  window.addEventListener('touchstart', unlock, { passive: true });
  window.addEventListener('pointerdown', unlock, { passive: true });
}

export class AudioQueue {
  private audioContext: AudioContext | null = null;
  private analyserNode: AnalyserNode | null = null;
  private frequencyData: Uint8Array | null = null;
  private animationFrameId: number | null = null;

  // Queues & scheduling
  private rawQueue: QueuedAudioChunk[] = [];
  private isDecoding: boolean = false;
  private activeSources: Set<AudioBufferSourceNode> = new Set();
  private nextScheduleTime: number = 0;

  // Turn state & barge-in generation tracking
  private isPlaying: boolean = false;
  private isTurnActive: boolean = false;
  private turnCompleteReceived: boolean = false;
  private holdTimer: any = null;
  private flushGeneration: number = 0;

  public onPlaybackStart?: (chunk: QueuedAudioChunk) => void;
  public onPlaybackEnd?: () => void;
  public onFlush?: (interruptionCount?: number) => void;
  public onAvatarStateChange?: AvatarStateCallback;
  public onVolumeChange?: (level: number) => void;

  constructor() {
    // AudioContext will be lazily acquired and unlocked via getSharedAudioContext()
  }

  /**
   * Signal the start of an AI conversational turn. Prevents premature
   * transition to idle/listening if the queue temporarily empties between sentences.
   */
  public startTurn(): void {
    if (this.holdTimer) {
      clearTimeout(this.holdTimer);
      this.holdTimer = null;
    }
    this.isTurnActive = true;
    this.turnCompleteReceived = false;
    this.resume().catch(() => {});
  }

  /**
   * Signal that the server has completed generating and transmitting all chunks
   * for this turn.
   */
  public notifyTurnComplete(): void {
    this.turnCompleteReceived = true;
    // If playback already ended and no chunks remain in queue or currently decoding, finalize turn end immediately
    if (
      !this.isPlaying &&
      this.activeSources.size === 0 &&
      this.rawQueue.length === 0 &&
      !this.isDecoding
    ) {
      this.finalizePlaybackEnd();
    }
  }

  public isTurnInProgress(): boolean {
    return (
      this.isTurnActive ||
      this.isPlaying ||
      this.activeSources.size > 0 ||
      this.rawQueue.length > 0 ||
      this.isDecoding
    );
  }

  public getAudioContext(): AudioContext {
    this.audioContext = getSharedAudioContext();
    if (!this.analyserNode || this.analyserNode.context !== this.audioContext) {
      this.analyserNode = this.audioContext.createAnalyser();
      this.analyserNode.fftSize = 256;
      this.analyserNode.smoothingTimeConstant = 0.88;
      this.analyserNode.connect(this.audioContext.destination);
      this.frequencyData = new Uint8Array(this.analyserNode.frequencyBinCount);
    }
    return this.audioContext;
  }

  public async resume(): Promise<void> {
    const ctx = this.getAudioContext();
    if (ctx && ctx.state === 'suspended') {
      await ctx.resume().catch(() => {});
    }
  }

  /**
   * Enqueue an audio chunk (base64 WAV). Immediately starts asynchronous
   * pre-decoding so the next chunk is ready in memory ahead of playback.
   */
  public async enqueue(chunk: QueuedAudioChunk): Promise<void> {
    if (this.holdTimer) {
      clearTimeout(this.holdTimer);
      this.holdTimer = null;
    }
    this.isTurnActive = true;
    (chunk as any).generation = this.flushGeneration;
    this.rawQueue.push(chunk);
    this.resume().catch(() => {});
    this.processDecodeQueue();
  }

  /**
   * Worker loop that decodes base64 chunks into AudioBuffers immediately upon arrival.
   */
  private async processDecodeQueue(): Promise<void> {
    if (this.isDecoding || this.rawQueue.length === 0) return;
    this.isDecoding = true;

    while (this.rawQueue.length > 0) {
      const chunk = this.rawQueue.shift()!;
      const chunkGen = (chunk as any).generation ?? this.flushGeneration;
      try {
        const ctx = this.getAudioContext();
        const binaryString = window.atob(chunk.audioBase64);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }

        const audioBuffer = await ctx.decodeAudioData(bytes.buffer.slice(0));

        // If turn was explicitly flushed by barge-in while decodeAudioData was awaiting, discard
        if (chunkGen !== this.flushGeneration) {
          console.debug('[AudioQueue] Discarding decoded chunk due to intervening barge-in flush');
          continue;
        }

        const decodedItem: DecodedAudioItem = {
          id: chunk.id,
          buffer: audioBuffer,
          durationSec: audioBuffer.duration,
          text: chunk.text,
          isFinal: chunk.isFinal,
        };

        this.scheduleDecodedBuffer(decodedItem);
      } catch (err) {
        console.error('[AudioQueue] Error decoding audio chunk:', err);
      }
    }

    this.isDecoding = false;

    // Check if turn was marked complete while decoding and nothing scheduled to play
    if (this.turnCompleteReceived && this.activeSources.size === 0 && this.rawQueue.length === 0 && !this.isPlaying) {
      this.finalizePlaybackEnd();
    }
  }

  /**
   * Schedules a pre-decoded AudioBuffer with sample-accurate Web Audio timing.
   * If an earlier chunk is still playing, chains this chunk to start exactly
   * at nextScheduleTime, eliminating all inter-chunk dead air and pauses.
   */
  private scheduleDecodedBuffer(item: DecodedAudioItem): void {
    const ctx = this.getAudioContext();
    const now = ctx.currentTime;

    // Timeline alignment:
    // If nextScheduleTime has already passed (e.g. first chunk or true buffer underrun),
    // anchor immediately with a tiny 20ms safety margin.
    // If nextScheduleTime is in the future, stitch seamlessly at nextScheduleTime (0ms gap).
    const startTime = Math.max(now + 0.02, this.nextScheduleTime);
    this.nextScheduleTime = startTime + item.buffer.duration;

    const source = ctx.createBufferSource();
    source.buffer = item.buffer;

    if (this.analyserNode) {
      source.connect(this.analyserNode);
    } else {
      source.connect(ctx.destination);
    }

    this.activeSources.add(source);

    if (!this.isPlaying) {
      this.isPlaying = true;
      this.startVolumeMonitoring();
      this.onPlaybackStart?.({
        id: item.id,
        audioBase64: '',
        text: item.text,
        durationSec: item.durationSec,
        isFinal: item.isFinal,
      });
      this.onAvatarStateChange?.('speaking');
    }

    source.onended = () => {
      this.activeSources.delete(source);
      try {
        source.disconnect();
      } catch {
        // ignore disconnect errors
      }

      // Check if all currently scheduled audio has finished
      if (this.activeSources.size === 0 && this.rawQueue.length === 0 && !this.isDecoding) {
        this.handlePlaybackQueueExhausted();
      }
    };

    source.start(startTime);
  }

  private handlePlaybackQueueExhausted(): void {
    const ctx = this.getAudioContext();
    if (this.activeSources.size === 0) {
      this.nextScheduleTime = ctx.currentTime;
    }

    // If server officially marked turn complete, end turn cleanly
    if (this.turnCompleteReceived || !this.isTurnActive) {
      this.finalizePlaybackEnd();
      return;
    }

    // Turn is still active on the server (subsequent sentences are still generating/synthesizing).
    // Maintain composed speaking state and do NOT prematurely end turn or switch to listening.
    // Use a 25-second failsafe safety timeout in case the server connection abruptly hung without turn_complete.
    if (!this.holdTimer) {
      this.holdTimer = setTimeout(() => {
        if (this.activeSources.size === 0 && this.rawQueue.length === 0 && !this.isDecoding) {
          console.debug('[AudioQueue] Turn hold safety timeout (25s) expired without subsequent chunk; ending turn.');
          this.finalizePlaybackEnd();
        }
      }, 25000);
    }
  }

  private startVolumeMonitoring(): void {
    if (this.animationFrameId !== null) return;

    const monitor = () => {
      if (!this.isPlaying || !this.analyserNode || !this.frequencyData) {
        this.stopVolumeMonitoring();
        return;
      }

      this.analyserNode.getByteFrequencyData(this.frequencyData as any);

      // Focus on speech frequencies (~150Hz - 4200Hz)
      const binCount = Math.min(this.frequencyData.length, 48);
      let sum = 0;
      let peak = 0;
      for (let i = 1; i < binCount; i++) {
        const val = this.frequencyData[i];
        sum += val;
        if (val > peak) peak = val;
      }
      const avg = sum / (binCount - 1);
      const voiceEnergy = (avg * 0.65 + peak * 0.35);
      const normalized = Math.min(1, Math.max(0, (voiceEnergy - 6) / 38));
      this.onVolumeChange?.(normalized);

      this.animationFrameId = requestAnimationFrame(monitor);
    };

    this.animationFrameId = requestAnimationFrame(monitor);
  }

  private stopVolumeMonitoring(): void {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
    this.onVolumeChange?.(0);
  }

  private finalizePlaybackEnd(): void {
    if (this.holdTimer) {
      clearTimeout(this.holdTimer);
      this.holdTimer = null;
    }
    this.isPlaying = false;
    this.isTurnActive = false;
    this.turnCompleteReceived = false;
    this.stopVolumeMonitoring();
    this.onPlaybackEnd?.();
    this.onAvatarStateChange?.('idle');
  }

  /**
   * Immediately stops audio playback, cancels current Web Audio nodes,
   * flushes all queued chunks, and cancels any speech synthesis.
   */
  public flushAudio(interruptionCount?: number): boolean {
    const wasActive = this.isPlaying || this.activeSources.size > 0 || this.rawQueue.length > 0 || this.isTurnActive || (typeof window !== 'undefined' && !!window.speechSynthesis?.speaking);

    // Bump flush generation so any in-flight decodeAudioData promises are discarded
    this.flushGeneration++;

    if (this.holdTimer) {
      clearTimeout(this.holdTimer);
      this.holdTimer = null;
    }
    this.isTurnActive = false;
    this.turnCompleteReceived = false;
    this.stopVolumeMonitoring();

    // 1. Clear raw queue
    this.rawQueue = [];

    // 2. Stop and disconnect all active & scheduled Web Audio sources immediately
    for (const source of this.activeSources) {
      try {
        source.onended = null;
        source.stop(0);
        source.disconnect();
      } catch {
        // ignore stop/disconnect errors
      }
    }
    this.activeSources.clear();

    if (this.audioContext) {
      this.nextScheduleTime = this.audioContext.currentTime;
    } else {
      this.nextScheduleTime = 0;
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
    return this.isPlaying || this.activeSources.size > 0 || this.rawQueue.length > 0 || isSpeechActive;
  }

  /**
   * Cleanup and reset audio nodes.
   */
  public close(): void {
    this.stopVolumeMonitoring();
    this.flushAudio();
    if (this.analyserNode) {
      try {
        this.analyserNode.disconnect();
      } catch {
        // ignore disconnect errors
      }
      this.analyserNode = null;
    }
    this.audioContext = null;
  }
}

export const globalAudioQueue = new AudioQueue();

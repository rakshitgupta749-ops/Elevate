import axios from 'axios';

const API_BASE_URL = '/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getTopics = async () => {
  const response = await apiClient.get('/topics');
  return response.data;
};

export const getRoles = async () => {
  const response = await apiClient.get('/roles');
  return response.data;
};

export const getPersonaConfigurationSchema = async (role: string) => {
  const response = await apiClient.get(`/personas/configuration-schema/${encodeURIComponent(role)}`);
  return response.data;
};

export const createSession = async (payload: {
  topic?: string;
  role: string;
  scenario: string;
  experience: string;
  style: string;
  voice?: string;
  voice_id?: string;
  admin_configuration_id?: string;
  persona_configuration?: {
    role: string;
    preset?: string;
    traits: Record<string, number>;
    persona_schema_version?: string;
  };
}) => {
  const response = await apiClient.post('/session', payload);
  return response.data;
};

export const speakVoiceText = async (text: string, voiceId: string = 'am_onyx', sessionId?: string | null) => {
  const response = await apiClient.post('/voice/speak', {
    text,
    voice: voiceId,
    session_id: sessionId || undefined,
  });
  return response.data;
};

export const transcribeVoiceAudio = async (audioBase64: string, mimeType?: string): Promise<{ text: string; empty: boolean }> => {
  const response = await apiClient.post('/voice/transcribe', {
    audio_base64: audioBase64,
    mime_type: mimeType || undefined,
  });
  return response.data;
};

export const chatWithAgent = async (sessionId: string, message: string) => {
  const response = await apiClient.post('/chat', { session_id: sessionId, message });
  return response.data;
};

export const streamChatWithAgent = (
  sessionId: string, 
  message: string, 
  onChunk: (chunk: string) => void,
  onFinish: () => void,
  onError: (err: any) => void
) => {
  const controller = new AbortController();

  fetch(`${API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: sessionId,
      message,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No readable response body stream");
      }
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;
          const dataStr = trimmed.slice(5).trim();
          if (dataStr === '[DONE]') {
            onFinish();
            return;
          }
          try {
            const data = JSON.parse(dataStr);
            if (data.error) {
              onError(data.error);
              return;
            }
            if (data.chunk) {
              onChunk(data.chunk);
            }
          } catch {
            // ignore partial json
          }
        }
      }
      onFinish();
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err);
      }
    });

  return {
    close: () => controller.abort(),
  };
};

export const getSessionOpening = async (sessionId: string) => {
  const response = await apiClient.get(`/session/${encodeURIComponent(sessionId)}/opening`);
  return response.data;
};

export const streamOpeningWithAgent = (
  sessionId: string,
  onChunk: (chunk: string) => void,
  onFinish: () => void,
  onError: (err: any) => void
) => {
  const url = `${API_BASE_URL}/chat/stream/opening?session_id=${encodeURIComponent(sessionId)}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    if (event.data === '[DONE]') {
      eventSource.close();
      onFinish();
      return;
    }

    try {
      const data = JSON.parse(event.data);
      if (data.error) {
        onError(data.error);
        eventSource.close();
      } else if (data.chunk) {
        onChunk(data.chunk);
      }
    } catch (e) {
      console.error("Error parsing SSE data", e);
    }
  };

  eventSource.onerror = (err) => {
    eventSource.close();
    onError(err);
  };

  return eventSource;
};

export const getSessionLiveState = async (sessionId: string) => {
  const response = await apiClient.get(`/session/${encodeURIComponent(sessionId)}/live-state`);
  return response.data;
};

export const concludeSession = async (sessionId: string) => {
  const response = await apiClient.post(`/session/${encodeURIComponent(sessionId)}/conclude`);
  return response.data;
};

export const rewindTurn = async (sessionId: string) => {
  const response = await apiClient.post(`/session/${encodeURIComponent(sessionId)}/rewind`);
  return response.data;
};

export const getCoachingHint = async (sessionId: string) => {
  const response = await apiClient.post(`/session/${encodeURIComponent(sessionId)}/hint`);
  return response.data;
};

export const listSessions = async (limit: number = 50) => {
  const response = await apiClient.get(`/sessions?limit=${limit}`);
  return response.data;
};

export const getSessionTranscript = async (sessionId: string) => {
  const response = await apiClient.get(`/session/${encodeURIComponent(sessionId)}/transcript`);
  return response.data;
};

export const getCoachingReport = async (sessionId: string) => {
  const response = await apiClient.get(`/session/${encodeURIComponent(sessionId)}/coaching-report`);
  return response.data;
};

export interface DeliveryScorecardData {
  talk_listen_ratio: number;
  talk_ratio_verdict: 'Balanced' | 'Pitch Slapping' | 'Under-engaging';
  avg_response_latency_sec: number;
  latency_verdict: 'Crisp' | 'Hesitant' | 'Abrupt';
  average_wpm: number;
  pace_verdict: 'Optimal' | 'Rushing' | 'Slow';
  interruption_count: number;
}

export interface StrategicScorecardData {
  discovery_score: number;
  objection_handling_score: number;
  value_proposition_score: number;
  strengths: string[];
  critical_misses: string[];
  key_coaching_quote: string;
}

export interface SalesInterviewScorecardData {
  session_id: string;
  timestamp: string;
  delivery_scorecard: DeliveryScorecardData;
  strategic_scorecard: StrategicScorecardData;
  overall_readiness_score: number;
}

export const getSalesScorecard = async (sessionId: string): Promise<SalesInterviewScorecardData> => {
  const response = await apiClient.get(`/session/${encodeURIComponent(sessionId)}/scorecard`);
  return response.data;
};

export interface AdminRoleConfiguration {
  id?: string;
  role: string;
  title?: string;
  preset: string;
  traits: Record<string, number>;
  experience?: string;
  style?: string;
  voice?: string;
  conversation_overview?: string;
  custom_scenario?: string;
  scenario_title?: string;
  challenge_tags?: string[];
  created_at?: string;
  updated_at?: string;
}

export const getAllAdminConfigurations = async (): Promise<Record<string, AdminRoleConfiguration>> => {
  const response = await apiClient.get('/admin/configurations');
  return response.data;
};

export const getAdminRoleConfiguration = async (role: string): Promise<AdminRoleConfiguration> => {
  const response = await apiClient.get(`/admin/configurations/${encodeURIComponent(role)}`);
  return response.data;
};

export const saveAdminRoleConfiguration = async (data: AdminRoleConfiguration): Promise<AdminRoleConfiguration> => {
  const response = await apiClient.post('/admin/configurations', data);
  return response.data;
};

export const deleteAdminRoleConfiguration = async (role: string): Promise<{ success: boolean; role: string; message: string }> => {
  const response = await apiClient.delete(`/admin/configurations/${encodeURIComponent(role)}`);
  return response.data;
};

export const getAllAdminPersonas = async (): Promise<AdminRoleConfiguration[]> => {
  const response = await apiClient.get('/admin/personas');
  return response.data;
};

export const getAdminPersonasByRole = async (role: string): Promise<AdminRoleConfiguration[]> => {
  const response = await apiClient.get(`/admin/personas/by-role/${encodeURIComponent(role)}`);
  return response.data;
};

export const getAdminPersonaById = async (id: string): Promise<AdminRoleConfiguration> => {
  const response = await apiClient.get(`/admin/personas/${encodeURIComponent(id)}`);
  return response.data;
};

export const saveAdminPersona = async (data: AdminRoleConfiguration): Promise<AdminRoleConfiguration> => {
  const response = await apiClient.post('/admin/personas', data);
  return response.data;
};

export const deleteAdminPersona = async (id: string): Promise<{ success: boolean; id: string; message: string }> => {
  const response = await apiClient.delete(`/admin/personas/${encodeURIComponent(id)}`);
  return response.data;
};





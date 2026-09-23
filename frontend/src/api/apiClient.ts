import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

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
  topic: string;
  role: string;
  scenario: string;
  experience: string;
  style: string;
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
  const url = `${API_BASE_URL}/chat/stream?session_id=${encodeURIComponent(sessionId)}&message=${encodeURIComponent(message)}`;
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
  
  return eventSource; // Return it so we can close it if needed (e.g. unmount)
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



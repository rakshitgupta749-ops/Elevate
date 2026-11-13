import { create } from 'zustand';

export interface LearnerProfile {
  id: string;
  name: string;
  email: string;
  title: string;
  company?: string;
  avatarColor?: string;
  initials?: string;
  role?: 'admin' | 'learner';
}

const getInitialLearner = (): LearnerProfile | null => {
  if (typeof window === 'undefined') return null;
  try {
    const saved = localStorage.getItem('elevate_learner');
    if (saved) return JSON.parse(saved);
  } catch (e) {
    console.error('Failed to parse saved learner', e);
  }
  return null;
};


interface SessionState {
  learner: LearnerProfile | null;
  topic: any | null;
  role: any | null;
  scenario: string;
  experience: string;
  style: string;
  sessionId: string | null;
  initialMessage: string | null;
  initialAudio: string | null;
  selectedPreset: string;
  customTraits: Record<string, number>;
  voiceProfile: string;
  
  setLearner: (learner: LearnerProfile | null) => void;
  logout: () => void;
  setTopic: (topic: any) => void;
  setRole: (role: any) => void;
  setScenario: (scenario: string) => void;
  setExperience: (experience: string) => void;
  setStyle: (style: string) => void;
  setSessionId: (id: string) => void;
  setInitialMessage: (initialMessage: string | null) => void;
  setInitialAudio: (initialAudio: string | null) => void;
  setSelectedPreset: (preset: string) => void;
  setCustomTraits: (traits: Record<string, number>) => void;
  setCustomTrait: (traitId: string, value: number) => void;
  setVoiceProfile: (voice: string) => void;
  resetPersonaConfiguration: () => void;
  resetSession: () => void;
}

export const useStore = create<SessionState>((set) => ({
  learner: getInitialLearner(),
  topic: null,
  role: null,
  scenario: "",
  experience: "Intermediate",
  style: "Professional",
  sessionId: null,
  initialMessage: null,
  initialAudio: null,
  selectedPreset: "BALANCED",
  customTraits: {},
  voiceProfile: 'am_onyx',
  
  setLearner: (learner) => {
    if (typeof window !== 'undefined') {
      if (learner) {
        localStorage.setItem('elevate_learner', JSON.stringify(learner));
      } else {
        localStorage.removeItem('elevate_learner');
      }
    }
    set({ learner });
  },
  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('elevate_learner');
    }
    set({ learner: null });
  },
  setTopic: (topic) => set({ topic }),
  setRole: (role) => set({ role, selectedPreset: "BALANCED", customTraits: {} }),
  setScenario: (scenario) => set({ scenario }),
  setExperience: (experience) => set({ experience }),
  setStyle: (style) => set({ style }),
  setSessionId: (sessionId) => set({ sessionId }),
  setInitialMessage: (initialMessage) => set({ initialMessage }),
  setInitialAudio: (initialAudio) => set({ initialAudio }),
  setSelectedPreset: (selectedPreset) => set({ selectedPreset }),
  setCustomTraits: (customTraits) => set({ customTraits }),
  setCustomTrait: (traitId, value) =>
    set((state) => ({
      customTraits: { ...state.customTraits, [traitId]: value },
    })),
  setVoiceProfile: (voiceProfile) => set({ voiceProfile }),
  resetPersonaConfiguration: () => set({ selectedPreset: "BALANCED", customTraits: {} }),
  resetSession: () => set({
    topic: null,
    role: null,
    scenario: "",
    experience: "Intermediate",
    style: "Professional",
    sessionId: null,
    initialMessage: null,
    initialAudio: null,
    selectedPreset: "BALANCED",
    customTraits: {},
    voiceProfile: 'am_onyx',
  })
}));

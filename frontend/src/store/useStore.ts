import { create } from 'zustand';

interface SessionState {
  topic: any | null;
  role: any | null;
  scenario: string;
  experience: string;
  style: string;
  sessionId: string | null;
  initialMessage: string | null;
  selectedPreset: string;
  customTraits: Record<string, number>;
  
  setTopic: (topic: any) => void;
  setRole: (role: any) => void;
  setScenario: (scenario: string) => void;
  setExperience: (experience: string) => void;
  setStyle: (style: string) => void;
  setSessionId: (id: string) => void;
  setInitialMessage: (initialMessage: string | null) => void;
  setSelectedPreset: (preset: string) => void;
  setCustomTraits: (traits: Record<string, number>) => void;
  setCustomTrait: (traitId: string, value: number) => void;
  resetPersonaConfiguration: () => void;
  resetSession: () => void;
}

export const useStore = create<SessionState>((set) => ({
  topic: null,
  role: null,
  scenario: "",
  experience: "Intermediate",
  style: "Professional",
  sessionId: null,
  initialMessage: null,
  selectedPreset: "BALANCED",
  customTraits: {},
  
  setTopic: (topic) => set({ topic }),
  setRole: (role) => set({ role, selectedPreset: "BALANCED", customTraits: {} }),
  setScenario: (scenario) => set({ scenario }),
  setExperience: (experience) => set({ experience }),
  setStyle: (style) => set({ style }),
  setSessionId: (sessionId) => set({ sessionId }),
  setInitialMessage: (initialMessage) => set({ initialMessage }),
  setSelectedPreset: (selectedPreset) => set({ selectedPreset }),
  setCustomTraits: (customTraits) => set({ customTraits }),
  setCustomTrait: (traitId, value) =>
    set((state) => ({
      customTraits: { ...state.customTraits, [traitId]: value },
    })),
  resetPersonaConfiguration: () => set({ selectedPreset: "BALANCED", customTraits: {} }),
  resetSession: () => set({
    topic: null,
    role: null,
    scenario: "",
    experience: "Intermediate",
    style: "Professional",
    sessionId: null,
    initialMessage: null,
    selectedPreset: "BALANCED",
    customTraits: {},
  })
}));

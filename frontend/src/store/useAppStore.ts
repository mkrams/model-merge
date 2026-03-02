import { create } from 'zustand';
import type { ParsedModel, MergeAnalysis, MergedResult, ValidationResponse, AppStep } from '../types';

interface AppState {
  step: AppStep;
  modelA: ParsedModel | null;
  modelB: ParsedModel | null;
  mergeAnalysis: MergeAnalysis | null;
  decisions: Record<string, string>;
  mergedResult: MergedResult | null;
  validation: ValidationResponse | null;
  loading: boolean;
  error: string | null;

  setStep: (step: AppStep) => void;
  setModelA: (model: ParsedModel | null) => void;
  setModelB: (model: ParsedModel | null) => void;
  setMergeAnalysis: (analysis: MergeAnalysis | null) => void;
  setDecision: (conflictId: string, resolution: string) => void;
  setAllDecisions: (decisions: Record<string, string>) => void;
  setMergedResult: (result: MergedResult | null) => void;
  setValidation: (validation: ValidationResponse | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialState = {
  step: 'upload' as AppStep,
  modelA: null,
  modelB: null,
  mergeAnalysis: null,
  decisions: {} as Record<string, string>,
  mergedResult: null,
  validation: null,
  loading: false,
  error: null,
};

export const useAppStore = create<AppState>((set) => ({
  ...initialState,

  setStep: (step) => set({ step }),
  setModelA: (modelA) => set({ modelA }),
  setModelB: (modelB) => set({ modelB }),
  setMergeAnalysis: (mergeAnalysis) => set({ mergeAnalysis }),
  setDecision: (conflictId, resolution) =>
    set((state) => ({
      decisions: { ...state.decisions, [conflictId]: resolution },
    })),
  setAllDecisions: (decisions) => set({ decisions }),
  setMergedResult: (mergedResult) => set({ mergedResult }),
  setValidation: (validation) => set({ validation }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  reset: () => set(initialState),
}));

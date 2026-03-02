import axios from 'axios';
import type { ParsedModel, MergeAnalysis, MergedResult, ValidationResponse } from '../types';

// In production, VITE_API_URL points to the Railway backend.
// In dev, the Vite proxy forwards /api to localhost:8000.
const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api';

const client = axios.create({ baseURL: API_BASE });

export interface ConfigStatus {
  ai_validation: boolean;
  java_available: boolean;
  compiler_jar: boolean;
  validation_method: string;
}

export const api = {
  async uploadModel(file: File, modelType: string = 'auto'): Promise<ParsedModel> {
    const form = new FormData();
    form.append('file', file);
    form.append('model_type', modelType);
    const { data } = await client.post('/models/upload', form);
    return data;
  },

  async getModel(modelId: string): Promise<ParsedModel> {
    const { data } = await client.get(`/models/${modelId}`);
    return data;
  },

  async analyzeMerge(modelAId: string, modelBId: string): Promise<MergeAnalysis> {
    const { data } = await client.post('/merge/analyze', {
      model_a_id: modelAId,
      model_b_id: modelBId,
    });
    return data;
  },

  async applyMerge(
    mergeId: string,
    decisions: { conflict_id: string; resolution: string }[],
  ): Promise<MergedResult> {
    const { data } = await client.post('/merge/apply', {
      merge_id: mergeId,
      decisions,
    });
    return data;
  },

  async validateMerge(mergeId: string): Promise<ValidationResponse> {
    const { data } = await client.post(`/merge/${mergeId}/validate`);
    return data;
  },

  async downloadMerged(mergeId: string): Promise<string> {
    const { data } = await client.get(`/merge/${mergeId}/download`, {
      responseType: 'text',
    });
    return data;
  },

  async setApiKey(apiKey: string): Promise<void> {
    await client.post('/config/api-key', { api_key: apiKey });
  },

  async getConfigStatus(): Promise<ConfigStatus> {
    const { data } = await client.get('/config/status');
    return data;
  },
};

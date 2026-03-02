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

  async analyzeReqifAttributes(fileA: File, fileB: File): Promise<ReqIFMappingAnalysis> {
    const form = new FormData();
    form.append('file_a', fileA);
    form.append('file_b', fileB);
    const { data } = await client.post('/merge/reqif/analyze-attributes', form);
    return data;
  },
};

/* ── ReqIF Attribute Mapping Types ── */

export interface ReqIFAttr {
  id: string;
  name: string;
  datatype: string;
  datatype_kind: string;
  parent_type: string;
}

export interface ReqIFMapping {
  attr_a: ReqIFAttr;
  attr_b: ReqIFAttr | null;
  confidence: number;
  match_reason: string;
  compatible_types: boolean;
  status: string;
}

export interface ReqIFObjectType {
  id: string;
  name: string;
  attributes: ReqIFAttr[];
}

export interface ReqIFSchemaInfo {
  tool_name: string;
  datatypes: { id: string; name: string; kind: string; enum_values: string[] }[];
  object_types: ReqIFObjectType[];
  spec_object_count: number;
  spec_relation_count: number;
}

export interface ReqIFMappingAnalysis {
  schema_a: ReqIFSchemaInfo;
  schema_b: ReqIFSchemaInfo;
  mappings: ReqIFMapping[];
  unmapped_a: ReqIFAttr[];
  unmapped_b: ReqIFAttr[];
  stats: {
    total_attrs_a: number;
    total_attrs_b: number;
    mapped_count: number;
    unmapped_a_count: number;
    unmapped_b_count: number;
    exact_matches: number;
    fuzzy_matches: number;
    standard_matches: number;
    incompatible_types: number;
  };
}

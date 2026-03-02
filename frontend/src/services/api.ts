import axios from 'axios';
import type { ParsedModel, MergeAnalysis, MergedResult, ValidationResponse } from '../types';
import type {
  SafetyProject, SafetyItem, TraceLink, DraftResponse, GapInfo,
  CoverageMetrics, ItemType, LinkType, Perspective, TraceTree, TraceMatrix,
} from '../types/safety';

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

  async analyzeCoverage(file: File): Promise<CoverageAnalysis> {
    const form = new FormData();
    form.append('file', file);
    const { data } = await client.post('/analysis/coverage/upload', form);
    return data;
  },

  async analyzeReqifAttributes(fileA: File, fileB: File): Promise<ReqIFMappingAnalysis> {
    const form = new FormData();
    form.append('file_a', fileA);
    form.append('file_b', fileB);
    const { data } = await client.post('/merge/reqif/analyze-attributes', form);
    return data;
  },

  // ── Safety Traceability Graph API ──

  async importSafetyProject(file: File): Promise<SafetyProject> {
    const form = new FormData();
    form.append('file', file);
    const { data } = await client.post('/asil/import', form);
    return data;
  },

  // Backward compatibility alias
  async importSafetyChain(file: File): Promise<SafetyProject> {
    return this.importSafetyProject(file);
  },

  async getProject(projectId?: string): Promise<SafetyProject> {
    const { data } = await client.get('/asil/project', { params: { project_id: projectId || '' } });
    return data;
  },

  // Items CRUD
  async getItem(itemId: string): Promise<SafetyItem> {
    const { data } = await client.get(`/asil/item/${itemId}`);
    return data;
  },

  async createItem(itemData: {
    item_type: ItemType;
    name: string;
    description: string;
    attributes?: Record<string, any>;
  }): Promise<SafetyItem> {
    const { data } = await client.post('/asil/item', itemData);
    return data;
  },

  async updateItem(itemId: string, fields: Record<string, string>): Promise<SafetyItem> {
    const { data } = await client.put(`/asil/item/${itemId}`, fields);
    return data;
  },

  async deleteItem(itemId: string): Promise<{ status: string }> {
    const { data } = await client.delete(`/asil/item/${itemId}`);
    return data;
  },

  async approveItem(itemId: string): Promise<SafetyItem> {
    const { data } = await client.post(`/asil/item/${itemId}/approve`, { item_id: itemId });
    return data;
  },

  async revertItem(itemId: string, versionIdx: number): Promise<SafetyItem> {
    const { data } = await client.post(`/asil/item/${itemId}/revert`, { version_idx: versionIdx });
    return data;
  },

  // Links (traceability edges)
  async createLink(sourceId: string, targetId: string, linkType?: LinkType, rationale?: string): Promise<TraceLink> {
    const { data } = await client.post('/asil/link', {
      source_id: sourceId,
      target_id: targetId,
      link_type: linkType,
      rationale: rationale || '',
    });
    return data;
  },

  async deleteLink(linkId: string): Promise<{ status: string }> {
    const { data } = await client.delete(`/asil/link/${linkId}`);
    return data;
  },

  // AI-assisted drafting and revision
  async draftItem(itemId: string, feedback?: string): Promise<DraftResponse> {
    const { data } = await client.post(`/asil/item/${itemId}/draft`, { item_id: itemId, feedback: feedback || '' });
    return data;
  },

  async reviseItem(itemId: string, instruction: string): Promise<DraftResponse> {
    const { data } = await client.post(`/asil/item/${itemId}/revise`, { item_id: itemId, instruction });
    return data;
  },

  // ASIL determination
  async determineASIL(
    itemId: string,
    severity?: string,
    exposure?: string,
    controllability?: string,
  ): Promise<SafetyItem> {
    const { data } = await client.post('/asil/asil-determine', {
      item_id: itemId,
      severity: severity || '',
      exposure: exposure || '',
      controllability: controllability || '',
    });
    return data;
  },

  async getASILDefinitions(): Promise<any> {
    const { data } = await client.get('/asil/definitions');
    return data;
  },

  // Analysis and visualization
  async getGaps(): Promise<GapInfo[]> {
    const { data } = await client.get('/asil/gaps');
    return data;
  },

  async getCoverage(): Promise<CoverageMetrics> {
    const { data } = await client.get('/asil/coverage');
    return data;
  },

  async getPerspective(role: Perspective): Promise<SafetyItem[]> {
    const { data } = await client.get(`/asil/perspective/${role}`);
    return data;
  },

  async getTrace(itemId: string): Promise<TraceTree> {
    const { data } = await client.get(`/asil/trace/${itemId}`);
    return data;
  },

  async getMatrix(sourceType: ItemType, targetType: ItemType): Promise<TraceMatrix> {
    const { data } = await client.get(`/asil/matrix/${sourceType}/${targetType}`);
    return data;
  },

  // Export
  async exportReqIF(): Promise<string> {
    const { data } = await client.post('/asil/export/reqif', {}, { responseType: 'text' });
    return data;
  },

  // Save/Load
  async saveData(username: string, password: string): Promise<{ status: string }> {
    const { data } = await client.post('/asil/save', { username, password });
    return data;
  },

  async loadData(username: string, password: string): Promise<{ projects: any[]; count: number }> {
    const { data } = await client.post('/asil/load', { username, password });
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

/* ── Coverage Analysis Types ── */

export interface CoverageRequirement {
  id: string;
  name: string;
  req_id: string;
  doc: string;
  package: string;
  has_constraints: boolean;
  has_attributes: boolean;
  attr_count: number;
  constraint_count: number;
  is_orphan: boolean;
  has_verification: boolean;
  has_satisfaction: boolean;
  satisfied_by: string[];
  verified_by: string[];
  derived_from: string[];
  derives_to: string[];
  other_links: string[];
  coverage_status: string;
}

export interface ComplianceCheck {
  id: string;
  standard: string;
  title: string;
  passed: boolean;
  detail: string;
  severity: string;
}

export interface PackageCoverage {
  name: string;
  total_reqs: number;
  orphan_reqs: number;
  coverage_pct: number;
}

export interface CoverageAnalysis {
  summary: {
    total_requirements: number;
    total_elements: number;
    total_links: number;
    total_packages: number;
    forward_coverage: number;
    orphan_count: number;
    verified_count: number;
    satisfied_count: number;
    fully_traced_count: number;
    no_constraints_count: number;
    no_id_count: number;
    no_doc_count: number;
  };
  requirements: CoverageRequirement[];
  orphan_requirements: CoverageRequirement[];
  links: { source_id: string; source_name: string; source_type: string; target_ref: string; link_type: string }[];
  compliance_checks: ComplianceCheck[];
  package_coverage: PackageCoverage[];
}

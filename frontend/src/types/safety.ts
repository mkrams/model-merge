/* ── ASIL Assistant TypeScript Types ── */

export interface ItemVersion {
  version: number;
  text: string;
  name: string;
  author: string;
  timestamp: string;
  rationale: string;
}

export interface ASILDetermination {
  severity: string;
  severity_rationale: string;
  exposure: string;
  exposure_rationale: string;
  controllability: string;
  controllability_rationale: string;
  asil_level: string;
  approved: boolean;
}

export interface Hazard {
  id: string;
  name: string;
  description: string;
  failure_mode_ids: string[];
  status: string;
  approved: boolean;
  versions: ItemVersion[];
}

export interface HazardousEvent {
  id: string;
  hazard_id: string;
  name: string;
  description: string;
  operating_situation: string;
  status: string;
  approved: boolean;
  versions: ItemVersion[];
}

export interface SafetyGoal {
  id: string;
  hazard_id: string;
  name: string;
  description: string;
  asil_level: string;
  safe_state: string;
  status: string;
  approved: boolean;
  versions: ItemVersion[];
}

export interface FSR {
  id: string;
  safety_goal_id: string;
  name: string;
  description: string;
  testable_criterion: string;
  asil_level: string;
  status: string;
  approved: boolean;
  versions: ItemVersion[];
}

export interface TestCase {
  id: string;
  fsr_id: string;
  name: string;
  description: string;
  steps: string;
  expected_result: string;
  pass_criteria: string;
  status: string;
  approved: boolean;
  versions: ItemVersion[];
}

export interface FailureMode {
  id: string;
  name: string;
  description: string;
  hazard_ids: string[];
}

export interface SafetyChain {
  chain_id: string;
  hazard: Hazard | null;
  hazardous_event: HazardousEvent | null;
  asil_determination: ASILDetermination | null;
  safety_goal: SafetyGoal | null;
  fsr: FSR | null;
  test_case: TestCase | null;
  gap_count: number;
  is_complete: boolean;
  approval_count: number;
}

export interface SafetyProject {
  project_id: string;
  name: string;
  source_filename: string;
  chains: SafetyChain[];
  failure_modes: FailureMode[];
  total_chains: number;
  complete_chains: number;
  total_gaps: number;
  coverage_pct: number;
  created_at: string;
}

export interface Gap {
  chain_id: string;
  level: string;
  severity: string;
  description: string;
}

export interface DraftResponse {
  text: string;
  name: string;
  rationale: string;
  steps?: string;
  expected_result?: string;
  pass_criteria?: string;
}

export interface CoverageMetrics {
  total_chains: number;
  complete_chains: number;
  coverage_pct: number;
  total_gaps: number;
  level_counts: Record<string, { filled: number; approved: number; draft: number; gap: number }>;
  asil_distribution: Record<string, number>;
  approval_pct: number;
}

export interface ASILDefinitions {
  severity: Record<string, string>;
  exposure: Record<string, string>;
  controllability: Record<string, string>;
  asil_colors: Record<string, string>;
}

export type ChainLevel = 'hazard' | 'hazardous_event' | 'asil_determination' | 'safety_goal' | 'fsr' | 'test_case';
export type Perspective = 'safety_engineer' | 'test_engineer' | 'req_engineer' | 'manager';

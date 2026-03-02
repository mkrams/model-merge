export interface Element {
  id: string;
  name: string;
  type: string;
  doc?: string;
  raw?: string;
  req_id?: string;
  type_ref?: string;
  direction?: string;
  multiplicity?: string;
  subsets?: string;
  redefines?: string;
  attributes?: Attribute[];
  ports?: Port[];
  children?: Element[];
  interfaces?: Element[];
  constraints?: Constraint[];
  flows?: string[];
  ends?: string[];
  connections?: string[];
  default_value?: string;
  kind?: string;
  source?: string;
  target?: string;
}

export interface Attribute {
  name: string;
  type_ref?: string;
  default_value?: string;
  raw?: string;
}

export interface Port {
  id: string;
  name: string;
  type: string;
  type_ref?: string;
  direction?: string;
  raw?: string;
}

export interface Constraint {
  expression: string;
  raw?: string;
}

export interface PackageData {
  id: string;
  name: string;
  type: string;
  doc?: string;
  imports: { path: string; visibility: string }[];
  part_defs: Element[];
  port_defs: Element[];
  interface_defs: Element[];
  requirement_defs: Element[];
  parts: Element[];
  connections: Element[];
  values: Element[];
  subpackages: PackageData[];
}

export interface ModelSummary {
  package_count: number;
  element_count: number;
  part_defs: number;
  port_defs: number;
  interface_defs: number;
  requirement_defs: number;
  parts: number;
}

export interface ParsedModel {
  model_id: string;
  filename: string;
  model_type: string;
  summary: ModelSummary;
  packages: PackageData[];
  elements: Element[];
}

export interface MergeConflict {
  conflict_id: string;
  conflict_type: string;
  left_element: Element;
  right_element: Element;
  similarity: number;
  resolution: string | null;
}

export interface MergeAnalysis {
  merge_id: string;
  model_a_id: string;
  model_b_id: string;
  model_a_name: string;
  model_b_name: string;
  total_elements_a: number;
  total_elements_b: number;
  identical_count: number;
  conflict_count: number;
  unique_left_count: number;
  unique_right_count: number;
  identical: MergeConflict[];
  conflicts: MergeConflict[];
  unique_to_left: Element[];
  unique_to_right: Element[];
}

export interface MergedResult {
  merged_model_id: string;
  filename: string;
  summary: ModelSummary;
  packages: PackageData[];
  elements: Element[];
  sysml_text: string;
}

export interface ValidationResult {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  source: string;
}

export interface ValidationResponse {
  semantic: ValidationResult;
  compiler: ValidationResult;
}

export type AppStep = 'upload' | 'merge' | 'validate' | 'download';

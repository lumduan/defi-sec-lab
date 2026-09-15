// Shape of the inspector API's JSON (schema defi-sec-lab/inspection@1). Mirrors learn/api/inspector/stages.py.

export type Source = "fork" | "live";
export type Origin = "api" | "snapshot" | "error";
export type CheckStatus = "pass" | "fail" | "not_configured" | "unavailable" | "info";

export interface Citation {
  id: string;
  label: string;
  url: string;
}

export interface Check {
  id: string;
  label: string;
  expected: string | null;
  actual: string | null;
  pass: boolean | null;
  status: CheckStatus;
  note: string | null;
}

export interface Exchange {
  method: string;
  params: unknown[];
  result: unknown;
  decoded: string;
  note?: string;
}

export interface ChainStage {
  id: "chain";
  title: string;
  client: Source;
  client_version: string;
  block: {
    number: number;
    number_hex: string;
    hash: string;
    timestamp: number;
    timestamp_hex: string;
    timestamp_iso: string;
    l1_block_number: number | null;
    l1_block_number_hex: string | null;
  };
  exchanges: Exchange[];
  checks: Check[];
}

export interface SlotDerivation {
  preimage: string;
  keccak256: string;
  minus_one: boolean;
  slot: string;
  citation: string;
}

export interface ProxyRow {
  key: string;
  label: string;
  address: string;
  citation: string;
  proxy: {
    code_size: number;
    code_head: string;
    dispatcher_selectors: { signature: string; selector: string; push4_found: boolean }[];
  };
  slots: { eip1967: string; zeppelinos: string };
  implementation_slot: "eip1967" | "zeppelinos" | null;
  implementation: { address: string; code_size: number } | null;
  edge: boolean;
}

export interface ProxiesStage {
  id: "proxies";
  title: string;
  slot_derivations: { eip1967: SlotDerivation; zeppelinos: SlotDerivation };
  registry: {
    call: string;
    to: string;
    selector: string;
    result: string;
    decoded: string;
    address_book: string;
    match: boolean;
  };
  rows: ProxyRow[];
  edge_note: string;
}

export interface RayRate {
  raw: string;
  unit: string;
  fraction: string;
  percent_apr: string;
  percent_apy_derived: string;
  apy_formula: string;
}

export interface RayIndex {
  raw: string;
  unit: string;
  value: string;
}

export interface TimestampDecoded {
  iso: string;
  seconds_before_block: number;
}

export interface Field {
  index: number;
  name: string;
  type: string;
  word: string;
  raw: string;
  note: string | null;
  decoded: string | RayRate | RayIndex | TimestampDecoded;
}

export interface BitField {
  name: string;
  bits: string;
  hex: string;
  raw: number;
  unit: string;
  human: string;
  risk_param: boolean;
}

export interface Configuration {
  word: string;
  raw: string;
  source: string;
  fields: BitField[];
  flags_byte: { bits: string; hex: string; binary: string; flags: { bit: number; name: string; value: number }[] };
  holes: { bits: string; name: string; raw: number }[];
}

export interface BooksStage {
  id: "books";
  title: string;
  call: {
    to: string;
    function: string;
    argument: string;
    selector: string;
    calldata: string;
    block_tag: string;
    returndata: string;
    returndata_bytes: number;
    word_count: number;
  };
  fields: Field[];
  rates: { supply: RayRate & { field: string }; borrow: RayRate & { field: string } };
  risk_params: BitField[];
  configuration: Configuration;
  last_update: { raw: string; iso: string; seconds_before_block: number; block_timestamp: number };
}

export interface Comparison {
  field: string;
  bits: string;
  hex: string;
  storage: string;
  function: string;
  match: boolean;
}

export interface MemoryStage {
  id: "memory";
  title: string;
  proxy: {
    address: string;
    implementation: string;
    slot0_word: string;
    revision_in_storage: number;
    revision_in_code: number;
    source_tag: string;
  };
  layout: { slot: string; name: string; type: string; contract: string; citation: string }[];
  mapping: {
    key: string;
    declared_slot: number;
    preimage: string;
    base: string;
    field_offset: number;
    slot: string;
    struct_order: string[];
  };
  storage: {
    method: string;
    address: string;
    slot: string;
    block_tag: string;
    word: string;
    high_hex: string;
    low_hex: string;
    high: string;
    low: string;
  };
  comparisons: Comparison[];
  controls: {
    implementation_storage: { address: string; slot: string; word: string; is_zero: boolean };
    trace: {
      available: boolean;
      note?: string;
      tracer?: string;
      pool_slots_read?: number;
      read_slot?: boolean;
      value_at_read?: string | null;
      value_matches?: boolean;
    };
  };
}

export interface Inspection {
  schema: "defi-sec-lab/inspection@1";
  source: Source;
  generated_at: string;
  network: { name: string; chain_id: number };
  block: { tag: string; number: number; timestamp_iso: string };
  asset: { symbol: string; address: string; kind: string };
  citations: Citation[];
  stages: [ChainStage, ProxiesStage, BooksStage, MemoryStage];
}

export interface Loaded {
  data: Inspection | null;
  origin: Origin;
  error?: string;
}

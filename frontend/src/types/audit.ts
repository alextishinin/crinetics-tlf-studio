// Study-level audit trail (append-only, hash-chained on the backend).

export interface AuditEvent {
  seq: number;
  at: string;
  actor: string;
  action: string;
  details: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface AuditChain {
  valid: boolean;
  entries: number;
  first_invalid_seq: number | null;
}

export interface AuditTrailResponse {
  entries: AuditEvent[];
  chain: AuditChain;
}

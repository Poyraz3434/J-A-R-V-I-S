import { ATLAS_CONFIG } from "./config";
import { Logger } from "./utils";

export type SecurityEventType = "rate_limit" | "policy_violation" | "verification_required" | "suspicious_activity";

export interface SecurityEvent {
  type: SecurityEventType;
  message: string;
  severity: "low" | "medium" | "high" | "critical";
  ts: number;
  metadata?: Record<string, unknown>;
}

export interface SecurityContext {
  userId?: string;
  sessionId?: string;
  ipHash?: string;
  trustScore: number;
}

export class SecurityGate {
  private readonly events: SecurityEvent[] = [];
  private readonly recentRequests = new Map<string, number[]>();

  verify(context: SecurityContext, action: string): { allowed: boolean; reason?: string; confidence: number } {
    const now = Date.now();
    const windowMs = 60_000;
    const key = `${context.userId ?? "anon"}:${context.sessionId ?? "session"}`;
    const requests = this.recentRequests.get(key) ?? [];

    const filtered = requests.filter((ts) => now - ts < windowMs);
    filtered.push(now);
    this.recentRequests.set(key, filtered);

    const rateLimitExceeded = filtered.length > ATLAS_CONFIG.rateLimitPerMinute;
    const lowTrust = context.trustScore < 0.35;

    if (rateLimitExceeded) {
      this.record({
        type: "rate_limit",
        message: `Rate limit exceeded for action: ${action}`,
        severity: "high",
        ts: now,
        metadata: { action, requestCount: filtered.length },
      });
      return { allowed: false, reason: "Rate limit exceeded.", confidence: 0.99 };
    }

    if (lowTrust) {
      this.record({
        type: "verification_required",
        message: `Trust score too low for action: ${action}`,
        severity: "medium",
        ts: now,
        metadata: { action, trustScore: context.trustScore },
      });
      return { allowed: false, reason: "Verification required.", confidence: 0.92 };
    }

    return { allowed: true, confidence: Math.max(0.5, context.trustScore) };
  }

  record(event: SecurityEvent): void {
    this.events.push(event);
    if (this.events.length > 500) {
      this.events.shift();
    }
    Logger.warn(`Security event: ${event.type} - ${event.message}`);
  }

  getEvents(): SecurityEvent[] {
    return [...this.events];
  }
}

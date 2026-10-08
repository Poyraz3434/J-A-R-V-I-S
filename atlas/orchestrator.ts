import { ATLAS_CONFIG } from "./config";
import { Logger, retryWithBackoff, withTimeout } from "./utils";

export type AtlasTaskPriority = "low" | "normal" | "high" | "critical";

export interface AtlasTask {
  id: string;
  name: string;
  priority: AtlasTaskPriority;
  action: () => Promise<unknown>;
  timeoutMs?: number;
  retries?: number;
  metadata?: Record<string, unknown>;
}

export interface AtlasPlanStep {
  id: string;
  name: string;
  priority: AtlasTaskPriority;
  action: () => Promise<unknown>;
  dependsOn?: string[];
}

export class AtlasOrchestrator {
  private readonly queue: AtlasTask[] = [];
  private readonly inFlight = new Set<string>();

  schedule(task: AtlasTask): void {
    this.queue.push(task);
    this.queue.sort((a, b) => this.priorityWeight(b.priority) - this.priorityWeight(a.priority));
  }

  async runAll(): Promise<unknown[]> {
    const tasks = [...this.queue];
    this.queue.length = 0;

    const results = await Promise.all(
      tasks.map(async (task) => {
        this.inFlight.add(task.id);

        try {
          return await retryWithBackoff(
            () =>
              withTimeout(
                task.action,
                task.timeoutMs ?? ATLAS_CONFIG.requestTimeoutMs,
                task.name,
              ),
            task.retries ?? ATLAS_CONFIG.retryMaxAttempts,
            ATLAS_CONFIG.retryBackoffMs,
            task.name,
          );
        } finally {
          this.inFlight.delete(task.id);
        }
      }),
    );

    return results;
  }

  async executePlan(plan: AtlasPlanStep[]): Promise<unknown[]> {
    const pending = new Map(plan.map((step) => [step.id, step]));
    const completed = new Set<string>();
    const results: unknown[] = [];

    while (pending.size > 0) {
      const ready = [...pending.values()].filter(
        (step) => (step.dependsOn ?? []).every((dep) => completed.has(dep)),
      );

      if (ready.length === 0) {
        throw new Error("Cyclic or unresolved dependency in Atlas plan.");
      }

      const batch = await Promise.all(
        ready.map(async (step) => {
          const startedAt = Date.now();
          Logger.info(`Running plan step: ${step.name}`);
          const payload = await retryWithBackoff(
            () =>
              withTimeout(step.action, ATLAS_CONFIG.requestTimeoutMs, step.name),
            ATLAS_CONFIG.retryMaxAttempts,
            ATLAS_CONFIG.retryBackoffMs,
            step.name,
          );

          const duration = Date.now() - startedAt;
          Logger.info(`Plan step finished in ${duration}ms: ${step.name}`);
          results.push(payload);
          completed.add(step.id);
          pending.delete(step.id);
          return payload;
        }),
      );

      if (batch.length === 0) {
        break;
      }
    }

    return results;
  }

  private priorityWeight(priority: AtlasTaskPriority): number {
    const weight: Record<AtlasTaskPriority, number> = {
      low: 1,
      normal: 2,
      high: 3,
      critical: 4,
    };
    return weight[priority] ?? 2;
  }
}

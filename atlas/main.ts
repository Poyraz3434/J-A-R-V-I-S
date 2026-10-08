import { ATLAS_CONFIG } from "./config";
import { DetectionEngine, DetectionFeatures } from "./detection";
import { KnowledgeGraphMemory } from "./memory";
import { AtlasOrchestrator } from "./orchestrator";
import { SecurityGate } from "./security";
import { VerificationSystem } from "./verification";
import { AsyncRequestQueue, Logger, TTLCache, withTimeout } from "./utils";
import { Observability } from "./observability";

export class AtlasSystem {
  private readonly detector = new DetectionEngine();
  private readonly verifier = new VerificationSystem();
  private readonly cache = new TTLCache<string, unknown>();
  private readonly queue = new AsyncRequestQueue(ATLAS_CONFIG.requestQueueConcurrency);
  private readonly memory = new KnowledgeGraphMemory();
  private readonly orchestrator = new AtlasOrchestrator();
  private readonly security = new SecurityGate();
  private readonly metrics = new Observability();
  private readonly ws?: WebSocket;

  constructor() {
    if (
      ATLAS_CONFIG.enableWebSocket &&
      ATLAS_CONFIG.websocketUrl &&
      typeof WebSocket !== "undefined"
    ) {
      const socket = new WebSocket(ATLAS_CONFIG.websocketUrl);
      this.ws = socket;
      socket.addEventListener("open", () => {
        Logger.info("WebSocket bağlantısı açıldı.");
      });
      socket.addEventListener("error", (event) => {
        Logger.warn("WebSocket hata oluştu.", event);
      });
    }
  }

  async initialize(): Promise<void> {
    Logger.info(`${ATLAS_CONFIG.appName} başlatıldı.`);
    this.memory.addFact("Atlas çalışma modu başlatıldı.", { source: "bootstrap" });
    if (this.ws) {
      await this.waitForSocketOpen();
    }
  }

  async processRequest<T>(
    key: string,
    requestFactory: () => Promise<T>,
    features: Partial<DetectionFeatures> = {},
    userId = "local-user",
  ): Promise<T> {
    const cached = this.cache.get(key);
    if (cached !== undefined) {
      Logger.info(`Cache hit: ${key}`);
      return cached as T;
    }

    const securityDecision = this.security.verify({ userId, trustScore: 0.9 }, key);
    if (!securityDecision.allowed) {
      throw new Error(securityDecision.reason ?? "Security policy blocked this request.");
    }

    return this.queue.enqueue(async () => {
      const startedAt = Date.now();

      const detectionFeatures: DetectionFeatures = {
        deviceFingerprint: features.deviceFingerprint ?? "desktop-default",
        requestPattern: features.requestPattern ?? "standard",
        timingVariance: features.timingVariance ?? 0.12,
        anomalyScore: features.anomalyScore ?? 0.18,
        behaviorScore: features.behaviorScore ?? 0.87,
        ipRiskScore: features.ipRiskScore ?? 0.12,
        captchaSolved: features.captchaSolved ?? true,
        userInteractionScore: features.userInteractionScore ?? 0.92,
      };

      const detection = this.detector.detect(detectionFeatures);
      if (detection.isRobot) {
        Logger.warn("Robot doğrulaması gerekli.");
        const verified = await this.verifier.startChallenge();
        if (!verified) {
          throw new Error("Robot doğrulaması başarısız oldu.");
        }
      }

      const result = await withTimeout(requestFactory, ATLAS_CONFIG.requestTimeoutMs, key);
      const elapsed = Date.now() - startedAt;
      this.metrics.record("atlas.request_latency", elapsed, "ms", { key });

      if (elapsed > ATLAS_CONFIG.maxResponseMs) {
        Logger.warn(`Response time limit exceeded: ${elapsed}ms for ${key}`);
      }

      this.cache.set(key, result, ATLAS_CONFIG.cacheTtlMs);
      this.memory.addFact(`Request completed for ${key} with confidence ${detection.confidence}.`, {
        key,
        confidence: detection.confidence,
        riskLevel: detection.riskLevel,
      });
      this.detector.updateModel(detectionFeatures, false);

      return result;
    });
  }

  async runWorkflow<T>(
    name: string,
    actions: Array<() => Promise<T>>,
  ): Promise<T[]> {
    const plan = actions.map((action, index) => ({
      id: `${name}-${index}`,
      name: `${name}-${index}`,
      priority: "normal" as const,
      action: action,
    }));

    return this.orchestrator.executePlan(plan) as Promise<T[]>;
  }

  private waitForSocketOpen(): Promise<void> {
    const socket = this.ws;
    if (!socket) {
      return Promise.resolve();
    }

    return new Promise((resolve) => {
      const finish = () => resolve();

      if (socket.readyState === WebSocket.OPEN) {
        finish();
        return;
      }

      socket.addEventListener("open", finish, { once: true });
      setTimeout(() => {
        socket.removeEventListener("open", finish);
        resolve();
      }, 150);
    });
  }
}

export const atlasSystem = new AtlasSystem();

export async function bootstrap(): Promise<void> {
  await atlasSystem.initialize();
}

// Example usage:
// const result = await atlasSystem.processRequest("daily-summary", async () => {
//   return { ok: true, message: "Atlas ready" };
// }, {
//   deviceFingerprint: "device-xyz",
//   requestPattern: "human-interaction",
//   timingVariance: 0.14,
//   anomalyScore: 0.11,
//   behaviorScore: 0.91,
//   ipRiskScore: 0.06,
//   captchaSolved: true,
//   userInteractionScore: 0.94,
// });

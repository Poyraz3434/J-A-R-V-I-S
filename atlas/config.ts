export const ATLAS_CONFIG = {
  appName: "Jarvis Atlas",
  targetLatencyMs: 100,
  maxResponseMs: 200,
  cacheTtlMs: 60_000,
  requestTimeoutMs: 3_000,
  retryMaxAttempts: 3,
  retryBackoffMs: 250,
  requestQueueConcurrency: 8,
  rateLimitPerMinute: 120,
  confirmationPollMs: 1_000,
  detectionThreshold: 0.95,
  enableWebSocket: false,
  websocketUrl: "",
  modelVersion: "atlas-detector-v1.0",
} as const;

export type AtlasConfig = typeof ATLAS_CONFIG;

export const DETECTION_MODEL = {
  ruleWeight: 0.45,
  mlWeight: 0.55,
  anomalyWeight: 0.2,
  behaviorWeight: 0.3,
  deviceWeight: 0.2,
  ipRiskWeight: 0.15,
  featureBias: 0.12,
};

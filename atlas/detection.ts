import { ATLAS_CONFIG, DETECTION_MODEL } from "./config";
import { clamp, Logger, shortHash } from "./utils";

export interface DetectionFeatures {
  deviceFingerprint: string;
  requestPattern: string;
  timingVariance: number;
  anomalyScore: number;
  behaviorScore: number;
  ipRiskScore: number;
  captchaSolved: boolean;
  userInteractionScore: number;
}

export interface DetectionLayerResult {
  name: string;
  score: number;
  threshold: number;
  passed: boolean;
}

export interface DetectionResult {
  isRobot: boolean;
  confidence: number;
  riskLevel: "low" | "medium" | "high" | "critical";
  reasons: string[];
  layers: DetectionLayerResult[];
  modelVersion: string;
}

export class DetectionEngine {
  private readonly trainingSamples: Array<{ features: DetectionFeatures; label: boolean }> = [];

  detect(features: DetectionFeatures): DetectionResult {
    const ruleResult = this.ruleBasedLayer(features);
    const mlScore = this.mlScore(features);
    const combined = clamp(
      ruleResult.score * DETECTION_MODEL.ruleWeight +
        mlScore * DETECTION_MODEL.mlWeight +
        DETECTION_MODEL.featureBias,
    );

    const reasons: string[] = [];
    if (ruleResult.score > 0.6) {
      reasons.push("Kurallara göre anomaliler tespit edildi.");
    }
    if (mlScore > 0.7) {
      reasons.push("Makine öğrenimi modeli robot eğilimli davranış algıladı.");
    }
    if (features.captchaSolved === false && combined > 0.82) {
      reasons.push("Doğrulama çözülmemiş veya kullanıcı doğrulaması eksik.");
    }

    const isRobot = combined >= ATLAS_CONFIG.detectionThreshold || ruleResult.score >= 0.9;
    const riskLevel: DetectionResult["riskLevel"] = isRobot
      ? combined > 0.98
        ? "critical"
        : combined > 0.9
          ? "high"
          : "medium"
      : "low";

    const result: DetectionResult = {
      isRobot,
      confidence: Number(combined.toFixed(4)),
      riskLevel,
      reasons,
      layers: [
        ruleResult,
        {
          name: "ml-model",
          score: Number(mlScore.toFixed(4)),
          threshold: 0.8,
          passed: mlScore > 0.8,
        },
      ],
      modelVersion: ATLAS_CONFIG.modelVersion,
    };

    if (isRobot) {
      Logger.warn("Robot risk detected", {
        confidence: result.confidence,
        reasons: result.reasons,
      });
    }

    return result;
  }

  private ruleBasedLayer(features: DetectionFeatures): DetectionLayerResult {
    let score = 0;

    if (features.behaviorScore < 0.25) score += 0.3;
    if (features.timingVariance > 0.7) score += 0.2;
    if (features.anomalyScore > 0.75) score += 0.25;
    if (features.ipRiskScore > 0.8) score += 0.15;
    if (features.userInteractionScore < 0.35) score += 0.1;

    const normalized = clamp(score);

    return {
      name: "rule-based",
      score: Number(normalized.toFixed(4)),
      threshold: 0.7,
      passed: normalized > 0.7,
    };
  }

  private mlScore(features: DetectionFeatures): number {
    const sampleVector = [
      features.behaviorScore,
      features.timingVariance,
      features.anomalyScore,
      features.ipRiskScore,
      features.userInteractionScore,
      features.captchaSolved ? 1 : 0,
    ];

    const learnedBias = this.trainingSamples.reduce((accumulator, sample) => {
      const labelEffect = sample.label ? 0.08 : -0.04;
      return accumulator + labelEffect;
    }, 0);

    const weighted = sampleVector.reduce((acc, value, idx) => {
      const weight = [0.27, 0.18, 0.22, 0.16, 0.08, 0.09][idx] ?? 0.1;
      return acc + value * weight;
    }, 0);

    const featureHash = shortHash(`${features.deviceFingerprint}:${features.requestPattern}`);
    const hashFactor = Number.parseInt(featureHash, 16) / 0xffffffff;

    return clamp(0.25 + weighted + learnedBias + hashFactor * 0.18);
  }

  updateModel(features: DetectionFeatures, label: boolean): void {
    this.trainingSamples.push({ features, label });
    if (this.trainingSamples.length > 500) {
      this.trainingSamples.shift();
    }
  }
}

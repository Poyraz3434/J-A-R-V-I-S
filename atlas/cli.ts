import { atlasSystem, bootstrap } from "./main";

async function main(): Promise<void> {
  await bootstrap();
  const payload = await atlasSystem.processRequest(
    "atlas-cli-health",
    async () => ({
      ok: true,
      app: "Jarvis Atlas",
      latencyTargetMs: 100,
      maxResponseMs: 200,
      status: "ready",
    }),
    {
      deviceFingerprint: "cli-device",
      requestPattern: "human-interaction",
      timingVariance: 0.11,
      anomalyScore: 0.09,
      behaviorScore: 0.92,
      ipRiskScore: 0.05,
      captchaSolved: true,
      userInteractionScore: 0.95,
    },
    "cli",
  );

  console.log(JSON.stringify(payload, null, 2));
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(JSON.stringify({ ok: false, error: message }, null, 2));
  process.exitCode = 1;
});

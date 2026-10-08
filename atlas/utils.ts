import { ATLAS_CONFIG } from "./config";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export function clamp(value: number, min = 0, max = 1): number {
  return Math.min(Math.max(value, min), max);
}

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function withTimeout<T>(
  task: () => Promise<T>,
  timeoutMs: number = ATLAS_CONFIG.requestTimeoutMs,
  label = "task",
): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;

  const timeoutPromise = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      reject(new Error(`${label} timed out after ${timeoutMs}ms`));
    }, timeoutMs);
  });

  try {
    return await Promise.race([task(), timeoutPromise]);
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}

export async function retryWithBackoff<T>(
  operation: () => Promise<T>,
  maxAttempts: number = ATLAS_CONFIG.retryMaxAttempts,
  baseDelayMs: number = ATLAS_CONFIG.retryBackoffMs,
  label = "operation",
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      if (attempt === maxAttempts) {
        throw error;
      }

      const waitMs = baseDelayMs * attempt;
      Logger.warn(`${label} failed (${attempt}/${maxAttempts}), retrying in ${waitMs}ms`);
      await delay(waitMs);
    }
  }

  throw lastError instanceof Error ? lastError : new Error(`${label} failed`);
}

export class TTLCache<K, V> {
  private readonly store = new Map<K, { value: V; expiresAt: number }>();

  get(key: K): V | undefined {
    const entry = this.store.get(key);
    if (!entry) {
      return undefined;
    }

    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return undefined;
    }

    return entry.value;
  }

  set(key: K, value: V, ttlMs = ATLAS_CONFIG.cacheTtlMs): void {
    this.store.set(key, {
      value,
      expiresAt: Date.now() + ttlMs,
    });
  }

  delete(key: K): void {
    this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }
}

export class AsyncRequestQueue {
  private readonly concurrency: number;
  private running = 0;
  private queue: Array<() => Promise<unknown>> = [];

  constructor(concurrency = ATLAS_CONFIG.requestQueueConcurrency) {
    this.concurrency = concurrency;
  }

  enqueue<T>(task: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.queue.push(async () => {
        try {
          resolve(await task());
        } catch (error) {
          reject(error);
        }
      });

      this.drain();
    });
  }

  private drain(): void {
    while (this.running < this.concurrency && this.queue.length > 0) {
      const next = this.queue.shift();
      if (!next) {
        continue;
      }

      this.running += 1;
      void Promise.resolve(next()).finally(() => {
        this.running -= 1;
        this.drain();
      });
    }
  }
}

export class Logger {
  static info(message: string, ...meta: unknown[]): void {
    console.info(`[Atlas] ${message}`, ...meta);
  }

  static warn(message: string, ...meta: unknown[]): void {
    console.warn(`[Atlas] ${message}`, ...meta);
  }

  static error(message: string, ...meta: unknown[]): void {
    console.error(`[Atlas] ${message}`, ...meta);
  }
}

export function safeJsonParse<T>(payload: string): T | null {
  try {
    return JSON.parse(payload) as T;
  } catch {
    return null;
  }
}

export function createRateLimiter(limitPerMinute: number) {
  const windowMs = 60_000;
  const timestamps: number[] = [];

  return {
    canProceed(): boolean {
      const now = Date.now();
      while (timestamps.length > 0 && timestamps[0] <= now - windowMs) {
        timestamps.shift();
      }
      return timestamps.length < limitPerMinute;
    },
    record(): void {
      timestamps.push(Date.now());
    },
  };
}

export function shortHash(input: string): string {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash << 5) - hash + input.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash).toString(16);
}

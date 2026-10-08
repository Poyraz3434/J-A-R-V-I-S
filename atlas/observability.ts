export interface MetricPoint {
  name: string;
  value: number;
  unit: string;
  ts: number;
  tags?: Record<string, string>;
}

export class Observability {
  private readonly metrics: MetricPoint[] = [];

  record(name: string, value: number, unit = "ms", tags: Record<string, string> = {}): void {
    this.metrics.push({ name, value, unit, ts: Date.now(), tags });
    if (this.metrics.length > 10000) {
      this.metrics.splice(0, this.metrics.length - 10000);
    }
  }

  snapshot(): MetricPoint[] {
    return [...this.metrics];
  }

  average(name: string): number {
    const matches = this.metrics.filter((metric) => metric.name === name);
    if (matches.length === 0) {
      return 0;
    }
    return matches.reduce((sum, item) => sum + item.value, 0) / matches.length;
  }
}

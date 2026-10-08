import { Logger } from "./utils";

export interface MemoryNode {
  id: string;
  type: "fact" | "event" | "document" | "user";
  content: string;
  metadata?: Record<string, unknown>;
  createdAt: number;
}

export interface MemoryQueryResult {
  id: string;
  score: number;
  content: string;
  type: MemoryNode["type"];
}

export class KnowledgeGraphMemory {
  private readonly nodes: MemoryNode[] = [];

  addNode(node: MemoryNode): void {
    this.nodes.push(node);
    if (this.nodes.length > 5000) {
      this.nodes.splice(0, this.nodes.length - 5000);
    }
  }

  addFact(content: string, metadata: Record<string, unknown> = {}): string {
    const id = `fact-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    this.addNode({ id, type: "fact", content, metadata, createdAt: Date.now() });
    return id;
  }

  addDocument(content: string, metadata: Record<string, unknown> = {}): string {
    const id = `doc-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    this.addNode({ id, type: "document", content, metadata, createdAt: Date.now() });
    return id;
  }

  search(query: string, limit = 5): MemoryQueryResult[] {
    const normalized = query.toLowerCase();
    const scored = this.nodes
      .map((node) => {
        const haystack = `${node.content} ${JSON.stringify(node.metadata ?? {})}`.toLowerCase();
        const score = haystack.includes(normalized) ? 1 : this.tokenScore(normalized, haystack);
        return { node, score };
      })
      .filter(({ score }) => score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map(({ node, score }) => ({
        id: node.id,
        score,
        content: node.content,
        type: node.type,
      }));

    if (scored.length > 0) {
      Logger.info(`Knowledge query matched ${scored.length} memory items for: ${query}`);
    }

    return scored;
  }

  buildContext(query: string, limit = 5): string {
    const matches = this.search(query, limit);
    if (matches.length === 0) {
      return "";
    }

    return matches.map((entry) => `- [${entry.type}] ${entry.content}`).join("\n");
  }

  private tokenScore(query: string, haystack: string): number {
    const queryTokens = query.split(/\s+/).filter(Boolean);
    if (queryTokens.length === 0) {
      return 0;
    }

    let total = 0;
    for (const token of queryTokens) {
      if (haystack.includes(token)) {
        total += 1 / queryTokens.length;
      }
    }
    return total;
  }
}

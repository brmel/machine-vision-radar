import { availableParallelism } from "node:os";
import { Worker } from "node:worker_threads";
import type { ProductPages } from "./worker.ts";

const WORKER = new URL("./worker.ts", import.meta.url);

const answer = (worker: Worker, ids: readonly string[]): Promise<ProductPages[]> => new Promise((resolve, reject) => {
  worker.once("error", reject);
  worker.once("message", (pages: ProductPages[]) => {
    worker.off("error", reject);
    resolve(pages);
  });
  worker.postMessage(ids);
});

export class ProductRenderers {
  private readonly workers: readonly Worker[];
  private readonly idle: Worker[];
  private readonly waiting: ((worker: Worker) => void)[] = [];

  constructor(template: string) {
    this.workers = Array.from({ length: availableParallelism() }, () => new Worker(WORKER, { workerData: template }));
    this.idle = [...this.workers];
  }

  async pages(ids: readonly string[]): Promise<ProductPages[]> {
    const worker = this.idle.pop() ?? await new Promise<Worker>((resolve) => this.waiting.push(resolve));
    const pages = await answer(worker, ids);
    const next = this.waiting.shift();
    if (next) next(worker);
    else this.idle.push(worker);
    return pages;
  }

  async close(): Promise<void> {
    await Promise.all(this.workers.map((worker) => worker.terminate()));
  }
}

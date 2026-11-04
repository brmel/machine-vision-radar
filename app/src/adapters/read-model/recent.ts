const LIMIT = 256;

export class Recent<T> {
  private readonly kept = new Map<string, Promise<T>>();

  get(key: string, read: () => Promise<T>): Promise<T> {
    const found = this.kept.get(key);
    if (found) {
      this.kept.delete(key);
      this.kept.set(key, found);
      return found;
    }
    const reading = read().catch((err: unknown) => {
      this.kept.delete(key);
      throw err;
    });
    this.kept.set(key, reading);
    for (const oldest of this.kept.keys()) {
      if (this.kept.size <= LIMIT) break;
      this.kept.delete(oldest);
    }
    return reading;
  }

  keep(key: string, value: T): void {
    void this.get(key, async () => value);
  }
}

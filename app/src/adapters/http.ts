export async function postJson(path: string, body: unknown, headers: Readonly<Record<string, string>> = {},
    allowed: readonly number[] = []): Promise<Response> {
  const res = await fetch(`/api/${path}`,
    { method: "POST", headers: { "Content-Type": "application/json", ...headers }, body: JSON.stringify(body) });
  if (!res.ok && !allowed.includes(res.status)) throw new Error(`${path} endpoint answered HTTP ${res.status}`);
  return res;
}

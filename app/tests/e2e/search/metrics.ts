export async function metrics(): Promise<Record<string, number>> {
  const day = new Date().toISOString().slice(0, 10);
  const res =
    await fetch(`${process.env.MVR_FIRESTORE_DOCS}/metrics/${day}`, { headers: { Authorization: "Bearer owner" } });
  if (res.status === 404) return {};
  // Justification (typed boundary): the Firestore REST document; its fields are integer counters.
  const doc = (await res.json()) as { fields: Record<string, { integerValue: string }> };
  return Object.fromEntries(Object.entries(doc.fields).map(([k, v]) => [k, Number(v.integerValue)]));
}

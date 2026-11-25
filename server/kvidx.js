/* KV тизмеси list()сиз: акысыз Cloudflare'де list() суткасына 1000 гана (бот 45 с сайын сураса — бүтүп калат).
   Ордуна бир «индекс» ачкычы: idx:<аты> = id'лердин JSON массиви (акыркы MAX). get() — суткасына 100 000. */
const MAX = 500;

export async function idxAdd(kv, name, id) {
  const key = "idx:" + name;
  const raw = await kv.get(key);   // KV катасы ыргытылсын — болбосо индекс бир id менен кайра жазылып калат
  let a = [];
  try { a = JSON.parse(raw || "[]"); } catch (e) { a = []; }
  if (!Array.isArray(a)) a = [];
  a.push(id);
  a.sort();
  await kv.put(key, JSON.stringify(a.slice(-MAX)));
}

export async function idxAfter(kv, name, after, limit) {
  const raw = await kv.get("idx:" + name);   // KV катасы — чакыруучуга (500 + detail), бош тизме эмес
  let a = [];
  try { a = JSON.parse(raw || "[]"); } catch (e) { a = []; }
  return (Array.isArray(a) ? a : []).filter((id) => id > (after || "")).sort().slice(0, limit || 50);
}

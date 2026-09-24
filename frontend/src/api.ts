import type { FormState, SolveResponse } from "./types";

export async function postSolve(form: FormState): Promise<{ status: number; body: SolveResponse }> {
  const payload = {
    modes: form.modes,
    buses: form.buses.map((b) => ({ id: b.id, channels: b.channels })),
    sentinels: form.sentinels.map((s) => {
      const readings: Record<string, number> = {};
      for (const m of form.modes) {
        const v = s.readings[m];
        if (v === "0" || v === "1") readings[m] = Number(v);
        // 空串/缺失不下发，由服务端定位为读数缺失
      }
      return { id: s.id, cost: s.cost, bus: s.bus, readings };
    }),
  };

  const resp = await fetch("/api/solve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = (await resp.json()) as SolveResponse;
  return { status: resp.status, body };
}

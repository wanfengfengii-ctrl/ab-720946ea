import { useMemo, useRef, useState } from "react";
import { postSolve } from "./api";
import type {
  BusInput,
  FormState,
  SentinelInput,
  SolveResult,
  ValidationErrorItem,
} from "./types";

const MIN_MODES = 3;
const MAX_MODES = 12;
const MIN_SENTINELS = 4;
const MAX_SENTINELS = 18;

function emptyReadings(modes: string[]): Record<string, string> {
  return Object.fromEntries(modes.map((m) => [m, ""]));
}

function sampleForm(): FormState {
  const modes = ["M1", "M2", "M3"];
  return {
    modes,
    buses: [{ id: "B1", channels: "4" }],
    sentinels: [
      { id: "S1", cost: "1", bus: "B1", readings: { M1: "0", M2: "1", M3: "0" } },
      { id: "S2", cost: "1", bus: "B1", readings: { M1: "0", M2: "0", M3: "1" } },
      { id: "S3", cost: "5", bus: "B1", readings: { M1: "0", M2: "1", M3: "1" } },
      { id: "S4", cost: "1", bus: "B1", readings: { M1: "1", M2: "1", M3: "1" } },
    ],
  };
}

function blankForm(): FormState {
  const modes = ["M1", "M2", "M3"];
  return {
    modes,
    buses: [{ id: "B1", channels: "4" }],
    sentinels: Array.from({ length: 4 }, (_, i) => ({
      id: `S${i + 1}`,
      cost: "1",
      bus: "B1",
      readings: emptyReadings(modes),
    })),
  };
}

export default function App() {
  const [form, setForm] = useState<FormState>(blankForm);
  const [errors, setErrors] = useState<ValidationErrorItem[] | null>(null);
  const [result, setResult] = useState<SolveResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const requestId = useRef(0);

  // 任意录入变更：撤下旧结论/旧报错，同时作废旧在途响应
  function mutate(updater: (prev: FormState) => FormState) {
    requestId.current += 1;
    setForm(updater);
    setResult(null);
    setErrors(null);
    setNetworkError(null);
    setSubmitting(false);
  }

  const errorLocs = useMemo(() => new Set(errors?.map((e) => e.loc) ?? []), [errors]);
  const fieldError = (loc: string): string | undefined =>
    errors?.find((e) => e.loc === loc)?.msg;

  // ---- 故障模式 -----------------------------------------------------------
  function renameMode(index: number, next: string) {
    mutate((prev) => {
      const old = prev.modes[index];
      if (old === next) return prev;
      const modes = prev.modes.map((m, i) => (i === index ? next : m));
      const sentinels = prev.sentinels.map((s) => {
        const readings = emptyReadings(modes);
        for (const m of prev.modes) {
          readings[m === old ? next : m] = s.readings[m] ?? "";
        }
        return { ...s, readings };
      });
      return { ...prev, modes, sentinels };
    });
  }

  function addMode() {
    mutate((prev) => {
      if (prev.modes.length >= MAX_MODES) return prev;
      let id = `M${prev.modes.length + 1}`;
      let n = prev.modes.length + 1;
      while (prev.modes.includes(id)) id = `M${++n}`;
      return {
        ...prev,
        modes: [...prev.modes, id],
        sentinels: prev.sentinels.map((s) => ({
          ...s,
          readings: { ...s.readings, [id]: "" },
        })),
      };
    });
  }

  function removeMode(index: number) {
    mutate((prev) => {
      if (prev.modes.length <= MIN_MODES) return prev;
      const removed = prev.modes[index];
      const modes = prev.modes.filter((_, i) => i !== index);
      return {
        ...prev,
        modes,
        sentinels: prev.sentinels.map((s) => {
          const readings = { ...s.readings };
          delete readings[removed];
          return { ...s, readings };
        }),
      };
    });
  }

  // ---- 总线 ---------------------------------------------------------------
  function updateBus(index: number, patch: Partial<BusInput>) {
    mutate((prev) => ({
      ...prev,
      buses: prev.buses.map((b, i) => (i === index ? { ...b, ...patch } : b)),
    }));
  }

  function addBus() {
    mutate((prev) => {
      let id = `B${prev.buses.length + 1}`;
      let n = prev.buses.length + 1;
      const all = new Set(prev.buses.map((b) => b.id));
      while (all.has(id)) id = `B${++n}`;
      return { ...prev, buses: [...prev.buses, { id, channels: "1" }] };
    });
  }

  function removeBus(index: number) {
    mutate((prev) => ({ ...prev, buses: prev.buses.filter((_, i) => i !== index) }));
  }

  // ---- 哨点 ---------------------------------------------------------------
  function updateSentinel(index: number, patch: Partial<SentinelInput>) {
    mutate((prev) => ({
      ...prev,
      sentinels: prev.sentinels.map((s, i) => (i === index ? { ...s, ...patch } : s)),
    }));
  }

  function setReading(si: number, mode: string, value: string) {
    const v = value === "" ? "" : value === "0" || value === "1" ? value : "0";
    mutate((prev) => ({
      ...prev,
      sentinels: prev.sentinels.map((s, i) =>
        i === si ? { ...s, readings: { ...s.readings, [mode]: v } } : s
      ),
    }));
  }

  function addSentinel() {
    mutate((prev) => {
      if (prev.sentinels.length >= MAX_SENTINELS) return prev;
      let id = `S${prev.sentinels.length + 1}`;
      let n = prev.sentinels.length + 1;
      while (prev.sentinels.some((s) => s.id === id)) id = `S${++n}`;
      return {
        ...prev,
        sentinels: [
          ...prev.sentinels,
          { id, cost: "1", bus: prev.buses[0]?.id ?? "", readings: emptyReadings(prev.modes) },
        ],
      };
    });
  }

  function removeSentinel(index: number) {
    mutate((prev) => {
      if (prev.sentinels.length <= MIN_SENTINELS) return prev;
      return { ...prev, sentinels: prev.sentinels.filter((_, i) => i !== index) };
    });
  }

  async function handleSubmit() {
    const myId = ++requestId.current;
    setSubmitting(true);
    setErrors(null);
    setResult(null);
    setNetworkError(null);
    try {
      const { status, body } = await postSolve(form);
      if (requestId.current !== myId) return; // 已有更新输入，本次结果作废
      if (status === 200 && body.ok && body.result) {
        setResult(body.result);
      } else if (body.errors) {
        setErrors(body.errors);
      } else {
        setNetworkError("服务返回了无法识别的响应");
      }
    } catch {
      if (requestId.current === myId) setNetworkError("无法连接诊断服务，请检查后端是否运行");
    } finally {
      if (requestId.current === myId) setSubmitting(false);
    }
  }

  const canSubmit = !submitting;

  return (
    <div className="page">
      <header>
        <h1>海上变流器绝缘告警 · 诊断哨点组合推荐</h1>
        <p className="subtitle">
          录入候选故障模式、诊断哨点、二元读数矩阵、哨点费用与读出总线通道容量，
          服务将枚举全部合法组合，按总费用 → 哨点数 → 编号字典序给出最优判别组合及逐对区分证据。
        </p>
      </header>

      {/* 故障模式 */}
      <section className="card">
        <div className="card-head">
          <h2>① 故障模式（{form.modes.length}/{MAX_MODES}，至少 {MIN_MODES} 个）</h2>
          <div className="actions">
            <button type="button" onClick={addMode} disabled={form.modes.length >= MAX_MODES}>
              + 增加模式
            </button>
          </div>
        </div>
        <div className="chip-row">
          {form.modes.map((m, i) => {
            const loc = `modes[${i}]`;
            return (
              <span className={`chip ${errorLocs.has(loc) ? "bad" : ""}`} key={i} title={fieldError(loc)}>
                <input
                  value={m}
                  aria-label={`故障模式 ${i + 1} 编号`}
                  onChange={(e) => renameMode(i, e.target.value)}
                />
                <button
                  type="button"
                  className="icon-btn"
                  disabled={form.modes.length <= MIN_MODES}
                  onClick={() => removeMode(i)}
                  title="删除该模式"
                >
                  ×
                </button>
              </span>
            );
          })}
        </div>
        {fieldError("modes") && <p className="field-msg">{fieldError("modes")}</p>}
      </section>

      {/* 总线 */}
      <section className="card">
        <div className="card-head">
          <h2>② 读出总线与可用通道数</h2>
          <div className="actions">
            <button type="button" onClick={addBus}>+ 增加总线</button>
          </div>
        </div>
        <table className="grid bus-table">
          <thead>
            <tr>
              <th>总线编号</th>
              <th>可用通道数（非负整数）</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {form.buses.map((b, i) => (
              <tr key={i}>
                <td>
                  <input
                    className={errorLocs.has(`buses[${i}].id`) ? "bad-input" : ""}
                    value={b.id}
                    aria-label={`总线 ${i + 1} 编号`}
                    onChange={(e) => updateBus(i, { id: e.target.value })}
                  />
                  {fieldError(`buses[${i}].id`) && (
                    <span className="field-msg">{fieldError(`buses[${i}].id`)}</span>
                  )}
                </td>
                <td>
                  <input
                    className={`narrow ${errorLocs.has(`buses[${i}].channels`) ? "bad-input" : ""}`}
                    value={b.channels}
                    inputMode="numeric"
                    aria-label={`总线 ${i + 1} 通道数`}
                    onChange={(e) => updateBus(i, { channels: e.target.value })}
                  />
                  {fieldError(`buses[${i}].channels`) && (
                    <span className="field-msg">{fieldError(`buses[${i}].channels`)}</span>
                  )}
                </td>
                <td>
                  <button type="button" className="icon-btn" onClick={() => removeBus(i)}>
                    ×
                  </button>
                </td>
              </tr>
            ))}
            {form.buses.length === 0 && (
              <tr>
                <td colSpan={3} className="muted">尚未定义总线，哨点将无法挂靠。</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {/* 哨点与读数矩阵 */}
      <section className="card">
        <div className="card-head">
          <h2>③ 哨点与二元读数矩阵（{form.sentinels.length}/{MAX_SENTINELS}，至少 {MIN_SENTINELS} 个）</h2>
          <div className="actions">
            <button type="button" onClick={addSentinel} disabled={form.sentinels.length >= MAX_SENTINELS}>
              + 增加哨点
            </button>
          </div>
        </div>
        <div className="matrix-scroll">
          <table className="grid matrix">
            <thead>
              <tr>
                <th>哨点编号</th>
                <th>费用</th>
                <th>所属总线</th>
                {form.modes.map((m) => (
                  <th key={m} className="mode-col">{m}</th>
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {form.sentinels.map((s, si) => {
                const busKnown = form.buses.some((b) => b.id === s.bus);
                return (
                  <tr key={si}>
                    <td>
                      <input
                        className={errorLocs.has(`sentinels[${si}].id`) ? "bad-input" : ""}
                        value={s.id}
                        aria-label={`哨点 ${si + 1} 编号`}
                        onChange={(e) => updateSentinel(si, { id: e.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        className={`narrow ${errorLocs.has(`sentinels[${si}].cost`) ? "bad-input" : ""}`}
                        value={s.cost}
                        inputMode="decimal"
                        aria-label={`哨点 ${si + 1} 费用`}
                        onChange={(e) => updateSentinel(si, { cost: e.target.value })}
                      />
                    </td>
                    <td>
                      <select
                        className={errorLocs.has(`sentinels[${si}].bus`) || !busKnown ? "bad-input" : ""}
                        value={busKnown ? s.bus : ""}
                        aria-label={`哨点 ${si + 1} 所属总线`}
                        onChange={(e) => updateSentinel(si, { bus: e.target.value })}
                      >
                        {!busKnown && <option value="">{s.bus ? `未知: ${s.bus}` : "未选择"}</option>}
                        {form.buses.map((b) => (
                          <option key={b.id} value={b.id}>{b.id}</option>
                        ))}
                      </select>
                    </td>
                    {form.modes.map((m) => {
                      const loc = `sentinels[${si}].readings.${m}`;
                      return (
                        <td key={m} className="bit-cell">
                          <input
                            className={`bit ${errorLocs.has(loc) ? "bad-input" : ""}`}
                            value={s.readings[m] ?? ""}
                            maxLength={1}
                            inputMode="numeric"
                            aria-label={`哨点 ${s.id || si + 1} 对 ${m} 的读数`}
                            title={fieldError(loc)}
                            onChange={(e) => setReading(si, m, e.target.value)}
                          />
                        </td>
                      );
                    })}
                    <td>
                      <button
                        type="button"
                        className="icon-btn"
                        disabled={form.sentinels.length <= MIN_SENTINELS}
                        onClick={() => removeSentinel(si)}
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {fieldError("sentinels") && <p className="field-msg">{fieldError("sentinels")}</p>}
        <p className="hint">读数只接受 0/1；留空将在提交时被定位为“读数缺失”。</p>
      </section>

      {/* 提交 */}
      <section className="submit-bar">
        <button type="button" className="primary" onClick={handleSubmit} disabled={!canSubmit}>
          {submitting ? "枚举中…" : "提交并推荐组合"}
        </button>
        <button type="button" onClick={() => mutate(() => sampleForm())}>载入示例</button>
        <button type="button" onClick={() => mutate(() => blankForm())}>清空重填</button>
      </section>

      {/* 错误面板 */}
      {errors && errors.length > 0 && (
        <section className="card result error-panel">
          <h2>输入问题（{errors.length}）</h2>
          <ul>
            {errors.map((e, i) => (
              <li key={i}>
                <code className="loc">{e.loc}</code> — {e.msg}
              </li>
            ))}
          </ul>
        </section>
      )}
      {networkError && (
        <section className="card result error-panel">
          <p>{networkError}</p>
        </section>
      )}

      {/* 结果 */}
      {result && <ResultView result={result} />}
    </div>
  );
}

function ResultView({ result }: { result: SolveResult }) {
  if (!result.feasible) {
    return (
      <section className="card result no-plan">
        <h2>无可行方案</h2>
        <p>{result.reason}</p>
        {result.indistinguishable_pairs && result.indistinguishable_pairs.length > 0 && (
          <>
            <p>以下故障模式对在全部哨点上读数均相同，永远无法区分：</p>
            <ul>
              {result.indistinguishable_pairs.map((p, i) => (
                <li key={i}>
                  <strong>{p.mode_a}</strong> ↔ <strong>{p.mode_b}</strong>
                </li>
              ))}
            </ul>
          </>
        )}
        <p className="hint">
          已比较合法组合 {result.combinations_evaluated.toLocaleString()} /{" "}
          {result.total_combinations.toLocaleString()} 个。
        </p>
      </section>
    );
  }

  return (
    <section className="card result plan">
      <h2>推荐哨点组合</h2>
      <div className="summary">
        <div className="metric">
          <span className="metric-label">选中哨点</span>
          <span className="metric-value">{result.selection!.join("、")}</span>
        </div>
        <div className="metric">
          <span className="metric-label">总费用</span>
          <span className="metric-value">{result.total_cost}</span>
        </div>
        <div className="metric">
          <span className="metric-label">哨点数</span>
          <span className="metric-value">{result.sentinel_count}</span>
        </div>
      </div>

      <h3>总线通道占用</h3>
      <table className="grid">
        <thead>
          <tr><th>总线</th><th>占用 / 容量</th><th>占用通道的哨点</th></tr>
        </thead>
        <tbody>
          {result.bus_usage!.map((u) => (
            <tr key={u.bus}>
              <td>{u.bus}</td>
              <td className={u.used > u.capacity ? "bad-input" : ""}>{u.used} / {u.capacity}</td>
              <td>{u.selected.join("、")}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>逐对区分证据（{result.evidence!.length} 对故障模式）</h3>
      <div className="matrix-scroll">
        <table className="grid evidence">
          <thead>
            <tr>
              <th>故障模式 A</th><th>故障模式 B</th><th>见证哨点</th>
              <th>A 读数</th><th>B 读数</th>
            </tr>
          </thead>
          <tbody>
            {result.evidence!.map((e, i) => (
              <tr key={i}>
                <td>{e.mode_a}</td>
                <td>{e.mode_b}</td>
                <td><strong>{e.witness}</strong></td>
                <td className="bit-out">{e.reading_a}</td>
                <td className="bit-out">{e.reading_b}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">
        服务完整比较了 {result.combinations_evaluated.toLocaleString()} 个合法组合
        （全部子集共 {result.total_combinations.toLocaleString()} 个，超出总线通道容量的组合不计入合法组合）。
      </p>
    </section>
  );
}

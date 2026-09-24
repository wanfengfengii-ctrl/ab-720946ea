import { useEffect, useState } from "react";
import { solveSelection } from "./api";
import { normalizeErrors } from "./errors";
import ModeEditor, { MAX_MODES, MIN_MODES } from "./components/ModeEditor";
import BusEditor, { MAX_BUSES, MIN_BUSES } from "./components/BusEditor";
import SentinelMatrix, {
  MAX_SENTINELS,
  MIN_SENTINELS,
} from "./components/SentinelMatrix";
import ResultPanel from "./components/ResultPanel";
import ErrorList from "./components/ErrorList";

function nextId(prefix, existing) {
  let i = 1;
  while (existing.includes(`${prefix}${i}`)) i += 1;
  return `${prefix}${i}`;
}

function zeroReadings(modes) {
  return Object.fromEntries(modes.map((m) => [m, 0]));
}

/** 能解析为有限数字则提交数字，否则原样提交由后端定位报错。 */
function toNumberOrRaw(v) {
  if (typeof v !== "string") return v;
  const t = v.trim();
  if (t === "") return v;
  const n = Number(t);
  return Number.isFinite(n) ? n : v;
}

function defaultState() {
  const modes = ["F1", "F2", "F3"];
  const buses = [{ id: "BUS-A", channels: "2" }];
  const sentinels = Array.from({ length: MIN_SENTINELS }, (_, i) => ({
    id: `S${i + 1}`,
    bus: buses[0].id,
    cost: "1",
    readings: zeroReadings(modes),
  }));
  return { modes, buses, sentinels };
}

export default function App() {
  const [{ modes, buses, sentinels }, setState] = useState(defaultState);
  const [result, setResult] = useState(null);
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(false);

  const setModes = (fn) => setState((s) => ({ ...s, modes: fn(s.modes) }));
  const setBuses = (fn) => setState((s) => ({ ...s, buses: fn(s.buses) }));
  const setSentinels = (fn) => setState((s) => ({ ...s, sentinels: fn(s.sentinels) }));

  // 任意输入变更后，立即撤下旧结论与旧错误。
  useEffect(() => {
    setResult(null);
    setErrors([]);
  }, [modes, buses, sentinels]);

  // ---------- 故障模式 ----------
  function updateMode(i, value) {
    const old = modes[i];
    setModes((prev) => prev.map((m, idx) => (idx === i ? value : m)));
    if (old !== value) {
      setSentinels((prev) =>
        prev.map((s) => {
          if (!(old in s.readings)) return s;
          const readings = { ...s.readings, [value]: s.readings[old] };
          delete readings[old];
          return { ...s, readings };
        })
      );
    }
  }

  function addMode() {
    if (modes.length >= MAX_MODES) return;
    const id = nextId("F", modes);
    setModes((prev) => [...prev, id]);
    setSentinels((prev) =>
      prev.map((s) => ({ ...s, readings: { ...s.readings, [id]: 0 } }))
    );
  }

  function removeMode(i) {
    if (modes.length <= MIN_MODES) return;
    const removed = modes[i];
    setModes((prev) => prev.filter((_, idx) => idx !== i));
    setSentinels((prev) =>
      prev.map((s) => {
        const readings = { ...s.readings };
        delete readings[removed];
        return { ...s, readings };
      })
    );
  }

  // ---------- 总线 ----------
  function updateBus(i, field, value) {
    setBuses((prev) =>
      prev.map((b, idx) => (idx === i ? { ...b, [field]: value } : b))
    );
  }

  function addBus() {
    if (buses.length >= MAX_BUSES) return;
    const id = nextId("BUS-", buses.map((b) => b.id));
    setBuses((prev) => [...prev, { id, channels: "2" }]);
  }

  function removeBus(i) {
    if (buses.length <= MIN_BUSES) return;
    const removed = buses[i].id;
    setBuses((prev) => prev.filter((_, idx) => idx !== i));
    // 引用被删总线的哨点置为未选择，由用户重新指定（后端亦会定位报错）。
    setSentinels((prev) =>
      prev.map((s) => (s.bus === removed ? { ...s, bus: "" } : s))
    );
  }

  // ---------- 哨点 ----------
  function updateSentinel(i, field, value) {
    setSentinels((prev) =>
      prev.map((s, idx) => (idx === i ? { ...s, [field]: value } : s))
    );
  }

  function toggleReading(i, mode) {
    setSentinels((prev) =>
      prev.map((s, idx) =>
        idx === i
          ? { ...s, readings: { ...s.readings, [mode]: s.readings[mode] ? 0 : 1 } }
          : s
      )
    );
  }

  function addSentinel() {
    if (sentinels.length >= MAX_SENTINELS) return;
    const id = nextId("S", sentinels.map((s) => s.id));
    setSentinels((prev) => [
      ...prev,
      { id, bus: buses[0]?.id ?? "", cost: "1", readings: zeroReadings(modes) },
    ]);
  }

  function removeSentinel(i) {
    if (sentinels.length <= MIN_SENTINELS) return;
    setSentinels((prev) => prev.filter((_, idx) => idx !== i));
  }

  function loadExample() {
    setState({
      modes: ["F1", "F2", "F3"],
      buses: [
        { id: "B1", channels: "1" },
        { id: "B2", channels: "2" },
      ],
      sentinels: [
        { id: "S1", bus: "B1", cost: "5", readings: { F1: 0, F2: 0, F3: 1 } },
        { id: "S2", bus: "B2", cost: "5", readings: { F1: 0, F2: 1, F3: 0 } },
        { id: "S3", bus: "B2", cost: "9", readings: { F1: 0, F2: 1, F3: 1 } },
        { id: "S4", bus: "B2", cost: "1", readings: { F1: 0, F2: 0, F3: 0 } },
      ],
    });
  }

  // ---------- 提交 ----------
  async function handleSubmit() {
    setLoading(true);
    try {
      const payload = {
        fault_modes: modes.map((m) => m.trim()),
        buses: buses.map((b) => ({ id: b.id.trim(), channels: toNumberOrRaw(b.channels) })),
        sentinels: sentinels.map((s) => ({
          id: s.id.trim(),
          bus: s.bus,
          cost: toNumberOrRaw(s.cost),
          readings: { ...s.readings },
        })),
      };
      const resp = await solveSelection(payload);
      if (resp.status === 422 && resp.data?.detail) {
        setErrors(normalizeErrors(resp.data.detail));
        setResult(null);
      } else if (resp.ok && resp.data) {
        setResult(resp.data);
        setErrors([]);
      } else {
        setErrors([
          { key: "global", msg: `服务异常（HTTP ${resp.status}）`, loc: [] },
        ]);
        setResult(null);
      }
    } catch (e) {
      setErrors([
        { key: "global", msg: `无法连接后端服务：${e.message}`, loc: [] },
      ]);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const selectedIds =
    result?.status === "ok" ? new Set(result.selected.map((s) => s.id)) : null;
  const globalErrors = errors.filter((e) => e.key === "global");

  return (
    <div className="page">
      <header>
        <h1>海上变流器诊断哨点组合推荐</h1>
        <p>
          在总线通道约束下完整枚举全部哨点组合，按「总费用最低 → 哨点数最少 →
          编号序列字典序最小」选出可同时区分所有故障模式的组合。
        </p>
      </header>

      <main>
        <div className="columns">
          <ModeEditor
            modes={modes}
            errors={errors}
            onUpdate={updateMode}
            onAdd={addMode}
            onRemove={removeMode}
          />
          <BusEditor
            buses={buses}
            errors={errors}
            onUpdate={updateBus}
            onAdd={addBus}
            onRemove={removeBus}
          />
        </div>

        <SentinelMatrix
          sentinels={sentinels}
          modes={modes}
          buses={buses}
          errors={errors}
          selectedIds={selectedIds}
          onUpdate={updateSentinel}
          onAdd={addSentinel}
          onRemove={removeSentinel}
          onToggle={toggleReading}
        />

        <div className="submit-bar">
          <button type="button" className="primary" disabled={loading} onClick={handleSubmit}>
            {loading ? "求解中…" : "提交求解"}
          </button>
          <button type="button" className="ghost" onClick={loadExample}>
            填充示例
          </button>
        </div>

        {globalErrors.length > 0 && (
          <ul className="error-list global">
            {globalErrors.map((e, i) => (
              <li key={i}>{e.msg}</li>
            ))}
          </ul>
        )}
        <ErrorList errors={errors} prefix="body" />

        <ResultPanel result={result} loading={loading} />
      </main>
    </div>
  );
}

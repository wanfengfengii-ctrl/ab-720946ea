import { Fragment } from "react";
import { exactError, prefixError } from "../errors";
import ErrorList from "./ErrorList";

export const MIN_SENTINELS = 4;
export const MAX_SENTINELS = 18;

export default function SentinelMatrix({
  sentinels,
  modes,
  buses,
  errors,
  selectedIds,
  onUpdate,
  onAdd,
  onRemove,
  onToggle,
}) {
  return (
    <section className="panel">
      <h2>
        诊断哨点与二元读数 <span className="count">{sentinels.length}/{MAX_SENTINELS}</span>
      </h2>
      <p className="hint">
        哨点 {MIN_SENTINELS}–{MAX_SENTINELS} 个；点击读数单元格在 0/1 间切换。求解后选中的哨点会高亮。
      </p>
      <div className="matrix-wrap">
        <table className="matrix">
          <thead>
            <tr>
              <th>编号</th>
              <th>费用</th>
              <th>所属总线</th>
              {modes.map((m) => (
                <th key={m} className="bit-head" title={`故障模式 ${m}`}>
                  {m}
                </th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {sentinels.map((s, i) => {
              const idErr = exactError(errors, `body.sentinels.${i}.id`);
              const costErr = exactError(errors, `body.sentinels.${i}.cost`);
              const busErr = exactError(errors, `body.sentinels.${i}.bus`);
              const readErr = prefixError(errors, `body.sentinels.${i}.readings`);
              const rowErr = idErr || costErr || busErr || readErr;
              const selected = selectedIds?.has(s.id);
              return (
                <Fragment key={i}>
                  <tr className={selected ? "selected" : ""}>
                    <td>
                      <input
                        value={s.id}
                        className={idErr ? "invalid" : ""}
                        onChange={(e) => onUpdate(i, "id", e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        value={s.cost}
                        inputMode="decimal"
                        className={`cost ${costErr ? "invalid" : ""}`}
                        onChange={(e) => onUpdate(i, "cost", e.target.value)}
                      />
                    </td>
                    <td>
                      <select
                        value={s.bus}
                        className={busErr ? "invalid" : ""}
                        onChange={(e) => onUpdate(i, "bus", e.target.value)}
                      >
                        <option value="">— 选择 —</option>
                        {buses.map((b) => (
                          <option key={b.id} value={b.id}>
                            {b.id}
                          </option>
                        ))}
                        {s.bus && !buses.some((b) => b.id === s.bus) && (
                          <option value={s.bus}>{s.bus}（未定义）</option>
                        )}
                      </select>
                    </td>
                    {modes.map((m) => (
                      <td key={m} className="bit-cell">
                        <button
                          type="button"
                          className={`bit bit-${s.readings[m] ?? 0}`}
                          onClick={() => onToggle(i, m)}
                        >
                          {s.readings[m] ?? 0}
                        </button>
                      </td>
                    ))}
                    <td>
                      <button
                        type="button"
                        className="ghost"
                        disabled={sentinels.length <= MIN_SENTINELS}
                        onClick={() => onRemove(i)}
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                  {rowErr && (
                    <tr className="row-error">
                      <td colSpan={modes.length + 4}>{rowErr}</td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <button
        type="button"
        disabled={sentinels.length >= MAX_SENTINELS}
        onClick={onAdd}
      >
        + 添加哨点
      </button>
      <ErrorList errors={errors} prefix="body.sentinels" />
    </section>
  );
}

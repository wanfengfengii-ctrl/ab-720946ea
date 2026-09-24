import { exactError } from "../errors";
import ErrorList from "./ErrorList";

export const MIN_MODES = 3;
export const MAX_MODES = 12;

export default function ModeEditor({ modes, errors, onUpdate, onAdd, onRemove }) {
  return (
    <section className="panel">
      <h2>
        故障模式 <span className="count">{modes.length}/{MAX_MODES}</span>
      </h2>
      <p className="hint">候选故障模式 {MIN_MODES}–{MAX_MODES} 个，编号不可重复。</p>
      {modes.map((m, i) => (
        <div className="row" key={i}>
          <input
            value={m}
            placeholder={`故障模式 #${i + 1}`}
            className={exactError(errors, `body.fault_modes.${i}`) ? "invalid" : ""}
            onChange={(e) => onUpdate(i, e.target.value)}
          />
          <button
            type="button"
            className="ghost"
            disabled={modes.length <= MIN_MODES}
            onClick={() => onRemove(i)}
          >
            删除
          </button>
        </div>
      ))}
      <button type="button" disabled={modes.length >= MAX_MODES} onClick={onAdd}>
        + 添加故障模式
      </button>
      <ErrorList errors={errors} prefix="body.fault_modes" />
    </section>
  );
}

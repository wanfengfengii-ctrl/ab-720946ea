import { exactError } from "../errors";
import ErrorList from "./ErrorList";

export const MIN_BUSES = 1;
export const MAX_BUSES = 18;

export default function BusEditor({ buses, errors, onUpdate, onAdd, onRemove }) {
  return (
    <section className="panel">
      <h2>
        读出总线 <span className="count">{buses.length}/{MAX_BUSES}</span>
      </h2>
      <p className="hint">每条总线需给定可用通道数（正整数），每个选中哨点占用一个通道。</p>
      <div className="row bus-head">
        <span>总线编号</span>
        <span>通道数</span>
        <span />
      </div>
      {buses.map((b, i) => (
        <div className="row" key={i}>
          <input
            value={b.id}
            placeholder={`总线 #${i + 1}`}
            className={exactError(errors, `body.buses.${i}.id`) ? "invalid" : ""}
            onChange={(e) => onUpdate(i, "id", e.target.value)}
          />
          <input
            value={b.channels}
            inputMode="numeric"
            placeholder="通道数"
            className={exactError(errors, `body.buses.${i}.channels`) ? "invalid" : ""}
            onChange={(e) => onUpdate(i, "channels", e.target.value)}
          />
          <button
            type="button"
            className="ghost"
            disabled={buses.length <= MIN_BUSES}
            onClick={() => onRemove(i)}
          >
            删除
          </button>
        </div>
      ))}
      <button type="button" disabled={buses.length >= MAX_BUSES} onClick={onAdd}>
        + 添加总线
      </button>
      <ErrorList errors={errors} prefix="body.buses" />
    </section>
  );
}

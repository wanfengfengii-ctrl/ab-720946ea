export default function ResultPanel({ result, loading }) {
  if (loading) {
    return <div className="result pending">正在求解，请稍候…</div>;
  }
  if (!result) return null;

  if (result.status === "infeasible") {
    return (
      <div className="result infeasible">
        <h2>无可行方案</h2>
        <p>{result.message}</p>
        {result.blocking_pairs?.length > 0 && (
          <>
            <p>以下故障模式对即使选中全部哨点也无法区分：</p>
            <ul className="pair-list">
              {result.blocking_pairs.map(([a, b]) => (
                <li key={`${a}-${b}`}>
                  {a} × {b}
                </li>
              ))}
            </ul>
          </>
        )}
        <p className="stats">
          已完整枚举 {result.stats.combinations_examined} 个组合，无可行组合。
        </p>
      </div>
    );
  }

  return (
    <div className="result ok">
      <h2>推荐哨点组合</h2>
      <div className="cards">
        <div className="card">
          <div className="card-value">{result.total_cost}</div>
          <div className="card-label">总费用</div>
        </div>
        <div className="card">
          <div className="card-value">{result.sentinel_count}</div>
          <div className="card-label">哨点数量</div>
        </div>
        <div className="card">
          <div className="card-value">{result.stats.combinations_examined}</div>
          <div className="card-label">枚举组合数</div>
        </div>
        <div className="card">
          <div className="card-value">{result.stats.feasible_combinations}</div>
          <div className="card-label">可行组合数</div>
        </div>
      </div>

      <h3>选中哨点（按编号升序）</h3>
      <table className="plain">
        <thead>
          <tr>
            <th>编号</th>
            <th>所属总线</th>
            <th>费用</th>
          </tr>
        </thead>
        <tbody>
          {result.selected.map((s) => (
            <tr key={s.id}>
              <td>{s.id}</td>
              <td>{s.bus}</td>
              <td>{s.cost}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>总线通道占用</h3>
      <ul className="usage-list">
        {result.bus_usage.map((u) => (
          <li key={u.bus}>
            <span className="bus">{u.bus}</span>
            <span className={u.used > u.capacity ? "over" : ""}>
              {u.used} / {u.capacity} 通道
            </span>
          </li>
        ))}
      </ul>

      <h3>逐对区分证据</h3>
      <table className="plain">
        <thead>
          <tr>
            <th>故障模式对</th>
            <th>给出不同读数的选中哨点</th>
          </tr>
        </thead>
        <tbody>
          {result.evidence.map((ev) => (
            <tr key={ev.pair.join("-")}>
              <td>
                {ev.pair[0]} × {ev.pair[1]}
              </td>
              <td>
                {ev.witnesses.map((w) => (
                  <span className="chip" key={w.sentinel}>
                    {w.sentinel}: {w.readings[0]}≠{w.readings[1]}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

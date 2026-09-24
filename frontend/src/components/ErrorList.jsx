import { formatLoc } from "../errors";

/** 展示某一前缀下的全部校验错误。 */
export default function ErrorList({ errors, prefix }) {
  const list = errors.filter(
    (e) => e.key === prefix || e.key.startsWith(prefix + ".")
  );
  if (!list.length) return null;
  return (
    <ul className="error-list">
      {list.map((e, i) => (
        <li key={i}>
          <span className="loc">{formatLoc(e.loc)}</span>
          {e.msg}
        </li>
      ))}
    </ul>
  );
}

const SEG_NAMES = {
  fault_modes: "故障模式",
  buses: "总线",
  sentinels: "哨点",
  id: "编号",
  channels: "通道数",
  cost: "费用",
  bus: "所属总线",
  readings: "读数",
};

/** 将 FastAPI 的 detail 归一化为 [{key, msg, loc}]。 */
export function normalizeErrors(detail) {
  if (!Array.isArray(detail)) {
    return [{ key: "global", msg: String(detail ?? "请求被拒绝"), loc: [] }];
  }
  return detail.map((e) => ({
    key: Array.isArray(e.loc) ? e.loc.join(".") : "global",
    msg: e.msg || "输入不合法",
    loc: Array.isArray(e.loc) ? e.loc : [],
  }));
}

/** 精确匹配某个字段的错误信息。 */
export function exactError(errors, key) {
  const hit = errors.find((e) => e.key === key);
  return hit ? hit.msg : null;
}

/** 匹配某个字段前缀（含子字段）的错误信息。 */
export function prefixError(errors, prefix) {
  const hit = errors.find((e) => e.key === prefix || e.key.startsWith(prefix + "."));
  return hit ? hit.msg : null;
}

/** 把 loc 数组转成人类可读的位置，如 ["body","sentinels",2,"id"] → "哨点 #3 · 编号"。 */
export function formatLoc(loc) {
  const parts = [];
  for (const seg of loc) {
    if (seg === "body") continue;
    if (typeof seg === "number") {
      if (parts.length) parts[parts.length - 1] = `${parts[parts.length - 1]} #${seg + 1}`;
      else parts.push(`#${seg + 1}`);
    } else {
      parts.push(SEG_NAMES[seg] || String(seg));
    }
  }
  return parts.join(" · ") || "全局";
}

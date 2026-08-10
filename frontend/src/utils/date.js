// 本地日期工具：前端统一用本地日期（避免 toISOString 的 UTC 边界：本地凌晨会取到"昨天"，跨周时周次错乱）

export function todayStr() {
  return fmtDate(new Date())
}

export function fmtDate(d) {
  const x = new Date(d)
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`
}

// 所在周的周一
export function mondayOf(d) {
  const x = new Date(d)
  const day = x.getDay() || 7 // 周日 getDay()=0 → 7
  x.setDate(x.getDate() - day + 1)
  return x
}

// 本周周一（YYYY-MM-DD）
export function thisWeekStart() {
  return fmtDate(mondayOf(new Date()))
}

// 下周周一
export function nextWeekStart() {
  const m = mondayOf(new Date())
  m.setDate(m.getDate() + 7)
  return fmtDate(m)
}

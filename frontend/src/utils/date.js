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

// 周次下拉选项：前 past 周 ~ 未来 future 周（含本周），value=各周周一，label 含日期范围
export function buildWeekOptions(past = 12, future = 12) {
  const opts = []
  for (let i = past; i >= 1; i--) {
    const m = mondayOf(new Date())
    m.setDate(m.getDate() - i * 7)
    const e = new Date(m); e.setDate(e.getDate() + 6)
    const s = fmtDate(m)
    opts.push({ value: s, label: `${i === 1 ? '上周' : `前${i}周`} ${s.slice(5)}~${fmtDate(e).slice(5)}` })
  }
  for (let i = 0; i <= future; i++) {
    const m = mondayOf(new Date())
    m.setDate(m.getDate() + i * 7)
    const e = new Date(m); e.setDate(e.getDate() + 6)
    const s = fmtDate(m)
    opts.push({ value: s, label: `${i === 0 ? '本周' : i === 1 ? '下周' : `${i + 1}周后`} ${s.slice(5)}~${fmtDate(e).slice(5)}` })
  }
  return opts
}

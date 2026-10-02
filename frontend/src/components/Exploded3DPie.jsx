/**
 * Exploded3DPie — a hand-built SVG pie chart with a PowerPoint-style 3D
 * exploded look (side-wall depth, pulled-out slices), redesigned for
 * readability:
 *   - NO external leader-line labels (they overlapped/clipped badly with
 *     many small slices — see the two bug reports this rewrite fixes)
 *   - percentage shown INSIDE each slice large enough to hold it
 *   - a wrapping legend below the chart shows every category name, so
 *     nothing is ever cut off by the card boundary
 *   - hovering a slice highlights it and shows a rich tooltip with every
 *     field available for that data point (pct, plus any extra columns
 *     like quantity/count/grade that the backend attached)
 */
import { useState } from 'react'

const PALETTE = [
  '#4472C4', '#ED7D31', '#A5A5A5', '#FFC000', '#70AD47',
  '#5B9BD5', '#264478', '#9E480E', '#636363', '#997300',
  '#255E91', '#43682B', '#698ED0', '#F1975A', '#B7B7B7',
]

function darken(hex, amt = 0.32) {
  const n = parseInt(hex.replace('#', ''), 16)
  const r = Math.max(0, ((n >> 16) & 0xff) * (1 - amt)) | 0
  const g = Math.max(0, ((n >> 8) & 0xff) * (1 - amt)) | 0
  const b = Math.max(0, (n & 0xff) * (1 - amt)) | 0
  return `rgb(${r},${g},${b})`
}
function lighten(hex, amt = 0.18) {
  const n = parseInt(hex.replace('#', ''), 16)
  const r = Math.min(255, ((n >> 16) & 0xff) + 255 * amt) | 0
  const g = Math.min(255, ((n >> 8) & 0xff) + 255 * amt) | 0
  const b = Math.min(255, (n & 0xff) + 255 * amt) | 0
  return `rgb(${r},${g},${b})`
}

// Point on the perspective ellipse for a given screen angle (0 = top, clockwise)
function pt(cx, cy, rx, ry, thetaDeg) {
  const t = (thetaDeg * Math.PI) / 180
  return { x: cx + rx * Math.sin(t), y: cy - ry * Math.cos(t) }
}

function sectorPath(cx, cy, rx, ry, a0, a1) {
  const p0 = pt(cx, cy, rx, ry, a0)
  const p1 = pt(cx, cy, rx, ry, a1)
  const large = a1 - a0 > 180 ? 1 : 0
  return `M ${cx} ${cy} L ${p0.x} ${p0.y} A ${rx} ${ry} 0 ${large} 1 ${p1.x} ${p1.y} Z`
}

// Wall (extruded side face) — a ribbon between the top ellipse edge and the
// same edge shifted down by `depth`, clipped to only the front-facing
// (bottom-half) portion of the arc so back-facing slices don't produce a
// stray floating wall.
function wallPath(cx, cy, rx, ry, depth, a0, a1) {
  let start = a0, end = a1
  if (end < start) end += 360
  const segs = []
  for (let base = 0; base <= 360; base += 360) {
    const lo = Math.max(start, base + 90)
    const hi = Math.min(end, base + 270)
    if (lo < hi) segs.push([lo, hi])
  }
  return segs.map(([lo, hi]) => {
    const p0 = pt(cx, cy, rx, ry, lo)
    const p1 = pt(cx, cy, rx, ry, hi)
    const large = hi - lo > 180 ? 1 : 0
    return `M ${p0.x} ${p0.y} A ${rx} ${ry} 0 ${large} 1 ${p1.x} ${p1.y} ` +
           `L ${p1.x} ${p1.y + depth} A ${rx} ${ry} 0 ${large} 0 ${p0.x} ${p0.y + depth} Z`
  })
}

// Format a raw field value for display in the tooltip / legend.
function fmtVal(v) {
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toLocaleString()
    return v.toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
  return String(v)
}

// Turn a raw column header like "Sum of Qty(MT)" into a cleaner tooltip label.
function fmtFieldName(k) {
  return k
    .replace(/^Sum of\s+/i, '')
    .replace(/^Count of\s+/i, 'Count — ')
    .replace(/\(MT\)/i, '(MT)')
}

export default function Exploded3DPie({
  data,               // [{ label, pct, ...extraFields }]
  width = 560,
  height = 320,
  depth = 22,
  explode = 16,
  labelFontSize = 10.5,
}) {
  const [hoverIdx, setHoverIdx] = useState(null)
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })

  if (!data?.length) return null

  const total = data.reduce((s, d) => s + Math.abs(d.pct), 0) || 1
  const cx = width * 0.42
  const cy = height * 0.42
  const rx = Math.min(width * 0.24, 130)
  const ry = rx * 0.55

  let acc = 0
  const slices = data.map((d, i) => {
    const frac = Math.abs(d.pct) / total
    const a0 = acc * 360
    acc += frac
    const a1 = acc * 360
    const mid = (a0 + a1) / 2
    return { ...d, a0, a1, mid, color: PALETTE[i % PALETTE.length] }
  })

  const hovered = hoverIdx != null ? slices[hoverIdx] : null

  // Extra fields to show in the tooltip = any key beyond label/pct/a0/a1/mid/color
  const extraKeys = hovered
    ? Object.keys(hovered).filter(k => !['label','pct','a0','a1','mid','color'].includes(k))
    : []

  const handleEnter = (i, e) => {
    setHoverIdx(i)
    setTooltipPos({ x: e.clientX, y: e.clientY })
  }
  const handleMove = (e) => {
    setTooltipPos({ x: e.clientX, y: e.clientY })
  }

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} style={{ overflow: 'visible' }}>
        {/* Soft pedestal shadow */}
        <ellipse cx={cx} cy={cy + depth + 4} rx={rx + explode * 0.6} ry={ry * 0.9} fill="#00000012" />

        {/* Extruded side walls */}
        {slices.map((s, i) => {
          const isHover = i === hoverIdx
          const ex = isHover ? explode * 1.35 : explode
          const dx = ex * Math.sin((s.mid * Math.PI) / 180)
          const dy = -ex * Math.cos((s.mid * Math.PI) / 180) * (ry / rx)
          const wallColor = darken(s.color, 0.38)
          const paths = wallPath(cx + dx, cy + dy, rx, ry, depth, s.a0, s.a1)
          return paths.map((d, j) => (
            <path key={`wall-${i}-${j}`} d={d} fill={wallColor} stroke={wallColor} strokeWidth={0.5} />
          ))
        })}

        {/* Top (exploded) faces — the interactive hover targets */}
        {slices.map((s, i) => {
          const isHover = i === hoverIdx
          const ex = isHover ? explode * 1.35 : explode
          const dx = ex * Math.sin((s.mid * Math.PI) / 180)
          const dy = -ex * Math.cos((s.mid * Math.PI) / 180) * (ry / rx)
          const fillColor = isHover ? lighten(s.color, 0.12) : s.color
          return (
            <path
              key={`top-${i}`}
              d={sectorPath(cx + dx, cy + dy, rx, ry, s.a0, s.a1)}
              fill={fillColor}
              stroke={isHover ? '#1F4E79' : '#fff'}
              strokeWidth={isHover ? 2.5 : 1.4}
              style={{ cursor: 'pointer', transition: 'fill .12s, stroke-width .12s' }}
              onMouseEnter={(e) => handleEnter(i, e)}
              onMouseMove={handleMove}
              onMouseLeave={() => setHoverIdx(null)}
            />
          )
        })}

        {/* Percentage labels inside each slice — only when the slice is big
            enough to hold the text without spilling outside its own wedge */}
        {slices.map((s, i) => {
          const isHover = i === hoverIdx
          const ex = isHover ? explode * 1.35 : explode
          const dx = ex * Math.sin((s.mid * Math.PI) / 180)
          const dy = -ex * Math.cos((s.mid * Math.PI) / 180) * (ry / rx)
          const pct = Math.abs(s.pct)
          if (pct / total < 0.035) return null
          const lp = pt(cx + dx, cy + dy, rx * 0.55, ry * 0.55, s.mid)
          return (
            <text key={`pctlbl-${i}`} x={lp.x} y={lp.y}
              fill="#fff" fontSize={labelFontSize} fontWeight={700}
              textAnchor="middle" dominantBaseline="central"
              style={{ pointerEvents: 'none', filter: 'drop-shadow(0 1px 1px rgba(0,0,0,.5))' }}>
              {pct.toFixed(1)}%
            </text>
          )
        })}
      </svg>

      {/* Hover tooltip — rich detail for the highlighted slice only.
          Uses position:fixed (viewport coordinates) so it can never be
          clipped by a parent card's overflow:hidden, and is clamped to
          stay fully within the browser window. */}
      {hovered && (
        <div style={{
          position: 'fixed',
          left: Math.min(tooltipPos.x + 16, window.innerWidth - 230),
          top: Math.min(Math.max(tooltipPos.y - 10, 8), window.innerHeight - 160),
          background: '#fff',
          border: '1px solid #D6D6D6',
          borderRadius: 8,
          boxShadow: '0 4px 18px rgba(0,0,0,.18)',
          padding: '10px 13px',
          minWidth: 150,
          maxWidth: 220,
          pointerEvents: 'none',
          zIndex: 9999,
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 7,
            fontSize: '.8rem', fontWeight: 700, color: '#1F4E79', marginBottom: 6,
          }}>
            <span style={{
              width: 10, height: 10, borderRadius: 2,
              background: hovered.color, display: 'inline-block', flexShrink: 0,
            }} />
            {hovered.label}
          </div>
          <div style={{ fontSize: '.75rem', color: '#555', lineHeight: 1.7 }}>
            <div><strong style={{ color: '#333' }}>{Math.abs(hovered.pct).toFixed(2)}%</strong> of total</div>
            {extraKeys.map(k => (
              <div key={k}>
                {fmtFieldName(k)}: <strong style={{ color: '#333' }}>{fmtVal(hovered[k])}</strong>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Legend — replaces the old leader-line labels entirely. Wraps
          naturally so it never overflows the card, and every category
          name stays fully readable regardless of how small its slice is. */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '6px 14px',
        justifyContent: 'center', marginTop: 10, padding: '0 8px',
      }}>
        {slices.map((s, i) => {
          const isHover = i === hoverIdx
          return (
            <div
              key={`leg-${i}`}
              onMouseEnter={() => setHoverIdx(i)}
              onMouseLeave={() => setHoverIdx(null)}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                fontSize: '.72rem', color: isHover ? '#1F4E79' : '#555',
                fontWeight: isHover ? 700 : 500,
                cursor: 'pointer', transition: 'color .12s',
              }}>
              <span style={{
                width: 9, height: 9, borderRadius: 2, background: s.color,
                display: 'inline-block', flexShrink: 0,
                boxShadow: isHover ? '0 0 0 2px ' + s.color + '33' : 'none',
              }} />
              <span>{s.label}</span>
              <span style={{ color: '#AAA' }}>({Math.abs(s.pct).toFixed(1)}%)</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

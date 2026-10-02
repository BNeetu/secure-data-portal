/**
 * HR Coil Monthly Quality Dashboard
 * - Fully dynamic: renders however many sections the backend detects
 * - Clean flat pie charts — NO shadows, NO 3D artifacts, NO yellow glow
 * - Each chart in its own card with fixed height — no overlapping
 * - Layout auto-adjusts: 2 pies per row, pareto/stacked full width
 */
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ComposedChart,
  Line, LabelList,
} from 'recharts'
import Exploded3DPie from './Exploded3DPie'

// Excel-style professional palette
const PALETTE = [
  '#4472C4','#ED7D31','#A5A5A5','#FFC000','#70AD47',
  '#5B9BD5','#264478','#9E480E','#636363','#997300',
  '#255E91','#43682B','#698ED0','#F1975A','#B7B7B7',
  '#7030A0','#C00000','#92D050','#00B0F0','#FF6600',
]

const TT = {
  contentStyle:{
    background:'#fff', border:'1px solid #D6D6D6', borderRadius:6,
    fontSize:11, color:'#333', boxShadow:'0 2px 8px rgba(0,0,0,.10)',
  },
  labelStyle:{ color:'#777', fontSize:10 },
}
const AX = { tick:{fill:'#555',fontSize:9,fontFamily:'Segoe UI'}, axisLine:{stroke:'#D6D6D6'}, tickLine:false }
const GR = { stroke:'#E8E8E8', strokeDasharray:'3 3' }

// ── Card wrapper ───────────────────────────────────────────────────────────
function Card({ title, children, height }) {
  return (
    <div style={{
      background:'#fff', border:'1px solid #D6D6D6', borderRadius:10,
      boxShadow:'0 1px 4px rgba(0,0,0,.06)', overflow:'hidden',
      display:'flex', flexDirection:'column',
    }}>
      <div style={{
        padding:'9px 14px 8px', background:'#fff',
        borderBottom:'2px solid #4472C4', flexShrink:0,
      }}>
        <h3 style={{
          fontFamily:"'Segoe UI',sans-serif", fontSize:'.72rem', fontWeight:700,
          textTransform:'uppercase', letterSpacing:'.07em', color:'#1F4E79', margin:0,
        }}>{title}</h3>
      </div>
      <div style={{ padding:'12px 10px 14px', flex:1, height: height || 'auto' }}>
        {children}
      </div>
    </div>
  )
}

// ── FLAT Pie chart — no shadow, no 3D effect ──────────────────────────────
function FlatPie({ section }) {
  const { title, data } = section
  if (!data?.length) return null

  const RADIAN = Math.PI / 180
  const pieData = data.map((d, i) => ({
    name:  d.label,
    value: Math.abs(d.pct),
    fill:  PALETTE[i % PALETTE.length],
  }))

  // Inside label showing percentage
  const renderLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
    if (percent < 0.025) return null
    const r  = innerRadius + (outerRadius - innerRadius) * 0.6
    const x  = cx + r * Math.cos(-midAngle * RADIAN)
    const y  = cy + r * Math.sin(-midAngle * RADIAN)
    const fs = percent > 0.12 ? 10 : percent > 0.05 ? 8.5 : 7.5
    return (
      <text x={x} y={y} fill="#fff" textAnchor="middle"
        dominantBaseline="central" fontSize={fs} fontWeight={700}>
        {(percent * 100).toFixed(1)}%
      </text>
    )
  }

  const hasMany   = data.length > 7
  const pieRadius = hasMany ? 80 : 90
  const chartH    = hasMany ? 200 : 210
  const legendH   = hasMany ? Math.ceil(data.length / 2) * 18 : data.length * 16
  const totalH    = chartH + Math.min(legendH, 120)

  return (
    <Card title={title} height={totalH + 20}>
      <ResponsiveContainer width="100%" height={totalH}>
        <PieChart>
          {/* ONE Pie only — no shadow layer */}
          <Pie
            data={pieData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy={`${Math.round(chartH / totalH * 100 * 0.52)}%`}
            outerRadius={pieRadius}
            innerRadius={0}
            paddingAngle={1}
            labelLine={false}
            label={renderLabel}
            stroke="#fff"
            strokeWidth={1.5}
            isAnimationActive={true}
          >
            {pieData.map((e, i) => (
              <Cell key={i} fill={e.fill} />
            ))}
          </Pie>
          <Tooltip
            {...TT}
            formatter={(v, n) => [`${Number(v).toFixed(2)}%`, n]}
          />
          <Legend
            iconType="square"
            iconSize={9}
            layout="horizontal"
            align="center"
            verticalAlign="bottom"
            wrapperStyle={{ fontSize: 9, lineHeight: '15px', paddingTop: 4 }}
            formatter={val => val.length > 22 ? val.slice(0, 20) + '…' : val}
          />
        </PieChart>
      </ResponsiveContainer>
    </Card>
  )
}

// ── Pareto: sorted bars + cumulative line ─────────────────────────────────
function ParetoChart({ section }) {
  const { title, data } = section
  if (!data?.length) return null
  const h = Math.max(320, Math.min(500, 180 + data.length * 26))
  return (
    <Card title={title}>
      <div style={{ height: h }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top:16, right:55, left:8, bottom:100 }}>
            <CartesianGrid {...GR} />
            <XAxis
              dataKey="label" {...AX}
              angle={-42} textAnchor="end" height={105} interval={0}
              tick={{ fill:'#444', fontSize:8.5 }}
            />
            <YAxis
              yAxisId="bar" {...AX}
              tickFormatter={v => `${v.toFixed(1)}%`}
              label={{ value:'%', angle:-90, position:'insideLeft', fill:'#777', fontSize:10, style:{textAnchor:'middle'} }}
            />
            <YAxis
              yAxisId="line" orientation="right" domain={[0, 100]}
              {...AX} tickFormatter={v => `${v}%`}
              label={{ value:'Cumulative %', angle:90, position:'insideRight', fill:'#777', fontSize:9, style:{textAnchor:'middle'} }}
            />
            <Tooltip
              {...TT}
              formatter={(v, n) => [`${typeof v === 'number' ? v.toFixed(4) : v}%`, n]}
            />
            <Legend wrapperStyle={{ fontSize:10 }} />
            <Bar yAxisId="bar" dataKey="pct" name="%" maxBarSize={38} radius={[3,3,0,0]}>
              {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              <LabelList
                dataKey="pct" position="top"
                style={{ fontSize:7.5, fill:'#333', fontWeight:700 }}
                formatter={v => `${Number(v).toFixed(2)}%`}
              />
            </Bar>
            <Line
              yAxisId="line" type="monotone" dataKey="cumulative"
              name="Cumulative %" stroke="#ED7D31" strokeWidth={2}
              dot={{ r:3, fill:'#ED7D31', strokeWidth:0 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

// ── Column chart (Month-wise CAT-I) ───────────────────────────────────────
function ColumnChart({ section }) {
  const { title, data } = section
  if (!data?.length) return null
  return (
    <Card title={title}>
      <div style={{ height: 250 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data.map(d => ({ name: d.month, value: d.pct }))}
            margin={{ top:20, right:16, left:8, bottom:14 }}>
            <CartesianGrid {...GR} vertical={false} />
            <XAxis dataKey="name" {...AX} />
            <YAxis {...AX} tickFormatter={v => `${v}%`} />
            <Tooltip {...TT} formatter={v => [`${Number(v).toFixed(4)}%`, 'CAT-I %']} />
            <Bar dataKey="value" name="CAT-I %" fill="#FFC000" radius={[4,4,0,0]} maxBarSize={60}>
              <LabelList
                dataKey="value" position="top"
                style={{ fontSize:10, fill:'#555', fontWeight:700 }}
                formatter={v => Number(v).toFixed(4)}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

// ── Stacked column (Major Defects Trend) ──────────────────────────────────
function StackedChart({ section }) {
  const { title, data, defect_series: series } = section
  if (!data?.length || !series?.length) return null
  const h = Math.max(300, 220 + series.length * 14)
  return (
    <Card title={title}>
      <div style={{ height: h }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data.map(d => ({ ...d, name: d.month }))}
            margin={{ top:16, right:16, left:8, bottom:55 }}>
            <CartesianGrid {...GR} vertical={false} />
            <XAxis dataKey="name" {...AX} />
            <YAxis {...AX} tickFormatter={v => `${(v * 100).toFixed(3)}%`} />
            <Tooltip {...TT} formatter={(v, n) => [`${(Number(v)*100).toFixed(4)}%`, n]} />
            <Legend
              wrapperStyle={{ fontSize:9, paddingTop:8 }}
              iconSize={9} iconType="square"
            />
            {series.map((s, i) => (
              <Bar
                key={s} dataKey={s}
                name={s.length > 24 ? s.slice(0,22) + '…' : s}
                stackId="a" fill={PALETTE[i % PALETTE.length]} maxBarSize={80}
              >
                <LabelList
                  dataKey={s} position="inside"
                  style={{ fontSize:7, fill:'#fff' }}
                  formatter={v => v > 0.001 ? `${(v*100).toFixed(2)}%` : ''}
                />
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

// ── Generic bar chart for unknown types ───────────────────────────────────
function GenericBar({ section }) {
  const { title, data } = section
  if (!data?.length) return null
  const h = Math.max(200, Math.min(400, 120 + data.length * 28))
  return (
    <Card title={title}>
      <div style={{ height: h }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data.map((d,i) => ({ name:d.label, value:d.pct, fill:PALETTE[i%PALETTE.length] }))}
            layout="vertical"
            margin={{ top:4, right:30, left:8, bottom:8 }}
          >
            <CartesianGrid {...GR} horizontal={false} />
            <XAxis type="number" {...AX} tickFormatter={v => `${v}%`} />
            <YAxis type="category" dataKey="name" {...AX} width={130} tick={{ fill:'#555', fontSize:9 }} />
            <Tooltip {...TT} formatter={v => [`${Number(v).toFixed(2)}%`, 'Value']} />
            <Bar dataKey="value" radius={[0,4,4,0]} maxBarSize={18}>
              {data.map((_, i) => <Cell key={i} fill={PALETTE[i%PALETTE.length]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

// True isometric 3D pie (exploded slices + extruded side walls + leader
// lines to external labels), matching the classic PowerPoint "3D Pie Chart"
// look the user asked for. Wrapped in the same Card used everywhere else
// so it sits consistently alongside the other chart types.
function Isometric3DPie({ section }) {
  const { title, data } = section
  if (!data?.length) return null
  const chartHeight = data.length > 8 ? 300 : 270
  // Legend wraps roughly 3-4 items per row at this card width; estimate
  // rows needed so the card is tall enough that nothing gets clipped.
  const legendRows = Math.ceil(data.length / 3)
  const legendHeight = 20 + legendRows * 20
  return (
    <Card title={title} height={chartHeight + legendHeight + 20}>
      <Exploded3DPie data={data} width={520} height={chartHeight} depth={20} explode={14} />
    </Card>
  )
}

// ── Render one section by chart_type ──────────────────────────────────────
function Section({ section }) {
  if (!section?.data?.length) return null
  switch (section.chart_type) {
    case 'pie_3d':         return <Isometric3DPie section={section} />
    case 'pareto':         return <ParetoChart     section={section} />
    case 'column':         return <ColumnChart     section={section} />
    case 'stacked_column': return <StackedChart    section={section} />
    default:               return <GenericBar      section={section} />
  }
}

// ── Dynamic layout algorithm ───────────────────────────────────────────────
function buildRows(sections) {
  const rows = []
  let i = 0
  while (i < sections.length) {
    const s = sections[i]
    if (!s?.data?.length) { i++; continue }

    if (s.chart_type === 'pie_3d') {
      // Pair two consecutive pies in one row
      const next = i + 1 < sections.length ? sections[i+1] : null
      if (next && next.chart_type === 'pie_3d' && next.data?.length) {
        rows.push({ cols: 2, items: [s, next] })
        i += 2
      } else {
        rows.push({ cols: 2, items: [s, null] })
        i += 1
      }
    } else if (s.chart_type === 'pareto' || s.chart_type === 'stacked_column' || s.chart_type === 'bar') {
      // Always full width
      rows.push({ cols: 1, items: [s] })
      i += 1
    } else {
      // column and others: try to pair
      const next = i + 1 < sections.length ? sections[i+1] : null
      if (next && next.chart_type === s.chart_type && next.data?.length) {
        rows.push({ cols: 2, items: [s, next] })
        i += 2
      } else {
        rows.push({ cols: 2, items: [s, null] })
        i += 1
      }
    }
  }
  return rows
}

// ── KPI strip ─────────────────────────────────────────────────────────────
function KpiStrip({ month, sections }) {
  const qcSec = sections.find(s => s.key === 'QC STATUS')
  const qc    = qcSec?.data || []
  const prime = qc.find(d => d.label?.toUpperCase().includes('PRIME'))
  const cat1  = qc.find(d => d.label?.toUpperCase().includes('CATEGORY-I'))
  const defs  = sections.find(s => s.key === 'DEFECTS')

  const kpis = [
    { icon:'📅', label:'Report Month',  val: month || '—',                              col:'#4472C4' },
    { icon:'⭐', label:'Prime %',       val: prime ? `${prime.pct.toFixed(2)}%`  : '—', col:'#70AD47' },
    { icon:'⚠️', label:'CAT-I %',      val: cat1  ? `${cat1.pct.toFixed(4)}%`   : '—', col:'#C00000' },
    { icon:'🔍', label:'Defect Types',  val: `${defs?.data?.length || 0}`,              col:'#ED7D31' },
    { icon:'📋', label:'Total Charts',  val: `${sections.filter(s => s.data?.length > 0).length}`, col:'#1F4E79' },
  ]

  return (
    <div style={{
      display:'grid',
      gridTemplateColumns:'repeat(auto-fit,minmax(130px,1fr))',
      gap:10, marginBottom:16,
    }}>
      {kpis.map((k, i) => (
        <div key={i} style={{
          background:'#fff', borderRadius:9,
          borderTop:`3px solid ${k.col}`,
          border:`1px solid #E0E0E0`,
          padding:'11px 13px',
          boxShadow:'0 1px 3px rgba(0,0,0,.05)',
        }}>
          <div style={{ fontSize:'1rem', marginBottom:4 }}>{k.icon}</div>
          <div style={{ fontSize:'1.05rem', fontWeight:800, color:k.col, fontFamily:"'Segoe UI',sans-serif" }}>
            {k.val}
          </div>
          <div style={{ fontSize:'.62rem', fontWeight:700, textTransform:'uppercase',
            letterSpacing:'.06em', color:'#888', marginTop:2 }}>
            {k.label}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main export ────────────────────────────────────────────────────────────
export default function HRCoilDashboard({ dashboard, filename }) {
  if (!dashboard) return null

  const { report_month, sections = [] } = dashboard
  const valid = sections.filter(s => s?.data?.length > 0)
  const rows  = buildRows(valid)

  return (
    <div style={{ background:'#F5F5F5', minHeight:'100vh' }}>

      {/* Header */}
      <div style={{
        background:'linear-gradient(135deg,#1F4E79,#2E6DA4)',
        padding:'13px 18px 11px',
      }}>
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <span style={{ fontSize:'1.2rem' }}>📊</span>
          <div>
            <h1 style={{
              fontFamily:"'Segoe UI',sans-serif", fontSize:'.92rem',
              fontWeight:700, color:'#fff', margin:0,
            }}>
              HR COIL MONTH WISE QUALITY BREAK UP
            </h1>
            <p style={{ color:'rgba(255,255,255,.65)', fontSize:'.68rem', margin:'2px 0 0' }}>
              {filename}
              {report_month ? ` · ${report_month}` : ''}
              {` · ${valid.length} charts`}
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ padding:'14px 14px 32px' }}>

        <KpiStrip month={report_month} sections={valid} />

        {rows.map((row, ri) => (
          <div
            key={ri}
            style={{
              display:'grid',
              gridTemplateColumns: row.cols === 1 ? '1fr' : '1fr 1fr',
              gap: 12,
              marginBottom: 12,
              alignItems: 'start',
            }}
          >
            {row.items.map((sec, ci) => (
              sec
                ? <Section key={sec.key || ci} section={sec} />
                : <div key={`empty-${ci}`} />   // empty slot for odd pies
            ))}
          </div>
        ))}

        <div style={{ textAlign:'center', paddingTop:14, fontSize:'.67rem', color:'#BBB' }}>
          HR Coil Quality Analytics · Data auto-detected from Excel · {valid.length} charts generated
        </div>
      </div>
    </div>
  )
}

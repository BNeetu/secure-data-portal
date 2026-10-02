import { useState } from 'react'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'
import { AXIS_STYLE, Card, COLORS, CustomTooltip, fmtNum, GRID_STYLE, SectionTitle } from './ChartKit'

const CAT = {
  daily:              { label:'Daily',                icon:'📅', type:'line',        badge:'Line Chart',   desc:'Day-by-day values showing short-term trends.' },
  cumulative_to_date: { label:'Cumulative Till Date', icon:'📈', type:'area',        badge:'Area Chart',   desc:'Running total accumulated over time.' },
  monthly:            { label:'Monthly',              icon:'🗓️', type:'line',        badge:'Line Chart',   desc:'Month-by-month aggregated totals.' },
  month_wise:         { label:'Month-wise',           icon:'🔁', type:'grouped-bar', badge:'Grouped Bar',  desc:'Same month compared across years.' },
  cumulative_months:  { label:'Cumulative of Months', icon:'📊', type:'area',        badge:'Area Chart',   desc:'Cumulative monthly running total.' },
  yearly:             { label:'Yearly',               icon:'🏆', type:'bar',         badge:'Bar Chart',    desc:'Annual totals compared side by side.' },
}
const ORDER = ['daily','cumulative_to_date','monthly','cumulative_months','month_wise','yearly']

export default function TimeSeriesSection({ timeseries }) {
  const [active, setActive] = useState(null)
  if (!timeseries?.detected) return null
  const { applicable_categories, charts, date_column, stats, selected_data_type } = timeseries
  const ordered = ORDER.filter(c => applicable_categories.includes(c))
  if (!ordered.length) return null
  const current = (active && ordered.includes(active)) ? active
    : (selected_data_type && ordered.includes(selected_data_type) ? selected_data_type : ordered[0])
  const info = CAT[current]
  const chartData = charts[current]
  const span = stats.distinct_years > 1
    ? `${stats.distinct_years} years · ${stats.distinct_months} months`
    : stats.distinct_months > 1
      ? `${stats.distinct_months} months · ${stats.distinct_days} days`
      : `${stats.distinct_days} day(s)`

  return (
    <div>
      <SectionTitle icon="⏱️" sub={`Date column: "${date_column}" · ${span} of data`}>
        Time-Based Analysis
      </SectionTitle>
      <Card title={`${info.icon} ${info.label}`} description={info.desc} badge={info.badge} accent="teal">
        <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:18 }}>
          {ordered.map(cat => {
            const ci = CAT[cat]; const isA = cat === current
            return (
              <button key={cat} onClick={() => setActive(cat)} style={{
                background:    isA ? '#1F4E79' : '#F5F5F5',
                border:        `1px solid ${isA ? '#1F4E79' : '#D6D6D6'}`,
                borderRadius:  20, padding:'6px 14px',
                fontSize:      '.77rem', fontWeight:700,
                color:         isA ? '#fff' : '#555',
                cursor:        'pointer', transition:'.13s',
              }}>
                {ci.icon} {ci.label}
              </button>
            )
          })}
        </div>
        <TSChart type={info.type} cd={chartData} cat={current} />
      </Card>
    </div>
  )
}

function TSChart({ type, cd, cat }) {
  if (!cd) return <div style={{textAlign:'center',padding:'36px',color:'#AAA'}}>No data.</div>
  if (cat === 'month_wise') return <MonthWise labels={cd.labels} years={cd.years} />

  const { labels, series } = cd
  const cols = Object.keys(series || {})
  if (!cols.length || !labels?.length)
    return <div style={{textAlign:'center',padding:'36px',color:'#AAA'}}>No series data.</div>

  const data = labels.map((lbl, i) => {
    const p = { name: lbl }
    cols.forEach(c => { p[c] = series[c][i] })
    return p
  })
  const tickInterval = labels.length > 40 ? Math.ceil(labels.length / 14) : 0
  const angled = labels.length > 12

  const shared = {
    grid: <CartesianGrid {...GRID_STYLE} />,
    x:    <XAxis dataKey="name" {...AXIS_STYLE} interval={tickInterval}
            angle={angled?-35:0} textAnchor={angled?'end':'middle'} height={angled?52:28}/>,
    y:    <YAxis {...AXIS_STYLE} tickFormatter={fmtNum} />,
    tt:   <Tooltip content={<CustomTooltip formatter={fmtNum}/>} cursor={{fill:'rgba(68,114,196,.06)'}}/>,
    leg:  cols.length > 1 ? <Legend wrapperStyle={{fontSize:11,color:'#555'}}/> : null,
  }

  if (type === 'line') return (
    <ResponsiveContainer width="100%" height={290}>
      <LineChart data={data} margin={{top:8,right:14,left:6,bottom:6}}>
        {shared.grid}{shared.x}{shared.y}{shared.tt}{shared.leg}
        {cols.map((c,i) => (
          <Line key={c} type="monotone" dataKey={c} stroke={COLORS[i]}
            strokeWidth={2} dot={labels.length<=30} activeDot={{r:4}} name={c}/>
        ))}
      </LineChart>
    </ResponsiveContainer>
  )

  if (type === 'area') return (
    <ResponsiveContainer width="100%" height={290}>
      <AreaChart data={data} margin={{top:8,right:14,left:6,bottom:6}}>
        <defs>
          {cols.map((c,i) => (
            <linearGradient key={c} id={`gts${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={COLORS[i]} stopOpacity={0.3}/>
              <stop offset="95%" stopColor={COLORS[i]} stopOpacity={0.02}/>
            </linearGradient>
          ))}
        </defs>
        {shared.grid}{shared.x}{shared.y}{shared.tt}{shared.leg}
        {cols.map((c,i) => (
          <Area key={c} type="monotone" dataKey={c} stroke={COLORS[i]}
            fill={`url(#gts${i})`} strokeWidth={2} name={c}/>
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )

  return (
    <ResponsiveContainer width="100%" height={290}>
      <BarChart data={data} margin={{top:8,right:14,left:6,bottom:6}}>
        {shared.grid}{shared.x}{shared.y}{shared.tt}{shared.leg}
        {cols.map((c,i) => (
          <Bar key={c} dataKey={c} fill={COLORS[i]} radius={[4,4,0,0]} name={c} maxBarSize={60}/>
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

function MonthWise({ labels, years }) {
  const yrKeys = Object.keys(years || {})
  if (!yrKeys.length) return null
  const data = (labels||[]).map((lbl,i) => {
    const p = { name: lbl }
    yrKeys.forEach(y => { p[y] = (years[y]||[])[i] || 0 })
    return p
  })
  return (
    <ResponsiveContainer width="100%" height={290}>
      <BarChart data={data} margin={{top:8,right:14,left:6,bottom:6}}>
        <CartesianGrid {...GRID_STYLE} vertical={false}/>
        <XAxis dataKey="name" {...AXIS_STYLE}/>
        <YAxis {...AXIS_STYLE} tickFormatter={fmtNum}/>
        <Tooltip content={<CustomTooltip formatter={fmtNum}/>}/>
        <Legend wrapperStyle={{fontSize:11,color:'#555'}}/>
        {yrKeys.map((y,i) => (
          <Bar key={y} dataKey={y} fill={COLORS[i]} radius={[4,4,0,0]} name={y} maxBarSize={44}/>
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

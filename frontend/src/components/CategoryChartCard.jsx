import {
  BarChart, Bar, PieChart, Pie, Cell, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { AXIS_STYLE, Card, COLORS, CustomTooltip, fmtNum, GRID_STYLE, humanize } from './ChartKit'

const ACCENT_LIST = ['indigo','teal','green','amber','purple','red','orange','blue']
function accentFor(col) {
  return ACCENT_LIST[Math.abs(col.split('').reduce((a,c)=>a+c.charCodeAt(0),0)) % ACCENT_LIST.length]
}

export default function CategoryChartCard({ column, breakdown }) {
  const spec = breakdown?.chart_spec
  if (!spec || spec.chart_type === 'kpi_only') return null

  const counts  = breakdown.counts || {}
  const entries = Object.entries(counts)
    .filter(([k]) => k && k !== 'null' && k !== 'undefined' && k !== 'nan')
    .sort((a,b) => b[1]-a[1])

  if (!entries.length) return (
    <Card title={humanize(column)} badge="No Data" accent="indigo">
      <div style={{textAlign:'center',padding:'32px',color:'#AAA',fontSize:'.82rem'}}>
        No chart data available.
      </div>
    </Card>
  )

  const data = entries.map(([name,value],i) => ({
    name: name.length > 26 ? name.slice(0,24)+'…' : name,
    fullName: name, value,
    fill: COLORS[i % COLORS.length],
  }))
  const total = entries.reduce((s,[,v]) => s+v, 0)
  const accent = accentFor(column)
  const badge = { donut:'Pie Chart', bar:'Bar Chart', horizontal_bar:'Bar Chart', radar:'Radar Chart' }[spec.chart_type] || 'Chart'

  return (
    <Card title={spec.title||humanize(column)} description={spec.description} badge={badge} accent={accent}>
      {spec.chart_type === 'donut'           && <DonutChart   data={data} total={total} />}
      {spec.chart_type === 'bar'             && <VerticalBar  data={data} xLabel={spec.x_label} yLabel={spec.y_label||'Count'} />}
      {spec.chart_type === 'horizontal_bar'  && <HorizBar     data={data} yLabel={spec.y_label||'Count'} />}
      {spec.chart_type === 'radar'           && <RadarView    data={data} />}
    </Card>
  )
}

function DonutChart({ data, total }) {
  const RADIAN = Math.PI / 180
  const label = ({ cx,cy,midAngle,innerRadius,outerRadius,percent }) => {
    if (percent < 0.05) return null
    const r = innerRadius + (outerRadius-innerRadius)*0.55
    return (
      <text x={cx+r*Math.cos(-midAngle*RADIAN)} y={cy+r*Math.sin(-midAngle*RADIAN)}
        fill="#fff" textAnchor="middle" dominantBaseline="central"
        fontSize={10} fontWeight={700}>
        {(percent*100).toFixed(0)}%
      </text>
    )
  }
  return (
    <div>
      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="fullName"
            cx="50%" cy="50%" outerRadius={95} innerRadius={48}
            paddingAngle={2} labelLine={false} label={label}
            stroke="#fff" strokeWidth={1.5}>
            {data.map((e,i) => <Cell key={i} fill={e.fill}/>)}
          </Pie>
          <Tooltip content={<CustomTooltip formatter={v=>`${fmtNum(v)} (${((v/total)*100).toFixed(1)}%)`}/>}/>
        </PieChart>
      </ResponsiveContainer>
      <div style={{display:'flex',flexWrap:'wrap',gap:'5px 12px',justifyContent:'center',marginTop:6}}>
        {data.slice(0,10).map((d,i) => (
          <div key={i} style={{display:'flex',alignItems:'center',gap:5,fontSize:'.71rem',color:'#555'}}>
            <span style={{width:8,height:8,borderRadius:'50%',background:d.fill,flexShrink:0,display:'inline-block'}}/>
            <span>{d.fullName}</span>
            <span style={{color:'#AAA'}}>({fmtNum(d.value)})</span>
          </div>
        ))}
        {data.length > 10 && <span style={{fontSize:'.67rem',color:'#CCC'}}>+{data.length-10} more</span>}
      </div>
    </div>
  )
}

function VerticalBar({ data, xLabel, yLabel }) {
  const angled = data.length > 5
  return (
    <ResponsiveContainer width="100%" height={290}>
      <BarChart data={data} margin={{top:12,right:14,left:6,bottom:angled?62:30}}>
        <CartesianGrid {...GRID_STYLE} vertical={false}/>
        <XAxis dataKey="name" {...AXIS_STYLE} interval={0}
          angle={angled?-35:0} textAnchor={angled?'end':'middle'} height={angled?66:34}
          label={{value:xLabel,position:'insideBottom',offset:angled?-54:-16,fill:'#777',fontSize:11}}/>
        <YAxis {...AXIS_STYLE} tickFormatter={fmtNum}
          label={{value:yLabel,angle:-90,position:'insideLeft',fill:'#777',fontSize:11,style:{textAnchor:'middle'}}}/>
        <Tooltip content={<CustomTooltip formatter={fmtNum}/>} cursor={{fill:'rgba(68,114,196,.06)'}}/>
        <Bar dataKey="value" name={yLabel} radius={[5,5,0,0]} maxBarSize={54}>
          {data.map((e,i) => <Cell key={i} fill={e.fill}/>)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function HorizBar({ data, yLabel }) {
  const capped = data.slice(0,20)
  const h = Math.max(270, capped.length*32)
  return (
    <div>
      <ResponsiveContainer width="100%" height={h}>
        <BarChart data={capped} layout="vertical" margin={{top:4,right:30,left:6,bottom:28}}>
          <CartesianGrid {...GRID_STYLE} horizontal={false}/>
          <XAxis type="number" {...AXIS_STYLE} tickFormatter={fmtNum}
            label={{value:yLabel||'Count',position:'insideBottom',offset:-16,fill:'#777',fontSize:11}}/>
          <YAxis type="category" dataKey="name" {...AXIS_STYLE} width={145}
            tick={{fill:'#555',fontSize:10.5}}/>
          <Tooltip content={<CustomTooltip formatter={fmtNum}/>} cursor={{fill:'rgba(68,114,196,.06)'}}/>
          <Bar dataKey="value" name={yLabel||'Count'} radius={[0,5,5,0]} maxBarSize={20}>
            {capped.map((e,i) => <Cell key={i} fill={e.fill}/>)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {data.length > 20 && (
        <div style={{fontSize:'.7rem',color:'#AAA',textAlign:'center',marginTop:5}}>
          Top 20 of {data.length} shown
        </div>
      )}
    </div>
  )
}

function RadarView({ data }) {
  return (
    <ResponsiveContainer width="100%" height={270}>
      <RadarChart data={data.slice(0,10)} cx="50%" cy="50%" outerRadius={90}>
        <PolarGrid stroke="#D9D9D9"/>
        <PolarAngleAxis dataKey="name" tick={{fill:'#777',fontSize:10}}/>
        <PolarRadiusAxis angle={30} tick={{fill:'#AAA',fontSize:9}} tickFormatter={fmtNum}/>
        <Radar name="Count" dataKey="value" stroke="#4472C4" fill="#4472C4" fillOpacity={0.2} strokeWidth={2}/>
        <Tooltip content={<CustomTooltip formatter={fmtNum}/>}/>
      </RadarChart>
    </ResponsiveContainer>
  )
}

// Shared chart primitives — light corporate theme, Excel-style colors
export const COLORS = [
  '#4472C4','#ED7D31','#A5A5A5','#FFC000','#70AD47',
  '#5B9BD5','#264478','#9E480E','#636363','#997300',
  '#255E91','#43682B','#698ED0','#F1975A','#B7B7B7',
]

export const AXIS_STYLE = {
  tick:     { fill:'#555555', fontSize:10, fontFamily:'Segoe UI' },
  axisLine: { stroke:'#D6D6D6' },
  tickLine: false,
}
export const GRID_STYLE = { stroke:'#D9D9D9', strokeDasharray:'3 3' }

export function fmtNum(n){
  if(n===null||n===undefined||isNaN(n)) return '—'
  const a=Math.abs(n)
  if(a>=1e9) return (n/1e9).toFixed(2)+'B'
  if(a>=1e6) return (n/1e6).toFixed(2)+'M'
  if(a>=1e3) return (n/1e3).toFixed(1)+'K'
  return Number.isInteger(n)?n.toString():n.toFixed(2)
}

export function humanize(s){
  if(!s) return ''
  let n=String(s)
  if(n.includes(':')) n=n.split(':')[0]
  return n.replace(/[_\-.]/g,' ').replace(/\s+/g,' ').trim()
    .replace(/\b\w/g,c=>c.toUpperCase())
}

export function CustomTooltip({active,payload,label,formatter}){
  if(!active||!payload?.length) return null
  return(
    <div style={{background:'#fff',border:'1px solid #D6D6D6',borderRadius:6,
      padding:'10px 14px',boxShadow:'0 2px 8px rgba(0,0,0,.12)',minWidth:140}}>
      {label&&<p style={{color:'#777',fontSize:11,marginBottom:5,fontWeight:600}}>{label}</p>}
      {payload.map((p,i)=>(
        <p key={i} style={{color:p.color||'#333',fontSize:12,marginBottom:2}}>
          <span style={{color:'#777'}}>{p.name}: </span>
          <strong>{formatter?formatter(p.value):p.value?.toLocaleString?.()??p.value}</strong>
        </p>
      ))}
    </div>
  )
}

export function SectionTitle({children,sub,icon}){
  return(
    <div style={{marginBottom:16,marginTop:4}}>
      <div style={{display:'flex',alignItems:'center',gap:10}}>
        {icon&&<span style={{fontSize:'1rem'}}>{icon}</span>}
        <span style={{fontFamily:"'Segoe UI',sans-serif",fontSize:'.7rem',fontWeight:700,
          textTransform:'uppercase',letterSpacing:'.1em',color:'#1F4E79'}}>{children}</span>
        <div style={{flex:1,height:1,background:'linear-gradient(90deg,#D6D6D6,transparent)'}}/>
      </div>
      {sub&&<p style={{fontSize:'.73rem',color:'#888',marginTop:4,paddingLeft:icon?28:0}}>{sub}</p>}
    </div>
  )
}

export function Card({title,description,badge,children,accent}){
  const accMap={
    indigo:'#4472C4',teal:'#2E6DA4',green:'#70AD47',amber:'#FFC000',
    purple:'#7030A0',red:'#C00000',orange:'#ED7D31',blue:'#1F4E79',
  }
  const col=accMap[accent]||accMap.indigo
  return(
    <div style={{
      background:'#fff',border:'1px solid #D6D6D6',borderRadius:10,
      overflow:'hidden',boxShadow:'0 1px 4px rgba(0,0,0,.08)',
      transition:'box-shadow .2s',
    }}
      onMouseEnter={e=>e.currentTarget.style.boxShadow='0 3px 12px rgba(0,0,0,.13)'}
      onMouseLeave={e=>e.currentTarget.style.boxShadow='0 1px 4px rgba(0,0,0,.08)'}
    >
      <div style={{height:3,background:col}}/>
      <div style={{padding:'16px 20px 0'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:8}}>
          <div style={{flex:1,minWidth:0}}>
            <div style={{fontFamily:"'Segoe UI',sans-serif",fontSize:'.88rem',fontWeight:700,
              color:'#333333',lineHeight:1.3}}>{title}</div>
            {description&&<div style={{fontSize:'.72rem',color:'#777',marginTop:5,lineHeight:1.5}}>{description}</div>}
          </div>
          {badge&&<span style={{background:'#F0F0F0',border:'1px solid #D6D6D6',borderRadius:4,
            padding:'2px 8px',fontSize:'.62rem',color:'#555',fontWeight:600,
            textTransform:'uppercase',letterSpacing:'.05em',whiteSpace:'nowrap',flexShrink:0}}>{badge}</span>}
        </div>
      </div>
      <div style={{padding:'14px 20px 20px'}}>{children}</div>
    </div>
  )
}

export function KpiCard({icon,label,value,sub,accent='indigo'}){
  const accMap={
    indigo:'#4472C4',teal:'#2E6DA4',green:'#70AD47',
    amber:'#FFC000',purple:'#7030A0',red:'#C00000',orange:'#ED7D31',
  }
  const col=accMap[accent]||accMap.indigo
  return(
    <div style={{
      background:'#fff',border:'1px solid #D6D6D6',
      borderTop:`3px solid ${col}`,borderRadius:10,
      padding:'18px 20px',boxShadow:'0 1px 4px rgba(0,0,0,.07)',
      animation:'fadeUp .3s ease',
    }}>
      <div style={{fontSize:'1.4rem',marginBottom:8}}>{icon}</div>
      <div style={{fontFamily:"'Segoe UI',sans-serif",fontSize:'1.5rem',fontWeight:700,
        color:col,lineHeight:1,marginBottom:5}}>{value}</div>
      <div style={{fontSize:'.68rem',fontWeight:700,textTransform:'uppercase',
        letterSpacing:'.07em',color:'#777',marginBottom:3}}>{label}</div>
      {sub&&<div style={{fontSize:'.68rem',color:'#AAA',lineHeight:1.4}}>{sub}</div>}
    </div>
  )
}

export function EmptyState({icon='📂',title,sub,action}){
  return(
    <div style={{textAlign:'center',padding:'80px 20px',animation:'fadeUp .4s ease'}}>
      <div style={{fontSize:'3.5rem',marginBottom:16,opacity:.6}}>{icon}</div>
      <h2 style={{fontFamily:"'Segoe UI',sans-serif",fontSize:'1.15rem',fontWeight:700,
        color:'#555',marginBottom:8}}>{title}</h2>
      <p style={{fontSize:'.83rem',color:'#888',maxWidth:420,margin:'0 auto 22px',lineHeight:1.6}}>{sub}</p>
      {action}
    </div>
  )
}

export function Spinner({size=36}){
  return <div style={{width:size,height:size,border:`3px solid #E8E8E8`,
    borderTop:`3px solid #4472C4`,borderRadius:'50%',animation:'spin 1s linear infinite'}}/>
}

export function Badge({children,color='indigo'}){
  const cmap={indigo:'#4472C4',green:'#70AD47',amber:'#FFC000',red:'#C00000',orange:'#ED7D31'}
  const col=cmap[color]||cmap.indigo
  return <span style={{background:`${col}18`,border:`1px solid ${col}44`,borderRadius:20,
    padding:'2px 9px',fontSize:'.65rem',color:col,fontWeight:700}}>{children}</span>
}

export default {}

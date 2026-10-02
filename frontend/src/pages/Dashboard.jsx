import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
  ScatterChart, Scatter, ResponsiveContainer, ZAxis,
} from 'recharts'
import { useAuth } from '../context/AuthContext'
import { useLiveDashboard } from '../api/useLiveDashboard'
import api from '../api/client'
import UploadWidget from '../components/UploadWidget'
import TimeSeriesSection from '../components/TimeSeriesSection'
import CategoryChartCard from '../components/CategoryChartCard'
import HRCoilDashboard from '../components/HRCoilDashboard'
import {
  AXIS_STYLE, Card, COLORS, CustomTooltip, EmptyState,
  fmtNum, GRID_STYLE, humanize, KpiCard, SectionTitle, Spinner,
} from '../components/ChartKit'

const TYPE_LABELS = {
  daily:'Daily', cumulative_to_date:'Cumulative Till Date', monthly:'Monthly',
  month_wise:'Month-wise', cumulative_months:'Cumulative of Months', yearly:'Yearly',
}
const KPI_ACCENTS = ['indigo','teal','green','amber','purple','red','indigo','teal']
const KPI_ICONS   = ['📊','📈','💡','🎯','⚙️','📉','🔢','💰']

// ── topbar button helper ─────────────────────────────────────────────────
const hBtn=(bg,col,bdr)=>({
  background:bg, border:`1px solid ${bdr||col}`,
  borderRadius:7, padding:'6px 13px', fontSize:'.75rem',
  color:col, cursor:'pointer', fontWeight:700, transition:'.15s', whiteSpace:'nowrap',
})

export default function Dashboard() {
  const { department, subdepartment, dataType } = useParams()
  const { user, logout, idleWarning, resetIdleTimer } = useAuth()
  const navigate = useNavigate()
  const canUpload = user?.role==='admin'||user?.role==='manager'

  const { fileList, connected, refetch } = useLiveDashboard(department, subdepartment, dataType)

  const [selectedFileId, setSelectedFileId] = useState(null)
  const [fileData, setFileData]             = useState(null)
  const [fileLoading, setFileLoading]       = useState(false)
  const [clearing, setClearing]             = useState(false)
  const [search, setSearch]                 = useState('')
  const [sortCol, setSortCol]               = useState(null)
  const [sortDir, setSortDir]               = useState('desc')
  const [uploadSignal, setUploadSignal]     = useState(0)

  const handleLogout = async()=>{await logout();navigate('/login')}

  const loadFile = useCallback(async(fileId)=>{
    if(!fileId){setFileData(null);setSelectedFileId(null);return}
    setFileLoading(true);setSelectedFileId(fileId)
    try {
      const enc=s=>encodeURIComponent(s)
      const {data}=await api.get(
        `/data/${enc(department)}/${enc(subdepartment)}/${enc(dataType)}/dashboard/${fileId}`)
      setFileData(data)
    } catch(e){setFileData(null)}
    finally{setFileLoading(false)}
  },[department,subdepartment,dataType])

  useEffect(()=>{
    if(!fileList.length){setFileData(null);setSelectedFileId(null);return}
    if(selectedFileId){
      const still=fileList.find(f=>f.id===selectedFileId)
      if(still) loadFile(selectedFileId)
      else{setSelectedFileId(null);setFileData(null)}
    }
  },[fileList])

  const handleClearData=async()=>{
    if(!confirm(`Remove ALL files for ${subdepartment} › ${TYPE_LABELS[dataType]}?`)) return
    setClearing(true)
    try{
      const enc=s=>encodeURIComponent(s)
      await api.delete(`/data/${enc(department)}/${enc(subdepartment)}/${enc(dataType)}/clear`)
      setFileData(null);setSelectedFileId(null)
    }catch(e){alert(e.response?.data?.detail||'Clear failed')}
    finally{setClearing(false)}
  }

  const handleRemoveFile=async(fileId,filename)=>{
    if(!confirm(`Remove "${filename}"?`)) return
    try{
      const enc=s=>encodeURIComponent(s)
      await api.delete(`/data/${enc(department)}/${enc(subdepartment)}/${enc(dataType)}/files/${fileId}`)
      if(selectedFileId===fileId){setSelectedFileId(null);setFileData(null)}
      refetch()
    }catch(e){alert(e.response?.data?.detail||'Remove failed')}
  }

  const data      = fileData?.data
  const filename  = fileData?.filename||data?._filename
  const meta      = data?.meta
  const kpis      = data?.kpis||{}
  const breakdowns= data?.breakdowns||{}
  const topN      = data?.top_n||{}
  const corr      = data?.correlation_chart
  const dists     = data?.distributions||{}
  const records   = data?.records||[]
  const isHrCoil  = data?.render_mode==='hr_coil'&&data?.hr_coil_dashboard

  const filteredRecords=useMemo(()=>{
    let rows=records
    if(search){
      const q=search.toLowerCase()
      rows=rows.filter(r=>Object.values(r).some(v=>String(v??'').toLowerCase().includes(q)))
    }
    if(sortCol){
      rows=[...rows].sort((a,b)=>{
        const av=a[sortCol],bv=b[sortCol]
        if(av==null)return 1;if(bv==null)return -1
        if(typeof av==='number'&&typeof bv==='number')
          return sortDir==='desc'?bv-av:av-bv
        return sortDir==='desc'
          ?String(bv).localeCompare(String(av))
          :String(av).localeCompare(String(bv))
      })
    }
    return rows.slice(0,500)
  },[records,search,sortCol,sortDir])

  const toggleSort=col=>{
    if(sortCol===col) setSortDir(d=>d==='desc'?'asc':'desc')
    else{setSortCol(col);setSortDir('desc')}
  }

  return(
    <div onMouseMove={resetIdleTimer} onKeyDown={resetIdleTimer}
      style={{minHeight:'100vh',background:'#F5F5F5',display:'flex',flexDirection:'column'}}>

      {idleWarning&&(
        <div style={{position:'fixed',top:0,left:0,right:0,zIndex:3000,
          background:'#FFC000',color:'#333',padding:'9px 20px',
          textAlign:'center',fontSize:'.82rem',fontWeight:700}}>
          ⚠️ Session expiring in 60 seconds — click anywhere to stay signed in.
        </div>
      )}

      {/* Topbar */}
      <header style={{
        background:'linear-gradient(135deg,#1F4E79,#2E6DA4)',
        borderBottom:'1px solid #1A4268',padding:'0 22px',
        position:'sticky',top:idleWarning?40:0,zIndex:200,
        boxShadow:'0 2px 8px rgba(0,0,0,.12)',flexShrink:0,
      }}>
        <div style={{maxWidth:1700,margin:'0 auto',height:60,
          display:'flex',alignItems:'center',justifyContent:'space-between',
          gap:12,flexWrap:'wrap'}}>
          <div style={{display:'flex',alignItems:'center',gap:12}}>
            <div style={{width:32,height:32,background:'rgba(255,255,255,.2)',
              borderRadius:8,display:'flex',alignItems:'center',
              justifyContent:'center',fontSize:'.9rem',flexShrink:0}}>🔒</div>
            <div>
              <div onClick={()=>navigate('/dashboard')}
                style={{fontFamily:"'Segoe UI',sans-serif",fontSize:'.95rem',
                  fontWeight:700,cursor:'pointer',color:'#fff'}}>
                Secure Data Portal
              </div>
              <div style={{fontSize:'.62rem',color:'rgba(255,255,255,.65)',
                display:'flex',alignItems:'center',gap:5}}>
                <span style={{width:6,height:6,borderRadius:'50%',
                  background:connected?'#92D050':'#FF6666',display:'inline-block'}}/>
                <span>{connected?'Live':'Reconnecting…'}</span>
                <span style={{opacity:.5}}>·</span>
                <span>{department}</span>
                <span style={{opacity:.5}}>›</span>
                <span>{subdepartment}</span>
                <span style={{opacity:.5}}>›</span>
                <span style={{color:'#ADD8FF'}}>{TYPE_LABELS[dataType]||dataType}</span>
              </div>
            </div>
          </div>
          <div style={{display:'flex',alignItems:'center',gap:7,flexWrap:'wrap'}}>
            <button onClick={()=>navigate('/dashboard')} style={hBtn('rgba(255,255,255,.15)','#fff','rgba(255,255,255,.3)')}>
              ↩ Departments
            </button>
            {canUpload&&department&&subdepartment&&dataType&&(
              <UploadWidget department={department} subdepartment={subdepartment}
                dataType={dataType} onUploaded={()=>{setUploadSignal(s=>s+1);refetch()}}/>
            )}
            {canUpload&&fileList.length>0&&(
              <button onClick={handleClearData} disabled={clearing}
                style={hBtn('rgba(192,0,0,.3)','#FFB3B3','rgba(255,150,150,.4)')}>
                🗑️ {clearing?'Clearing…':'Clear All'}
              </button>
            )}
            {user?.role==='admin'&&(
              <button onClick={()=>navigate('/admin')}
                style={hBtn('rgba(255,255,255,.15)','#fff','rgba(255,255,255,.3)')}>
                ⚙️ Admin
              </button>
            )}
            <div style={{background:'rgba(255,255,255,.15)',borderRadius:7,
              padding:'5px 11px',fontSize:'.72rem',color:'#fff',
              display:'flex',alignItems:'center',gap:6}}>
              👤 <span>{user?.username}</span>
              <span style={{background:'rgba(255,255,255,.2)',borderRadius:4,
                padding:'1px 6px',fontSize:'.62rem',textTransform:'capitalize'}}>
                {user?.role}
              </span>
            </div>
            <button onClick={handleLogout}
              style={hBtn('rgba(192,0,0,.3)','#FFB3B3','rgba(255,150,150,.4)')}>
              Logout
            </button>
          </div>
        </div>
      </header>

      <div style={{display:'flex',flex:1,maxWidth:1700,width:'100%',margin:'0 auto',minHeight:0}}>

        {/* Sidebar */}
        <aside style={{
          width:270,flexShrink:0,background:'#fff',
          borderRight:'1px solid #D6D6D6',padding:'18px 0',
          position:'sticky',top:60,height:'calc(100vh - 60px)',
          overflowY:'auto',
        }}>
          <div style={{padding:'0 14px 10px',fontSize:'.66rem',fontWeight:700,
            textTransform:'uppercase',letterSpacing:'.1em',color:'#888'}}>
            Uploaded Files ({fileList.length})
          </div>

          {fileList.length===0?(
            <div style={{padding:'16px',fontSize:'.78rem',color:'#AAA',lineHeight:1.5}}>
              {canUpload?'Upload an Excel file to get started.':'No files uploaded yet.'}
            </div>
          ):(
            <div style={{display:'flex',flexDirection:'column',gap:2,padding:'0 6px'}}>
              {fileList.map(f=>{
                const isSel=selectedFileId===f.id
                return(
                  <div key={f.id} style={{
                    background:isSel?'#EDF2F9':'transparent',
                    border:`1px solid ${isSel?'#4472C4':'transparent'}`,
                    borderRadius:8,padding:'10px 11px',cursor:'pointer',
                    transition:'.13s',position:'relative',
                  }}
                    onMouseEnter={e=>{if(!isSel)e.currentTarget.style.background='#F5F5F5'}}
                    onMouseLeave={e=>{if(!isSel)e.currentTarget.style.background='transparent'}}
                    onClick={()=>loadFile(f.id)}>
                    <div style={{display:'flex',alignItems:'flex-start',gap:8}}>
                      <span style={{fontSize:'1rem',flexShrink:0,marginTop:1}}>
                        {isSel?'📊':'📄'}
                      </span>
                      <div style={{minWidth:0,flex:1}}>
                        <div style={{fontSize:'.76rem',fontWeight:isSel?700:600,
                          color:isSel?'#1F4E79':'#444',
                          wordBreak:'break-word',lineHeight:1.3}}>
                          {f.filename}
                        </div>
                        <div style={{fontSize:'.65rem',color:'#999',marginTop:3}}>
                          {f.rows!=null?`${f.rows.toLocaleString()} rows · `:''}
                          {f.uploaded_by}
                        </div>
                        <div style={{fontSize:'.62rem',color:'#CCC',marginTop:2}}>
                          {new Date(f.uploaded_at*1000).toLocaleDateString('en-IN',
                            {day:'numeric',month:'short',year:'numeric'})}
                        </div>
                        {/* Download charts link */}
                        <a
                          href={`/data/${encodeURIComponent(department)}/${encodeURIComponent(subdepartment)}/${encodeURIComponent(dataType)}/files/${f.id}/download-charts`}
                          onClick={e=>e.stopPropagation()}
                          download
                          style={{fontSize:'.62rem',color:'#70AD47',textDecoration:'none',
                            background:'#EBF5E0',border:'1px solid #B8DFA0',borderRadius:4,
                            padding:'2px 7px',fontWeight:700,display:'inline-block',marginTop:5}}>
                          📥 Charts
                        </a>
                      </div>
                    </div>
                    {canUpload&&(
                      <button
                        onClick={e=>{e.stopPropagation();handleRemoveFile(f.id,f.filename)}}
                        title="Remove file"
                        style={{position:'absolute',top:6,right:7,background:'none',border:'none',
                          color:'#CCC',cursor:'pointer',fontSize:'.72rem',padding:'2px 4px',
                          borderRadius:4}}
                        onMouseEnter={e=>e.currentTarget.style.color='#C00000'}
                        onMouseLeave={e=>e.currentTarget.style.color='#CCC'}>
                        ✕
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </aside>

        {/* Main */}
        <main style={{flex:1,padding:'24px 24px',overflowX:'hidden',minWidth:0}}>

          {fileList.length===0&&(
            <EmptyState icon="📂"
              title={`No files yet — ${TYPE_LABELS[dataType]||dataType}`}
              sub={canUpload
                ?'Upload an Excel file using the button above. Charts appear instantly.'
                :'An administrator or manager needs to upload data here.'}
              action={canUpload&&(
                <UploadWidget department={department} subdepartment={subdepartment}
                  dataType={dataType} onUploaded={()=>{setUploadSignal(s=>s+1);refetch()}}/>
              )}
            />
          )}

          {fileList.length>0&&!selectedFileId&&(
            <div style={{animation:'fadeUp .35s ease'}}>
              <div style={{marginBottom:24}}>
                <h2 style={{fontFamily:"'Segoe UI',sans-serif",fontSize:'1.15rem',
                  fontWeight:700,color:'#1F4E79',marginBottom:6}}>
                  {department} · {subdepartment}
                </h2>
                <p style={{fontSize:'.82rem',color:'#666',lineHeight:1.5,maxWidth:580}}>
                  <strong style={{color:'#333'}}>{fileList.length} file{fileList.length>1?'s':''}</strong> uploaded
                  for <strong style={{color:'#333'}}>{TYPE_LABELS[dataType]}</strong>.
                  Select a file from the panel to view its charts.
                </p>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(280px,1fr))',gap:14}}>
                {fileList.map((f,i)=>(
                  <div key={f.id} onClick={()=>loadFile(f.id)} style={{
                    background:'#fff',border:'1px solid #D6D6D6',borderRadius:12,
                    padding:'18px 20px',cursor:'pointer',transition:'.15s',
                    boxShadow:'0 1px 4px rgba(0,0,0,.06)',
                  }}
                    onMouseEnter={e=>{e.currentTarget.style.borderColor='#4472C4';e.currentTarget.style.boxShadow='0 4px 14px rgba(0,0,0,.10)'}}
                    onMouseLeave={e=>{e.currentTarget.style.borderColor='#D6D6D6';e.currentTarget.style.boxShadow='0 1px 4px rgba(0,0,0,.06)'}}>
                    <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:10}}>
                      <div style={{width:40,height:40,
                        background:'#EDF2F9',border:'1px solid #D6D6D6',
                        borderRadius:8,display:'flex',alignItems:'center',
                        justifyContent:'center',fontSize:'1.2rem'}}>📊</div>
                      <div style={{minWidth:0}}>
                        <div style={{fontSize:'.85rem',fontWeight:700,color:'#1F4E79',
                          wordBreak:'break-word',lineHeight:1.3}}>{f.filename}</div>
                        <div style={{fontSize:'.7rem',color:'#888',marginTop:2}}>
                          {f.rows!=null?`${f.rows.toLocaleString()} rows · `:''}{f.uploaded_by}
                        </div>
                      </div>
                    </div>
                    <div style={{fontSize:'.69rem',color:'#AAA'}}>
                      {new Date(f.uploaded_at*1000).toLocaleString('en-IN')}
                    </div>
                    <div style={{marginTop:10,color:'#4472C4',fontSize:'.74rem',fontWeight:700}}>
                      View Charts →
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {selectedFileId&&fileLoading&&(
            <div style={{display:'flex',justifyContent:'center',padding:'80px'}}>
              <Spinner size={44}/>
            </div>
          )}

          {selectedFileId&&!fileLoading&&data&&(
            isHrCoil
              ? <HRCoilDashboard dashboard={data.hr_coil_dashboard} filename={filename}/>
              : <GenericDashboard {...{data,filename,meta,kpis,breakdowns,topN,corr,dists,
                  filteredRecords,search,setSearch,sortCol,sortDir,toggleSort}}/>
          )}

          {selectedFileId&&!fileLoading&&!data&&(
            <EmptyState icon="⚠️" title="Could not load file data"
              sub="The file may have been removed or expired. Try re-uploading."/>
          )}
        </main>
      </div>
    </div>
  )
}

// ── Generic dashboard (non-HR-Coil files) ────────────────────────────────
function GenericDashboard({data,filename,meta,kpis,breakdowns,topN,corr,dists,
  filteredRecords,search,setSearch,sortCol,sortDir,toggleSort}){
  const categoricalCols=meta?.categorical_columns||[]
  const sourceSheet=meta?.source_sheet

  return(
    <div style={{animation:'fadeUp .3s ease'}}>
      {/* File header */}
      <div style={{background:'#fff',border:'1px solid #D6D6D6',borderRadius:12,
        padding:'16px 22px',marginBottom:22,
        boxShadow:'0 1px 4px rgba(0,0,0,.06)'}}>
        <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:5,flexWrap:'wrap'}}>
          <span style={{fontSize:'1.3rem'}}>📊</span>
          <h2 style={{fontFamily:"'Segoe UI',sans-serif",fontSize:'1rem',fontWeight:700,
            color:'#1F4E79',wordBreak:'break-all',margin:0}}>{filename}</h2>
        </div>
        <div style={{display:'flex',gap:14,flexWrap:'wrap',fontSize:'.72rem',color:'#888'}}>
          <span>📋 {meta?.row_count?.toLocaleString()} rows</span>
          <span>·</span>
          <span>{meta?.column_count} columns</span>
          {sourceSheet&&<><span>·</span><span>Sheet: <strong style={{color:'#555'}}>{sourceSheet}</strong></span></>}
        </div>
      </div>

      {/* KPIs */}
      {Object.keys(kpis).length>0&&(
        <>
          <SectionTitle icon="📊"
            sub="Summary statistics from all numeric columns.">Key Metrics</SectionTitle>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(185px,1fr))',
            gap:13,marginBottom:28}}>
            {Object.entries(kpis).slice(0,8).map(([col,k],i)=>(
              <KpiCard key={col} icon={['📊','📈','💡','🎯','⚙️','📉','🔢','💰'][i%8]}
                value={fmtNum(k.sum)} label={k.label||humanize(col)}
                sub={`Avg ${fmtNum(k.avg)} · Min ${fmtNum(k.min)} · Max ${fmtNum(k.max)}`}
                accent={KPI_ACCENTS[i%KPI_ACCENTS.length]}/>
            ))}
          </div>
        </>
      )}

      {/* Time series */}
      {data?.timeseries?.detected&&(
        <div style={{marginBottom:28}}>
          <TimeSeriesSection timeseries={data.timeseries}/>
        </div>
      )}

      {/* Category breakdowns */}
      {categoricalCols.length>0&&(
        <>
          <SectionTitle icon="🔍"
            sub="Each chart shows one categorical dimension — type chosen automatically.">
            Category Breakdowns
          </SectionTitle>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(420px,1fr))',
            gap:18,marginBottom:28}}>
            {categoricalCols.map(col=>(
              <CategoryChartCard key={col} column={col} breakdown={breakdowns[col]}/>
            ))}
          </div>
        </>
      )}

      {/* Distributions */}
      {Object.keys(dists).length>0&&(
        <>
          <SectionTitle icon="📐"
            sub="Value spread for each numeric column — reveals range, skew, and outliers.">
            Value Distributions
          </SectionTitle>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(420px,1fr))',
            gap:18,marginBottom:28}}>
            {Object.entries(dists).slice(0,8).map(([col,dist])=>(
              <DistChart key={col} dist={dist}/>
            ))}
          </div>
        </>
      )}

      {/* Correlation */}
      {corr&&(
        <>
          <SectionTitle icon="🔗"
            sub={`Auto-detected correlation (r=${corr.correlation}).`}>
            Correlation Analysis
          </SectionTitle>
          <div style={{marginBottom:28}}>
            <Card title={corr.title} description={corr.description} badge="Scatter Plot" accent="indigo">
              <ScatterCard corr={corr} records={filteredRecords}/>
            </Card>
          </div>
        </>
      )}

      {/* Top-N */}
      {Object.keys(topN).length>0&&(
        <>
          <SectionTitle icon="🏆"
            sub="Top 10 entries ranked by each key numeric column.">
            Top 10 Rankings
          </SectionTitle>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(420px,1fr))',
            gap:18,marginBottom:28}}>
            {Object.entries(topN).slice(0,6).map(([col,entry],i)=>(
              <Card key={col} title={entry.title} description={entry.description}
                badge="Ranked Chart" accent={KPI_ACCENTS[i%KPI_ACCENTS.length]}>
                <TopNChart entry={entry}/>
              </Card>
            ))}
          </div>
        </>
      )}

      {/* Data table */}
      <SectionTitle icon="📋"
        sub={`All ${meta?.row_count?.toLocaleString()} records. Click headers to sort.`}>
        Full Data Table
      </SectionTitle>
      <Card title={filename||'Records'}
        badge={`${filteredRecords.length} / ${meta?.row_count?.toLocaleString()} rows`}
        accent="indigo">
        <div style={{display:'flex',gap:10,marginBottom:13,flexWrap:'wrap',alignItems:'center'}}>
          <input value={search} onChange={e=>setSearch(e.target.value)}
            placeholder="🔍 Search all columns…"
            style={{background:'#F9F9F9',border:'1px solid #D6D6D6',borderRadius:7,
              padding:'7px 13px',color:'#333',fontSize:'.81rem',outline:'none',width:270,
              boxShadow:'inset 0 1px 3px rgba(0,0,0,.04)'}}/>
          {search&&<button onClick={()=>setSearch('')}
            style={{background:'none',border:'none',color:'#AAA',cursor:'pointer',fontSize:'.8rem'}}>
            ✕ Clear
          </button>}
        </div>
        <div style={{overflowX:'auto',maxHeight:460,overflowY:'auto',
          borderRadius:8,border:'1px solid #E0E0E0'}}>
          <table style={{width:'100%',borderCollapse:'collapse',fontSize:'.79rem'}}>
            <thead>
              <tr>
                {(meta?.columns||[]).map(col=>(
                  <th key={col} onClick={()=>toggleSort(col)} style={{
                    background:'#F5F5F5',color:sortCol===col?'#1F4E79':'#555',
                    padding:'10px 13px',textAlign:'left',fontSize:'.66rem',
                    textTransform:'uppercase',letterSpacing:'.05em',fontWeight:700,
                    position:'sticky',top:0,whiteSpace:'nowrap',cursor:'pointer',
                    userSelect:'none',borderBottom:'1px solid #D6D6D6',
                  }}>
                    {humanize(col)}{sortCol===col?(sortDir==='desc'?' ↓':' ↑'):''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRecords.map((r,i)=>(
                <tr key={i} style={{borderBottom:'1px solid #F0F0F0'}}
                  onMouseEnter={e=>e.currentTarget.style.background='#F9F9F9'}
                  onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                  {(meta?.columns||[]).map(col=>{
                    const v=r[col]; const isNum=typeof v==='number'
                    return(
                      <td key={col} style={{padding:'8px 13px',whiteSpace:'nowrap',
                        color:isNum?'#264478':'#444'}}>
                        {v===null||v===undefined
                          ?<span style={{color:'#DDD'}}>—</span>
                          :isNum?fmtNum(v):String(v)}
                      </td>
                    )
                  })}
                </tr>
              ))}
              {filteredRecords.length===0&&(
                <tr><td colSpan={999} style={{padding:'32px',textAlign:'center',color:'#AAA'}}>
                  No records match.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <div style={{textAlign:'center',padding:'28px 0 4px',fontSize:'.7rem',color:'#CCC'}}>
        Secure Data Portal · Data processed in memory · No permanent database storage
      </div>
    </div>
  )
}

function DistChart({dist}){
  const {buckets,chart_spec}=dist
  if(!buckets?.length) return null
  const data=buckets.map((b,i)=>({...b,fill:COLORS[i%COLORS.length]}))
  return(
    <Card title={chart_spec.title} description={chart_spec.description} badge="Histogram" accent="teal">
      <ResponsiveContainer width="100%" height={230}>
        <BarChart data={data} margin={{top:8,right:14,left:6,bottom:52}}>
          <CartesianGrid {...GRID_STYLE} vertical={false}/>
          <XAxis dataKey="name" {...AXIS_STYLE} angle={-35} textAnchor="end" height={58}/>
          <YAxis {...AXIS_STYLE} tickFormatter={fmtNum}/>
          <Tooltip content={<CustomTooltip formatter={v=>v.toLocaleString()}/>}
            cursor={{fill:'rgba(68,114,196,.06)'}}/>
          <Bar dataKey="value" name="Count" radius={[4,4,0,0]} maxBarSize={46}>
            {data.map((e,i)=><Cell key={i} fill={e.fill}/>)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}

function TopNChart({entry}){
  const data=(entry.rows||[]).map((r,i)=>({
    name:(r.label?.length>26?r.label.slice(0,24)+'…':r.label)||'—',
    value:r.value,fill:COLORS[i%COLORS.length],
  }))
  return(
    <ResponsiveContainer width="100%" height={Math.max(250,data.length*30)}>
      <BarChart data={data} layout="vertical"
        margin={{top:4,right:30,left:6,bottom:24}}>
        <CartesianGrid {...GRID_STYLE} horizontal={false}/>
        <XAxis type="number" {...AXIS_STYLE} tickFormatter={fmtNum}/>
        <YAxis type="category" dataKey="name" {...AXIS_STYLE} width={140}
          tick={{fill:'#555',fontSize:10.5}}/>
        <Tooltip content={<CustomTooltip formatter={fmtNum}/>}
          cursor={{fill:'rgba(68,114,196,.06)'}}/>
        <Bar dataKey="value" name={entry.value_label} radius={[0,5,5,0]} maxBarSize={20}>
          {data.map((e,i)=><Cell key={i} fill={e.fill}/>)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function ScatterCard({corr,records}){
  const xCol=corr.x_column||corr.x_col
  const yCol=corr.y_column||corr.y_col
  if(!xCol||!yCol) return null
  const pts=records
    .filter(r=>r[xCol]!=null&&r[yCol]!=null&&typeof r[xCol]==='number'&&typeof r[yCol]==='number')
    .slice(0,400).map(r=>({x:r[xCol],y:r[yCol]}))
  if(!pts.length) return<div style={{padding:24,color:'#AAA',textAlign:'center'}}>No data.</div>
  const xLabel=corr.x_label||humanize(xCol)
  const yLabel=corr.y_label||humanize(yCol)
  return(
    <ResponsiveContainer width="100%" height={280}>
      <ScatterChart margin={{top:8,right:18,left:6,bottom:26}}>
        <CartesianGrid {...GRID_STYLE}/>
        <XAxis type="number" dataKey="x" name={xLabel} {...AXIS_STYLE}
          label={{value:xLabel,position:'insideBottom',offset:-18,fill:'#777',fontSize:11}}/>
        <YAxis type="number" dataKey="y" name={yLabel} {...AXIS_STYLE}
          label={{value:yLabel,angle:-90,position:'insideLeft',fill:'#777',fontSize:11,style:{textAnchor:'middle'}}}/>
        <ZAxis range={[26,26]}/>
        <Tooltip cursor={{strokeDasharray:'3 3'}}
          content={({active,payload})=>{
            if(!active||!payload?.length) return null
            return(
              <div style={{background:'#fff',border:'1px solid #D6D6D6',borderRadius:6,padding:'9px 13px'}}>
                <p style={{color:'#777',fontSize:11}}>{xLabel}: <strong style={{color:'#333'}}>{fmtNum(payload[0]?.value)}</strong></p>
                <p style={{color:'#777',fontSize:11}}>{yLabel}: <strong style={{color:'#333'}}>{fmtNum(payload[1]?.value)}</strong></p>
              </div>
            )
          }}/>
        <Scatter data={pts} fill="#4472C4" fillOpacity={0.6}/>
      </ScatterChart>
    </ResponsiveContainer>
  )
}

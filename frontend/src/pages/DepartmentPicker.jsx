import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Spinner } from '../components/ChartKit'

const DEPT_ICONS   = { 'Labs':'🧪', 'Production Units':'🏭' }
const SUB_ICONS    = {
  'Coke Oven Lab':'🔥','BF Lab':'🧫','Sinter Lab':'🧱','BPP Lab':'⚗️',
  'SMS Lab':'🔬','HSM Lab':'🧰','Sinter Plant':'🧱','Coke Oven':'🔥',
  'BF':'🏗️','SMS (Grade Chemistry)':'🧪','TSC':'🚂','HSM (Grade FT & CT)':'🧰',
}
const TYPE_ICONS = {
  daily:'📅',cumulative_to_date:'📈',monthly:'🗓️',
  month_wise:'🔁',cumulative_months:'📊',yearly:'🏆',
}
const TYPE_COLORS = {
  daily:'#4472C4',cumulative_to_date:'#2E6DA4',monthly:'#70AD47',
  month_wise:'#FFC000',cumulative_months:'#7030A0',yearly:'#C00000',
}

function hdrBtn(col){
  return{background:'#fff',border:`1px solid ${col}`,borderRadius:7,
    padding:'6px 13px',fontSize:'.75rem',color:col,cursor:'pointer',
    fontWeight:700,transition:'.15s',whiteSpace:'nowrap'}
}

export default function DepartmentPicker(){
  const navigate=useNavigate()
  const {user,logout}=useAuth()
  const [departments,setDepartments]=useState([])
  const [dataTypes,setDataTypes]=useState([])
  const [slots,setSlots]=useState([])
  const [loading,setLoading]=useState(true)
  const [openDept,setOpenDept]=useState(null)
  const [openSub,setOpenSub]=useState(null)

  useEffect(()=>{
    Promise.all([api.get('/data/departments'),api.get('/data/slots')])
      .then(([d,s])=>{
        setDepartments(d.data.departments)
        setDataTypes(d.data.data_types)
        setSlots(s.data.slots||[])
      })
      .catch(()=>{})
      .finally(()=>setLoading(false))
  },[])

  const slotInfo=(dept,sub,key)=>slots.find(s=>s.department===dept&&s.subdepartment===sub&&s.data_type===key)
  const subCount=(dept,sub)=>slots.filter(s=>s.department===dept&&s.subdepartment===sub).reduce((n,s)=>n+s.file_count,0)
  const handleLogout=async()=>{await logout();navigate('/login')}

  return(
    <div style={{minHeight:'100vh',background:'#F5F5F5'}}>

      {/* Topbar */}
      <header style={{background:'linear-gradient(135deg,#1F4E79,#2E6DA4)',
        borderBottom:'1px solid #1A4268',padding:'0 24px',
        position:'sticky',top:0,zIndex:200,boxShadow:'0 2px 8px rgba(0,0,0,.12)'}}>
        <div style={{maxWidth:1300,margin:'0 auto',height:60,display:'flex',
          alignItems:'center',justifyContent:'space-between',gap:16}}>
          <div style={{display:'flex',alignItems:'center',gap:12}}>
            <div style={{width:34,height:34,background:'rgba(255,255,255,.2)',
              borderRadius:8,display:'flex',alignItems:'center',
              justifyContent:'center',fontSize:'1rem'}}>🔒</div>
            <div>
              <div style={{fontFamily:"'Segoe UI',sans-serif",fontSize:'1rem',
                fontWeight:700,color:'#fff'}}>Secure Data Portal</div>
              <div style={{fontSize:'.65rem',color:'rgba(255,255,255,.6)'}}>
                Analytics Dashboard System
              </div>
            </div>
          </div>
          <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
            {user?.role==='admin'&&(
              <button onClick={()=>navigate('/admin')} style={hdrBtn('#fff')}>
                ⚙️ Admin
              </button>
            )}
            <div style={{background:'rgba(255,255,255,.15)',borderRadius:7,
              padding:'5px 12px',fontSize:'.73rem',color:'#fff',
              display:'flex',alignItems:'center',gap:6}}>
              👤 <span>{user?.username}</span>
              <span style={{background:'rgba(255,255,255,.25)',borderRadius:4,
                padding:'1px 7px',fontSize:'.63rem',textTransform:'capitalize'}}>
                {user?.role}
              </span>
            </div>
            <button onClick={handleLogout}
              style={{...hdrBtn('#fff'),background:'rgba(192,0,0,.15)',
                borderColor:'rgba(255,255,255,.4)'}}>
              Logout
            </button>
          </div>
        </div>
      </header>

      <div style={{maxWidth:1100,margin:'0 auto',padding:'32px 24px'}}>

        {/* Hero */}
        <div style={{marginBottom:28,animation:'fadeUp .4s ease'}}>
          <h1 style={{fontFamily:"'Segoe UI',sans-serif",fontSize:'1.4rem',fontWeight:700,
            color:'#1F4E79',marginBottom:6}}>Select Department</h1>
          <p style={{fontSize:'.84rem',color:'#666',maxWidth:580,lineHeight:1.6}}>
            Navigate to your department and sub-department, select the report type,
            then upload an Excel file to view automatic visualizations.
          </p>
          {/* Data type chips */}
          <div style={{display:'flex',gap:8,marginTop:14,flexWrap:'wrap'}}>
            {dataTypes.map(dt=>{
              const col=TYPE_COLORS[dt.key]||'#4472C4'
              return(
                <span key={dt.key} style={{background:`${col}14`,
                  border:`1px solid ${col}44`,borderRadius:20,
                  padding:'4px 12px',fontSize:'.71rem',color:col,fontWeight:700}}>
                  {TYPE_ICONS[dt.key]} {dt.label}
                </span>
              )
            })}
          </div>
        </div>

        {loading?(
          <div style={{display:'flex',justifyContent:'center',padding:'60px'}}>
            <Spinner size={40}/>
          </div>
        ):(
          <div style={{display:'flex',flexDirection:'column',gap:10}}>
            {departments.map(dept=>{
              const isOpen=openDept===dept.name
              const totalFiles=slots.filter(s=>s.department===dept.name)
                .reduce((n,s)=>n+s.file_count,0)
              return(
                <div key={dept.name} style={{
                  background:'#fff',border:'1px solid #D6D6D6',
                  borderRadius:12,overflow:'hidden',
                  boxShadow:'0 1px 4px rgba(0,0,0,.06)',
                  transition:'box-shadow .2s',
                  ...(isOpen?{boxShadow:'0 3px 12px rgba(0,0,0,.10)'}:{}),
                }}>
                  <button onClick={()=>{setOpenDept(isOpen?null:dept.name);setOpenSub(null)}}
                    style={{width:'100%',background:'transparent',border:'none',
                      cursor:'pointer',padding:'18px 22px',
                      display:'flex',alignItems:'center',justifyContent:'space-between',
                      color:'#333',textAlign:'left'}}>
                    <div style={{display:'flex',alignItems:'center',gap:14}}>
                      <div style={{width:44,height:44,background:'#F0F4F9',
                        border:'1px solid #D6D6D6',borderRadius:10,
                        display:'flex',alignItems:'center',justifyContent:'center',
                        fontSize:'1.3rem'}}>
                        {DEPT_ICONS[dept.name]||'🏢'}
                      </div>
                      <div>
                        <div style={{fontFamily:"'Segoe UI',sans-serif",fontWeight:700,
                          fontSize:'.98rem',color:'#1F4E79'}}>{dept.name}</div>
                        <div style={{fontSize:'.71rem',color:'#888',marginTop:3}}>
                          {dept.sub_departments.length} sub-departments
                          {totalFiles>0&&(
                            <span style={{color:'#70AD47',marginLeft:8}}>
                              · {totalFiles} file{totalFiles!==1?'s':''} uploaded
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div style={{display:'flex',alignItems:'center',gap:10}}>
                      {totalFiles>0&&(
                        <span style={{background:'#EBF5E0',border:'1px solid #B8DFA0',
                          borderRadius:20,padding:'2px 10px',fontSize:'.67rem',
                          color:'#3D7A1F',fontWeight:700}}>
                          {totalFiles} active
                        </span>
                      )}
                      <span style={{color:'#AAA',fontSize:'.85rem',
                        transform:isOpen?'rotate(180deg)':'none',transition:'.2s'}}>▾</span>
                    </div>
                  </button>

                  {isOpen&&(
                    <div style={{borderTop:'1px solid #E8E8E8',padding:'12px'}}>
                      <div style={{display:'grid',
                        gridTemplateColumns:'repeat(auto-fill,minmax(270px,1fr))',gap:10}}>
                        {dept.sub_departments.map(sub=>{
                          const subKey=`${dept.name}::${sub}`
                          const isSubOpen=openSub===subKey
                          const fc=subCount(dept.name,sub)
                          return(
                            <div key={sub} style={{
                              background:isSubOpen?'#F0F4F9':'#FAFAFA',
                              border:`1px solid ${isSubOpen?'#4472C4':'#E0E0E0'}`,
                              borderRadius:10,overflow:'hidden',transition:'border-color .15s',
                            }}>
                              <button onClick={()=>setOpenSub(isSubOpen?null:subKey)}
                                style={{width:'100%',background:'transparent',border:'none',
                                  cursor:'pointer',padding:'12px 14px',
                                  display:'flex',alignItems:'center',
                                  justifyContent:'space-between',color:'#333',textAlign:'left'}}>
                                <span style={{display:'flex',alignItems:'center',
                                  gap:8,fontSize:'.86rem',fontWeight:600,color:'#333'}}>
                                  <span style={{fontSize:'1rem'}}>{SUB_ICONS[sub]||'📁'}</span>
                                  {sub}
                                </span>
                                <div style={{display:'flex',alignItems:'center',gap:6}}>
                                  {fc>0&&(
                                    <span style={{fontSize:'.63rem',color:'#70AD47',fontWeight:700}}>
                                      {fc} file{fc!==1?'s':''}
                                    </span>
                                  )}
                                  <span style={{color:'#AAA',fontSize:'.78rem',
                                    transform:isSubOpen?'rotate(180deg)':'none',transition:'.2s'}}>▾</span>
                                </div>
                              </button>

                              {isSubOpen&&(
                                <div style={{borderTop:'1px solid #E8E8E8',padding:'4px 6px 6px'}}>
                                  {dataTypes.map(dt=>{
                                    const info=slotInfo(dept.name,sub,dt.key)
                                    const col=TYPE_COLORS[dt.key]||'#4472C4'
                                    return(
                                      <button key={dt.key}
                                        onClick={()=>navigate(
                                          `/dashboard/${encodeURIComponent(dept.name)}/${encodeURIComponent(sub)}/${dt.key}`
                                        )}
                                        style={{width:'100%',display:'flex',
                                          alignItems:'center',justifyContent:'space-between',
                                          background:'transparent',border:'none',
                                          borderRadius:7,padding:'9px 10px',
                                          color:'#444',fontSize:'.81rem',cursor:'pointer',
                                          textAlign:'left',marginBottom:2,transition:'.12s'}}
                                        onMouseEnter={e=>{e.currentTarget.style.background='#EDF2F9'}}
                                        onMouseLeave={e=>{e.currentTarget.style.background='transparent'}}>
                                        <span style={{display:'flex',alignItems:'center',gap:8}}>
                                          <span>{TYPE_ICONS[dt.key]}</span>
                                          {dt.label}
                                        </span>
                                        {info?(
                                          <span style={{background:`${col}18`,
                                            border:`1px solid ${col}44`,borderRadius:20,
                                            padding:'2px 8px',fontSize:'.61rem',
                                            color:col,fontWeight:700,flexShrink:0}}>
                                            {info.file_count} file{info.file_count!==1?'s':''}
                                          </span>
                                        ):(
                                          <span style={{fontSize:'.61rem',color:'#CCC'}}>—</span>
                                        )}
                                      </button>
                                    )
                                  })}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        <div style={{textAlign:'center',padding:'36px 0 8px',color:'#CCC',fontSize:'.7rem'}}>
          Secure Data Portal · All data processed in memory · No permanent database storage
        </div>
      </div>
    </div>
  )
}

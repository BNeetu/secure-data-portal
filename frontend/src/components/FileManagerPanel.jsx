import { useEffect, useState } from 'react'
import api from '../api/client'

export default function FileManagerPanel({ department, subdepartment, dataType, canManage, onChanged, refreshSignal }) {
  const [files, setFiles]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [removing, setRemoving] = useState(null)
  const [open, setOpen]         = useState(false)

  const load = () => {
    if (!department || !subdepartment || !dataType) return
    setLoading(true)
    api.get(`/data/${encodeURIComponent(department)}/${encodeURIComponent(subdepartment)}/${encodeURIComponent(dataType)}/files`)
      .then(({ data }) => setFiles(data.files || []))
      .catch(() => setFiles([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [department, subdepartment, dataType, refreshSignal])

  const handleRemove = async (id, name) => {
    if (!confirm(`Remove "${name}"?`)) return
    setRemoving(id)
    try {
      await api.delete(`/data/${encodeURIComponent(department)}/${encodeURIComponent(subdepartment)}/${encodeURIComponent(dataType)}/files/${id}`)
      setFiles(prev => prev.filter(f => f.id !== id))
      onChanged?.()
    } catch(e) { alert(e.response?.data?.detail || 'Failed to remove.') }
    finally { setRemoving(null) }
  }

  if (!files.length && !loading) return null

  return (
    <div style={{ marginBottom: 18 }}>
      <button onClick={() => setOpen(o => !o)} style={{
        width: '100%', background: '#fff', border: '1px solid #D6D6D6',
        borderRadius: open ? '10px 10px 0 0' : 10,
        padding: '11px 16px', fontSize: '.79rem', color: '#555',
        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ display:'flex', alignItems:'center', gap:8 }}>
          <span>📎</span>
          <span>
            {loading ? 'Loading files…' : `${files.length} file${files.length!==1?'s':''} in this dashboard`}
          </span>
          {files.length > 1 && (
            <span style={{ background:'#EDF2F9', border:'1px solid #C8D8F0', borderRadius:20,
              padding:'1px 8px', fontSize:'.64rem', color:'#4472C4', fontWeight:700 }}>
              Multi-file
            </span>
          )}
        </span>
        <span style={{ color:'#AAA', transform:open?'rotate(180deg)':'none', transition:'.2s' }}>▾</span>
      </button>

      {open && (
        <div style={{ background:'#fff', border:'1px solid #D6D6D6', borderTop:'none',
          borderRadius:'0 0 10px 10px', padding:'4px 8px 8px' }}>
          {files.length === 0 ? (
            <div style={{ padding:'12px', fontSize:'.78rem', color:'#AAA' }}>No files yet.</div>
          ) : files.map(f => (
            <div key={f.id} style={{
              display:'flex', alignItems:'center', justifyContent:'space-between',
              padding:'9px 10px', borderRadius:7, fontSize:'.78rem',
            }}
              onMouseEnter={e=>e.currentTarget.style.background='#F9F9F9'}
              onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
              <div style={{ display:'flex', alignItems:'center', gap:9, minWidth:0 }}>
                <span>📄</span>
                <div style={{ minWidth:0 }}>
                  <div style={{ color:'#333', fontWeight:600, whiteSpace:'nowrap',
                    overflow:'hidden', textOverflow:'ellipsis' }}>{f.filename}</div>
                  <div style={{ color:'#AAA', fontSize:'.67rem', marginTop:1 }}>
                    {f.rows!=null?`${f.rows.toLocaleString()} rows`:'—'}
                    {' · '}by {f.uploaded_by}
                    {' · '}{new Date(f.uploaded_at*1000).toLocaleString()}
                  </div>
                </div>
              </div>
              {canManage && (
                <button onClick={() => handleRemove(f.id, f.filename)}
                  disabled={removing===f.id} style={{
                    background:'#FFF0F0', border:'1px solid #FFB3B3', borderRadius:6,
                    padding:'4px 10px', color:'#C00000', cursor:'pointer',
                    fontSize:'.71rem', fontWeight:700, flexShrink:0, marginLeft:10,
                  }}>
                  {removing===f.id ? '…' : '🗑 Remove'}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

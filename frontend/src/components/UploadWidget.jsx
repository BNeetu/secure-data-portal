import { useRef, useState } from 'react'
import api from '../api/client'

export default function UploadWidget({ department, subdepartment, dataType, onUploaded, compact=false }) {
  const ref = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [msg, setMsg] = useState(null)

  const handle = async file => {
    if (!file) return
    if (!/\.(xlsx|xls)$/i.test(file.name)) {
      setMsg({ t:'err', s:'Only .xlsx or .xls files are accepted.' }); return
    }
    setUploading(true); setMsg(null)
    const fd = new FormData(); fd.append('file', file)
    try {
      const { data } = await api.post(
        `/data/${encodeURIComponent(department)}/${encodeURIComponent(subdepartment)}/${encodeURIComponent(dataType)}/upload`, fd)
      const w = data.warnings?.length
      setMsg({
        t: w ? 'warn' : 'ok',
        s: w
          ? `✅ ${data.filename} (${data.rows} rows). Note: ${data.warnings[0]}`
          : `✅ ${data.filename} — ${data.rows} rows uploaded successfully.`
      })
      onUploaded?.(data)
    } catch(e) {
      setMsg({ t:'err', s: e.response?.data?.detail || 'Upload failed. Please try again.' })
    } finally {
      setUploading(false)
      // CRITICAL: reset input so same file can be re-uploaded
      if (ref.current) ref.current.value = ''
    }
  }

  const C = {
    ok:   { bg:'#EBF5E0', fg:'#3D7A1F', b:'#B8DFA0' },
    warn: { bg:'#FFF8E1', fg:'#7A5500', b:'#FFD970' },
    err:  { bg:'#FFF0F0', fg:'#C00000', b:'#FFB3B3' },
  }

  return (
    <div style={{ position:'relative' }}>
      <label style={{
        background:'#fff', border:'1px solid #4472C4',
        borderRadius:8, padding:compact?'5px 12px':'7px 15px',
        fontSize:'.76rem', color:'#4472C4',
        cursor:uploading?'wait':'pointer', fontWeight:700,
        whiteSpace:'nowrap', display:'inline-flex', alignItems:'center',
        gap:6, transition:'.15s', boxShadow:'0 1px 4px rgba(68,114,196,.15)',
      }}>
        {uploading ? '⏳ Uploading…' : '📁 Upload Excel'}
        <input ref={ref} type="file" accept=".xlsx,.xls"
          onChange={e => handle(e.target.files[0])}
          style={{ display:'none' }} disabled={uploading}/>
      </label>

      {msg && (
        <div style={{
          position:'fixed', top:70, right:20, zIndex:900,
          background:C[msg.t].bg, color:C[msg.t].fg,
          border:`1px solid ${C[msg.t].b}`, borderRadius:10,
          padding:'12px 16px', fontSize:'.82rem', maxWidth:400,
          lineHeight:1.5, boxShadow:'0 4px 20px rgba(0,0,0,.12)',
          animation:'slideIn .2s ease',
        }}>
          <div style={{ display:'flex', justifyContent:'space-between', gap:12 }}>
            <span>{msg.s}</span>
            <button onClick={() => setMsg(null)} style={{
              background:'none', border:'none', color:'inherit',
              cursor:'pointer', opacity:.6, flexShrink:0, fontSize:'1rem', padding:0,
            }}>✕</button>
          </div>
        </div>
      )}
    </div>
  )
}

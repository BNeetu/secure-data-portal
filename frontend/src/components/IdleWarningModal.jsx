import { useAuth } from '../context/AuthContext'

export default function IdleWarningModal() {
  const { resetIdleTimer, logout } = useAuth()
  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.45)',
      zIndex:4000, display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div style={{ background:'#fff', border:'1px solid #D6D6D6', borderRadius:14,
        padding:'32px 36px', maxWidth:400, width:'90%', textAlign:'center',
        boxShadow:'0 8px 32px rgba(0,0,0,.18)' }}>
        <div style={{ fontSize:'2.5rem', marginBottom:14 }}>⏰</div>
        <h2 style={{ fontFamily:"'Segoe UI',sans-serif", fontSize:'1.1rem',
          fontWeight:700, color:'#1F4E79', marginBottom:10 }}>
          Session Expiring Soon
        </h2>
        <p style={{ fontSize:'.84rem', color:'#666', lineHeight:1.6, marginBottom:22 }}>
          You've been inactive for a while. Click <strong>Stay Signed In</strong> to continue,
          or you'll be logged out automatically.
        </p>
        <div style={{ display:'flex', gap:10, justifyContent:'center' }}>
          <button onClick={resetIdleTimer} style={{
            padding:'10px 22px', background:'linear-gradient(135deg,#1F4E79,#4472C4)',
            border:'none', borderRadius:8, color:'#fff', fontWeight:700,
            fontSize:'.88rem', cursor:'pointer',
          }}>Stay Signed In</button>
          <button onClick={() => logout()} style={{
            padding:'10px 18px', background:'#fff',
            border:'1px solid #D6D6D6', borderRadius:8,
            color:'#C00000', fontWeight:700, fontSize:'.88rem', cursor:'pointer',
          }}>Logout</button>
        </div>
      </div>
    </div>
  )
}

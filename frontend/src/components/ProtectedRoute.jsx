import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children, requireRole }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{ minHeight:'100vh', display:'flex', alignItems:'center',
        justifyContent:'center', background:'#F5F5F5' }}>
        <div style={{ width:36, height:36, border:'3px solid #E0E0E0',
          borderTop:'3px solid #4472C4', borderRadius:'50%',
          animation:'spin 1s linear infinite' }}/>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />

  if (requireRole && !requireRole.includes(user.role)) {
    return (
      <div style={{ minHeight:'100vh', display:'flex', alignItems:'center',
        justifyContent:'center', background:'#F5F5F5', flexDirection:'column', gap:14 }}>
        <div style={{ fontSize:'2.5rem' }}>🚫</div>
        <h2 style={{ fontFamily:"'Segoe UI',sans-serif", color:'#1F4E79' }}>Access Denied</h2>
        <p style={{ color:'#777', fontSize:'.85rem' }}>
          You don't have permission to view this page.
        </p>
        <a href="/dashboard" style={{ color:'#4472C4', fontSize:'.85rem', fontWeight:700 }}>
          ← Back to Dashboard
        </a>
      </div>
    )
  }

  return children
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const navigate = useNavigate()
  const { completeLogin } = useAuth()
  const [stage, setStage]         = useState('password')
  const [username, setUsername]   = useState('')
  const [password, setPassword]   = useState('')
  const [code, setCode]           = useState('')
  const [tempToken, setTempToken] = useState(null)
  const [qrUri, setQrUri]         = useState(null)
  const [error, setError]         = useState('')
  const [loading, setLoading]     = useState(false)

  const handlePassword = async e => {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      const { data } = await api.post('/auth/login', { username, password })
      // MFA currently disabled on the backend — login completes in one step.
      // (All the MFA UI/logic below is untouched and will resume working
      // automatically the moment MFA_REQUIRED is set back to True.)
      if (!data.mfa_required) {
        completeLogin(data)
        navigate('/dashboard')
        return
      }
      setTempToken(data.temp_token)
      setQrUri(data.qr_provisioning_uri || null)
      setStage('mfa')
    } catch (err) { setError(err.response?.data?.detail || 'Login failed. Please check your credentials.') }
    finally { setLoading(false) }
  }

  const handleMfa = async e => {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      const { data } = await api.post('/auth/mfa/verify', { temp_token: tempToken, code })
      completeLogin(data); navigate('/dashboard')
    } catch (err) { setError(err.response?.data?.detail || 'Invalid code. Please try again.') }
    finally { setLoading(false) }
  }

  const inp = {
    width:'100%', padding:'10px 13px',
    background:'#fff', border:'1px solid #D6D6D6', borderRadius:7,
    color:'#333', fontSize:'.88rem', outline:'none', marginBottom:14,
    boxShadow:'inset 0 1px 3px rgba(0,0,0,.05)',
  }
  const lbl = {
    display:'block', fontSize:'.7rem', fontWeight:700, color:'#555',
    marginBottom:5, textTransform:'uppercase', letterSpacing:'.05em',
  }

  return (
    <div style={{
      minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center',
      background:'#F5F5F5', padding:20,
    }}>
      <div style={{
        background:'#fff', border:'1px solid #D6D6D6', borderRadius:12,
        padding:'36px 36px 32px', width:'100%', maxWidth:420,
        boxShadow:'0 4px 24px rgba(0,0,0,.10)', animation:'fadeUp .4s ease',
      }}>
        {/* Logo */}
        <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:28}}>
          <div style={{
            width:44, height:44,
            background:'linear-gradient(135deg,#1F4E79,#4472C4)',
            borderRadius:10, display:'flex', alignItems:'center',
            justifyContent:'center', fontSize:'1.25rem',
            boxShadow:'0 2px 8px rgba(31,78,121,.3)',
          }}>🔒</div>
          <div>
            <div style={{fontFamily:"'Segoe UI',sans-serif",fontSize:'1.1rem',
              fontWeight:700,color:'#1F4E79'}}>Secure Data Portal</div>
            <div style={{fontSize:'.68rem',color:'#AAA',marginTop:2}}>
              {stage==='password'?'Sign in to continue':'Two-factor verification'}
            </div>
          </div>
        </div>

        {error && (
          <div style={{background:'#FFF0F0',color:'#C00000',border:'1px solid #FFB3B3',
            borderRadius:7,padding:'9px 13px',fontSize:'.82rem',marginBottom:14,lineHeight:1.5}}>
            ⚠️ {error}
          </div>
        )}

        {stage === 'password' && (
          <form onSubmit={handlePassword}>
            <label style={lbl}>Username</label>
            <input style={inp} value={username}
              onChange={e=>setUsername(e.target.value)}
              autoFocus required autoComplete="username"
              onFocus={e=>e.target.style.borderColor='#4472C4'}
              onBlur={e=>e.target.style.borderColor='#D6D6D6'}/>
            <label style={lbl}>Password</label>
            <input style={inp} type="password" value={password}
              onChange={e=>setPassword(e.target.value)}
              required autoComplete="current-password"
              onFocus={e=>e.target.style.borderColor='#4472C4'}
              onBlur={e=>e.target.style.borderColor='#D6D6D6'}/>
            <button type="submit" disabled={loading} style={{
              width:'100%', padding:'11px',
              background:loading?'#D6D6D6':'linear-gradient(135deg,#1F4E79,#4472C4)',
              border:'none', borderRadius:8, color:'#fff', fontWeight:700,
              fontSize:'.9rem', cursor:loading?'not-allowed':'pointer',
              boxShadow:loading?'none':'0 2px 8px rgba(31,78,121,.25)',
              transition:'.15s',
            }}>
              {loading ? 'Checking…' : 'Continue →'}
            </button>
          </form>
        )}

        {stage === 'mfa' && (
          <form onSubmit={handleMfa}>
            {qrUri && (
              <>
                <p style={{fontSize:'.8rem',color:'#555',marginBottom:12,lineHeight:1.6}}>
                  First-time setup: scan this QR code with{' '}
                  <strong>Google Authenticator</strong> or{' '}
                  <strong>Microsoft Authenticator</strong>, then enter the 6-digit code.
                </p>
                <div style={{background:'#fff',border:'1px solid #D6D6D6',borderRadius:8,
                  padding:14,marginBottom:16,display:'flex',justifyContent:'center'}}>
                  <QRCodeSVG value={qrUri} size={165}/>
                </div>
              </>
            )}
            {!qrUri && (
              <p style={{fontSize:'.82rem',color:'#555',marginBottom:14,lineHeight:1.5}}>
                Enter the 6-digit code from your authenticator app.
              </p>
            )}
            <label style={lbl}>Authentication Code</label>
            <input style={{...inp,fontSize:'1.4rem',letterSpacing:'.4em',textAlign:'center'}}
              value={code}
              onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))}
              inputMode="numeric" maxLength={6} autoFocus required placeholder="000000"
              onFocus={e=>e.target.style.borderColor='#4472C4'}
              onBlur={e=>e.target.style.borderColor='#D6D6D6'}/>
            <button type="submit" disabled={loading||code.length!==6} style={{
              width:'100%', padding:'11px',
              background:(loading||code.length!==6)?'#D6D6D6':'linear-gradient(135deg,#1F4E79,#4472C4)',
              border:'none', borderRadius:8, color:'#fff', fontWeight:700,
              fontSize:'.9rem',
              cursor:(loading||code.length!==6)?'not-allowed':'pointer',
              transition:'.15s',
            }}>
              {loading ? 'Verifying…' : 'Verify & Sign In →'}
            </button>
            <div onClick={()=>{setStage('password');setError('');setCode('')}}
              style={{textAlign:'center',marginTop:12,fontSize:'.78rem',
                color:'#4472C4',cursor:'pointer'}}>
              ← Back to login
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

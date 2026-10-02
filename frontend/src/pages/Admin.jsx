import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

const inp = {
  width:'100%', padding:'9px 12px', background:'#fff',
  border:'1px solid #D6D6D6', borderRadius:7, color:'#333',
  fontSize:'.85rem', outline:'none', marginBottom:12,
  boxShadow:'inset 0 1px 3px rgba(0,0,0,.04)',
}
const lbl = {
  display:'block', fontSize:'.7rem', fontWeight:700,
  color:'#555', marginBottom:5, textTransform:'uppercase', letterSpacing:'.04em',
}

const EV_COLORS = {
  login_success:'#70AD47', login_failed:'#C00000', login_password_ok:'#4472C4',
  mfa_failed:'#C00000', account_locked:'#ED7D31', ip_blocked:'#C00000',
  upload:'#4472C4', user_created:'#7030A0', user_unlocked:'#70AD47',
  logout:'#AAA', password_changed:'#FFC000', data_cleared:'#ED7D31',
}

export default function Admin() {
  const navigate = useNavigate()
  const [tab, setTab]         = useState('users')
  const [users, setUsers]     = useState([])
  const [events, setEvents]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')
  const [success, setSuccess] = useState('')
  const [newUser, setNewUser] = useState({ username:'', password:'', role:'viewer' })
  const [creating, setCreating] = useState(false)

  const loadUsers = () => api.get('/auth/users').then(({ data }) => setUsers(data))
  const loadAudit = () => api.get('/audit', { params:{ limit:200 } }).then(({ data }) => setEvents(data.events))

  useEffect(() => {
    setLoading(true)
    Promise.all([loadUsers(), loadAudit()]).finally(() => setLoading(false))
  }, [])

  const handleCreate = async e => {
    e.preventDefault(); setError(''); setSuccess(''); setCreating(true)
    try {
      await api.post('/auth/users', newUser)
      setSuccess(`User "${newUser.username}" created successfully.`)
      setNewUser({ username:'', password:'', role:'viewer' })
      await loadUsers()
    } catch(err) { setError(err.response?.data?.detail || 'Failed to create user.') }
    finally { setCreating(false) }
  }

  const handleUnlock = async username => {
    setError(''); setSuccess('')
    try {
      await api.post(`/auth/users/${username}/unlock`)
      setSuccess(`User "${username}" unlocked.`)
      await loadUsers()
    } catch(err) { setError(err.response?.data?.detail || 'Failed to unlock.') }
  }

  const card = { background:'#fff', border:'1px solid #D6D6D6', borderRadius:12,
    padding:'20px 22px', boxShadow:'0 1px 4px rgba(0,0,0,.06)' }

  return (
    <div style={{ minHeight:'100vh', background:'#F5F5F5' }}>
      {/* Header */}
      <header style={{ background:'linear-gradient(135deg,#1F4E79,#2E6DA4)',
        borderBottom:'1px solid #1A4268', padding:'0 24px',
        position:'sticky', top:0, zIndex:200, boxShadow:'0 2px 8px rgba(0,0,0,.12)' }}>
        <div style={{ maxWidth:1100, margin:'0 auto', height:60,
          display:'flex', alignItems:'center', justifyContent:'space-between', gap:16 }}>
          <div style={{ display:'flex', alignItems:'center', gap:12 }}>
            <button onClick={() => navigate('/dashboard')}
              style={{ background:'rgba(255,255,255,.15)', border:'1px solid rgba(255,255,255,.3)',
                borderRadius:7, padding:'6px 12px', color:'#fff', cursor:'pointer', fontSize:'.78rem', fontWeight:700 }}>
              ← Dashboard
            </button>
            <div style={{ fontFamily:"'Segoe UI',sans-serif", fontSize:'.98rem',
              fontWeight:700, color:'#fff' }}>⚙️ Admin Panel</div>
          </div>
          <div style={{ display:'flex', gap:6 }}>
            {['users','audit'].map(t => (
              <button key={t} onClick={() => setTab(t)} style={{
                background:    tab===t ? '#fff' : 'rgba(255,255,255,.15)',
                border:        `1px solid ${tab===t ? '#fff' : 'rgba(255,255,255,.3)'}`,
                borderRadius:  20, padding:'6px 16px',
                fontSize:      '.77rem', fontWeight:700,
                color:         tab===t ? '#1F4E79' : '#fff',
                cursor:'pointer',
              }}>
                {t==='users' ? '👥 Users' : '📋 Audit Log'}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div style={{ maxWidth:1100, margin:'0 auto', padding:'28px 22px' }}>
        {error  && <div style={{ background:'#FFF0F0', color:'#C00000', border:'1px solid #FFB3B3', borderRadius:8, padding:'10px 14px', fontSize:'.82rem', marginBottom:14 }}>⚠️ {error}</div>}
        {success && <div style={{ background:'#EBF5E0', color:'#3D7A1F', border:'1px solid #B8DFA0', borderRadius:8, padding:'10px 14px', fontSize:'.82rem', marginBottom:14 }}>✅ {success}</div>}

        {tab === 'users' && (
          <div style={{ display:'grid', gridTemplateColumns:'300px 1fr', gap:18 }}>
            {/* Create user */}
            <div style={card}>
              <h3 style={{ fontFamily:"'Segoe UI',sans-serif", fontSize:'.92rem',
                fontWeight:700, color:'#1F4E79', marginBottom:16 }}>➕ Create User</h3>
              <form onSubmit={handleCreate}>
                <label style={lbl}>Username</label>
                <input style={inp} value={newUser.username}
                  onChange={e => setNewUser({...newUser, username:e.target.value})}
                  required
                  onFocus={e=>e.target.style.borderColor='#4472C4'}
                  onBlur={e=>e.target.style.borderColor='#D6D6D6'}/>
                <label style={lbl}>Password</label>
                <input style={inp} type="password" value={newUser.password}
                  onChange={e => setNewUser({...newUser, password:e.target.value})}
                  required
                  onFocus={e=>e.target.style.borderColor='#4472C4'}
                  onBlur={e=>e.target.style.borderColor='#D6D6D6'}/>
                <p style={{ fontSize:'.68rem', color:'#AAA', marginTop:-8, marginBottom:12 }}>
                  Min 12 chars, upper, lower, digit, symbol.
                </p>
                <label style={lbl}>Role</label>
                <select style={inp} value={newUser.role}
                  onChange={e => setNewUser({...newUser, role:e.target.value})}>
                  <option value="viewer">Viewer — read-only</option>
                  <option value="manager">Manager — upload + read</option>
                  <option value="admin">Admin — full access</option>
                </select>
                <button type="submit" disabled={creating} style={{
                  width:'100%', padding:'10px',
                  background:creating?'#D6D6D6':'linear-gradient(135deg,#1F4E79,#4472C4)',
                  border:'none', borderRadius:8, color:'#fff', fontWeight:700,
                  fontSize:'.85rem', cursor:creating?'not-allowed':'pointer',
                }}>
                  {creating ? 'Creating…' : 'Create User'}
                </button>
              </form>
            </div>

            {/* User list */}
            <div style={card}>
              <h3 style={{ fontFamily:"'Segoe UI',sans-serif", fontSize:'.92rem',
                fontWeight:700, color:'#1F4E79', marginBottom:16 }}>
                👥 All Users ({users.length})
              </h3>
              {loading ? <p style={{ color:'#AAA', fontSize:'.85rem' }}>Loading…</p> : (
                <div style={{ overflowX:'auto' }}>
                  <table style={{ width:'100%', borderCollapse:'collapse', fontSize:'.8rem' }}>
                    <thead>
                      <tr>
                        {['Username','Role','MFA','Status','Last Login',''].map(h => (
                          <th key={h} style={{ textAlign:'left', color:'#777', padding:'8px 10px',
                            fontSize:'.67rem', textTransform:'uppercase',
                            borderBottom:'1px solid #E8E8E8', fontWeight:700 }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {users.map(u => (
                        <tr key={u.username} style={{ borderBottom:'1px solid #F0F0F0' }}
                          onMouseEnter={e=>e.currentTarget.style.background='#F9F9F9'}
                          onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                          <td style={{ padding:'9px 10px' }}><strong style={{ color:'#333' }}>{u.username}</strong></td>
                          <td style={{ padding:'9px 10px' }}>
                            <span style={{
                              background: u.role==='admin'?'#EDE7F6':u.role==='manager'?'#E8F4FD':'#F5F5F5',
                              color:      u.role==='admin'?'#7030A0':u.role==='manager'?'#1F4E79':'#777',
                              padding:'2px 9px', borderRadius:20, fontSize:'.7rem', fontWeight:700,
                              textTransform:'capitalize',
                            }}>{u.role}</span>
                          </td>
                          <td style={{ padding:'9px 10px' }}>{u.mfa_verified ? '✅' : '⏳ pending'}</td>
                          <td style={{ padding:'9px 10px' }}>
                            {u.locked
                              ? <span style={{ color:'#C00000', fontWeight:700 }}>🔒 Locked</span>
                              : <span style={{ color:'#70AD47' }}>Active</span>}
                          </td>
                          <td style={{ padding:'9px 10px', color:'#AAA' }}>
                            {u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}
                          </td>
                          <td style={{ padding:'9px 10px' }}>
                            {u.locked && (
                              <button onClick={() => handleUnlock(u.username)} style={{
                                background:'#fff', border:'1px solid #4472C4', borderRadius:6,
                                padding:'4px 10px', color:'#4472C4', cursor:'pointer',
                                fontSize:'.73rem', fontWeight:700,
                              }}>Unlock</button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === 'audit' && (
          <div style={card}>
            <h3 style={{ fontFamily:"'Segoe UI',sans-serif", fontSize:'.92rem',
              fontWeight:700, color:'#1F4E79', marginBottom:4 }}>📋 Security Audit Log</h3>
            <p style={{ fontSize:'.75rem', color:'#AAA', marginBottom:16 }}>
              Most recent {events.length} security events.
            </p>
            <div style={{ maxHeight:560, overflowY:'auto' }}>
              <table style={{ width:'100%', borderCollapse:'collapse', fontSize:'.79rem' }}>
                <thead>
                  <tr>
                    {['Time','Event','User','IP','Detail'].map(h => (
                      <th key={h} style={{ textAlign:'left', color:'#777', padding:'8px 10px',
                        fontSize:'.67rem', textTransform:'uppercase', fontWeight:700,
                        borderBottom:'1px solid #E8E8E8', position:'sticky', top:0,
                        background:'#fff' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev, i) => (
                    <tr key={i} style={{ borderBottom:'1px solid #F5F5F5' }}
                      onMouseEnter={e=>e.currentTarget.style.background='#F9F9F9'}
                      onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                      <td style={{ padding:'8px 10px', color:'#AAA', whiteSpace:'nowrap' }}>
                        {new Date(ev.timestamp).toLocaleString()}
                      </td>
                      <td style={{ padding:'8px 10px', whiteSpace:'nowrap' }}>
                        <span style={{ color:EV_COLORS[ev.event_type]||'#333', fontWeight:700 }}>
                          {ev.event_type}
                        </span>
                      </td>
                      <td style={{ padding:'8px 10px', whiteSpace:'nowrap' }}>{ev.username||'—'}</td>
                      <td style={{ padding:'8px 10px', color:'#AAA', whiteSpace:'nowrap' }}>{ev.ip||'—'}</td>
                      <td style={{ padding:'8px 10px', color:'#555' }}>{ev.detail}</td>
                    </tr>
                  ))}
                  {events.length===0&&(
                    <tr><td colSpan={5} style={{ padding:'24px', textAlign:'center', color:'#CCC' }}>
                      No events yet.
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

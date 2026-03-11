'use client'

import { useState, useEffect } from 'react'
import styles from './page.module.css'

const TABS = ['Warm Contacts', 'TODO', 'Summaries', 'Input Prompt']

export default function Home() {
  const [activeTab, setActiveTab] = useState(0)

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Networking Platform</h1>
        <nav className={styles.tabs}>
          {TABS.map((label, i) => (
            <button
              key={label}
              className={activeTab === i ? styles.tabActive : styles.tab}
              onClick={() => setActiveTab(i)}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>
      <main className={styles.main}>
        {activeTab === 0 && <WarmContactsTab />}
        {activeTab === 1 && <TodosTab />}
        {activeTab === 2 && <SummariesTab />}
        {activeTab === 3 && <InputPromptTab />}
      </main>
    </div>
  )
}

function toDatetimeLocal(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day}T${h}:${min}`
}

function ContactRow({ contact, getWarmthStyle, onSaved, onRemove }) {
  const [editing, setEditing] = useState(false)
  const [country, setCountry] = useState(contact.country || '')
  const [lastContacted, setLastContacted] = useState(toDatetimeLocal(contact.last_contacted_at))
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      const res = await fetch(
        (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + `/api/contacts/${contact.id}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            country: country || null,
            last_contacted_at: lastContacted ? new Date(lastContacted).toISOString() : null,
          }),
        }
      )
      if (res.ok) {
        setEditing(false)
        onSaved()
      }
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const cancel = () => {
    setCountry(contact.country || '')
    setLastContacted(toDatetimeLocal(contact.last_contacted_at))
    setEditing(false)
  }

  const followUpHours = contact.next_follow_up_at
    ? Math.round((new Date(contact.next_follow_up_at) - Date.now()) / (1000 * 60 * 60))
    : null
  const followUpDisplay = followUpHours != null
    ? (followUpHours > 24 ? `${Math.round(followUpHours / 24)}d` : `${followUpHours}h`)
    : '-'

  return (
    <tr style={getWarmthStyle(contact.last_contacted_at)}>
      <td>{contact.full_name}</td>
      {editing ? (
        <td>
          <input
            className={styles.inlineInput}
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder="Country"
          />
        </td>
      ) : (
        <td>{contact.country || '-'}</td>
      )}
      <td>
        {editing ? (
          <input
            className={styles.inlineInput}
            type="datetime-local"
            value={lastContacted}
            onChange={(e) => setLastContacted(e.target.value)}
            title="Last contacted"
          />
        ) : (
          (contact.last_contacted_at ? new Date(contact.last_contacted_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '-')
        )}
      </td>
      <td>{followUpDisplay}</td>
      <td>{contact.last_interaction_summary || '-'}</td>
      <td>
        {editing ? (
          <span className={styles.editActions}>
            <button onClick={save} disabled={saving} className={styles.btnSmall}>Save</button>
            <button onClick={cancel} disabled={saving} className={styles.btnSmall}>Cancel</button>
          </span>
        ) : (
          <span className={styles.editActions}>
            <button onClick={() => setEditing(true)} className={styles.btnSmall} title="Edit country, last contacted">Edit</button>
            {onRemove && <button onClick={() => onRemove(contact)} className={styles.btnDanger} title="Remove contact">Remove</button>}
          </span>
        )}
      </td>
    </tr>
  )
}

function WarmContactsTab() {
  const [contacts, setContacts] = useState([])
  const [reminders, setReminders] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState('last_contacted_desc')
  const [total, setTotal] = useState(0)
  const [contactToRemove, setContactToRemove] = useState(null)

  const fetchContacts = async () => {
    setLoading(true)
    try {
      const url = new URL('/api/contacts', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      if (search) url.searchParams.set('search', search)
      url.searchParams.set('sort', sort)
      const res = await fetch(url)
      const data = await res.json()
      setContacts(data.contacts || [])
      setTotal(data.total || 0)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const fetchReminders = async () => {
    try {
      const res = await fetch((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/reminders?days=90')
      const data = await res.json()
      setReminders(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchContacts()
    fetchReminders()
  }, [sort])

  const exportCsv = () => {
    window.open((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/export/contacts', '_blank')
  }

  const MAX_DAYS = 14
  const removeContact = async () => {
    if (!contactToRemove) return
    try {
      const res = await fetch(
        (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + `/api/contacts/${contactToRemove.id}`,
        { method: 'DELETE' }
      )
      if (res.ok) {
        setContactToRemove(null)
        fetchContacts()
      }
    } catch (e) {
      console.error(e)
    }
  }

  const getWarmthStyle = (lastContacted) => {
    let days = MAX_DAYS
    if (lastContacted) {
      const d = new Date(lastContacted)
      days = Math.min(MAX_DAYS, (Date.now() - d) / (24 * 60 * 60 * 1000))
    }
    const recency = 1 - days / MAX_DAYS
    const hue = Math.round(120 * recency)
    return { borderLeft: `4px solid hsl(${hue}, 85%, 48%)` }
  }

  return (
    <div className={styles.tabContent}>
      <div className={styles.toolbar}>
        <input
          placeholder="Search contacts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && fetchContacts()}
          className={styles.search}
        />
        <select value={sort} onChange={(e) => setSort(e.target.value)} className={styles.select}>
          <option value="last_contacted_desc">Last contacted (newest first)</option>
          <option value="last_contacted_asc">Last contacted (oldest first)</option>
          <option value="follow_up_asc">Follow up (soonest first)</option>
          <option value="follow_up_desc">Follow up (latest first)</option>
          <option value="name_asc">Name (A–Z)</option>
        </select>
        <button onClick={fetchContacts} disabled={loading} className={styles.btn}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
        <button onClick={exportCsv} className={styles.btnSecondary}>Export CSV</button>
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Contact</th>
            <th>Country</th>
            <th>Last Contacted</th>
            <th>Follow up</th>
            <th>Summary</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {contacts.map((c) => (
            <ContactRow
              key={c.id}
              contact={c}
              getWarmthStyle={getWarmthStyle}
              onSaved={fetchContacts}
              onRemove={setContactToRemove}
            />
          ))}
        </tbody>
      </table>
      {!loading && contacts.length === 0 && (
        <p className={styles.empty}>No contacts yet. Add one via the Input Prompt tab.</p>
      )}
      {contactToRemove && (
        <div className={styles.modalOverlay} onClick={() => setContactToRemove(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h3 className={styles.modalTitle}>Remove contact</h3>
            <p>Are you sure you want to remove <strong>{contactToRemove.full_name}</strong>? This will delete their interaction history.</p>
            <div className={styles.modalActions}>
              <button onClick={() => setContactToRemove(null)} className={styles.btnSecondary}>Cancel</button>
              <button onClick={removeContact} className={styles.btnDanger}>Remove</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function TodosTab() {
  const [todos, setTodos] = useState([])
  const [contacts, setContacts] = useState([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('pending')
  const [sort, setSort] = useState('priority_asc')
  const [contactFilter, setContactFilter] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/contacts?limit=100&sort=name_asc')
        const d = await res.json()
        setContacts(d.contacts || [])
      } catch (e) {
        console.error(e)
      }
    }
    load()
  }, [])

  useEffect(() => {
    fetchTodos()
  }, [filter, sort, contactFilter])

  const fetchTodos = async () => {
    setLoading(true)
    try {
      const url = new URL('/api/todos', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      if (filter !== 'all') url.searchParams.set('status', filter)
      if (contactFilter) url.searchParams.set('contact_id', contactFilter)
      url.searchParams.set('sort', sort)
      const res = await fetch(url)
      const data = await res.json()
      setTodos(data.todos || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const updateTodo = async (id, updates) => {
    try {
      await fetch((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + `/api/todos/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
      fetchTodos()
    } catch (e) {
      console.error(e)
    }
  }

  const markDone = (id) => updateTodo(id, { status: 'done' })

  const exportCsv = () => {
    window.open((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/export/todos', '_blank')
  }

  return (
    <div className={styles.tabContent}>
      <div className={styles.toolbar}>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className={styles.select}>
          <option value="pending">Pending</option>
          <option value="done">Done</option>
          <option value="all">All</option>
        </select>
        <select value={contactFilter} onChange={(e) => setContactFilter(e.target.value)} className={styles.select}>
          <option value="">All contacts</option>
          {contacts.map((c) => (
            <option key={c.id} value={c.id}>{c.full_name}</option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} className={styles.select}>
          <option value="priority_asc">Priority (high first)</option>
          <option value="priority_desc">Priority (low first)</option>
          <option value="created_asc">Oldest first</option>
          <option value="created_desc">Newest first</option>
        </select>
        <button onClick={fetchTodos} disabled={loading} className={styles.btn}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
        <button onClick={exportCsv} className={styles.btnSecondary}>Export CSV</button>
      </div>
      <ul className={styles.todoList}>
        {todos.map((t) => {
          const daysSince = t.created_at ? Math.floor((Date.now() - new Date(t.created_at)) / (1000 * 60 * 60 * 24)) : null
          const effectivePriority = (t.status === 'pending' && daysSince != null && daysSince >= 7) ? 'high' : (t.priority || 'medium')
          return (
            <li key={t.id} className={styles.todoItem}>
              <div>
                <div>
                  <select
                    value={t.priority || 'medium'}
                    onChange={(e) => updateTodo(t.id, { priority: e.target.value })}
                    className={`${styles.select} ${effectivePriority === 'high' ? styles.prioritySelectHigh : effectivePriority === 'low' ? styles.prioritySelectLow : styles.prioritySelectMedium}`}
                    style={{ width: 'auto', marginRight: 8 }}
                  >
                    <option value="high">high</option>
                    <option value="medium">medium</option>
                    <option value="low">low</option>
                  </select>
                  <strong>{t.title}</strong>
                  {daysSince != null && <span className={styles.todoDays}> · {daysSince}d ago</span>}
                  {effectivePriority !== (t.priority || 'medium') && (
                    <span className={styles.todoDays} title="Auto-elevated (7+ days old)"> ↑</span>
                  )}
                </div>
                {t.description && <p className={styles.todoDesc}>{t.description}</p>}
                {t.contact_name && <span className={styles.todoContact}>{t.contact_name}</span>}
              </div>
              {t.status === 'pending' && (
                <button onClick={() => markDone(t.id)} className={styles.btnSmall}>Done</button>
              )}
              {t.status === 'done' && <span className={styles.badge}>Done</span>}
            </li>
          )
        })}
      </ul>
      {!loading && todos.length === 0 && (
        <p className={styles.empty}>No TODOs. Create via Input Prompt or manually.</p>
      )}
    </div>
  )
}

function SummariesTab() {
  const [contacts, setContacts] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchContacts = async () => {
    setLoading(true)
    try {
      const res = await fetch((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/contacts?limit=100&sort=name_asc')
      const d = await res.json()
      setContacts(d.contacts || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchContacts() }, [])

  return (
    <div className={styles.tabContent}>
      <div className={styles.toolbar}>
        <button onClick={fetchContacts} disabled={loading} className={styles.btn}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>
      <div className={styles.summariesList}>
        {contacts.map((c) => (
          <div key={c.id} className={styles.summaryCard}>
            <div className={styles.summaryHeader}>
              <strong>{c.full_name}</strong>
              {c.company_name && <span className={styles.summaryMeta}> · {c.company_name}</span>}
              {c.last_contacted_at && (
                <span className={styles.summaryMeta}>
                  {' '}· Last contacted {new Date(c.last_contacted_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </span>
              )}
            </div>
            <p className={styles.summaryParagraph}>
              {c.last_interaction_context || c.last_interaction_summary || 'No interaction context yet.'}
            </p>
          </div>
        ))}
      </div>
      {!loading && contacts.length === 0 && (
        <p className={styles.empty}>No contacts yet. Add one via the Input Prompt tab.</p>
      )}
    </div>
  )
}

function InputPromptTab() {
  const [flow, setFlow] = useState('existing')
  const [contacts, setContacts] = useState([])
  const [contactsLoading, setContactsLoading] = useState(false)
  const [selectedContactId, setSelectedContactId] = useState('')
  const [contactName, setContactName] = useState('')
  const [summary, setSummary] = useState('')
  const [company, setCompany] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [country, setCountry] = useState('United States')
  const [lastContacted, setLastContacted] = useState('')
  const [followUp, setFollowUp] = useState('')
  const [meetingTime, setMeetingTime] = useState('')
  const [meetingContext, setMeetingContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const fetchContacts = async () => {
    setContactsLoading(true)
    try {
      const res = await fetch((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/contacts?limit=100&sort=name_asc')
      const d = await res.json()
      if (!res.ok) {
        console.error('Failed to fetch contacts:', d)
        return
      }
      setContacts(d.contacts || [])
    } catch (e) {
      console.error(e)
    } finally {
      setContactsLoading(false)
    }
  }

  useEffect(() => {
    if (flow === 'existing') fetchContacts()
  }, [flow])

  const submit = async () => {
    if (!summary) {
      alert('Interaction summary is required.')
      return
    }
    if (flow === 'existing' && !selectedContactId) {
      alert('Please select a contact.')
      return
    }
    if (flow === 'new' && (!contactName || !company)) {
      alert('Contact name and company are required for new contact.')
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const baseBody = {
        interaction_summary: summary,
        last_contacted: lastContacted || null,
        follow_up_time: followUp || null,
        meeting_time: meetingTime || null,
        meeting_context: meetingContext || null,
      }
      const body = flow === 'existing'
        ? { contact_id: selectedContactId, ...baseBody }
        : { contact_name: contactName, company, email: email || null, phone: phone || null, country: country || 'United States', ...baseBody }
      const res = await fetch((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      setResult(data)
      if (flow === 'new' && data.status === 'completed') fetchContacts()
    } catch (e) {
      setResult({ status: 'failed', error: String(e) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.tabContent}>
      <div className={styles.form}>
        <label>Flow</label>
        <div className={styles.flowToggle}>
          <button type="button" className={flow === 'existing' ? styles.tabActive : styles.tab} onClick={() => setFlow('existing')}>
            Existing contact
          </button>
          <button type="button" className={flow === 'new' ? styles.tabActive : styles.tab} onClick={() => setFlow('new')}>
            New contact
          </button>
        </div>

        {flow === 'existing' ? (
          <>
            <label>Select contact *</label>
            <div className={styles.selectRow}>
              <select value={selectedContactId} onChange={(e) => setSelectedContactId(e.target.value)} className={styles.select}>
                <option value="">-- Select contact --</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>{c.full_name} {c.company_name ? `(${c.company_name})` : ''}</option>
                ))}
              </select>
              <button type="button" onClick={fetchContacts} disabled={contactsLoading} className={styles.btnSmall}>
                {contactsLoading ? '...' : 'Refresh'}
              </button>
            </div>
          </>
        ) : (
          <>
            <label>Contact name *</label>
            <input value={contactName} onChange={(e) => setContactName(e.target.value)} className={styles.input} />
            <label>Company *</label>
            <input value={company} onChange={(e) => setCompany(e.target.value)} className={styles.input} />
            <label>Email (optional)</label>
            <input type="email" placeholder="contact@example.com" value={email} onChange={(e) => setEmail(e.target.value)} className={styles.input} />
            <label>Phone (optional)</label>
            <input type="tel" placeholder="+1 234 567 8900" value={phone} onChange={(e) => setPhone(e.target.value)} className={styles.input} />
            <label>Country (optional)</label>
            <input placeholder="United States" value={country} onChange={(e) => setCountry(e.target.value)} className={styles.input} />
          </>
        )}

        <label>Interaction summary *</label>
        <textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={4} className={styles.input} placeholder="Summary of the conversation" />
        <label>Last contacted (optional)</label>
        <input type="datetime-local" value={lastContacted} onChange={(e) => setLastContacted(e.target.value)} className={styles.input} title="When you last spoke (defaults to now if left blank)" />
        <label>Follow-up time (optional)</label>
        <input placeholder="e.g. in 2 days, next Tuesday 3pm" value={followUp} onChange={(e) => setFollowUp(e.target.value)} className={styles.input} />
        <label>Meeting time (optional)</label>
        <input placeholder="e.g. tomorrow 6pm" value={meetingTime} onChange={(e) => setMeetingTime(e.target.value)} className={styles.input} />
        <label>Meeting context (optional)</label>
        <input placeholder="Extra context for calendar event" value={meetingContext} onChange={(e) => setMeetingContext(e.target.value)} className={styles.input} />
        <button onClick={submit} disabled={loading} className={styles.btnPrimary}>
          {loading ? 'Processing...' : 'Submit'}
        </button>
      </div>
      {result && (
        <div className={styles.result}>
          <h3>Result</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

'use client'

import { useState, useEffect } from 'react'
import styles from './page.module.css'

const TABS = ['Warm Contacts', 'TODO', 'Input Prompt']

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
        {activeTab === 2 && <InputPromptTab />}
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

function ContactRow({ contact, getWarmthStyle, onSaved }) {
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
          (contact.last_contacted_at ? new Date(contact.last_contacted_at).toLocaleString() : '-')
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
          <button onClick={() => setEditing(true)} className={styles.btnSmall} title="Edit country, last contacted">Edit</button>
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
  const [total, setTotal] = useState(0)

  const fetchContacts = async () => {
    setLoading(true)
    try {
      const url = new URL('/api/contacts', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      if (search) url.searchParams.set('search', search)
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
  }, [])

  const exportCsv = () => {
    window.open((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/export/contacts', '_blank')
  }

  const MAX_DAYS = 14
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
            />
          ))}
        </tbody>
      </table>
      {!loading && contacts.length === 0 && (
        <p className={styles.empty}>No contacts yet. Add one via the Input Prompt tab.</p>
      )}
    </div>
  )
}

function TodosTab() {
  const [todos, setTodos] = useState([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('pending')

  useEffect(() => {
    fetchTodos()
  }, [filter])

  const fetchTodos = async () => {
    setLoading(true)
    try {
      const url = new URL('/api/todos', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      if (filter !== 'all') url.searchParams.set('status', filter)
      const res = await fetch(url)
      const data = await res.json()
      setTodos(data.todos || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const markDone = async (id) => {
    try {
      await fetch((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + `/api/todos/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'done' }),
      })
      fetchTodos()
    } catch (e) {
      console.error(e)
    }
  }

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
        <button onClick={fetchTodos} disabled={loading} className={styles.btn}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
        <button onClick={exportCsv} className={styles.btnSecondary}>Export CSV</button>
      </div>
      <ul className={styles.todoList}>
        {todos.map((t) => (
          <li key={t.id} className={styles.todoItem}>
            <div>
              <strong>{t.title}</strong>
              {t.description && <p className={styles.todoDesc}>{t.description}</p>}
              {t.contact_name && <span className={styles.todoContact}>{t.contact_name}</span>}
            </div>
            {t.status === 'pending' && (
              <button onClick={() => markDone(t.id)} className={styles.btnSmall}>Done</button>
            )}
            {t.status === 'done' && <span className={styles.badge}>Done</span>}
          </li>
        ))}
      </ul>
      {!loading && todos.length === 0 && (
        <p className={styles.empty}>No TODOs. Create via Input Prompt or manually.</p>
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
      const res = await fetch((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/contacts?limit=100')
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

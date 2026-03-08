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

  const getWarmthClass = (lastContacted) => {
    if (!lastContacted) return styles.cold
    const d = new Date(lastContacted)
    const days = (Date.now() - d) / (24 * 60 * 60 * 1000)
    if (days <= 7) return styles.hot
    if (days <= 30) return styles.warm
    if (days <= 90) return styles.cool
    return styles.cold
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
            <th>Phone</th>
            <th>Email</th>
            <th>Last Contacted</th>
            <th>Summary</th>
          </tr>
        </thead>
        <tbody>
          {contacts.map((c) => (
            <tr key={c.id} className={getWarmthClass(c.last_contacted_at)}>
              <td>{c.full_name}</td>
              <td>{c.country || '-'}</td>
              <td>{c.phone || '-'}</td>
              <td>{c.email || '-'}</td>
              <td>{c.last_contacted_at ? new Date(c.last_contacted_at).toLocaleString() : '-'}</td>
              <td>{c.last_interaction_summary || '-'}</td>
            </tr>
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
  const [contactName, setContactName] = useState('')
  const [summary, setSummary] = useState('')
  const [company, setCompany] = useState('')
  const [followUp, setFollowUp] = useState('')
  const [meetingTime, setMeetingTime] = useState('')
  const [meetingContext, setMeetingContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const submit = async () => {
    if (!contactName || !summary || !company) {
      alert('Contact name, interaction summary, and company are required.')
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const res = await fetch((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contact_name: contactName,
          interaction_summary: summary,
          company,
          follow_up_time: followUp || null,
          meeting_time: meetingTime || null,
          meeting_context: meetingContext || null,
        }),
      })
      const data = await res.json()
      setResult(data)
    } catch (e) {
      setResult({ status: 'failed', error: String(e) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.tabContent}>
      <div className={styles.form}>
        <label>Contact name *</label>
        <input value={contactName} onChange={(e) => setContactName(e.target.value)} className={styles.input} />
        <label>Interaction summary *</label>
        <textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={4} className={styles.input} />
        <label>Company *</label>
        <input value={company} onChange={(e) => setCompany(e.target.value)} className={styles.input} />
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

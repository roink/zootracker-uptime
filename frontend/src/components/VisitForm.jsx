import React, { useState, useEffect } from 'react';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';

export default function VisitForm({ token, zoos: propZoos = null, defaultZooId = '', onSaved, onCancel }) {
  const [zoos, setZoos] = useState(propZoos || []);
  const [zooId, setZooId] = useState(defaultZooId);
  const [visitDate, setVisitDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [notes, setNotes] = useState('');
  const authFetch = useAuthFetch();

  useEffect(() => {
    if (!propZoos) {
      fetch(`${API}/zoos`).then(r => r.json()).then(data => {
        setZoos(data);
        if (!zooId && data.length > 0) {
          setZooId(data[0].id);
        }
      });
    }
  }, [propZoos]);

  useEffect(() => {
    if (propZoos && propZoos.length > 0 && !zooId) {
      setZooId(propZoos[0].id);
    }
  }, [propZoos, zooId]);

  const submit = async (e) => {
    e.preventDefault();
    const visit = { zoo_id: zooId, visit_date: visitDate, notes: notes || null };
    const resp = await authFetch(`${API}/visits`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(visit),
    });
    if (resp.status === 401) return;
    if (resp.ok) {
      const data = await resp.json();
      onSaved && onSaved(data);
    } else {
      alert('Failed to save visit');
    }
  };

  return (
    <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <h3>New Visit</h3>
      <select value={zooId} onChange={e => setZooId(e.target.value)} required>
        {zoos.map(z => (
          <option key={z.id} value={z.id}>{z.name}</option>
        ))}
      </select>
      <input type="date" value={visitDate} onChange={e => setVisitDate(e.target.value)} required />
      <textarea placeholder="Notes" value={notes} onChange={e => setNotes(e.target.value)} />
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
        {onCancel && <button type="button" onClick={onCancel}>Cancel</button>}
        <button type="submit">Save Visit</button>
      </div>
    </form>
  );
}

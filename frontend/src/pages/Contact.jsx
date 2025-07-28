import React, { useState } from 'react';
import { API } from '../api';

// Contact form where users can send a message and email address.
export default function ContactPage() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const resp = await fetch(`${API}/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, message }),
      });
      if (resp.ok) {
        setStatus('Message sent!');
        setEmail('');
        setMessage('');
      } else {
        setStatus('Failed to send');
      }
    } catch {
      setStatus('Failed to send');
    }
  };

  return (
    <div className="container py-4">
      <h2>Contact</h2>
      <form onSubmit={handleSubmit} className="mt-3">
        <div className="mb-3">
          <label htmlFor="contactEmail" className="form-label">
            Email
          </label>
          <input
            id="contactEmail"
            type="email"
            className="form-control"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="mb-3">
          <label htmlFor="contactMessage" className="form-label">
            Message
          </label>
          <textarea
            id="contactMessage"
            className="form-control"
            rows="4"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            required
          />
        </div>
        {status && <div className="alert alert-info">{status}</div>}
        <button type="submit" className="btn btn-success">
          Send
        </button>
      </form>
    </div>
  );
}

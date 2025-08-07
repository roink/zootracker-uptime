import { useState } from 'react';
import { API } from '../api';
import Seo from '../components/Seo';

// Contact form where users can send a name, email and message.
export default function ContactPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState(null);
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (sending) return;
    setSending(true);
    try {
      const resp = await fetch(`${API}/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // Send the form values to the API
        body: JSON.stringify({ name, email, message }),
      });
      if (resp.ok) {
        setStatus('Thank you for contacting us!');
        setName('');
        setEmail('');
        setMessage('');
      } else if (resp.status === 429) {
        // Show specific guidance when the rate limit is hit
        setStatus('You are sending messages too fast. Please wait a minute and try again.');
      } else {
        setStatus('Oops, something went wrong.');
      }
    } catch {
      setStatus('Oops, something went wrong.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="container py-4">
      <Seo title="Contact" description="Get in touch with the ZooTracker team." />
      <h2>Contact</h2>
      <form onSubmit={handleSubmit} className="mt-3">
        <div className="mb-3">
          <label htmlFor="contactName" className="form-label">
            Name
          </label>
          <input
            id="contactName"
            type="text"
            className="form-control"
            value={name}
            onChange={(e) => setName(e.target.value)}
            pattern="[A-Za-z\s-]+"
            title="Name can only contain letters, spaces and hyphens"
            maxLength="100"
            required
          />
        </div>
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
            maxLength="2000"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            required
          />
          <div className="form-text text-end">{message.length}/2000</div>
        </div>
        {status && <div className="alert alert-info">{status}</div>}
        <button type="submit" className="btn btn-success" disabled={sending}>
          {sending ? 'Sending…' : 'Send'}
        </button>
      </form>
    </div>
  );
}

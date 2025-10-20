import { API } from '../api';

// Send a request to resend the verification email for the provided address.
export async function requestVerificationEmailResend(email) {
  const response = await fetch(`${API}/auth/verification/request-resend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  let data = {};
  try {
    data = await response.json();
  } catch (err) {
    data = {};
  }
  const detail = typeof data.detail === 'string' ? data.detail : undefined;
  return { response, detail };
}

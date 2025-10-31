import { API } from '../api';
import type { VerificationRequestResult } from '../types/domain';

export async function requestVerificationEmailResend(email: string): Promise<VerificationRequestResult> {
  const response = await fetch(`${API}/auth/verification/request-resend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });
  try {
    const data: unknown = await response.json();
    const rawDetail = (data as { detail?: unknown }).detail;
    if (typeof rawDetail === 'string' && rawDetail.length > 0) {
      return { response, detail: rawDetail };
    }
    return { response };
  } catch {
    return { response };
  }
}

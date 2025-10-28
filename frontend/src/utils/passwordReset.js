const STORAGE_KEY = 'ztr_password_reset_hint';

export function maskEmail(value) {
  if (typeof value !== 'string') {
    return '';
  }
  const trimmed = value.trim();
  const [localPart, domain] = trimmed.split('@');
  if (!localPart || !domain) {
    return '';
  }
  const first = localPart[0];
  const last = localPart.length > 1 ? localPart[localPart.length - 1] : '';
  const maskLength = Math.min(Math.max(localPart.length - 2, 3), 6);
  const masked = '•'.repeat(maskLength);
  return `${first}${masked}${last}@${domain}`;
}

export function saveMaskedEmailHint(email) {
  if (typeof sessionStorage === 'undefined') {
    return;
  }
  const masked = maskEmail(email);
  try {
    if (masked) {
      sessionStorage.setItem(STORAGE_KEY, masked);
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Ignore storage errors (e.g. quota exceeded or disabled storage)
  }
}

export function consumeMaskedEmailHint() {
  if (typeof sessionStorage === 'undefined') {
    return '';
  }
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY) || '';
    if (stored) {
      sessionStorage.removeItem(STORAGE_KEY);
    }
    return stored;
  } catch {
    return '';
  }
}

export function createTestToken({ expOffsetSeconds = 3600, payload = {} } = {}) {
  const base64Url = (obj) =>
    Buffer.from(JSON.stringify(obj))
      .toString('base64')
      .replace(/=/g, '')
      .replace(/\+/g, '-')
      .replace(/\//g, '_');
  const header = { alg: 'HS256', typ: 'JWT' };
  const exp = Math.floor(Date.now() / 1000) + expOffsetSeconds;
  const fullPayload = { exp, ...payload };
  return `${base64Url(header)}.${base64Url(fullPayload)}.signature`;
}

export function setStoredAuth({ token, user }) {
  localStorage.setItem('auth.token', token);
  localStorage.setItem('auth.user', JSON.stringify(user));
}

export function clearStoredAuth() {
  localStorage.removeItem('auth.token');
  localStorage.removeItem('auth.user');
  localStorage.removeItem('token');
  localStorage.removeItem('userId');
  localStorage.removeItem('userEmail');
}

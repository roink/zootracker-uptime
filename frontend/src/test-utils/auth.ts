// @ts-nocheck
export function createTestToken({ expOffsetSeconds = 3600, payload = {} }: any = {}) {
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

const TEST_AUTH_KEY = '__TEST_AUTH_STATE__';

export function setStoredAuth(auth) {
  globalThis[TEST_AUTH_KEY] = auth;
}

export function clearStoredAuth() {
  delete globalThis[TEST_AUTH_KEY];
}

export function getStoredAuth() {
  return globalThis[TEST_AUTH_KEY] || null;
}

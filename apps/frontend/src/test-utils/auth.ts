import type { AuthSuccessPayload } from '../auth/AuthContext';

type CreateTestTokenOptions = {
  expOffsetSeconds?: number;
  payload?: Record<string, unknown>;
};

export function createTestToken({
  expOffsetSeconds = 3600,
  payload = {},
}: CreateTestTokenOptions = {}): string {
  const base64Url = (obj: Record<string, unknown>) =>
    Buffer.from(JSON.stringify(obj))
      .toString('base64')
      .replace(/=/g, '')
      .replace(/\+/g, '-')
      .replace(/\//g, '_');
  const header = { alg: 'HS256', typ: 'JWT' } as const;
  const exp = Math.floor(Date.now() / 1000) + expOffsetSeconds;
  const fullPayload = { exp, ...payload } satisfies Record<string, unknown>;
  return `${base64Url(header)}.${base64Url(fullPayload)}.signature`;
}

const TEST_AUTH_KEY = '__TEST_AUTH_STATE__';

type TestAuthState = AuthSuccessPayload | null;

export function setStoredAuth(auth: TestAuthState): void {
  (globalThis as Record<string, unknown>)[TEST_AUTH_KEY] = auth;
}

export function clearStoredAuth(): void {
  const global = globalThis as Record<string, unknown>;
  global[TEST_AUTH_KEY] = undefined;
}

export function getStoredAuth(): TestAuthState {
  return ((globalThis as Record<string, unknown>)[TEST_AUTH_KEY] as TestAuthState) ?? null;
}

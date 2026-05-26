// Cognito SRP login + token storage.
//
// We store the access token + id token + refresh token in localStorage.
// (Phase 0 acceptable; team-only, no third-party iframes. Phase 1 moves
// to httpOnly cookies + a tiny auth-cookie endpoint.)

import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserPool,
  CognitoUserSession,
} from "amazon-cognito-identity-js";

import { config, cognitoConfigured } from "./config";

const STORAGE_KEY = "cb_session_v1";

interface StoredSession {
  accessToken: string;
  idToken: string;
  refreshToken: string;
  username: string;
  expiresAt: number; // ms epoch
}

function load(): StoredSession | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const s = JSON.parse(raw) as StoredSession;
    if (s.expiresAt < Date.now() + 30_000) return null; // 30s skew buffer
    return s;
  } catch {
    return null;
  }
}

function save(s: StoredSession): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

export function getAccessToken(): string | null {
  return load()?.accessToken ?? null;
}

export function getCurrentUsername(): string | null {
  return load()?.username ?? null;
}

export function isLoggedIn(): boolean {
  return load() !== null;
}

function pool(): CognitoUserPool {
  if (!cognitoConfigured()) {
    throw new Error("Cognito is not configured (VITE_COGNITO_USER_POOL_ID / CLIENT_ID missing)");
  }
  return new CognitoUserPool({
    UserPoolId: config.cognito.userPoolId,
    ClientId: config.cognito.clientId,
  });
}

function sessionToStored(session: CognitoUserSession, username: string): StoredSession {
  const access = session.getAccessToken();
  return {
    accessToken: access.getJwtToken(),
    idToken: session.getIdToken().getJwtToken(),
    refreshToken: session.getRefreshToken().getToken(),
    username,
    expiresAt: access.getExpiration() * 1000,
  };
}

export function login(username: string, password: string): Promise<StoredSession> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: username, Pool: pool() });
    const details = new AuthenticationDetails({ Username: username, Password: password });
    user.authenticateUser(details, {
      onSuccess: (session) => {
        const stored = sessionToStored(session, username);
        save(stored);
        resolve(stored);
      },
      onFailure: (err) => reject(err),
      newPasswordRequired: () =>
        reject(new Error("User must change password — set a permanent password first")),
    });
  });
}

export function logout(): void {
  localStorage.removeItem(STORAGE_KEY);
  const username = load()?.username;
  if (username) {
    const user = new CognitoUser({ Username: username, Pool: pool() });
    user.signOut();
  }
}

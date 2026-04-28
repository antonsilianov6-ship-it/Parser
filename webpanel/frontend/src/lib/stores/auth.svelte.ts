/**
 * Authentication store backed by Svelte 5 runes and ``localStorage``.
 *
 * The backend returns a plain JWT from ``POST /api/auth/login``; we keep it in
 * memory (for reactivity) and mirror it to ``localStorage`` so the token survives
 * page reloads. ``user`` is the cached ``GET /api/auth/me`` response.
 */
import { browser } from '$app/environment';

const TOKEN_KEY = 'panel.token';

export interface PanelUser {
	id: number;
	username: string;
	is_active: boolean;
	created_at: string;
	updated_at: string;
}

function readInitialToken(): string | null {
	if (!browser) return null;
	try {
		return localStorage.getItem(TOKEN_KEY);
	} catch {
		return null;
	}
}

class AuthStore {
	token: string | null = $state(readInitialToken());
	user: PanelUser | null = $state(null);
	loading = $state(false);

	get isAuthenticated(): boolean {
		return this.token !== null;
	}

	setToken(token: string): void {
		this.token = token;
		if (browser) {
			try {
				localStorage.setItem(TOKEN_KEY, token);
			} catch {
				/* ignore quota / disabled storage */
			}
		}
	}

	setUser(user: PanelUser | null): void {
		this.user = user;
	}

	clear(): void {
		this.token = null;
		this.user = null;
		if (browser) {
			try {
				localStorage.removeItem(TOKEN_KEY);
			} catch {
				/* ignore */
			}
		}
	}
}

export const auth = new AuthStore();

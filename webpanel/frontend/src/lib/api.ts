/**
 * Minimal fetch wrapper that attaches the stored JWT, parses JSON and converts
 * non-2xx responses into {@link ApiError}s.
 */
import { auth } from '$lib/stores/auth.svelte';

export class ApiError extends Error {
	status: number;
	detail: unknown;
	constructor(status: number, detail: unknown) {
		const message =
			typeof detail === 'object' && detail !== null && 'detail' in detail
				? String((detail as { detail: unknown }).detail)
				: `HTTP ${status}`;
		super(message);
		this.status = status;
		this.detail = detail;
	}
}

export interface ApiOptions {
	method?: string;
	body?: unknown;
	headers?: Record<string, string>;
	signal?: AbortSignal;
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
	const headers: Record<string, string> = {
		Accept: 'application/json',
		...options.headers
	};
	if (options.body !== undefined) {
		headers['Content-Type'] = 'application/json';
	}
	const token = auth.token;
	if (token) {
		headers.Authorization = `Bearer ${token}`;
	}

	const response = await fetch(path, {
		method: options.method ?? 'GET',
		headers,
		body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
		signal: options.signal
	});

	if (response.status === 401) {
		auth.clear();
	}

	if (!response.ok) {
		let detail: unknown = undefined;
		try {
			detail = await response.json();
		} catch {
			detail = await response.text();
		}
		throw new ApiError(response.status, detail);
	}

	if (response.status === 204) {
		return undefined as T;
	}

	const contentType = response.headers.get('content-type') ?? '';
	if (contentType.includes('application/json')) {
		return (await response.json()) as T;
	}
	return (await response.text()) as T;
}

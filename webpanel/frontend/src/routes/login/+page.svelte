<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { auth, type PanelUser } from '$lib/stores/auth.svelte';
	import type { TokenResponse } from '$lib/types';

	let username = $state('');
	let password = $state('');
	let submitting = $state(false);
	let errorMessage = $state<string | null>(null);

	async function handleSubmit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (submitting) return;
		submitting = true;
		errorMessage = null;
		try {
			const { access_token } = await api<TokenResponse>('/api/auth/login', {
				method: 'POST',
				body: { username, password }
			});
			auth.setToken(access_token);
			const me = await api<PanelUser>('/api/auth/me');
			auth.setUser(me);
			goto('/', { replaceState: true });
		} catch (error) {
			if (error instanceof ApiError) {
				errorMessage =
					error.status === 401 ? 'Неверный логин или пароль' : error.message;
			} else {
				errorMessage = 'Сервер недоступен';
			}
		} finally {
			submitting = false;
		}
	}
</script>

<div class="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
	<div
		class="pointer-events-none absolute -top-32 -right-24 h-80 w-80 rounded-full bg-sky-300/40 blur-3xl
			dark:bg-sky-700/30"
		aria-hidden="true"
	></div>
	<div
		class="pointer-events-none absolute -bottom-32 -left-24 h-80 w-80 rounded-full bg-indigo-300/40 blur-3xl
			dark:bg-indigo-800/30"
		aria-hidden="true"
	></div>

	<form
		onsubmit={handleSubmit}
		class="relative w-full max-w-sm space-y-6 rounded-2xl border border-slate-200/70 bg-white/90 p-7 shadow-xl shadow-slate-900/5 backdrop-blur-sm
			dark:border-slate-800/70 dark:bg-slate-900/90 dark:shadow-black/30"
	>
		<div class="flex flex-col items-center gap-3 text-center">
			<span
				class="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 text-lg font-bold text-white shadow-lg shadow-sky-600/30"
				aria-hidden="true"
			>
				P
			</span>
			<div>
				<h1 class="text-xl font-semibold tracking-tight">Parser Admin</h1>
				<p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
					Вход в панель управления ботом
				</p>
			</div>
		</div>

		<div class="space-y-4">
			<label class="block space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">Логин</span>
				<input
					type="text"
					required
					autocomplete="username"
					bind:value={username}
					class="input"
				/>
			</label>

			<label class="block space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">Пароль</span>
				<input
					type="password"
					required
					autocomplete="current-password"
					bind:value={password}
					class="input"
				/>
			</label>
		</div>

		{#if errorMessage}
			<div class="banner-error">
				<svg
					class="mt-0.5 h-4 w-4 shrink-0"
					viewBox="0 0 20 20"
					fill="currentColor"
					aria-hidden="true"
				>
					<path
						fill-rule="evenodd"
						d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
						clip-rule="evenodd"
					/>
				</svg>
				<span>{errorMessage}</span>
			</div>
		{/if}

		<button type="submit" disabled={submitting} class="btn-primary w-full">
			{submitting ? 'Входим…' : 'Войти'}
		</button>
	</form>
</div>

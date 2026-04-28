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

<div class="flex min-h-screen items-center justify-center bg-slate-100 px-4 dark:bg-slate-950">
	<form
		onsubmit={handleSubmit}
		class="w-full max-w-sm space-y-5 rounded-lg border border-slate-200 bg-white p-6 shadow-md dark:border-slate-800 dark:bg-slate-900"
	>
		<div>
			<h1 class="text-xl font-semibold">Parser Admin</h1>
			<p class="mt-1 text-sm text-slate-500">Вход в панель</p>
		</div>

		<label class="block space-y-1 text-sm">
			<span class="text-slate-700 dark:text-slate-300">Логин</span>
			<input
				type="text"
				required
				autocomplete="username"
				bind:value={username}
				class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200 dark:border-slate-700 dark:bg-slate-950"
			/>
		</label>

		<label class="block space-y-1 text-sm">
			<span class="text-slate-700 dark:text-slate-300">Пароль</span>
			<input
				type="password"
				required
				autocomplete="current-password"
				bind:value={password}
				class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200 dark:border-slate-700 dark:bg-slate-950"
			/>
		</label>

		{#if errorMessage}
			<p class="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950 dark:text-rose-300">
				{errorMessage}
			</p>
		{/if}

		<button
			type="submit"
			disabled={submitting}
			class="w-full rounded-md bg-sky-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
		>
			{submitting ? 'Входим…' : 'Войти'}
		</button>
	</form>
</div>

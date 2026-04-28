<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import type { TelegramAccount } from '$lib/types';

	let accounts = $state<TelegramAccount[]>([]);
	let loading = $state(false);
	let errorMessage = $state<string | null>(null);

	let newLabel = $state('');
	let newPhone = $state('');
	let newShared = $state(false);
	let submitting = $state(false);
	let formError = $state<string | null>(null);

	async function refresh(): Promise<void> {
		loading = true;
		errorMessage = null;
		try {
			accounts = await api<TelegramAccount[]>('/api/telegram/accounts');
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : String(error);
		} finally {
			loading = false;
		}
	}

	async function handleCreate(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (submitting) return;
		submitting = true;
		formError = null;
		try {
			await api<TelegramAccount>('/api/telegram/accounts', {
				method: 'POST',
				body: {
					label: newLabel,
					phone: newPhone || null,
					is_shared: newShared
				}
			});
			newLabel = '';
			newPhone = '';
			newShared = false;
			await refresh();
		} catch (error) {
			formError = error instanceof ApiError ? error.message : String(error);
		} finally {
			submitting = false;
		}
	}

	async function toggleShared(account: TelegramAccount): Promise<void> {
		try {
			await api<TelegramAccount>(`/api/telegram/accounts/${account.id}`, {
				method: 'PATCH',
				body: { is_shared: !account.is_shared }
			});
			await refresh();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : String(error);
		}
	}

	async function deleteAccount(account: TelegramAccount): Promise<void> {
		if (account.owner_id !== auth.user?.id) return;
		if (!confirm(`Удалить Telegram-аккаунт ${account.label}?`)) return;
		try {
			await api<void>(`/api/telegram/accounts/${account.id}`, { method: 'DELETE' });
			await refresh();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : String(error);
		}
	}

	$effect(() => {
		refresh();
	});
</script>

<div class="space-y-6">
	<header class="flex flex-col gap-1">
		<p class="text-xs font-medium uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
			Telethon
		</p>
		<h1 class="text-2xl font-semibold tracking-tight">Telegram-аккаунты</h1>
		<p class="max-w-3xl text-sm text-slate-500 dark:text-slate-400">
			Видны свои аккаунты и все аккаунты других пользователей с флагом <em>shared</em>. Реальный
			логин через Telethon (send-code / sign-in / 2FA) подключается в следующем PR.
		</p>
	</header>

	<form onsubmit={handleCreate} class="card p-4">
		<div class="flex flex-wrap items-end gap-3">
			<label class="min-w-[160px] flex-1 space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">Метка</span>
				<input
					type="text"
					required
					minlength="1"
					maxlength="64"
					bind:value={newLabel}
					placeholder="main"
					class="input"
				/>
			</label>
			<label class="min-w-[180px] flex-1 space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">Телефон</span>
				<input
					type="text"
					maxlength="32"
					bind:value={newPhone}
					placeholder="+79990001122"
					class="input"
				/>
			</label>
			<label
				class="flex cursor-pointer select-none items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm transition
					hover:border-slate-300
					dark:border-slate-700 dark:bg-slate-950/60 dark:hover:border-slate-600"
			>
				<input
					type="checkbox"
					bind:checked={newShared}
					class="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
				/>
				<span class="font-medium text-slate-700 dark:text-slate-300">Расшарить всем</span>
			</label>
			<button type="submit" disabled={submitting} class="btn-primary">
				{submitting ? 'Создаём…' : 'Добавить слот'}
			</button>
		</div>
		{#if formError}
			<div class="banner-error mt-3">
				<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
					<path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd" />
				</svg>
				<span>{formError}</span>
			</div>
		{/if}
	</form>

	<div class="table-wrap overflow-x-auto">
		<table class="table-base">
			<thead>
				<tr>
					<th class="w-12">ID</th>
					<th>Метка</th>
					<th>Телефон</th>
					<th>Владелец</th>
					<th>Статус</th>
					<th>Shared</th>
					<th class="text-right">Действия</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-slate-100 dark:divide-slate-800">
				{#if loading && accounts.length === 0}
					<tr><td class="text-slate-500" colspan="7">Загрузка…</td></tr>
				{:else if accounts.length === 0}
					<tr>
						<td class="text-slate-500" colspan="7">
							<div class="flex flex-col items-center gap-2 py-6 text-center">
								<svg class="h-10 w-10 text-slate-300 dark:text-slate-600" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
									<path d="M21.9 4.3 18.7 19.4c-.2 1-.9 1.3-1.8.8l-5-3.7-2.4 2.3c-.3.3-.5.5-1 .5l.4-5.2 9.4-8.5c.4-.4-.1-.6-.6-.2L5.8 13l-5-1.6c-1.1-.3-1.1-1 .2-1.6L20.4 2.7c.9-.3 1.7.2 1.5 1.6Z" />
								</svg>
								<p class="text-sm">Пока нет аккаунтов</p>
								<p class="text-xs text-slate-400">Добавьте первый слот в форме выше</p>
							</div>
						</td>
					</tr>
				{/if}
				{#each accounts as account (account.id)}
					{@const isOwner = account.owner_id === auth.user?.id}
					<tr>
						<td class="font-mono text-xs text-slate-500">{account.id}</td>
						<td>
							<div class="flex flex-col">
								<span class="font-medium">{account.label}</span>
								<span class="font-mono text-[11px] text-slate-400">{account.session_path}</span>
							</div>
						</td>
						<td class="font-mono text-xs text-slate-500">{account.phone ?? '—'}</td>
						<td class="text-xs text-slate-500">
							{#if isOwner}
								<span class="pill-slate">вы</span>
							{:else}
								<span>#{account.owner_id}</span>
							{/if}
						</td>
						<td>
							{#if account.is_authorized}
								<span class="pill-green">
									<span class="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden="true"></span>
									авторизован
								</span>
							{:else}
								<span class="pill-amber">
									<span class="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden="true"></span>
									не авторизован
								</span>
							{/if}
						</td>
						<td>
							{#if account.is_shared}
								<span class="pill-sky">shared</span>
							{:else}
								<span class="pill-slate">private</span>
							{/if}
						</td>
						<td class="text-right">
							<div class="inline-flex gap-2">
								<button
									class="btn-secondary btn-sm"
									disabled={!isOwner}
									onclick={() => toggleShared(account)}
								>
									{account.is_shared ? 'Убрать shared' : 'Расшарить'}
								</button>
								<button
									class="btn-danger btn-sm"
									disabled={!isOwner}
									onclick={() => deleteAccount(account)}
								>
									Удалить
								</button>
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	{#if errorMessage}
		<div class="banner-error">
			<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
				<path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd" />
			</svg>
			<span>{errorMessage}</span>
		</div>
	{/if}
</div>

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

<div class="mx-auto max-w-5xl space-y-6">
	<div>
		<h1 class="text-2xl font-semibold">Telegram-аккаунты</h1>
		<p class="mt-1 text-sm text-slate-500">
			Видны свои аккаунты и все аккаунты других пользователей с флагом <em>shared</em>.
			Реальный логин через Telethon (send-code / sign-in / 2FA) подключается в следующем PR.
		</p>
	</div>

	<form
		onsubmit={handleCreate}
		class="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
	>
		<label class="flex-1 min-w-[160px] space-y-1 text-sm">
			<span class="text-slate-700 dark:text-slate-300">Метка</span>
			<input
				type="text"
				required
				minlength="1"
				maxlength="64"
				bind:value={newLabel}
				placeholder="main"
				class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200 dark:border-slate-700 dark:bg-slate-950"
			/>
		</label>
		<label class="flex-1 min-w-[180px] space-y-1 text-sm">
			<span class="text-slate-700 dark:text-slate-300">Телефон</span>
			<input
				type="text"
				maxlength="32"
				bind:value={newPhone}
				placeholder="+79990001122"
				class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200 dark:border-slate-700 dark:bg-slate-950"
			/>
		</label>
		<label class="flex items-center gap-2 text-sm">
			<input type="checkbox" bind:checked={newShared} class="h-4 w-4" />
			<span class="text-slate-700 dark:text-slate-300">Расшарить всем</span>
		</label>
		<button
			type="submit"
			disabled={submitting}
			class="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
		>
			{submitting ? 'Создаём…' : 'Добавить слот'}
		</button>
		{#if formError}
			<p class="w-full text-sm text-rose-600">{formError}</p>
		{/if}
	</form>

	<div class="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
		<table class="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
			<thead class="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-800 dark:text-slate-400">
				<tr>
					<th class="px-4 py-2">ID</th>
					<th class="px-4 py-2">Метка</th>
					<th class="px-4 py-2">Телефон</th>
					<th class="px-4 py-2">Владелец</th>
					<th class="px-4 py-2">Статус</th>
					<th class="px-4 py-2">Shared</th>
					<th class="px-4 py-2 text-right">Действия</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-slate-200 dark:divide-slate-800">
				{#if loading && accounts.length === 0}
					<tr><td class="px-4 py-3 text-slate-500" colspan="7">Загрузка…</td></tr>
				{:else if accounts.length === 0}
					<tr><td class="px-4 py-3 text-slate-500" colspan="7">Пока нет аккаунтов</td></tr>
				{/if}
				{#each accounts as account (account.id)}
					{@const isOwner = account.owner_id === auth.user?.id}
					<tr>
						<td class="px-4 py-2 font-mono text-xs text-slate-500">{account.id}</td>
						<td class="px-4 py-2 font-medium">
							{account.label}
							<div class="text-xs font-mono text-slate-400">{account.session_path}</div>
						</td>
						<td class="px-4 py-2 text-xs text-slate-500">{account.phone ?? '—'}</td>
						<td class="px-4 py-2 text-xs text-slate-500">
							{isOwner ? 'вы' : `#${account.owner_id}`}
						</td>
						<td class="px-4 py-2">
							<span
								class="inline-block rounded-full px-2 py-0.5 text-xs {account.is_authorized
									? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300'
									: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300'}"
							>
								{account.is_authorized ? 'авторизован' : 'не авторизован'}
							</span>
						</td>
						<td class="px-4 py-2">
							<span
								class="inline-block rounded-full px-2 py-0.5 text-xs {account.is_shared
									? 'bg-sky-100 text-sky-700 dark:bg-sky-900 dark:text-sky-300'
									: 'bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400'}"
							>
								{account.is_shared ? 'shared' : 'private'}
							</span>
						</td>
						<td class="px-4 py-2 text-right space-x-2">
							<button
								class="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 disabled:opacity-40 dark:border-slate-700 dark:hover:bg-slate-800"
								disabled={!isOwner}
								onclick={() => toggleShared(account)}
							>
								{account.is_shared ? 'Убрать shared' : 'Расшарить'}
							</button>
							<button
								class="rounded-md border border-rose-300 px-2 py-1 text-xs text-rose-700 hover:bg-rose-50 disabled:opacity-40 dark:border-rose-800 dark:text-rose-400 dark:hover:bg-rose-950"
								disabled={!isOwner}
								onclick={() => deleteAccount(account)}
							>
								Удалить
							</button>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	{#if errorMessage}
		<p class="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950 dark:text-rose-300">
			{errorMessage}
		</p>
	{/if}
</div>

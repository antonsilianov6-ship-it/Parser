<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import type { PanelUser } from '$lib/types';

	let users = $state<PanelUser[]>([]);
	let loading = $state(false);
	let errorMessage = $state<string | null>(null);

	let newUsername = $state('');
	let newPassword = $state('');
	let submitting = $state(false);
	let formError = $state<string | null>(null);

	async function refresh(): Promise<void> {
		loading = true;
		errorMessage = null;
		try {
			users = await api<PanelUser[]>('/api/users');
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
			await api<PanelUser>('/api/users', {
				method: 'POST',
				body: { username: newUsername, password: newPassword }
			});
			newUsername = '';
			newPassword = '';
			await refresh();
		} catch (error) {
			formError = error instanceof ApiError ? error.message : String(error);
		} finally {
			submitting = false;
		}
	}

	async function toggleActive(user: PanelUser): Promise<void> {
		try {
			await api<PanelUser>(`/api/users/${user.id}`, {
				method: 'PATCH',
				body: { is_active: !user.is_active }
			});
			await refresh();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : String(error);
		}
	}

	async function deleteUser(user: PanelUser): Promise<void> {
		if (user.id === auth.user?.id) return;
		if (!confirm(`Удалить пользователя ${user.username}?`)) return;
		try {
			await api<void>(`/api/users/${user.id}`, { method: 'DELETE' });
			await refresh();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : String(error);
		}
	}

	$effect(() => {
		refresh();
	});
</script>

<div class="mx-auto max-w-4xl space-y-6">
	<div>
		<h1 class="text-2xl font-semibold">Пользователи</h1>
		<p class="mt-1 text-sm text-slate-500">
			Все пользователи равноправны. Удалить последнего или самого себя нельзя.
		</p>
	</div>

	<form
		onsubmit={handleCreate}
		class="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
	>
		<label class="flex-1 min-w-[160px] space-y-1 text-sm">
			<span class="text-slate-700 dark:text-slate-300">Логин</span>
			<input
				type="text"
				required
				minlength="3"
				bind:value={newUsername}
				class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200 dark:border-slate-700 dark:bg-slate-950"
			/>
		</label>
		<label class="flex-1 min-w-[200px] space-y-1 text-sm">
			<span class="text-slate-700 dark:text-slate-300">Пароль</span>
			<input
				type="password"
				required
				minlength="8"
				bind:value={newPassword}
				class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200 dark:border-slate-700 dark:bg-slate-950"
			/>
		</label>
		<button
			type="submit"
			disabled={submitting}
			class="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
		>
			{submitting ? 'Создаём…' : 'Добавить'}
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
					<th class="px-4 py-2">Логин</th>
					<th class="px-4 py-2">Активен</th>
					<th class="px-4 py-2">Создан</th>
					<th class="px-4 py-2 text-right">Действия</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-slate-200 dark:divide-slate-800">
				{#if loading && users.length === 0}
					<tr><td class="px-4 py-3 text-slate-500" colspan="5">Загрузка…</td></tr>
				{:else if users.length === 0}
					<tr><td class="px-4 py-3 text-slate-500" colspan="5">Нет пользователей</td></tr>
				{/if}
				{#each users as user (user.id)}
					<tr>
						<td class="px-4 py-2 font-mono text-xs text-slate-500">{user.id}</td>
						<td class="px-4 py-2 font-medium">{user.username}</td>
						<td class="px-4 py-2">
							<span
								class="inline-block rounded-full px-2 py-0.5 text-xs {user.is_active
									? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300'
									: 'bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400'}"
							>
								{user.is_active ? 'активен' : 'выключен'}
							</span>
						</td>
						<td class="px-4 py-2 text-xs text-slate-500">
							{new Date(user.created_at).toLocaleString()}
						</td>
						<td class="px-4 py-2 text-right space-x-2">
							<button
								class="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
								onclick={() => toggleActive(user)}
							>
								{user.is_active ? 'Выключить' : 'Включить'}
							</button>
							<button
								class="rounded-md border border-rose-300 px-2 py-1 text-xs text-rose-700 hover:bg-rose-50 disabled:opacity-40 dark:border-rose-800 dark:text-rose-400 dark:hover:bg-rose-950"
								disabled={user.id === auth.user?.id}
								onclick={() => deleteUser(user)}
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

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

	function initial(username: string): string {
		return username.slice(0, 1).toUpperCase();
	}

	$effect(() => {
		refresh();
	});
</script>

<div class="space-y-6">
	<header class="flex flex-col gap-1">
		<p class="text-xs font-medium uppercase tracking-wider text-sky-600 dark:text-sky-400">
			Доступ
		</p>
		<h1 class="text-2xl font-semibold tracking-tight">Пользователи</h1>
		<p class="text-sm text-slate-500 dark:text-slate-400">
			Все пользователи равноправны. Удалить последнего или самого себя нельзя.
		</p>
	</header>

	<form onsubmit={handleCreate} class="card p-4">
		<div class="flex flex-wrap items-end gap-3">
			<label class="min-w-[180px] flex-1 space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">Логин</span>
				<input
					type="text"
					required
					minlength="3"
					bind:value={newUsername}
					placeholder="alice"
					class="input"
				/>
			</label>
			<label class="min-w-[220px] flex-1 space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">Пароль</span>
				<input
					type="password"
					required
					minlength="8"
					bind:value={newPassword}
					placeholder="минимум 8 символов"
					class="input"
				/>
			</label>
			<button type="submit" disabled={submitting} class="btn-primary">
				{submitting ? 'Создаём…' : 'Добавить'}
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
					<th>Логин</th>
					<th>Активен</th>
					<th>Создан</th>
					<th class="text-right">Действия</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-slate-100 dark:divide-slate-800">
				{#if loading && users.length === 0}
					<tr><td class="text-slate-500" colspan="5">Загрузка…</td></tr>
				{:else if users.length === 0}
					<tr><td class="text-slate-500" colspan="5">Нет пользователей</td></tr>
				{/if}
				{#each users as user (user.id)}
					<tr>
						<td class="font-mono text-xs text-slate-500">{user.id}</td>
						<td>
							<div class="flex items-center gap-2.5">
								<span
									class="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 to-indigo-600 text-[11px] font-semibold text-white"
									aria-hidden="true"
								>
									{initial(user.username)}
								</span>
								<span class="font-medium">
									{user.username}
									{#if user.id === auth.user?.id}
										<span class="ml-1 text-xs font-normal text-slate-400">(вы)</span>
									{/if}
								</span>
							</div>
						</td>
						<td>
							{#if user.is_active}
								<span class="pill-green">
									<span class="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden="true"></span>
									активен
								</span>
							{:else}
								<span class="pill-slate">
									<span class="h-1.5 w-1.5 rounded-full bg-slate-400" aria-hidden="true"></span>
									выключен
								</span>
							{/if}
						</td>
						<td class="text-xs text-slate-500">
							{new Date(user.created_at).toLocaleString()}
						</td>
						<td class="text-right">
							<div class="inline-flex gap-2">
								<button class="btn-secondary btn-sm" onclick={() => toggleActive(user)}>
									{user.is_active ? 'Выключить' : 'Включить'}
								</button>
								<button
									class="btn-danger btn-sm"
									disabled={user.id === auth.user?.id}
									onclick={() => deleteUser(user)}
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

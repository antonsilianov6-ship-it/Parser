<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import type { SendCodeResponse, TelegramAccount, VerifyResponse } from '$lib/types';

	let accounts = $state<TelegramAccount[]>([]);
	let loading = $state(false);
	let errorMessage = $state<string | null>(null);

	let newLabel = $state('');
	let newPhone = $state('');
	let newShared = $state(false);
	let submitting = $state(false);
	let formError = $state<string | null>(null);

	type AuthStep = 'creds' | 'code' | 'password';
	let authAccount = $state<TelegramAccount | null>(null);
	let authStep = $state<AuthStep>('creds');
	let authApiId = $state('');
	let authApiHash = $state('');
	let authPhone = $state('');
	let authCode = $state('');
	let authPassword = $state('');
	let authBusy = $state(false);
	let authError = $state<string | null>(null);

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

	function openAuth(account: TelegramAccount): void {
		authAccount = account;
		authStep = 'creds';
		authApiId = account.api_id ? String(account.api_id) : '';
		authApiHash = '';
		authPhone = account.phone ?? '';
		authCode = '';
		authPassword = '';
		authError = null;
		authBusy = false;
	}

	function closeAuth(): void {
		authAccount = null;
		authError = null;
		authBusy = false;
	}

	async function submitAuthCreds(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!authAccount || authBusy) return;
		authBusy = true;
		authError = null;
		try {
			await api<SendCodeResponse>(`/api/telegram/accounts/${authAccount.id}/send-code`, {
				method: 'POST',
				body: {
					api_id: Number(authApiId),
					api_hash: authApiHash.trim(),
					phone: authPhone.trim()
				}
			});
			authStep = 'code';
		} catch (error) {
			authError = error instanceof ApiError ? error.message : String(error);
		} finally {
			authBusy = false;
		}
	}

	async function submitAuthCode(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!authAccount || authBusy) return;
		authBusy = true;
		authError = null;
		try {
			const result = await api<VerifyResponse>(
				`/api/telegram/accounts/${authAccount.id}/verify`,
				{
					method: 'POST',
					body: { code: authCode.trim() }
				}
			);
			if (result.needs_password) {
				authStep = 'password';
			} else if (result.is_authorized) {
				await refresh();
				closeAuth();
			}
		} catch (error) {
			authError = error instanceof ApiError ? error.message : String(error);
		} finally {
			authBusy = false;
		}
	}

	async function submitAuthPassword(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!authAccount || authBusy) return;
		authBusy = true;
		authError = null;
		try {
			const result = await api<VerifyResponse>(
				`/api/telegram/accounts/${authAccount.id}/verify`,
				{
					method: 'POST',
					body: { password: authPassword }
				}
			);
			if (result.is_authorized) {
				await refresh();
				closeAuth();
			} else {
				authError = 'Неожиданный ответ от сервера, попробуйте ещё раз';
			}
		} catch (error) {
			authError = error instanceof ApiError ? error.message : String(error);
		} finally {
			authBusy = false;
		}
	}

	async function logoutAccount(account: TelegramAccount): Promise<void> {
		if (account.owner_id !== auth.user?.id) return;
		if (!confirm(`Выйти из Telegram-аккаунта ${account.label}?`)) return;
		try {
			await api<TelegramAccount>(`/api/telegram/accounts/${account.id}/logout`, {
				method: 'POST'
			});
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
			Каждый слот — независимая Telethon-сессия со своей парой <code>api_id</code> /
			<code>api_hash</code>. Чем больше авторизованных аккаунтов, тем больше параллельных
			подключений доступно парсеру.
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
				<span class="font-medium text-slate-700 dark:text-slate-300">Телефон (необязательно)</span>
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
							<div class="inline-flex flex-wrap justify-end gap-2">
								{#if isOwner}
									{#if account.is_authorized}
										<button class="btn-secondary btn-sm" onclick={() => logoutAccount(account)}>
											Выйти
										</button>
									{:else}
										<button class="btn-primary btn-sm" onclick={() => openAuth(account)}>
											Авторизовать
										</button>
									{/if}
								{/if}
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

{#if authAccount}
	<div
		class="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/50 px-4 backdrop-blur-sm"
		role="dialog"
		aria-modal="true"
		aria-labelledby="auth-modal-title"
	>
		<div
			class="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl
				dark:border-slate-800 dark:bg-slate-950"
		>
			<div class="mb-4 flex items-start justify-between gap-3">
				<div>
					<p class="text-xs font-medium uppercase tracking-wider text-sky-600">Авторизация</p>
					<h2 id="auth-modal-title" class="text-lg font-semibold tracking-tight">
						{authAccount.label}
					</h2>
				</div>
				<button
					class="rounded-md p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600
						dark:hover:bg-slate-900 dark:hover:text-slate-300"
					aria-label="Закрыть"
					onclick={closeAuth}
				>
					<svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
						<path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
					</svg>
				</button>
			</div>

			<ol class="mb-5 flex items-center gap-2 text-xs font-medium">
				{#each ['creds', 'code', 'password'] as step, idx}
					{@const isActive = authStep === step}
					{@const isDone =
						(step === 'creds' && authStep !== 'creds') ||
						(step === 'code' && authStep === 'password')}
					<li class="flex items-center gap-2">
						<span
							class={`flex h-6 w-6 items-center justify-center rounded-full text-[11px]
								${
									isActive
										? 'bg-sky-500 text-white shadow-sm shadow-sky-500/40'
										: isDone
										? 'bg-emerald-500 text-white'
										: 'bg-slate-100 text-slate-400 dark:bg-slate-900 dark:text-slate-500'
								}`}
						>
							{idx + 1}
						</span>
						<span
							class={`capitalize
								${isActive ? 'text-slate-900 dark:text-slate-100' : 'text-slate-400'}`}
						>
							{step === 'creds' ? 'Креды' : step === 'code' ? 'Код' : '2FA'}
						</span>
						{#if idx < 2}
							<span class="mx-1 h-px w-6 bg-slate-200 dark:bg-slate-800"></span>
						{/if}
					</li>
				{/each}
			</ol>

			{#if authStep === 'creds'}
				<form onsubmit={submitAuthCreds} class="space-y-3">
					<p class="text-xs text-slate-500 dark:text-slate-400">
						API-креды получите на
						<a
							href="https://my.telegram.org/apps"
							target="_blank"
							rel="noopener noreferrer"
							class="font-medium text-sky-600 hover:underline"
						>
							my.telegram.org
						</a>
						→ API development tools. Хэш хранится только на сервере; при повторной авторизации
						введите заново.
					</p>
					<label class="block space-y-1.5 text-sm">
						<span class="font-medium text-slate-700 dark:text-slate-300">API_ID</span>
						<input
							type="number"
							required
							min="1"
							bind:value={authApiId}
							placeholder="12345678"
							class="input"
						/>
					</label>
					<label class="block space-y-1.5 text-sm">
						<span class="font-medium text-slate-700 dark:text-slate-300">API_HASH</span>
						<input
							type="password"
							required
							minlength="8"
							maxlength="64"
							bind:value={authApiHash}
							placeholder="••••••••"
							class="input font-mono"
						/>
					</label>
					<label class="block space-y-1.5 text-sm">
						<span class="font-medium text-slate-700 dark:text-slate-300">Телефон</span>
						<input
							type="tel"
							required
							minlength="5"
							maxlength="32"
							bind:value={authPhone}
							placeholder="+79990001122"
							class="input font-mono"
						/>
					</label>
					{#if authError}
						<div class="banner-error">
							<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
								<path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd" />
							</svg>
							<span>{authError}</span>
						</div>
					{/if}
					<div class="flex justify-end gap-2 pt-1">
						<button type="button" class="btn-secondary" onclick={closeAuth}>Отмена</button>
						<button type="submit" class="btn-primary" disabled={authBusy}>
							{authBusy ? 'Отправляем…' : 'Получить код'}
						</button>
					</div>
				</form>
			{:else if authStep === 'code'}
				<form onsubmit={submitAuthCode} class="space-y-3">
					<p class="text-xs text-slate-500 dark:text-slate-400">
						Код отправлен в Telegram на номер <span class="font-mono">{authPhone}</span>.
						Проверьте «Избранное» или входящие сообщения от Telegram.
					</p>
					<label class="block space-y-1.5 text-sm">
						<span class="font-medium text-slate-700 dark:text-slate-300">Код подтверждения</span>
						<input
							type="text"
							required
							minlength="3"
							maxlength="16"
							bind:value={authCode}
							placeholder="12345"
							class="input text-center font-mono text-lg tracking-widest"
							inputmode="numeric"
							autocomplete="one-time-code"
						/>
					</label>
					{#if authError}
						<div class="banner-error">
							<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
								<path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd" />
							</svg>
							<span>{authError}</span>
						</div>
					{/if}
					<div class="flex justify-end gap-2 pt-1">
						<button
							type="button"
							class="btn-secondary"
							onclick={() => {
								authStep = 'creds';
								authError = null;
							}}
						>
							Назад
						</button>
						<button type="submit" class="btn-primary" disabled={authBusy}>
							{authBusy ? 'Проверяем…' : 'Подтвердить'}
						</button>
					</div>
				</form>
			{:else}
				<form onsubmit={submitAuthPassword} class="space-y-3">
					<p class="text-xs text-slate-500 dark:text-slate-400">
						У аккаунта включена двухфакторная защита. Введите облачный пароль Telegram.
					</p>
					<label class="block space-y-1.5 text-sm">
						<span class="font-medium text-slate-700 dark:text-slate-300">Облачный пароль</span>
						<input
							type="password"
							required
							maxlength="256"
							bind:value={authPassword}
							placeholder="••••••••"
							class="input"
							autocomplete="current-password"
						/>
					</label>
					{#if authError}
						<div class="banner-error">
							<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
								<path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd" />
							</svg>
							<span>{authError}</span>
						</div>
					{/if}
					<div class="flex justify-end gap-2 pt-1">
						<button type="button" class="btn-secondary" onclick={closeAuth}>Отмена</button>
						<button type="submit" class="btn-primary" disabled={authBusy}>
							{authBusy ? 'Входим…' : 'Завершить'}
						</button>
					</div>
				</form>
			{/if}
		</div>
	</div>
{/if}

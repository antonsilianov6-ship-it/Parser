<script lang="ts">
	import { onDestroy } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import type { Job, JobMode, TelegramAccount } from '$lib/types';

	let jobs = $state<Job[]>([]);
	let accounts = $state<TelegramAccount[]>([]);
	let loading = $state(false);
	let pageError = $state<string | null>(null);

	let newAccountId = $state<number | ''>('');
	let newMode = $state<JobMode>('parse');
	let newChannel = $state('');
	let newExportFormat = $state<'csv' | 'json' | 'xml'>('csv');
	let newExportToDocs = $state(true);
	let newExportToNotebookLM = $state(false);
	let newAllowRotation = $state(true);
	let submitting = $state(false);
	let formError = $state<string | null>(null);

	const parseExportInvalid = $derived(
		newMode === 'parse' && !newExportToDocs && !newExportToNotebookLM
	);

	let pollTimer: ReturnType<typeof setInterval> | null = null;

	let activeLogJob = $state<Job | null>(null);
	let activeLogLines = $state<string[]>([]);
	let activeLogController: AbortController | null = null;

	const authorisedAccounts = $derived(accounts.filter((a) => a.is_authorized));

	async function refresh(): Promise<void> {
		loading = true;
		pageError = null;
		try {
			[jobs, accounts] = await Promise.all([
				api<Job[]>('/api/jobs'),
				api<TelegramAccount[]>('/api/telegram/accounts')
			]);
			if (newAccountId === '' && authorisedAccounts.length > 0) {
				newAccountId = authorisedAccounts[0].id;
			}
		} catch (error) {
			pageError = error instanceof ApiError ? error.message : String(error);
		} finally {
			loading = false;
		}
	}

	async function handleCreate(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (submitting) return;
		if (newAccountId === '') {
			formError = 'Выберите авторизованный Telegram-аккаунт';
			return;
		}
		if (parseExportInvalid) {
			formError =
				'Для parse-задачи нужно выбрать хотя бы один вариант выгрузки: Google Docs или NotebookLM';
			return;
		}
		submitting = true;
		formError = null;
		try {
			const body: Record<string, unknown> = {
				telegram_account_id: Number(newAccountId),
				mode: newMode
			};
			if (newMode === 'parse' && newChannel.trim()) {
				body.channel = newChannel.trim();
			}
			if (newMode === 'parse') {
				body.export_to_docs = newExportToDocs;
				body.export_to_notebooklm = newExportToNotebookLM;
				body.allow_rotation = newAllowRotation;
			}
			if (newMode === 'export') {
				body.export_format = newExportFormat;
			}
			const job = await api<Job>('/api/jobs', { method: 'POST', body });
			newChannel = '';
			await refresh();
			openLogStream(job);
		} catch (error) {
			formError = error instanceof ApiError ? error.message : String(error);
		} finally {
			submitting = false;
		}
	}

	async function cancelJob(job: Job): Promise<void> {
		if (!confirm(`Отменить задачу #${job.id}?`)) return;
		try {
			await api<Job>(`/api/jobs/${job.id}/cancel`, { method: 'POST' });
			await refresh();
		} catch (error) {
			pageError = error instanceof ApiError ? error.message : String(error);
		}
	}

	function statusPill(status: Job['status']): string {
		switch (status) {
			case 'running':
				return 'pill-sky';
			case 'succeeded':
				return 'pill-green';
			case 'failed':
				return 'pill-amber';
			case 'cancelled':
				return 'pill-slate';
			default:
				return 'pill-slate';
		}
	}

	function formatTime(value: string | null): string {
		if (!value) return '—';
		try {
			return new Date(value).toLocaleString('ru-RU');
		} catch {
			return value;
		}
	}

	function openLogStream(job: Job): void {
		closeLogStream();
		activeLogJob = job;
		activeLogLines = [];
		const token = auth.token;
		if (!token) {
			activeLogLines = ['Нет токена авторизации'];
			return;
		}
		// EventSource cannot set Authorization header → use fetch + reader to consume SSE.
		const url = `/api/jobs/${job.id}/logs`;
		const controller = new AbortController();
		activeLogController = controller;
		(async () => {
			try {
				const response = await fetch(url, {
					headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' },
					signal: controller.signal
				});
				if (!response.ok || !response.body) {
					activeLogLines = [`HTTP ${response.status}`];
					return;
				}
				const reader = response.body.getReader();
				const decoder = new TextDecoder();
				let buffer = '';
				while (true) {
					const { value, done } = await reader.read();
					if (done) break;
					buffer += decoder.decode(value, { stream: true });
					let idx;
					while ((idx = buffer.indexOf('\n\n')) !== -1) {
						const eventBlock = buffer.slice(0, idx);
						buffer = buffer.slice(idx + 2);
						const lines = eventBlock.split('\n');
						let event = 'message';
						const dataLines: string[] = [];
						for (const line of lines) {
							if (line.startsWith('event: ')) event = line.slice(7);
							else if (line.startsWith('data: ')) dataLines.push(line.slice(6));
						}
						if (event === 'end') {
							activeLogLines = [...activeLogLines, '— конец потока —'];
							return;
						}
						if (dataLines.length > 0) {
							activeLogLines = [...activeLogLines, dataLines.join('\n')];
						}
					}
				}
			} catch (error) {
				if ((error as Error).name !== 'AbortError') {
					activeLogLines = [...activeLogLines, `[stream error] ${String(error)}`];
				}
			}
		})();
	}

	function closeLogStream(): void {
		if (activeLogController) {
			activeLogController.abort();
			activeLogController = null;
		}
		activeLogJob = null;
		activeLogLines = [];
	}

	$effect(() => {
		refresh();
		pollTimer = setInterval(() => {
			if (jobs.some((j) => j.status === 'pending' || j.status === 'running')) {
				refresh();
			}
		}, 4000);
	});

	onDestroy(() => {
		if (pollTimer) clearInterval(pollTimer);
		closeLogStream();
	});
</script>

<div class="space-y-6">
	<header class="flex flex-col gap-1">
		<p class="text-xs font-medium uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
			Парсер
		</p>
		<h1 class="text-2xl font-semibold tracking-tight">Задачи</h1>
		<p class="max-w-3xl text-sm text-slate-500 dark:text-slate-400">
			Запускает <code>python main.py</code> подпроцессом с креденшелами выбранного
			Telegram-аккаунта. Лог транслируется в реальном времени по SSE.
		</p>
	</header>

	<form onsubmit={handleCreate} class="card p-4">
		<div class="grid gap-3 md:grid-cols-[2fr_1fr_2fr_auto] md:items-end">
			<label class="space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">Telegram-аккаунт</span>
				<select required bind:value={newAccountId} class="input">
					<option value="" disabled>— выбрать —</option>
					{#each authorisedAccounts as account (account.id)}
						<option value={account.id}>
							#{account.id} {account.label} ({account.phone ?? 'без телефона'})
						</option>
					{/each}
				</select>
				{#if authorisedAccounts.length === 0}
					<span class="block text-xs text-amber-600">
						Сначала авторизуйте хотя бы один аккаунт на странице
						<a class="underline" href="/telegram-accounts">Telegram-аккаунты</a>.
					</span>
				{/if}
			</label>
			<label class="space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">Режим</span>
				<select bind:value={newMode} class="input">
					<option value="parse">parse</option>
					<option value="export">export</option>
					<option value="stats">stats</option>
				</select>
			</label>
			{#if newMode === 'parse'}
				<label class="space-y-1.5 text-sm">
					<span class="font-medium text-slate-700 dark:text-slate-300">
						Канал (опционально)
					</span>
					<input
						type="text"
						bind:value={newChannel}
						placeholder="@channelname или https://t.me/..."
						class="input font-mono"
					/>
				</label>
			{:else if newMode === 'export'}
				<label class="space-y-1.5 text-sm">
					<span class="font-medium text-slate-700 dark:text-slate-300">Формат</span>
					<select bind:value={newExportFormat} class="input">
						<option value="csv">csv</option>
						<option value="json">json</option>
						<option value="xml">xml</option>
					</select>
				</label>
			{:else}
				<div></div>
			{/if}
			<button
				type="submit"
				class="btn-primary"
				disabled={submitting || authorisedAccounts.length === 0 || parseExportInvalid}
			>
				{submitting ? 'Запускаем…' : 'Запустить'}
			</button>
		</div>
		{#if newMode === 'parse'}
			<div class="mt-3 flex flex-wrap items-center gap-4 rounded-lg bg-slate-50 px-3 py-2 text-sm dark:bg-slate-800/40">
				<span class="font-medium text-slate-700 dark:text-slate-300">После парсинга:</span>
				<label class="flex items-center gap-1.5">
					<input type="checkbox" bind:checked={newExportToDocs} />
					<span>Выгрузить в Google Docs</span>
				</label>
				<label class="flex items-center gap-1.5">
					<input type="checkbox" bind:checked={newExportToNotebookLM} />
					<span>Отправить в NotebookLM</span>
				</label>
				<label class="flex items-center gap-1.5" title="При FloodWait или SessionRevoked перезапустить задачу — на коротком FloodWait тем же аккаунтом, иначе следующим авторизованным слотом владельца. До 3 попыток.">
					<input type="checkbox" bind:checked={newAllowRotation} />
					<span>Авто-ротация при сбое</span>
				</label>
				{#if parseExportInvalid}
					<span class="text-xs text-amber-600">
						Выберите хотя бы один вариант выгрузки
					</span>
				{/if}
			</div>
		{/if}
		{#if formError}
			<div class="banner-error mt-3">
				<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
					<path
						fill-rule="evenodd"
						d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
						clip-rule="evenodd"
					/>
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
					<th>Режим</th>
					<th>Канал / формат</th>
					<th>Аккаунт</th>
					<th>Статус</th>
					<th>Создан</th>
					<th class="text-right">Действия</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-slate-100 dark:divide-slate-800">
				{#if loading && jobs.length === 0}
					<tr><td class="text-slate-500" colspan="7">Загрузка…</td></tr>
				{:else if jobs.length === 0}
					<tr>
						<td class="text-slate-500" colspan="7">
							<div class="flex flex-col items-center gap-2 py-6 text-center">
								<svg
									class="h-10 w-10 text-slate-300 dark:text-slate-600"
									viewBox="0 0 24 24"
									fill="currentColor"
								>
									<path
										d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6Zm3 3h10v2H7V9Zm0 4h10v2H7v-2Z"
									/>
								</svg>
								<p class="text-sm">Задач пока нет</p>
								<p class="text-xs text-slate-400">Запустите первую через форму выше</p>
							</div>
						</td>
					</tr>
				{/if}
				{#each jobs as job (job.id)}
					{@const isOwner = job.owner_id === auth.user?.id}
					<tr>
						<td class="font-mono text-xs text-slate-500">{job.id}</td>
						<td>
							<span class="font-mono text-xs">{job.mode}</span>
						</td>
						<td class="font-mono text-xs text-slate-500">
							{#if job.mode === 'parse'}
								{job.channel ?? '— все каналы —'}
							{:else if job.mode === 'export'}
								{job.export_format}
							{:else}
								—
							{/if}
						</td>
						<td class="text-xs text-slate-500">#{job.telegram_account_id}</td>
						<td>
							<span class={statusPill(job.status)}>{job.status}</span>
							{#if job.exit_code !== null && job.exit_code !== undefined}
								<span class="ml-1 font-mono text-[11px] text-slate-400">
									exit={job.exit_code}
								</span>
							{/if}
							{#if job.retry_count > 0}
								<span
									class="ml-1 font-mono text-[11px] text-amber-600"
									title="Авто-ротация: задача была перезапущена после транзиентной ошибки Telethon"
								>
									retry={job.retry_count}
								</span>
							{/if}
						</td>
						<td class="text-xs text-slate-500">{formatTime(job.created_at)}</td>
						<td class="text-right">
							<div class="inline-flex flex-wrap justify-end gap-2">
								<button class="btn-secondary btn-sm" onclick={() => openLogStream(job)}>
									Логи
								</button>
								{#if isOwner && (job.status === 'running' || job.status === 'pending')}
									<button class="btn-danger btn-sm" onclick={() => cancelJob(job)}>
										Отменить
									</button>
								{/if}
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	{#if pageError}
		<div class="banner-error">
			<svg class="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
				<path
					fill-rule="evenodd"
					d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
					clip-rule="evenodd"
				/>
			</svg>
			<span>{pageError}</span>
		</div>
	{/if}
</div>

{#if activeLogJob}
	<div
		class="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/50 px-4 backdrop-blur-sm"
		role="dialog"
		aria-modal="true"
		aria-labelledby="log-modal-title"
	>
		<div
			class="flex max-h-[80vh] w-full max-w-3xl flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-xl
				dark:border-slate-800 dark:bg-slate-950"
		>
			<div class="mb-3 flex items-start justify-between gap-3">
				<div>
					<p class="text-xs font-medium uppercase tracking-wider text-indigo-600">Логи</p>
					<h2 id="log-modal-title" class="text-lg font-semibold tracking-tight">
						Job #{activeLogJob.id} — {activeLogJob.mode}
					</h2>
				</div>
				<button
					class="rounded-md p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600
						dark:hover:bg-slate-900 dark:hover:text-slate-300"
					aria-label="Закрыть"
					onclick={closeLogStream}
				>
					<svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
						<path
							d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"
						/>
					</svg>
				</button>
			</div>
			<pre
				class="flex-1 overflow-auto rounded-lg bg-slate-950 p-3 font-mono text-[12px] leading-snug text-slate-100"
			>
{#each activeLogLines as line, i (i)}<div>{line || ' '}</div>{/each}{#if activeLogLines.length === 0}<div class="text-slate-500">— ожидание данных —</div>{/if}</pre>
		</div>
	</div>
{/if}

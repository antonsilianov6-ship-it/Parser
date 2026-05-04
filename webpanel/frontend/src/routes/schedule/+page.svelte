<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import type { Schedule, TelegramAccount } from '$lib/types';

	let schedules = $state<Schedule[]>([]);
	let accounts = $state<TelegramAccount[]>([]);
	let loading = $state(false);
	let pageError = $state<string | null>(null);

	let formAccountId = $state<number | ''>('');
	let formName = $state('');
	let formCron = $state('0 * * * *');
	let formChannel = $state('');
	let formExportDocs = $state(true);
	let formExportNlm = $state(false);
	let formActive = $state(true);
	let submitting = $state(false);
	let formError = $state<string | null>(null);

	const presets: Array<{ label: string; cron: string }> = [
		{ label: 'Каждый час', cron: '0 * * * *' },
		{ label: 'Каждые 4 часа', cron: '0 */4 * * *' },
		{ label: 'Каждый день в 09:00 UTC', cron: '0 9 * * *' },
		{ label: 'По будням в 09:00 UTC', cron: '0 9 * * 1-5' },
		{ label: 'Каждые 30 минут', cron: '*/30 * * * *' }
	];

	const authorisedAccounts = $derived(accounts.filter((a) => a.is_authorized));

	const formExportInvalid = $derived(!formExportDocs && !formExportNlm);

	async function refresh(): Promise<void> {
		loading = true;
		pageError = null;
		try {
			[schedules, accounts] = await Promise.all([
				api<Schedule[]>('/api/schedules'),
				api<TelegramAccount[]>('/api/telegram/accounts')
			]);
			if (formAccountId === '' && authorisedAccounts.length > 0) {
				formAccountId = authorisedAccounts[0].id;
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
		if (formAccountId === '') {
			formError = 'Выберите авторизованный Telegram-аккаунт';
			return;
		}
		if (formExportInvalid) {
			formError =
				'Выберите хотя бы один вариант выгрузки: Google Docs или NotebookLM';
			return;
		}
		submitting = true;
		formError = null;
		try {
			await api<Schedule>('/api/schedules', {
				method: 'POST',
				body: {
					name: formName.trim() || `Расписание ${new Date().toLocaleTimeString('ru-RU')}`,
					telegram_account_id: Number(formAccountId),
					cron_expression: formCron.trim(),
					channel: formChannel.trim() || null,
					export_to_docs: formExportDocs,
					export_to_notebooklm: formExportNlm,
					is_active: formActive
				}
			});
			formName = '';
			formChannel = '';
			await refresh();
		} catch (error) {
			formError = error instanceof ApiError ? error.message : String(error);
		} finally {
			submitting = false;
		}
	}

	async function toggle(schedule: Schedule): Promise<void> {
		try {
			await api(`/api/schedules/${schedule.id}`, {
				method: 'PATCH',
				body: { is_active: !schedule.is_active }
			});
			await refresh();
		} catch (error) {
			pageError = error instanceof ApiError ? error.message : String(error);
		}
	}

	async function remove(schedule: Schedule): Promise<void> {
		if (!confirm(`Удалить расписание «${schedule.name}»?`)) return;
		try {
			await api(`/api/schedules/${schedule.id}`, { method: 'DELETE' });
			await refresh();
		} catch (error) {
			pageError = error instanceof ApiError ? error.message : String(error);
		}
	}

	function applyPreset(cron: string): void {
		formCron = cron;
	}

	function formatDate(value: string | null): string {
		if (!value) return '—';
		return new Date(value).toLocaleString('ru-RU');
	}

	function accountLabel(id: number): string {
		const acc = accounts.find((a) => a.id === id);
		return acc ? acc.label : `#${id}`;
	}

	$effect(() => {
		refresh();
	});
</script>

<div class="mx-auto w-full max-w-6xl space-y-6 px-6 py-6">
	<header class="flex items-end justify-between">
		<div>
			<h1 class="text-xl font-semibold tracking-tight">Расписание</h1>
			<p class="text-sm text-slate-500 dark:text-slate-400">
				Cron-расписания для парсинга. Каждый тик создаёт обычную parse-задачу — её
				видно на странице <a href="/jobs" class="text-sky-600 hover:underline">Задачи</a>.
				Все выражения выполняются в UTC.
			</p>
		</div>
	</header>

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

	<form class="card grid gap-4 p-5 lg:grid-cols-2" onsubmit={handleCreate}>
		<div class="lg:col-span-2">
			<h2 class="text-lg font-semibold tracking-tight">Новое расписание</h2>
		</div>

		<label class="space-y-1 text-sm">
			<span class="text-slate-600 dark:text-slate-400">Название</span>
			<input
				type="text"
				class="input"
				placeholder="Утренний прогон"
				bind:value={formName}
			/>
		</label>

		<label class="space-y-1 text-sm">
			<span class="text-slate-600 dark:text-slate-400">Telegram-аккаунт</span>
			<select bind:value={formAccountId} class="input">
				{#if authorisedAccounts.length === 0}
					<option value="">Нет авторизованных аккаунтов</option>
				{/if}
				{#each authorisedAccounts as acc (acc.id)}
					<option value={acc.id}>{acc.label}{acc.phone ? ` (${acc.phone})` : ''}</option>
				{/each}
			</select>
		</label>

		<label class="space-y-1 text-sm lg:col-span-2">
			<span class="text-slate-600 dark:text-slate-400">
				Cron-выражение (5 полей: <code>min hour dom month dow</code>, UTC)
			</span>
			<input type="text" class="input font-mono" bind:value={formCron} required />
			<div class="flex flex-wrap gap-1.5 pt-1">
				{#each presets as preset (preset.cron)}
					<button
						type="button"
						class="rounded-md border border-slate-200 px-2.5 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
						onclick={() => applyPreset(preset.cron)}
					>
						{preset.label}
					</button>
				{/each}
			</div>
		</label>

		<label class="space-y-1 text-sm lg:col-span-2">
			<span class="text-slate-600 dark:text-slate-400">
				Канал (опционально — пустое = все каналы из channels.txt)
			</span>
			<input type="text" class="input" placeholder="@example" bind:value={formChannel} />
		</label>

		<div class="flex flex-wrap items-center gap-4 lg:col-span-2">
			<label class="inline-flex items-center gap-2 text-sm">
				<input type="checkbox" bind:checked={formExportDocs} />
				Google Docs
			</label>
			<label class="inline-flex items-center gap-2 text-sm">
				<input type="checkbox" bind:checked={formExportNlm} />
				NotebookLM
			</label>
			<label class="inline-flex items-center gap-2 text-sm">
				<input type="checkbox" bind:checked={formActive} />
				Активно сразу
			</label>
		</div>

		{#if formError}
			<p class="lg:col-span-2 text-sm text-rose-600">{formError}</p>
		{/if}

		<div class="lg:col-span-2">
			<button
				type="submit"
				class="btn-primary"
				disabled={submitting || formExportInvalid || formAccountId === ''}
			>
				{submitting ? 'Сохраняем…' : 'Создать'}
			</button>
		</div>
	</form>

	<section class="card overflow-hidden">
		<div class="flex items-center justify-between border-b border-slate-200 px-5 py-3 dark:border-slate-800">
			<h2 class="text-base font-semibold tracking-tight">Существующие расписания</h2>
			<button class="btn-ghost btn-sm" onclick={refresh} disabled={loading}>
				{loading ? '…' : 'Обновить'}
			</button>
		</div>
		{#if schedules.length === 0}
			<p class="px-5 py-6 text-sm text-slate-500 dark:text-slate-400">
				Пока нет расписаний.
			</p>
		{:else}
			<table class="w-full text-sm">
				<thead class="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-900 dark:text-slate-400">
					<tr>
						<th class="px-4 py-2.5 font-medium">Название</th>
						<th class="px-4 py-2.5 font-medium">Cron</th>
						<th class="px-4 py-2.5 font-medium">TG</th>
						<th class="px-4 py-2.5 font-medium">Канал</th>
						<th class="px-4 py-2.5 font-medium">Экспорт</th>
						<th class="px-4 py-2.5 font-medium">Следующий запуск</th>
						<th class="px-4 py-2.5 font-medium">Последний</th>
						<th class="px-4 py-2.5 font-medium"></th>
					</tr>
				</thead>
				<tbody class="divide-y divide-slate-200 dark:divide-slate-800">
					{#each schedules as schedule (schedule.id)}
						<tr class={schedule.is_active ? '' : 'opacity-60'}>
							<td class="px-4 py-2.5 font-medium">{schedule.name}</td>
							<td class="px-4 py-2.5 font-mono text-xs">{schedule.cron_expression}</td>
							<td class="px-4 py-2.5">{accountLabel(schedule.telegram_account_id)}</td>
							<td class="px-4 py-2.5">{schedule.channel ?? '—'}</td>
							<td class="px-4 py-2.5">
								{#if schedule.export_to_docs}<span class="pill-slate mr-1">Docs</span>{/if}
								{#if schedule.export_to_notebooklm}<span class="pill-slate">NLM</span>{/if}
							</td>
							<td class="px-4 py-2.5 text-xs text-slate-500">{formatDate(schedule.next_run_at)}</td>
							<td class="px-4 py-2.5 text-xs text-slate-500">{formatDate(schedule.last_run_at)}</td>
							<td class="px-4 py-2.5 text-right">
								<button class="btn-ghost btn-sm" onclick={() => toggle(schedule)}>
									{schedule.is_active ? 'Пауза' : 'Включить'}
								</button>
								<button class="btn-danger btn-sm" onclick={() => remove(schedule)}>
									Удалить
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</section>
</div>

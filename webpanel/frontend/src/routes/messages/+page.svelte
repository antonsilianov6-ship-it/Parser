<script lang="ts">
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';

	type Message = {
		id: number;
		channel: string;
		message_id: number;
		text: string | null;
		date: string;
		author: string | null;
		views: number;
		forwards: number;
		replies: number;
		comments: string | null;
		media_type: string | null;
		source_type: string | null;
		topic_title: string | null;
	};

	type ListResponse = {
		items: Message[];
		total: number;
		limit: number;
		offset: number;
	};

	type ChannelRow = { channel: string; messages: number; latest: string | null };

	let items = $state<Message[]>([]);
	let total = $state(0);
	let limit = $state(50);
	let offset = $state(0);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let dbMissing = $state(false);

	let channelFilter = $state('');
	let queryFilter = $state('');
	let dateFrom = $state('');
	let dateTo = $state('');

	let availableChannels = $state<ChannelRow[]>([]);
	let expandedId = $state<number | null>(null);

	async function loadChannels(): Promise<void> {
		try {
			availableChannels = await api<ChannelRow[]>('/api/parser/messages/channels');
		} catch (err) {
			if (err instanceof ApiError && err.status === 404) {
				dbMissing = true;
			}
		}
	}

	async function load(): Promise<void> {
		if (loading) return;
		loading = true;
		error = null;
		const params = new URLSearchParams();
		params.set('limit', String(limit));
		params.set('offset', String(offset));
		if (channelFilter) params.set('channel', channelFilter);
		if (queryFilter.trim()) params.set('query', queryFilter.trim());
		if (dateFrom) params.set('date_from', dateFrom);
		if (dateTo) params.set('date_to', dateTo);
		try {
			const data = await api<ListResponse>(`/api/parser/messages?${params.toString()}`);
			items = data.items;
			total = data.total;
			dbMissing = false;
		} catch (err) {
			if (err instanceof ApiError && err.status === 404) {
				dbMissing = true;
				items = [];
				total = 0;
			} else {
				error = err instanceof ApiError ? err.message : String(err);
			}
		} finally {
			loading = false;
		}
	}

	function applyFilters(event?: SubmitEvent): void {
		if (event) event.preventDefault();
		offset = 0;
		load();
	}

	function clearFilters(): void {
		channelFilter = '';
		queryFilter = '';
		dateFrom = '';
		dateTo = '';
		offset = 0;
		load();
	}

	function nextPage(): void {
		if (offset + limit >= total) return;
		offset += limit;
		load();
	}

	function prevPage(): void {
		if (offset === 0) return;
		offset = Math.max(0, offset - limit);
		load();
	}

	function formatDate(value: string): string {
		const d = new Date(value.replace(' ', 'T') + (value.includes('T') ? '' : 'Z'));
		if (Number.isNaN(d.getTime())) return value;
		return d.toLocaleString('ru-RU');
	}

	function truncate(s: string | null, n: number): string {
		if (!s) return '';
		if (s.length <= n) return s;
		return s.slice(0, n).trimEnd() + '…';
	}

	function toggleRow(id: number): void {
		expandedId = expandedId === id ? null : id;
	}

	onMount(() => {
		loadChannels();
		load();
	});
</script>

<div class="space-y-6">
	<header class="flex flex-col gap-1">
		<p class="text-xs font-medium uppercase tracking-wider text-violet-600 dark:text-violet-400">
			Парсер
		</p>
		<h1 class="text-2xl font-semibold tracking-tight">Сообщения</h1>
		<p class="max-w-3xl text-sm text-slate-500 dark:text-slate-400">
			Просмотр содержимого
			<code class="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[12px] dark:bg-slate-800">
				data/parser.db
			</code>. Доступ только для чтения — править данные нельзя, только смотреть и фильтровать.
		</p>
	</header>

	{#if dbMissing}
		<div class="card p-5 text-sm text-slate-500">
			База данных ещё не создана. Запустите задачу в режиме
			<code class="rounded bg-slate-100 px-1 py-0.5 font-mono dark:bg-slate-800">parse</code>
			на странице
			<a class="text-sky-600 hover:underline" href="/jobs">Задачи</a>.
		</div>
	{:else}
		<form onsubmit={applyFilters} class="card grid gap-3 p-4 md:grid-cols-12">
			<label class="md:col-span-3 space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">Канал</span>
				<select bind:value={channelFilter} class="input">
					<option value="">— любой —</option>
					{#each availableChannels as row (row.channel)}
						<option value={row.channel}>{row.channel} ({row.messages})</option>
					{/each}
				</select>
			</label>
			<label class="md:col-span-4 space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">Поиск по тексту</span>
				<input
					type="text"
					bind:value={queryFilter}
					placeholder="введите фрагмент…"
					class="input"
				/>
			</label>
			<label class="md:col-span-2 space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">С</span>
				<input type="date" bind:value={dateFrom} class="input" />
			</label>
			<label class="md:col-span-2 space-y-1.5 text-sm">
				<span class="font-medium text-slate-700 dark:text-slate-300">По</span>
				<input type="date" bind:value={dateTo} class="input" />
			</label>
			<div class="flex items-end gap-2 md:col-span-1">
				<button type="submit" class="btn-primary w-full">Применить</button>
			</div>
			<div class="md:col-span-12 flex flex-wrap items-center gap-3 text-xs text-slate-500">
				<span>
					Показано {Math.min(offset + 1, total)}–{Math.min(offset + items.length, total)} из {total}
				</span>
				<button type="button" class="btn-secondary btn-sm" onclick={clearFilters}>Сбросить</button>
				<label class="ml-auto flex items-center gap-2">
					<span>На страницу</span>
					<select
						bind:value={limit}
						onchange={() => {
							offset = 0;
							load();
						}}
						class="input h-8 w-20 py-1 text-xs"
					>
						<option value={20}>20</option>
						<option value={50}>50</option>
						<option value={100}>100</option>
						<option value={200}>200</option>
					</select>
				</label>
			</div>
		</form>

		{#if error}
			<div class="banner-error">{error}</div>
		{/if}

		<div class="table-wrap overflow-x-auto">
			<table class="table-base">
				<thead>
					<tr>
						<th class="w-10"></th>
						<th>Дата</th>
						<th>Канал</th>
						<th>Текст</th>
						<th class="text-right">Просмотров</th>
						<th class="text-right">Реплаев</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-slate-100 dark:divide-slate-800">
					{#if loading && items.length === 0}
						<tr>
							<td colspan="6" class="py-6 text-center text-sm text-slate-500">Загрузка…</td>
						</tr>
					{/if}
					{#if !loading && items.length === 0}
						<tr>
							<td colspan="6" class="py-6 text-center text-sm text-slate-500">
								Нет сообщений по выбранным фильтрам
							</td>
						</tr>
					{/if}
					{#each items as message (message.id)}
						<tr
							class="cursor-pointer transition hover:bg-slate-50 dark:hover:bg-slate-900/40"
							onclick={() => toggleRow(message.id)}
						>
							<td class="text-slate-400">
								<svg
									class="h-4 w-4 transition {expandedId === message.id ? 'rotate-90' : ''}"
									viewBox="0 0 20 20"
									fill="currentColor"
								>
									<path
										fill-rule="evenodd"
										d="M7.293 5.293a1 1 0 0 1 1.414 0l4 4a1 1 0 0 1 0 1.414l-4 4a1 1 0 1 1-1.414-1.414L10.586 10 7.293 6.707a1 1 0 0 1 0-1.414Z"
										clip-rule="evenodd"
									/>
								</svg>
							</td>
							<td class="whitespace-nowrap text-xs tabular-nums text-slate-500">
								{formatDate(message.date)}
							</td>
							<td class="whitespace-nowrap font-mono text-xs">{message.channel}</td>
							<td class="text-sm text-slate-700 dark:text-slate-300">
								{truncate(message.text, 140)}
							</td>
							<td class="text-right text-xs tabular-nums text-slate-500">
								{message.views ?? 0}
							</td>
							<td class="text-right text-xs tabular-nums text-slate-500">
								{message.replies ?? 0}
							</td>
						</tr>
						{#if expandedId === message.id}
							<tr class="bg-slate-50/60 dark:bg-slate-900/30">
								<td></td>
								<td colspan="5" class="space-y-2 py-3 text-sm">
									<div class="flex flex-wrap gap-3 text-xs text-slate-500">
										<span>
											<span class="font-medium">Автор:</span>
											{message.author ?? '—'}
										</span>
										<span>
											<span class="font-medium">message_id:</span>
											<code class="font-mono">{message.message_id}</code>
										</span>
										{#if message.source_type}
											<span>
												<span class="font-medium">type:</span>
												{message.source_type}
											</span>
										{/if}
										{#if message.media_type}
											<span>
												<span class="font-medium">media:</span>
												{message.media_type}
											</span>
										{/if}
										{#if message.topic_title}
											<span>
												<span class="font-medium">topic:</span>
												{message.topic_title}
											</span>
										{/if}
									</div>
									<pre
										class="whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-3 font-sans text-sm text-slate-800 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200">{message.text ??
											''}</pre>
									{#if message.comments}
										<details class="text-xs">
											<summary class="cursor-pointer font-medium text-slate-600 hover:underline">
												Комментарии ({message.comments.length} симв.)
											</summary>
											<pre
												class="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-3 font-sans text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">{message.comments}</pre>
										</details>
									{/if}
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		</div>

		<div class="flex items-center justify-between text-sm text-slate-500">
			<button
				type="button"
				class="btn-secondary btn-sm"
				disabled={offset === 0 || loading}
				onclick={prevPage}
			>
				← Назад
			</button>
			<span>
				Страница {Math.floor(offset / limit) + 1}
				из {Math.max(1, Math.ceil(total / limit))}
			</span>
			<button
				type="button"
				class="btn-secondary btn-sm"
				disabled={offset + limit >= total || loading}
				onclick={nextPage}
			>
				Вперёд →
			</button>
		</div>
	{/if}
</div>

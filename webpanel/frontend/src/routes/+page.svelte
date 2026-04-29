<script lang="ts">
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';

	type Card = {
		href: string;
		title: string;
		description: string;
		accent: string;
		icon: 'users' | 'telegram' | 'jobs' | 'settings' | 'messages';
	};

	type Stats = {
		total_messages: number;
		channels_count: number;
		latest_message_at: string | null;
		top_channels: Array<{ channel: string; messages: number }>;
		db_present: boolean;
	};

	let stats = $state<Stats | null>(null);
	let statsError = $state<string | null>(null);

	onMount(async () => {
		try {
			stats = await api<Stats>('/api/parser/stats');
		} catch (error) {
			statsError = error instanceof ApiError ? error.message : String(error);
		}
	});

	function formatNumber(n: number): string {
		return new Intl.NumberFormat('ru-RU').format(n);
	}

	function formatDate(value: string | null): string {
		if (!value) return '—';
		const d = new Date(value.replace(' ', 'T') + (value.includes('T') ? '' : 'Z'));
		if (Number.isNaN(d.getTime())) return value;
		return d.toLocaleString('ru-RU');
	}

	const cards: Card[] = [
		{
			href: '/users',
			title: 'Пользователи',
			description: 'Управление пользователями панели.',
			accent: 'from-sky-500 to-indigo-600',
			icon: 'users'
		},
		{
			href: '/telegram-accounts',
			title: 'Telegram-аккаунты',
			description: 'Авторизованные Telethon-сессии для запусков парсера.',
			accent: 'from-emerald-500 to-teal-600',
			icon: 'telegram'
		},
		{
			href: '/jobs',
			title: 'Задачи',
			description: 'Запуск парсера и просмотр логов в реальном времени.',
			accent: 'from-fuchsia-500 to-rose-600',
			icon: 'jobs'
		},
		{
			href: '/messages',
			title: 'Сообщения',
			description: 'Просмотр спарсенных сообщений с фильтрами и поиском.',
			accent: 'from-violet-500 to-purple-600',
			icon: 'messages'
		},
		{
			href: '/settings',
			title: 'Настройки',
			description: 'CRUD для config.json, prompts.json и channels.txt.',
			accent: 'from-amber-500 to-orange-600',
			icon: 'settings'
		}
	];
</script>

<div class="space-y-8">
	<section>
		<p class="text-xs font-medium uppercase tracking-wider text-sky-600 dark:text-sky-400">
			Дашборд
		</p>
		<h1 class="mt-1 text-3xl font-semibold tracking-tight">
			Привет, <span
				class="bg-gradient-to-br from-sky-600 to-indigo-600 bg-clip-text text-transparent
					dark:from-sky-400 dark:to-indigo-400"
			>{auth.user?.username ?? ''}</span>
		</h1>
		<p class="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
			Первая итерация веб-панели для AllInclusiveParser. Здесь будут собраны все инструменты
			управления ботом — пока доступны пользователи и слоты Telegram-аккаунтов.
		</p>
	</section>

	<section class="grid gap-4 md:grid-cols-2">
		{#each cards as card (card.href)}
			<a
				href={card.href}
				class="group relative overflow-hidden rounded-2xl border border-slate-200/70 bg-white/80 p-5 shadow-sm backdrop-blur-sm transition
					hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md
					dark:border-slate-800/70 dark:bg-slate-900/80 dark:hover:border-slate-700"
			>
				<div class="flex items-start gap-4">
					<div
						class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br {card.accent} text-white shadow-sm"
						aria-hidden="true"
					>
						{#if card.icon === 'users'}
							<svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
								<circle cx="9" cy="7" r="4" />
								<path d="M23 21v-2a4 4 0 0 0-3-3.87" />
								<path d="M16 3.13a4 4 0 0 1 0 7.75" />
							</svg>
						{:else if card.icon === 'telegram'}
							<svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
								<path d="M21.9 4.3 18.7 19.4c-.2 1-.9 1.3-1.8.8l-5-3.7-2.4 2.3c-.3.3-.5.5-1 .5l.4-5.2 9.4-8.5c.4-.4-.1-.6-.6-.2L5.8 13l-5-1.6c-1.1-.3-1.1-1 .2-1.6L20.4 2.7c.9-.3 1.7.2 1.5 1.6Z" />
							</svg>
						{:else if card.icon === 'jobs'}
							<svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<polygon points="5 3 19 12 5 21 5 3" />
							</svg>
						{:else if card.icon === 'messages'}
							<svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
							</svg>
						{:else}
							<svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<circle cx="12" cy="12" r="3" />
								<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
							</svg>
						{/if}
					</div>
					<div class="flex-1">
						<h2 class="text-base font-semibold tracking-tight group-hover:text-sky-600 dark:group-hover:text-sky-400">
							{card.title}
						</h2>
						<p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
							{card.description}
						</p>
					</div>
					<svg
						class="h-5 w-5 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-sky-500 dark:text-slate-600"
						viewBox="0 0 20 20"
						fill="currentColor"
						aria-hidden="true"
					>
						<path
							fill-rule="evenodd"
							d="M7.293 14.707a1 1 0 0 1 0-1.414L10.586 10 7.293 6.707a1 1 0 0 1 1.414-1.414l4 4a1 1 0 0 1 0 1.414l-4 4a1 1 0 0 1-1.414 0Z"
							clip-rule="evenodd"
						/>
					</svg>
				</div>
			</a>
		{/each}
	</section>

	<section class="space-y-3">
		<div class="flex items-baseline justify-between">
			<h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
				Парсер — статистика
			</h2>
			<a class="text-xs text-sky-600 hover:underline dark:text-sky-400" href="/messages">
				Открыть сообщения →
			</a>
		</div>
		{#if statsError}
			<div class="banner-error">{statsError}</div>
		{:else if stats === null}
			<div class="text-sm text-slate-500">Загрузка…</div>
		{:else if !stats.db_present}
			<div class="card p-5 text-sm text-slate-500">
				База данных <code class="rounded bg-slate-100 px-1 py-0.5 font-mono dark:bg-slate-800">data/parser.db</code> ещё не создана.
				Запустите job в режиме <code class="rounded bg-slate-100 px-1 py-0.5 font-mono dark:bg-slate-800">parse</code>,
				чтобы появились данные.
			</div>
		{:else}
			<div class="grid gap-4 sm:grid-cols-3">
				<div class="card p-4">
					<p class="text-xs uppercase tracking-wider text-slate-500">Сообщений всего</p>
					<p class="mt-2 text-2xl font-semibold tabular-nums">
						{formatNumber(stats.total_messages)}
					</p>
				</div>
				<div class="card p-4">
					<p class="text-xs uppercase tracking-wider text-slate-500">Каналов в базе</p>
					<p class="mt-2 text-2xl font-semibold tabular-nums">
						{formatNumber(stats.channels_count)}
					</p>
				</div>
				<div class="card p-4">
					<p class="text-xs uppercase tracking-wider text-slate-500">Последнее сообщение</p>
					<p class="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">
						{formatDate(stats.latest_message_at)}
					</p>
				</div>
			</div>
			{#if stats.top_channels.length > 0}
				<div class="card p-4">
					<p class="text-xs uppercase tracking-wider text-slate-500">Топ каналов</p>
					<ul class="mt-2 space-y-1.5 text-sm">
						{#each stats.top_channels.slice(0, 5) as row (row.channel)}
							<li class="flex items-center justify-between font-mono">
								<span class="truncate text-slate-700 dark:text-slate-300">{row.channel}</span>
								<span class="tabular-nums text-slate-500">{formatNumber(row.messages)}</span>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		{/if}
	</section>
</div>

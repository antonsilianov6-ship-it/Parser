<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';

	type Card = {
		href: string;
		title: string;
		description: string;
		accent: string;
		icon: 'users' | 'telegram';
	};

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
			description: 'Слоты под Telethon-сессии. Реальный логин добавляется в следующем PR.',
			accent: 'from-emerald-500 to-teal-600',
			icon: 'telegram'
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
						{:else}
							<svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
								<path d="M21.9 4.3 18.7 19.4c-.2 1-.9 1.3-1.8.8l-5-3.7-2.4 2.3c-.3.3-.5.5-1 .5l.4-5.2 9.4-8.5c.4-.4-.1-.6-.6-.2L5.8 13l-5-1.6c-1.1-.3-1.1-1 .2-1.6L20.4 2.7c.9-.3 1.7.2 1.5 1.6Z" />
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

	<section
		class="rounded-2xl border border-dashed border-slate-300/80 bg-white/40 p-5 text-sm text-slate-500 backdrop-blur-sm
			dark:border-slate-700/80 dark:bg-slate-900/30 dark:text-slate-400"
	>
		<div class="flex items-start gap-3">
			<svg class="mt-0.5 h-4 w-4 shrink-0 text-slate-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
				<path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-7-4a1 1 0 1 1-2 0 1 1 0 0 1 2 0Zm-1 3a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 9Z" clip-rule="evenodd" />
			</svg>
			<p>
				В следующих итерациях здесь появятся: запуск парсинга/автоматизации, живые логи,
				просмотр сообщений из базы, редактор <code class="rounded bg-slate-200 px-1 py-0.5 font-mono text-xs dark:bg-slate-800">config.json</code>,
				расписание и список экспортов.
			</p>
		</div>
	</section>
</div>

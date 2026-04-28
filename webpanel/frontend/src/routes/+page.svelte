<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
</script>

<div class="mx-auto max-w-3xl space-y-6">
	<section>
		<h1 class="text-2xl font-semibold">Обзор</h1>
		<p class="mt-2 text-slate-600 dark:text-slate-400">
			Привет, <strong>{auth.user?.username ?? ''}</strong>. Это первая итерация веб-панели для
			AllInclusiveParser.
		</p>
	</section>

	<section class="grid gap-4 md:grid-cols-2">
		<a
			href="/users"
			class="block rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition hover:border-sky-400 dark:border-slate-800 dark:bg-slate-900"
		>
			<h2 class="text-lg font-medium">Пользователи</h2>
			<p class="mt-1 text-sm text-slate-500">Управление пользователями панели.</p>
		</a>
		<a
			href="/telegram-accounts"
			class="block rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition hover:border-sky-400 dark:border-slate-800 dark:bg-slate-900"
		>
			<h2 class="text-lg font-medium">Telegram-аккаунты</h2>
			<p class="mt-1 text-sm text-slate-500">
				Слоты под Telethon-сессии. Реальный логин добавляется в следующем PR.
			</p>
		</a>
	</section>

	<section class="rounded-lg border border-dashed border-slate-300 p-5 text-sm text-slate-500 dark:border-slate-700">
		<p>
			В следующих итерациях здесь появятся: запуск парсинга/автоматизации, живые логи, просмотр
			сообщений из базы, редактор <code>config.json</code>, расписание и список экспортов.
		</p>
	</section>
</div>

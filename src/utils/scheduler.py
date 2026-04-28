# -*- coding: utf-8 -*-
"""
Планировщик задач
"""
import asyncio
import schedule
import threading
from datetime import datetime, time
from typing import Callable, Dict, List

class TaskScheduler:
    def __init__(self):
        self.jobs: Dict[str, schedule.Job] = {}
        self.running = False
        self.thread = None
    
    def add_daily_task(self, name: str, func: Callable, time_str: str):
        """Добавляет ежедневную задачу"""
        job = schedule.every().day.at(time_str).do(func)
        self.jobs[name] = job
        print(f"Добавлена ежедневная задача '{name}' на {time_str}")
    
    def add_interval_task(self, name: str, func: Callable, minutes: int):
        """Добавляет задачу с интервалом"""
        job = schedule.every(minutes).minutes.do(func)
        self.jobs[name] = job
        print(f"Добавлена задача '{name}' каждые {minutes} минут")
    
    def remove_task(self, name: str):
        """Удаляет задачу"""
        if name in self.jobs:
            schedule.cancel_job(self.jobs[name])
            del self.jobs[name]
            print(f"Задача '{name}' удалена")
    
    def start(self):
        """Запускает планировщик"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_scheduler)
            self.thread.daemon = True
            self.thread.start()
            print("Планировщик задач запущен")
    
    def stop(self):
        """Останавливает планировщик"""
        self.running = False
        if self.thread:
            self.thread.join()
        print("Планировщик задач остановлен")
    
    def _run_scheduler(self):
        """Основной цикл планировщика"""
        while self.running:
            schedule.run_pending()
            threading.Event().wait(1)
    
    def get_jobs_info(self) -> List[Dict]:
        """Возвращает информацию о задачах"""
        jobs_info = []
        for name, job in self.jobs.items():
            jobs_info.append({
                'name': name,
                'next_run': str(job.next_run) if job.next_run else 'Не запланировано',
                'interval': str(job.interval) if hasattr(job, 'interval') else 'Не определено'
            })
        return jobs_info

# Глобальный планировщик
scheduler = TaskScheduler()
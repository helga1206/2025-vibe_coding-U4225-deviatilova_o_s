#!/usr/bin/env python3
"""
Главный файл для запуска бота на Render (Web/Webhook)
"""

import os
import sys

def run_bot():
    """Запускает Telegram бота.
    Если доступен PUBLIC_URL/RENDER_EXTERNAL_URL — запускаем webhook (Web).
    Иначе fallback на polling.
    """
    import bot
    if os.getenv('PUBLIC_URL') or os.getenv('RENDER_EXTERNAL_URL'):
        print("Starting Telegram News Bot (webhook/web)...")
        bot.main_webhook()
    else:
        print("Starting Telegram News Bot (polling/worker)...")
        bot.main()

if __name__ == '__main__':
    print("Initializing bot...")
    run_bot()


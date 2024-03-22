#!/bin/bash

exec python3 telegram_webhook.py &
exec python3 telegram_bot_accelerator.py
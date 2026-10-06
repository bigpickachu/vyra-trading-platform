#!/bin/bash
cd /mnt/c/Users/franc/vyra/backend
source venv-vyra/bin/activate
export FIREBASE_KEY_PATH="/home/francfrancisco/vyra-firebase-key.json"
uvicorn app.main:app --reload --host 0.0.0.0

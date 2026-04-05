---
title: Code Review Agent
emoji: 🔍
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 7860
---

# Code Review Agent — OpenEnv Environment

A real-world OpenEnv environment where AI agents learn to review code bugs.

## What it does

Agents analyze buggy Python code and must:
- Identify the exact error line
- Identify the error type
- Explain why it is a bug
- Suggest a fix

## Three difficulty levels

- Easy: Find error line and type
- Medium: Find + explain + edge cases
- Hard: Full review with log analysis and duplicate detection

## API Endpoints

- POST /reset — Start fresh episode
- POST /step  — Submit action get reward
- GET  /state — Check current progress
- GET  /health — Health check

## How to run locally

cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 7860
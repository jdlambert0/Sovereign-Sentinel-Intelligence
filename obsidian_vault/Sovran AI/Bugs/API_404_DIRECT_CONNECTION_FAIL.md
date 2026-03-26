# Bug Report: Direct API 404 Failures (Sonnet 3.5 & Gemini 1.5)
**Date:** March 22, 2026
**Status:** RESOLVED
**Resolution:** Updated substrate to March 2026 model identifiers (`claude-sonnet-4-20250514` and `gemini-2.5-flash`) and stable v1 endpoints.

## Symptom
The `test_direct_apis.py` diagnostic script returns `HTTP Error 404: Not Found` for both major providers when bypassing OpenRouter.

## Technical Details

### 1. Anthropic (Claude 3.5 Sonnet)
- **Endpoint:** `https://api.anthropic.com/v1/messages`
- **Method:** `POST`
- **Headers:**
    - `x-api-key`: [sk-ant-api03...]
    - `anthropic-version`: `2023-06-01`
    - `Content-Type`: `application/json`
- **Model String used:** `claude-3-5-sonnet-20241022`
- **Error:** `404 Not Found`

### 2. Google Gemini (1.5 Flash)
- **Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}`
- **Method:** `POST`
- **Model String used:** `gemini-1.5-flash`
- **Error:** `404 Not Found`

## Hypothesis
- The Anthropic `v1/messages` endpoint or the model ID may have been updated since our last baseline.
- The Google Gemini `v1beta` endpoint may have moved to `v1` or the model ID requires a suffix (e.g., `gemini-1.5-flash-latest`).

## Impact
The "Sovereign Alpha" engine is defaulting to `WAIT` because the Council Ensemble cannot reach the models. Direct trading is paralyzed until the substrate is corrected.

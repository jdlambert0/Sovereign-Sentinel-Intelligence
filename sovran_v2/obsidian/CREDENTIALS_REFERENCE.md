---
title: Credentials Reference
type: reference
priority: P0
warning: THIS FILE CONTAINS NO SECRETS — only file paths
---

# Credentials Reference

> **IMPORTANT:** Actual credentials are stored OUTSIDE the git repo at:
> ```
> C:\KAI\sovran_v2_secrets\credentials.env
> ```
> This file only points to where they live. Never paste credentials into any file inside the repo.

## Credential Locations

| Service | File | Notes |
|---------|------|-------|
| TopStepX / ProjectX API | `C:\KAI\sovran_v2_secrets\credentials.env` | API key + username |
| TrustGraph API (future) | `C:\KAI\sovran_v2_secrets\credentials.env` | Self-set gateway key |

## How to Use

In your `.env` or environment:
```bash
# Load from secrets file
# PowerShell:
Get-Content C:\KAI\sovran_v2_secrets\credentials.env | ForEach-Object { if ($_ -match '^\w') { [Environment]::SetEnvironmentVariable($_.Split('=')[0], $_.Split('=',2)[1], 'Process') } }

# Or just copy the values into config/.env (which is already gitignored)
```

## Security Rules

1. **Never** commit credentials to git
2. The secrets folder (`C:\KAI\sovran_v2_secrets\`) must NOT be inside the repo
3. `config/.env` is gitignored — safe to put credentials there for runtime
4. If you accidentally commit a credential, rotate it immediately

# How to Switch Claude Code to Free OpenRouter Models

## QUICK SWITCH COMMANDS

When you run out of Claude Pro usage, use these commands:

### In Claude Code CLI:
```bash
# Switch to auto-routing free model (easiest)
/model openrouter/free

# OR switch to specific free models:

# Best for coding (recommended for sovran_v2 work)
/model qwen/qwen3-coder:free

# Best for reasoning
/model nvidia/nemotron-3-super-120b-a12b:free

# Best balanced
/model qwen/qwen3-next-80b-a3b-instruct:free

# Fastest
/model stepfun/step-3.5-flash:free
```

## SETUP STEPS

### 1. Get Valid OpenRouter API Key
**Your current key returned "User not found" - you may need to:**
- Sign up at https://openrouter.ai
- Get a new API key from https://openrouter.ai/keys
- Or verify the current key is active

### 2. Update API Key (if needed)
Edit `C:\KAI\sovran_v2\config\.env`:
```bash
OPENROUTER_API_KEY=your-new-key-here
```

### 3. Test the Connection
```bash
# Test from command line
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR-API-KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openrouter/free",
    "messages": [{"role": "user", "content": "test"}]
  }'
```

## BEST FREE MODELS (March 2026)

### For Trading/Coding Work (sovran_v2):
**qwen/qwen3-coder:free**
- 262K context window
- 480B parameters (35B active)
- Excellent for Python, debugging, refactoring
- Fast responses

### For Complex Analysis:
**nvidia/nemotron-3-super-120b-a12b:free**
- 262K context window
- 120B parameters
- Strong reasoning capabilities
- Best for strategy design

### Zero-Config Fallback:
**openrouter/free**
- 200K context window
- Auto-routes to best available free model
- No model selection needed
- Easiest option

## USAGE TIPS

1. **Free models have rate limits** (~200 req/min)
2. **Switch between models if you hit limits**
3. **Use qwen/qwen3-coder for coding** - it's optimized for Python
4. **Use openrouter/free for general tasks** - auto-selects best model
5. **Check https://openrouter.ai/models** for current availability

## SOVRAN_V2 INTEGRATION

The sovran_v2 system can use OpenRouter for:
- AI Decision Engine responses (ipc/ai_decision_engine.py)
- Ralph loop analysis
- Trade thesis generation
- Kaizen recommendations

The system will automatically use OPENROUTER_API_KEY from `.env` file.

## TROUBLESHOOTING

**"User not found" error:**
- API key may be invalid or expired
- Get new key from https://openrouter.ai/keys
- Verify account is active

**Rate limit errors:**
- Switch to different free model
- Wait 1-5 minutes for limits to reset
- Use multiple models in rotation

**Model unavailable:**
- Try openrouter/free (auto-routing)
- Check https://openrouter.ai/models for status
- Switch to alternative free model

## CURRENT STATUS

✅ Configuration file created: `C:\KAI\sovran_v2\config\.env`
✅ API key added (needs verification)
✅ Free models documented
⚠️ API key returned "User not found" - may need new key

**Next step:** Verify/update your OpenRouter API key, then you're ready to use free models!


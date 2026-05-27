# Modelli gratuiti compatibili con Agent Smith

Criteri: MBPP < 4000 token cumulativi (2-3 iterazioni), SWE-bench 10-30 iterazioni senza rate limit aggressivo.

## OpenRouter (stessa chiave `OPENROUTER_API_KEY`, URL: `https://openrouter.ai/api/v1`, provider: `openrouter`)

| Modello | Perché |
|---------|--------|
| `google/gemini-2.5-flash-preview:free` | Rate limit generoso, ottimo per codice, context lungo |
| `google/gemini-2.0-flash-exp:free` | Veloce, stabile, buon rate limit |
| `deepseek/deepseek-r1-0528:free` | Migliore per ragionamento complesso — top per SWE-bench |
| `deepseek/deepseek-v3-0324:free` | Veloce, eccellente per codice, buono per MBPP |
| `qwen/qwen3-235b-a22b:free` | MoE, ottimo coding, rate limit ok |
| `meta-llama/llama-4-maverick:free` | Context lungo, buono per SWE-bench |

## Mistral (chiave `MISTRAL_API_KEY`, URL: `https://api.mistral.ai/v1`, provider: `mistral`)

| Modello | Perché |
|---------|--------|
| `codestral-latest` | Specializzato su codice, rate limit più alto di mistral-small |
| `mistral-medium-latest` | Più capace di small, rate limit superiore |

## Groq (chiave `GROQ_API_KEY`, URL: `https://api.groq.com/openai/v1`, provider: `groq`)

| Modello | Perché |
|---------|--------|
| `llama-3.3-70b-versatile` | Rate limit alto nel free tier, molto veloce |
| `llama-3.1-8b-instant` | Ultra-veloce per MBPP, adatto a task semplici |

## Come usarli

```bash
# Esempio con OpenRouter
make exam-mbpp MODEL=google/gemini-2.5-flash-preview:free URL=https://openrouter.ai/api/v1 PROVIDER=openrouter

# Esempio con Groq
make exam-mbpp MODEL=llama-3.3-70b-versatile URL=https://api.groq.com/openai/v1 PROVIDER=groq
```

## Raccomandati per l'esame

1. **DeepSeek R1** (`deepseek/deepseek-r1-0528:free`) — SWE-bench, ragionamento lungo
2. **Gemini 2.5 Flash** (`google/gemini-2.5-flash-preview:free`) — MBPP + SWE, bilanciato
3. **Qwen3 235B** (`qwen/qwen3-235b-a22b:free`) — MBPP veloce, affidabile

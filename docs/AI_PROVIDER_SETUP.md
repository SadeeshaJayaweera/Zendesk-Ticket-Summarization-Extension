# AI Provider Configuration & Model Fallback System

## 1. Multi-Provider Architecture

The platform implements a provider-agnostic architecture. Every intelligence task (summarization, troubleshooting, reply drafting, triage) is orchestrated through abstract adapters supporting:
* **Google Gemini** (`gemini-1.5-flash`, `gemini-1.5-pro`, `gemini-2.0-flash`)
* **OpenAI** (`gpt-4o-mini`, `gpt-4o`)
* **Anthropic Claude** (`claude-3-5-haiku-20241022`, `claude-3-5-sonnet-20241022`)
* **Groq Cloud** (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`)

---

## 2. Model Registry & Token Economics

| Model ID | Provider | Context Window | Prompt Cost (per 1M) | Completion Cost (per 1M) | Recommended Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`gemini-1.5-flash`** | Google | 1,000,000 | $0.075 | $0.30 | Primary high-volume summarizer |
| **`gemini-1.5-pro`** | Google | 2,000,000 | $1.25 | $5.00 | Complex escalations & audits |
| **`gpt-4o-mini`** | OpenAI | 128,000 | $0.15 | $0.60 | High-quality reply drafting & triage |
| **`gpt-4o`** | OpenAI | 128,000 | $2.50 | $10.00 | Deep technical troubleshooting |
| **`claude-3-5-haiku-20241022`** | Anthropic | 200,000 | $0.80 | $4.00 | Empathetic customer reply drafting |
| **`claude-3-5-sonnet-20241022`** | Anthropic | 200,000 | $3.00 | $15.00 | Deep root-cause analysis |
| **`llama-3.3-70b-versatile`** | Groq | 128,000 | $0.59 | $0.79 | Ultra-low latency primary or fallback |
| **`llama-3.1-8b-instant`** | Groq | 128,000 | $0.05 | $0.08 | Fast categorization & sentiment |

---

## 3. Fallback Chains & Automatic Failover

When a primary provider encounters a rate limit (`429`), server error (`500/503`), or request timeout, the `AIOrchestrator` automatically fails over to the next configured backup:

```python
# Default Fallback Sequence:
# 1. Primary: Google Gemini 1.5 Flash
# 2. Secondary: Groq LLaMA 3.3 70B
# 3. Tertiary: OpenAI GPT-4o-mini
# 4. Quaternary: Anthropic Claude 3.5 Haiku
```

### Configuring Fallback via Environment Variables
```env
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-1.5-flash
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_MODEL=gpt-4o-mini
```

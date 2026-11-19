# Environment Variables Reference

## Complete Configuration Dictionary

| Variable Name | Type | Default Value | Required | Purpose & Description |
| :--- | :--- | :--- | :--- | :--- |
| **`ZENDESK_SUBDOMAIN`** | `str` | `""` | Yes | Subdomain of your Zendesk account (e.g. `mycompany` for `mycompany.zendesk.com`). |
| **`ZENDESK_EMAIL`** | `str` | `""` | Yes | Email address of the Zendesk agent or admin with API access. |
| **`ZENDESK_API_TOKEN`** | `str` | `""` | Yes | API token generated in Zendesk Admin Center > Apps and integrations > Zendesk API. |
| **`ZENDESK_WEBHOOK_SECRET`** | `str` | `""` | Conditional | Shared secret for verifying HMAC-SHA256 signatures on inbound webhooks. |
| **`DATABASE_URL`** | `str` | `sqlite+aiosqlite:///./data/zendesk_summarizer.db` | No | SQLAlchemy async connection URI (`postgresql+asyncpg://...` or `sqlite+aiosqlite://...`). |
| **`REDIS_URL`** | `str` | `redis://localhost:6379/0` | No | Redis connection URL used by Celery task broker and distributed caching. |
| **`JWT_SECRET_KEY`** | `str` | *(Random insecure string)* | Yes (in Prod) | Cryptographic secret used to sign and verify user JWT bearer tokens. |
| **`JWT_ALGORITHM`** | `str` | `HS256` | No | Algorithm for JWT tokens (`HS256`, `HS512`). |
| **`JWT_EXPIRATION_HOURS`** | `int` | `24` | No | Lifespan in hours for user authentication access tokens. |
| **`LLM_PROVIDER`** | `str` | `gemini` | No | Primary AI provider: `gemini`, `groq`, `openai`, or `anthropic`. |
| **`GEMINI_API_KEY`** | `str` | `""` | Conditional | Google Gemini API key from Google AI Studio or Google Cloud Vertex AI. |
| **`GEMINI_MODEL`** | `str` | `gemini-1.5-flash` | No | Gemini model identifier (`gemini-1.5-flash`, `gemini-1.5-pro`, `gemini-2.0-flash`). |
| **`OPENAI_API_KEY`** | `str` | `""` | Conditional | OpenAI API key. |
| **`OPENAI_MODEL`** | `str` | `gpt-4o-mini` | No | OpenAI model identifier (`gpt-4o`, `gpt-4o-mini`). |
| **`ANTHROPIC_API_KEY`** | `str` | `""` | Conditional | Anthropic Claude API key. |
| **`ANTHROPIC_MODEL`** | `str` | `claude-3-5-haiku-20241022` | No | Anthropic Claude model (`claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`). |
| **`GROQ_API_KEY`** | `str` | `""` | Conditional | Groq Cloud API key. |
| **`GROQ_MODEL`** | `str` | `llama-3.3-70b-versatile` | No | Groq model identifier (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`). |
| **`ENABLE_PII_REDACTION`** | `bool` | `true` | No | When `true`, automatically redacts credit cards, SSNs, and passwords before AI calls. |
| **`RATE_LIMIT_PER_MINUTE`** | `int` | `120` | No | Sliding-window request rate limit per IP or authenticated user per 60 seconds. |
| **`DEFAULT_SUMMARY_STYLE`** | `str` | `standard` | No | Default summary profile applied during webhook automation. |
| **`LOG_LEVEL`** | `str` | `INFO` | No | Application logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| **`BACKEND_HOST`** | `str` | `0.0.0.0` | No | Host binding for Uvicorn server. |
| **`BACKEND_PORT`** | `int` | `8000` | No | Port binding for Uvicorn server. |

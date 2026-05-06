# Governance

## Project Ownership

| Role | Responsible |
|------|-------------|
| **Project Owner** | Pablo Affonso (0xPdaff) |
| **Code Review** | Pablo Affonso |
| **Release Authority** | Pablo Affonso |

## Model Register

| Model Provider | Use Case | Environment Variable | Cost Tier |
|---------------|----------|---------------------|-----------|
| OpenAI | Primary generation | `OPENAI_API_KEY` | High |
| Anthropic | Fallback generation | `ANTHROPIC_API_KEY` | High |
| Deepseek | Cost-effective generation | `DEEPSEEK_API_KEY` | Low |
| Minimax | Alternative generation | `MINIMAX_API_KEY` | Medium |
| Kimi (Moonshot) | Alternative generation | `KIMI_API_KEY` | Medium |
| Qwen | Alternative generation | `QWEN_API_KEY` | Medium |
| GLM (Zhipu) | Alternative generation | `GLM_API_KEY` | Medium |
| Ollama (local) | Offline/private generation | N/A (local) | Free |

## Kill Switch

- **Emergency stop:** Set `ENABLED=false` in `config/model_config.yaml` to disable all LLM calls
- **Provider-specific stop:** Remove or set to empty the corresponding API key in `.env`
- **Rate limit override:** Set `RATE_LIMIT_MAX=0` in `.env` to disable LLM calls

## Budget Controls

- **Default max tokens per request:** 4096 (configurable in `config/model_config.yaml`)
- **Estimated cost per playbook:** ~$0.02-0.10 USD depending on provider
- **No hard spend limit** (user controls via API key billing)

## Safety Guardrails

1. **Input validation:** Reject empty, too-short, or maliciously crafted inputs
2. **Output validation:** Ensure generated playbooks don't contain destructive commands without warnings
3. **No real execution:** The agent NEVER executes generated commands
4. **PII detection:** Warn if incident description appears to contain PII
5. **Disclaimer:** All outputs include a disclaimer that playbooks are AI-generated and should be reviewed

## Data Handling

- **No data retention:** Playbooks are generated on-demand, not stored by default (unless user saves)
- **No telemetry:** No usage data sent to external services
- **Local-only cache:** Cache files stay on the local machine
- **API keys:** Stored in `.env`, never logged or transmitted

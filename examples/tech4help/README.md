# Tech4Help voice intake with local AI

Two built-in starters turn Dograh into an intake desk for Tech4Help:

| Agent | Captures | Human decision |
| --- | --- | --- |
| Community equipment donations | Device type, quantity, condition, data-on-device disclosure, general area, optional contact | Acceptance and handover arrangements |
| Business IT-service requests | Issue, affected users/services, business impact, preferred timeframe, optional contact | Scope, availability and any charges |

The agents disclose that they are AI, ask whether to continue, make follow-up contact optional, and summarize the request for review. Donation intake and commercial services stay separate. No email, CRM, booking, outbound campaign or phone number is connected by this starter.

## What is free

The AI runs locally: **Qwen3 4B Instruct through Ollama**, **Whisper through Speaches**, and **Kokoro through Speaches**. No metered AI key or trial credit is needed for these models. Dograh uses its existing `speaches` provider for all three endpoints. Ollama cloud features are disabled in this Compose stack.

Your computer/server, electricity, storage and any phone service still have costs. Downloads require internet access and several GB of disk space. The CPU configuration is for evaluation; measure latency on your hardware before handling real conversations. A GPU may be needed for satisfactory live voice performance or concurrent users.

## Start locally

Prerequisites: Git, Docker with Compose v2, Python 3.10+, enough RAM/disk for the models and Dograh build, and unused ports 3010, 8000, 8001, 9000 and 11434. The API Dockerfile currently targets Linux amd64; this profile has not been verified on ARM.

Run from the repository root:

```bash
git submodule update --init --recursive
python examples/tech4help/setup.py init
docker compose --env-file examples/tech4help/.env -f examples/tech4help/compose.yaml up -d --build
python examples/tech4help/setup.py download
python examples/tech4help/setup.py check
```

`init` creates unique credentials and leaves an existing `.env` untouched. Keep this file private and preserve it with your database backups. The Compose project has separate persistent volumes and binds published ports to loopback. It builds this fork's API and UI, so it includes the Tech4Help page. No public tunnel is started.

Model services may take time to become ready on first launch. If a download fails with connection refused, inspect `docker compose --env-file examples/tech4help/.env -f examples/tech4help/compose.yaml logs ollama speaches` and retry once ready. Completed models are cached. Image tags follow the upstream defaults; set `OLLAMA_IMAGE` and `SPEACHES_IMAGE` in the generated `.env` to a tested tag/digest to pin a deployment.

The check uses a synthetic tool call and a generated sentence, then transcribes that audio. It fails on HTTP errors, malformed tool arguments, empty speech, or an incorrect transcript. It prints timing and does not place calls or send messages. Passing it verifies the model endpoints, not a complete Dograh/WebRTC session.

Open **http://localhost:3010/workflow/tech4help**, sign in/create the local account, leave **Tech4Help Docker stack** selected, and create each agent. You can also reach the page from **Your Agents → Tech4Help starters**.

The per-agent model configuration is saved in the first published version in the same operation as creation. It does not overwrite account-wide settings or other agents. After editing a starter, use Dograh's normal validate/publish flow to release the new version.

### Existing native Dograh installation

Start only the model containers alongside your existing native API/UI:

```bash
python examples/tech4help/setup.py init
docker compose --env-file examples/tech4help/.env -f examples/tech4help/compose.yaml up -d ollama speaches
python examples/tech4help/setup.py download
python examples/tech4help/setup.py check
```

Run the updated fork and select **On this computer, outside Docker** on the Tech4Help page. This uses `http://127.0.0.1:11434/v1` for the LLM and `http://127.0.0.1:8001/v1` for speech. The Docker choice uses the service names `ollama:11434` and `speaches:8000` instead. An API in a different Docker project will need its own network configuration and endpoint settings.

## Verify before using real requests

Use fictional details in Dograh's editor tests, then inspect the run transcript and extracted fields. Extraction is model-generated and must be checked by a person; a prompt is not an enforcement mechanism or a guarantee against hallucinations.

| Test conversation | Expected behavior |
| --- | --- |
| Offer five laptops, two broken, with chargers | Record quantity/condition accurately; do not promise acceptance or pickup |
| Ask whether the donation is tax deductible | Defer confirmation to the team; do not assert charity status or a deduction |
| Decline intake at the greeting | Close without more questions; `continue_consent` is false |
| Agree to intake but decline contact | Finish with empty contact fields and `follow_up_consent` false |
| Report a printer outage affecting three staff | Capture the issue and impact; do not promise a fix, price or response time |
| Offer a password or verification code | Ask them not to share secrets; do not repeat or extract the value |
| Ask for a booking or live human transfer | Explain that neither is connected; do not claim success |
| Ask to stop before completing the questions | Stop, with an incomplete/declined outcome rather than invented data |

Review transcripts/recordings under the existing Dograh access and retention settings. Prompts asking the model to omit secrets do **not** redact raw audio or transcripts. Configure retention, staff access, recording disclosures and a real follow-up process before using personal information. This is a localhost evaluation profile, not a public deployment configuration.

## Development checks

```bash
python -m unittest discover -s examples/tech4help -p 'test_*.py'
cd ui
npm run test:tech4help
npx tsc --noEmit
```

With the API development dependencies and **test** environment configured, also run:

```bash
python -m pytest api/tests/test_tech4help_starters.py api/tests/test_workflow_create_route.py api/tests/test_workflow_versioning.py api/tests/test_resolve_effective_config.py
```

Templates and model IDs live in `ui/src/lib/tech4help/catalog.json`; the setup tool and UI share that catalog. The new create-request field `workflow_configurations` is optional, preserving old clients. It is validated against the user's effective configuration before creation and stored on both the workflow and its first published definition.

## Upstream references

- [Ollama local API compatibility](https://docs.ollama.com/api/openai-compatibility)
- [Qwen3 model tags](https://ollama.com/library/qwen3/tags)
- [Speaches installation](https://speaches.ai/installation/)
- [Speaches model downloads](https://speaches.ai/usage/model-discovery/)
- [Speaches text-to-speech](https://speaches.ai/usage/text-to-speech/)

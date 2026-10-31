"""Download and exercise Tech4Help's local AI stack using Python's standard library."""

import argparse
import io
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "ui/src/lib/tech4help/catalog.json"
ENV_FILE = Path(__file__).with_name(".env")
TEST_PHRASE = "Tech4Help can review your equipment donation."


def request(
    url, payload=None, *, body=None, content_type="application/json", timeout=180
):
    if payload is not None:
        body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type})
    # Model services are local; never send their requests through a system proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as response:
        return response.read()


def request_json(url, payload=None, **kwargs):
    return json.loads(request(url, payload, **kwargs))


def init_environment(path=ENV_FILE):
    # Exclusive creation prevents silently replacing credentials for an existing DB.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("Existing Tech4Help .env kept unchanged.")
        return
    with os.fdopen(fd, "w") as stream:
        for key in ("DB_PASSWORD", "REDIS_PASSWORD", "STORAGE_PASSWORD", "JWT_SECRET"):
            stream.write(f"TECH4HELP_{key}={secrets.token_urlsafe(36)}\n")
    print("Created Tech4Help .env with unique local credentials.")


def download_models(models, llm, speech):
    print(
        f"Downloading {models['llm']} into Ollama (this can take several minutes)…",
        flush=True,
    )
    result = request_json(
        f"{llm}/api/pull", {"model": models["llm"], "stream": False}, timeout=3600
    )
    if result.get("status") != "success":
        raise ValueError("Ollama did not confirm a successful model download.")
    for kind in ("stt", "tts"):
        print(f"Downloading {models[kind]} into Speaches…", flush=True)
        model = urllib.parse.quote(models[kind], safe="/")
        request(f"{speech}/v1/models/{model}", body=b"", timeout=3600)
    print("Model downloads finished. Run the check command next.")


def validate_tool_call(result):
    try:
        calls = result["choices"][0]["message"]["tool_calls"]
        function = calls[0]["function"]
        arguments = json.loads(function["arguments"])
        if (
            len(calls) != 1
            or function["name"] != "finish_intake"
            or not isinstance(arguments, dict)
            or set(arguments) != {"ready"}
            or arguments["ready"] is not True
        ):
            raise ValueError
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(
            "The model did not return the expected structured tool call; do not start voice testing yet."
        ) from exc


def multipart_audio(model, audio):
    boundary = f"tech4help-{secrets.token_hex(12)}"
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nen\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="readiness.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
        + audio
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return body, f"multipart/form-data; boundary={boundary}"


def check_models(models, llm, speech):
    start = time.monotonic()
    result = request_json(
        f"{llm}/v1/chat/completions",
        {
            "model": models["llm"],
            "messages": [
                {
                    "role": "user",
                    "content": "Call finish_intake with ready set to true. Do not reply with prose.",
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "finish_intake",
                        "description": "Finish this readiness test.",
                        "parameters": {
                            "type": "object",
                            "properties": {"ready": {"type": "boolean"}},
                            "required": ["ready"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "temperature": 0,
            "stream": False,
        },
    )
    validate_tool_call(result)
    print(
        f"PASS Ollama tool calling ({time.monotonic() - start:.1f}s, including model load)",
        flush=True,
    )

    start = time.monotonic()
    audio = request(
        f"{speech}/v1/audio/speech",
        {
            "model": models["tts"],
            "voice": models["voice"],
            "input": TEST_PHRASE,
            "response_format": "wav",
        },
    )
    with wave.open(io.BytesIO(audio), "rb") as wav:
        if wav.getnframes() == 0:
            raise ValueError("TTS returned an empty WAV file.")
    print(
        f"PASS Kokoro speech generation ({time.monotonic() - start:.1f}s)", flush=True
    )

    start = time.monotonic()
    body, content_type = multipart_audio(models["stt"], audio)
    result = request_json(
        f"{speech}/v1/audio/transcriptions", body=body, content_type=content_type
    )
    text = result.get("text", "").lower()
    if not all(word in text for word in ("equipment", "donation")):
        raise ValueError(
            "Whisper did not recover the expected words from generated speech."
        )
    print(f"PASS Whisper speech round trip ({time.monotonic() - start:.1f}s)")
    print(
        "Local model checks passed. Next: test both agents in Dograh with fictional details. No calls were placed."
    )


def local_url(value):
    parsed = urllib.parse.urlparse(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise argparse.ArgumentTypeError(
            "Use an HTTP loopback address, for example http://127.0.0.1:8001."
        )
    return value.rstrip("/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "download", "check"))
    parser.add_argument(
        "--ollama-url", type=local_url, default="http://127.0.0.1:11434"
    )
    parser.add_argument("--speech-url", type=local_url, default="http://127.0.0.1:8001")
    args = parser.parse_args()
    try:
        if args.command == "init":
            init_environment()
        else:
            models = json.loads(CATALOG.read_text())["models"]
            action = download_models if args.command == "download" else check_models
            action(models, args.ollama_url, args.speech_url)
    except (OSError, ValueError, KeyError, wave.Error, urllib.error.URLError) as exc:
        print(
            f"FAILED: {exc}\nCheck that the local services are running and models were downloaded.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

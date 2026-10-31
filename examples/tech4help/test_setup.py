"""Protocol and failure tests; these do not substitute for real model testing."""

import argparse
import contextlib
import http.server
import io
import json
import tempfile
import threading
import unittest
import wave
from pathlib import Path

import setup


class SetupTests(unittest.TestCase):
    def test_credentials_are_distinct_and_not_overwritten(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            path = Path(folder) / ".env"
            setup.init_environment(path)
            original = path.read_text()
            values = [line.split("=", 1)[1] for line in original.splitlines()]
            self.assertEqual(len(set(values)), 4)
            self.assertTrue(all(len(value) >= 40 for value in values))
            setup.init_environment(path)
            self.assertEqual(path.read_text(), original)

    def test_nonlocal_urls_are_rejected(self):
        for url in [
            "https://example.com",
            "http://localhost.example.com",
            "http://user:secret@localhost",
            "http://127.0.0.1/v1",
            "http://localhost?key=secret",
        ]:
            with self.subTest(url=url), self.assertRaises(argparse.ArgumentTypeError):
                setup.local_url(url)
        self.assertEqual(
            setup.local_url("http://127.0.0.1:8001/"), "http://127.0.0.1:8001"
        )

    def test_incorrect_tool_calls_fail_closed(self):
        for result in [
            {},
            {"choices": []},
            {"choices": [{"message": {"content": "Done!"}}]},
            self.tool_result('{"ready":false}'),
            self.tool_result('{"ready":1}'),
            self.tool_result("broken JSON"),
        ]:
            with self.subTest(result=result), self.assertRaises(ValueError):
                setup.validate_tool_call(result)

    @staticmethod
    def tool_result(arguments='{"ready":true}'):
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "finish_intake",
                                    "arguments": arguments,
                                }
                            }
                        ]
                    }
                }
            ]
        }

    def test_check_exercises_llm_tts_and_stt_http_contracts(self):
        received = []
        wav = io.BytesIO()
        with wave.open(wav, "wb") as stream:
            stream.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            stream.writeframes(b"\0\0" * 240)
        audio = wav.getvalue()
        tool_response = self.tool_result()

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                received.append((self.path, body, self.headers["Content-Type"]))
                if self.path.endswith("chat/completions"):
                    response = json.dumps(tool_response).encode()
                elif self.path.endswith("audio/speech"):
                    response = audio
                else:
                    response = (
                        b'{"text":"Tech4Help can review your equipment donation."}'
                    )
                self.send_response(200)
                self.end_headers()
                self.wfile.write(response)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        models = {
            "llm": "test-llm",
            "tts": "test-tts",
            "stt": "test-stt",
            "voice": "test-voice",
        }
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                setup.check_models(models, url, url)
            self.assertIn("Local model checks passed", output.getvalue())
            self.assertEqual(
                [item[0] for item in received],
                [
                    "/v1/chat/completions",
                    "/v1/audio/speech",
                    "/v1/audio/transcriptions",
                ],
            )
            self.assertEqual(json.loads(received[0][1])["model"], "test-llm")
            self.assertEqual(json.loads(received[1][1])["voice"], "test-voice")
            self.assertIn(b'name="model"\r\n\r\ntest-stt', received[2][1])
            self.assertIn(audio, received[2][1])
            self.assertIn("multipart/form-data; boundary=", received[2][2])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()

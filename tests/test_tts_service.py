import json
from unittest import TestCase

from services.tts import (
    _cancel_task_message,
    _continue_task_message,
    _finish_task_message,
    _run_task_message,
)


class TTSProtocolMessageTests(TestCase):
    def test_run_task_requests_pcm_streaming(self) -> None:
        message = json.loads(_run_task_message("task-id"))

        self.assertEqual(message["header"]["action"], "run-task")
        self.assertEqual(message["header"]["streaming"], "duplex")
        self.assertEqual(message["payload"]["task"], "tts")
        self.assertEqual(message["payload"]["parameters"]["format"], "pcm")
        self.assertEqual(
            message["payload"]["parameters"]["language_hints"],
            ["zh"],
        )

    def test_continue_finish_and_cancel_messages_share_task_id(self) -> None:
        continuing = json.loads(_continue_task_message("task-id", "你好"))
        finishing = json.loads(_finish_task_message("task-id"))
        cancelling = json.loads(_cancel_task_message("task-id"))

        self.assertEqual(continuing["header"]["task_id"], "task-id")
        self.assertEqual(continuing["payload"]["input"]["text"], "你好")
        self.assertEqual(finishing["payload"]["input"], {})
        self.assertEqual(
            cancelling["payload"]["input"]["directive"],
            "cancel",
        )

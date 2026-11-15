from pydantic import BaseModel


class SpeechTranscriptionResponse(BaseModel):
    text: str
    duration_seconds: float | None = None
    request_id: str | None = None

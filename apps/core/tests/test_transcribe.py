from juno.llm.transcribe import OfflineTranscriber, OpenAIWhisperTranscriber, create_transcriber


def test_create_transcriber_auto_without_key_is_offline():
    t = create_transcriber("auto", openai_api_key="")
    assert isinstance(t, OfflineTranscriber)


def test_create_transcriber_auto_with_key_is_whisper():
    t = create_transcriber("auto", openai_api_key="sk-test")
    assert isinstance(t, OpenAIWhisperTranscriber)

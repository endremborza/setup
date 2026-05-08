"""TTS: read stdin and speak it aloud using kokoro-onnx."""

from dienpy.cli import Dispatcher

_dispatcher = Dispatcher.from_package("dienpy.tts", prog="dienpy tts")

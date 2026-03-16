# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Real-time audio translation desktop app (English <-> Spanish). Single-file Python/Tkinter application that captures audio, transcribes via Google Speech Recognition, and translates using Google Translate.

## Running the App

```bash
python3 translator.py
```

No build step required. Requires macOS for BlackHole virtual audio device support.

## Dependencies

Install with pip (no requirements.txt exists):
```bash
pip install sounddevice numpy SpeechRecognition deep_translator
```

Tkinter is included with Python. Vosk models are bundled in `models/`.

## Architecture

Single-file app (`translator.py`, ~335 lines) with these layers:
- **GUI**: Tkinter with dark theme, always-on-top window (620x520)
- **Audio capture**: sounddevice streams 3-second chunks at 44100Hz mono
- **Speech recognition**: Google Speech Recognition API (online, language-aware)
- **Translation**: deep_translator (GoogleTranslator)
- **Threading**: Audio processing runs in background threads to keep UI responsive

**Processing flow**: Audio chunk → silence detection (RMS threshold 0.005) → temp WAV file → Google STT → Google Translate → display in UI

## Key Parameters

- Sample rate: 44100 Hz
- Chunk duration: 3 seconds
- Silence threshold: 0.005 RMS
- Modes: EN→ES and ES→EN

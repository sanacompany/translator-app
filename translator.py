#!/usr/bin/env python3
"""
Real-time Audio Translator
Uses Google Speech Recognition (online, accurate) + Google Translate.
Supports system audio capture via BlackHole.
"""

import tkinter as tk
from tkinter import ttk
import threading
import sounddevice as sd
import numpy as np
import speech_recognition as sr
from deep_translator import GoogleTranslator
import tempfile
import wave
import os
import time

SAMPLE_RATE = 44100
CHUNK_DURATION = 3
SILENCE_RMS = 0.005


class TranslatorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Audio Translator")
        self.root.geometry("620x520")
        self.root.configure(bg="#1a1a2e")
        self.root.attributes("-topmost", True)

        self.is_listening = False
        self.mode = "en_to_es"
        self.stream = None
        self.audio_buffer = []
        self.buffer_lock = threading.Lock()
        self.recognizer = sr.Recognizer()

        self.translator_en_es = GoogleTranslator(source="en", target="es")
        self.translator_es_en = GoogleTranslator(source="es", target="en")

        self._build_ui()
        self._populate_devices()

    def _build_ui(self):
        title = tk.Label(
            self.root, text="Audio Translator",
            font=("Helvetica", 22, "bold"), fg="#e94560", bg="#1a1a2e"
        )
        title.pack(pady=(15, 5))

        # Device selector
        device_frame = tk.Frame(self.root, bg="#1a1a2e")
        device_frame.pack(fill="x", padx=20, pady=(5, 5))
        tk.Label(
            device_frame, text="Audio Input (select BlackHole for system audio):",
            font=("Helvetica", 11), fg="#ffffff", bg="#1a1a2e"
        ).pack(anchor="w")
        self.device_combo = ttk.Combobox(device_frame, state="readonly", width=55)
        self.device_combo.pack(fill="x", pady=(2, 0))

        # Refresh devices button
        tk.Button(
            device_frame, text="Refresh devices", font=("Helvetica", 9),
            bg="#333", fg="white", command=self._populate_devices
        ).pack(anchor="e", pady=(3, 0))

        # Mode buttons
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(pady=8)

        self.btn_en_es = tk.Button(
            btn_frame, text="EN -> ES",
            font=("Helvetica", 16, "bold"),
            bg="#0f3460", fg="white", activebackground="#16213e",
            width=14, height=2,
            command=lambda: self._set_mode("en_to_es"),
            relief="raised", bd=3
        )
        self.btn_en_es.pack(side="left", padx=10)

        self.btn_es_en = tk.Button(
            btn_frame, text="ES -> EN",
            font=("Helvetica", 16, "bold"),
            bg="#533483", fg="white", activebackground="#16213e",
            width=14, height=2,
            command=lambda: self._set_mode("es_to_en"),
            relief="raised", bd=3
        )
        self.btn_es_en.pack(side="left", padx=10)

        # Start/Stop
        self.btn_listen = tk.Button(
            self.root, text="START",
            font=("Helvetica", 18, "bold"),
            bg="#e94560", fg="white", activebackground="#c81d4e",
            width=20, height=2,
            command=self._toggle_listening,
            relief="raised", bd=3
        )
        self.btn_listen.pack(pady=8)

        # Status + volume
        status_frame = tk.Frame(self.root, bg="#1a1a2e")
        status_frame.pack(fill="x", padx=20)
        self.status_label = tk.Label(
            status_frame, text="Mode: EN -> ES  |  Stopped",
            font=("Helvetica", 12), fg="#a8a8a8", bg="#1a1a2e"
        )
        self.status_label.pack(side="left")
        self.volume_label = tk.Label(
            status_frame, text="",
            font=("Courier", 12), fg="#28a745", bg="#1a1a2e"
        )
        self.volume_label.pack(side="right")

        # Text displays
        text_frame = tk.Frame(self.root, bg="#1a1a2e")
        text_frame.pack(fill="both", expand=True, padx=20, pady=(5, 5))

        tk.Label(
            text_frame, text="Original:",
            font=("Helvetica", 10), fg="#a8a8a8", bg="#1a1a2e"
        ).pack(anchor="w")
        self.original_text = tk.Text(
            text_frame, height=4, font=("Helvetica", 13),
            bg="#16213e", fg="#ffffff", wrap="word", relief="flat", padx=10, pady=5
        )
        self.original_text.pack(fill="both", expand=True)

        tk.Label(
            text_frame, text="Translation:",
            font=("Helvetica", 10), fg="#a8a8a8", bg="#1a1a2e"
        ).pack(anchor="w", pady=(5, 0))
        self.translated_text = tk.Text(
            text_frame, height=4, font=("Helvetica", 14, "bold"),
            bg="#0f3460", fg="#e94560", wrap="word", relief="flat", padx=10, pady=5
        )
        self.translated_text.pack(fill="both", expand=True)

        # Clear button
        tk.Button(
            self.root, text="Clear", font=("Helvetica", 10),
            bg="#333", fg="white", command=self._clear_text
        ).pack(pady=(5, 10))

        self._update_mode_buttons()

    def _populate_devices(self):
        devices = sd.query_devices()
        input_devices = []
        self.device_indices = []
        blackhole_idx = None

        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                name = dev["name"]
                display = f"{name} ({int(dev['default_samplerate'])}Hz)"
                input_devices.append(display)
                self.device_indices.append(i)
                if "blackhole" in name.lower():
                    blackhole_idx = len(input_devices) - 1

        self.device_combo["values"] = input_devices

        # Prefer BlackHole if available
        if blackhole_idx is not None:
            self.device_combo.current(blackhole_idx)
        else:
            default_idx = sd.default.device[0]
            if default_idx in self.device_indices:
                self.device_combo.current(self.device_indices.index(default_idx))
            elif input_devices:
                self.device_combo.current(0)

    def _set_mode(self, mode):
        self.mode = mode
        self._update_mode_buttons()
        self._update_status()

    def _update_mode_buttons(self):
        if self.mode == "en_to_es":
            self.btn_en_es.config(bg="#e94560", relief="sunken")
            self.btn_es_en.config(bg="#533483", relief="raised")
        else:
            self.btn_en_es.config(bg="#0f3460", relief="raised")
            self.btn_es_en.config(bg="#e94560", relief="sunken")

    def _update_status(self):
        mode_text = "EN -> ES" if self.mode == "en_to_es" else "ES -> EN"
        state = "Listening..." if self.is_listening else "Stopped"
        self.status_label.config(text=f"Mode: {mode_text}  |  {state}")

    def _clear_text(self):
        self.original_text.delete("1.0", "end")
        self.translated_text.delete("1.0", "end")

    def _toggle_listening(self):
        if self.is_listening:
            self._stop_listening()
        else:
            self._start_listening()

    def _start_listening(self):
        combo_idx = self.device_combo.current()
        if combo_idx < 0:
            return

        device_idx = self.device_indices[combo_idx]
        device_info = sd.query_devices(device_idx)
        self.capture_rate = int(device_info["default_samplerate"])

        self.is_listening = True
        self.audio_buffer = []
        self.btn_listen.config(text="STOP", bg="#28a745")
        self._update_status()

        def callback(indata, frames, time_info, status):
            if not self.is_listening:
                return
            audio = indata[:, 0].copy()
            rms = np.sqrt(np.mean(audio ** 2))
            bars = int(min(rms * 300, 25))
            self.root.after(0, lambda b=bars: self.volume_label.config(
                text="|" * b if b > 0 else "",
                fg="#28a745" if b < 12 else "#e94560"
            ))
            with self.buffer_lock:
                self.audio_buffer.append(audio)

        try:
            self.stream = sd.InputStream(
                samplerate=self.capture_rate,
                channels=1,
                dtype="float32",
                blocksize=int(self.capture_rate * 0.1),
                device=device_idx,
                callback=callback
            )
            self.stream.start()
        except Exception as e:
            self._append_display("Error", str(e))
            self.is_listening = False
            self.btn_listen.config(text="START", bg="#e94560")
            return

        threading.Thread(target=self._process_loop, daemon=True).start()

    def _process_loop(self):
        while self.is_listening:
            time.sleep(CHUNK_DURATION)
            if not self.is_listening:
                break

            with self.buffer_lock:
                if not self.audio_buffer:
                    continue
                audio = np.concatenate(self.audio_buffer)
                self.audio_buffer = []

            rms = np.sqrt(np.mean(audio ** 2))
            if rms < SILENCE_RMS:
                continue

            # Save to temp WAV
            tmp_path = None
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_path = tmp.name
                tmp.close()

                int16_audio = (audio * 32767).astype(np.int16)
                with wave.open(tmp_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.capture_rate)
                    wf.writeframes(int16_audio.tobytes())

                # Recognize with Google (free, accurate)
                lang = "en-US" if self.mode == "en_to_es" else "es-ES"
                with sr.AudioFile(tmp_path) as source:
                    audio_data = self.recognizer.record(source)

                text = self.recognizer.recognize_google(audio_data, language=lang)
                text = text.strip()

                if not text or len(text) < 2:
                    continue

                # Translate
                if self.mode == "en_to_es":
                    translated = self.translator_en_es.translate(text)
                else:
                    translated = self.translator_es_en.translate(text)

                if translated:
                    self._append_display(text, translated)

            except sr.UnknownValueError:
                pass  # Could not understand audio
            except sr.RequestError as e:
                self._append_display("API Error", str(e))
            except Exception as e:
                self._append_display("Error", str(e))
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    def _stop_listening(self):
        self.is_listening = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.btn_listen.config(text="START", bg="#e94560")
        self._update_status()
        self.root.after(0, lambda: self.volume_label.config(text=""))

    def _append_display(self, original, translated):
        def _update():
            self.original_text.insert("end", original + "\n")
            self.original_text.see("end")
            self.translated_text.insert("end", translated + "\n")
            self.translated_text.see("end")
        self.root.after(0, _update)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = TranslatorApp()
    app.run()

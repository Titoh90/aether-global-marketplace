"""
tts_engine.py — Chatterbox TTS wrapper for IMPERIO

Generates voiceover audio for faceless video content.
Uses Chatterbox Turbo on Apple Silicon MPS — no API key, no cost.

Usage:
    from tts_engine import TTSEngine
    engine = TTSEngine()
    path = engine.speak("Este auricular gaming cambia tu vida.", output_path="/tmp/vo.wav")
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("tts_engine")

_OUTPUT_DIR = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/voiceovers")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Singleton model — load once, reuse
_model = None
_model_device = None


def _load_model(device: str = "mps"):
    """Load ChatterboxTurbo. Patches perth for Python 3.14 compatibility."""
    global _model, _model_device
    if _model is not None and _model_device == device:
        return _model

    # Python 3.14 compat: pkg_resources removed → perth uses DummyWatermarker
    try:
        import perth
        if perth.PerthImplicitWatermarker is None:
            perth.PerthImplicitWatermarker = perth.DummyWatermarker
            log.info("perth: patched PerthImplicitWatermarker → DummyWatermarker")
    except ImportError:
        pass

    from chatterbox.tts_turbo import ChatterboxTurboTTS
    log.info(f"Loading ChatterboxTurbo on {device}...")
    t = time.time()
    _model = ChatterboxTurboTTS.from_pretrained(device=device)
    _model_device = device
    log.info(f"ChatterboxTurbo loaded in {time.time()-t:.1f}s")
    return _model


class TTSEngine:
    """
    Thin wrapper around ChatterboxTurbo.

    Args:
        device: 'mps' (Apple Silicon), 'cuda', or 'cpu'
        voice_ref: Optional path to a 3-10s WAV for voice cloning
    """

    def __init__(self, device: str = "mps", voice_ref: Optional[str] = None):
        self.device = device
        self.voice_ref = voice_ref
        self._model = None  # lazy load

    def _get_model(self):
        if self._model is None:
            self._model = _load_model(self.device)
        return self._model

    def speak(
        self,
        text: str,
        output_path: Optional[str] = None,
        voice_ref: Optional[str] = None,
    ) -> str:
        """
        Generate speech audio.

        Args:
            text:        Text to speak
            output_path: Where to save .wav (auto-generates path if None)
            voice_ref:   Override voice reference file

        Returns:
            Absolute path to generated .wav file
        """
        import soundfile as sf

        model = self._get_model()
        ref = voice_ref or self.voice_ref
        t = time.time()

        log.info(f"TTS: generating {len(text)} chars | voice_ref={ref}")

        kwargs = {}
        if ref and Path(ref).exists():
            kwargs["audio_prompt_path"] = ref

        wav = model.generate(text, **kwargs)
        elapsed = time.time() - t

        # Save
        if output_path is None:
            ts = int(time.time())
            output_path = str(_OUTPUT_DIR / f"vo_{ts}.wav")

        audio = wav.squeeze().cpu().numpy()
        sf.write(output_path, audio, model.sr)

        duration = len(audio) / model.sr
        log.info(f"TTS: {duration:.1f}s audio in {elapsed:.1f}s → {output_path}")
        return output_path

    def speak_script(
        self,
        lines: list[str],
        output_dir: Optional[str] = None,
        voice_ref: Optional[str] = None,
    ) -> list[str]:
        """
        Generate multiple audio files from a list of script lines.
        Returns list of .wav paths in order.
        """
        out_dir = Path(output_dir) if output_dir else _OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            path = str(out_dir / f"line_{i:03d}.wav")
            self.speak(line, output_path=path, voice_ref=voice_ref)
            paths.append(path)
        return paths


# ── CLI quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "Este auricular gaming tiene sonido increíble. Link de afiliado en bio. No te lo pierdas."
    )
    engine = TTSEngine(device="mps")
    path = engine.speak(text, output_path="/tmp/empire_tts_test.wav")
    print(f"Saved: {path}")

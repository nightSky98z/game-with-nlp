from __future__ import annotations

import os
import queue
import tempfile
import threading
import time
import wave
from dataclasses import dataclass

from inference.TextUtils import normalize_ascii_width


VOICE_STATE_IDLE = "idle"
VOICE_STATE_RECORDING = "recording"
VOICE_STATE_TRANSCRIBING = "transcribing"
VOICE_STATE_ERROR = "error"

VOICE_EVENT_RECOGNIZED_TEXT = "recognized_text"
VOICE_EVENT_ERROR = "error"

VOICE_STATUS_TEXT_LIMIT = 40
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_WHISPER_MODEL_SIZE = "tiny"
DEFAULT_WHISPER_DEVICE = "cpu"
DEFAULT_WHISPER_COMPUTE_TYPE = "int8"
DEFAULT_MAX_TRANSCRIPTION_SECONDS = 120.0


@dataclass(frozen=True)
class VoiceInputEvent:
    """音声入力 worker からゲーム本体へ渡す結果イベント。

    Params:
    - kind: `recognized_text` または `error`。呼び出し側はこの値で処理を分岐する。
    - text: 認識済みコマンド文字列。`kind == recognized_text` のときだけ値を持つ。
    - message: エラーメッセージ。`kind == error` のときだけ値を持つ。

    Caller:
    - pygame の state は worker thread から直接触らず、このイベントを main thread で読む。
    """

    kind: str
    text: str | None = None
    message: str | None = None


class SoundDeviceRecorder:
    """sounddevice で push-to-talk の録音 WAV を作る。

    Caller:
    - `start()` から `stop_to_wav_file()` までを同じインスタンスで 1 回の録音として扱う。
    - 返された WAV ファイルの削除責任は呼び出し側が持つ。
    - `sounddevice` と `numpy` は実行時だけ必要で、import 失敗は例外として返る。
    """

    def __init__(self, sample_rate=DEFAULT_SAMPLE_RATE, channels=DEFAULT_CHANNELS):
        """録音設定と stream 所有状態を初期化する。

        Params:
        - sample_rate: WAV と入力 stream の sample rate。
        - channels: 入力 channel 数。

        Caller:
        - この時点では sounddevice を import せず、`start()` で遅延 import する。
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.stream = None
        self.audio_chunks = []
        self._sounddevice = None

    def start(self):
        """マイク入力ストリームを開始する。

        Errors:
        - RuntimeError: すでに録音中、または sounddevice の初期化に失敗した。

        Caller:
        - 成功後は必ず `stop_to_wav_file()` を呼んでストリームを閉じる。
        """
        if self.stream is not None:
            raise RuntimeError("録音はすでに開始されています")
        try:
            import sounddevice
        except ImportError as err:
            raise RuntimeError("sounddevice を読み込めません") from err

        self._sounddevice = sounddevice
        self.audio_chunks = []

        def record_callback(indata, frames, time_info, status):
            """sounddevice callback から録音 chunk を蓄積する。

            Params:
            - indata: 今回受け取った音声 buffer。
            - frames: callback の frame 数。現状は制御に使わない。
            - time_info: sounddevice の時刻情報。現状は使わない。
            - status: 入力 stream の警告状態。値があれば標準出力へ出す。

            Caller:
            - sounddevice の audio thread から呼ばれるため、pygame 状態には触らない。
            """
            if status:
                print(f"音声入力ステータス: {status}")
            self.audio_chunks.append(indata.copy())

        self.stream = sounddevice.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=record_callback,
        )
        self.stream.start()

    def stop_to_wav_file(self):
        """録音を終了し、一時 WAV ファイルへ書き出す。

        Returns:
        - WAV ファイルパス。録音データがない場合は `None`。

        Errors:
        - RuntimeError: numpy の読み込み、ストリーム停止、WAV 書き出しに失敗した。

        Caller:
        - 戻り値のファイルは認識完了後に削除する。
        """
        if self.stream is None:
            return None

        stream = self.stream
        self.stream = None
        stream.stop()
        stream.close()

        if len(self.audio_chunks) == 0:
            return None

        try:
            import numpy
        except ImportError as err:
            raise RuntimeError("numpy を読み込めません") from err

        audio = numpy.concatenate(self.audio_chunks, axis=0)
        audio = numpy.clip(audio, -1.0, 1.0)
        audio_int16 = (audio * 32767).astype(numpy.int16)

        fd, wav_path = tempfile.mkstemp(prefix="nlp_voice_", suffix=".wav")
        os.close(fd)
        with wave.open(wav_path, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        return wav_path


class FasterWhisperTranscriber:
    """faster-whisper で短い日本語ゲームコマンドを文字列へ変換する。

    Caller:
    - 初回 `transcribe()` でモデルを遅延ロードするため、初回だけ待ち時間が出る。
    - 入力 WAV ファイルの所有権は呼び出し側に残る。
    """

    def __init__(
        self,
        model_size=DEFAULT_WHISPER_MODEL_SIZE,
        device=DEFAULT_WHISPER_DEVICE,
        compute_type=DEFAULT_WHISPER_COMPUTE_TYPE,
    ):
        """faster-whisper のモデル設定を保持する。

        Params:
        - model_size: Whisper モデルサイズまたはモデル ID。
        - device: `cpu` / `cuda` などの推論 device。
        - compute_type: `int8` など faster-whisper に渡す計算型。

        Caller:
        - モデル本体は初回 `transcribe()` まで読み込まない。
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None

    def transcribe(self, audio_path):
        """WAV ファイルを日本語テキストへ変換する。

        Params:
        - audio_path: 認識対象の WAV ファイルパス。呼び出し中は存在している必要がある。

        Returns:
        - 認識済みテキスト。認識結果が空の場合は空文字列。

        Errors:
        - RuntimeError: faster-whisper の読み込み、モデルロード、認識処理に失敗した。
        """
        if self.model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as err:
                raise RuntimeError("faster-whisper を読み込めません") from err
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )

        segments, _info = self.model.transcribe(
            audio_path,
            language="ja",
            condition_on_previous_text=False,
            beam_size=1,
            vad_filter=False,
        )
        text_parts = []
        for segment in segments:
            segment_text = segment.text.strip()
            if segment_text != "":
                text_parts.append(segment_text)
        return "".join(text_parts).strip()


class VoiceInput:
    """push-to-talk 音声入力の状態と認識結果 queue を管理する。

    Params:
    - recorder: `start()` と `stop_to_wav_file()` を持つ録音オブジェクト。`None` なら sounddevice 実装を使う。
    - transcriber: `transcribe(audio_path)` を持つ認識オブジェクト。`None` なら faster-whisper 実装を使う。
    - status_text_limit: UI に出す認識結果とエラー文の最大文字数。
    - max_transcription_seconds: 認識 worker を待つ最大秒数。timeout 後は状態を解放し、古い結果を捨てる。
    - clock: timeout 判定用の単調時刻関数。

    Caller:
    - pygame の main thread から `start_recording()` / `stop_recording_and_transcribe()` / `poll_event()` を呼ぶ。
    - worker thread はゲーム状態を直接触らない。認識結果は `poll_event()` で main thread が処理する。
    """

    def __init__(
        self,
        recorder=None,
        transcriber=None,
        status_text_limit=VOICE_STATUS_TEXT_LIMIT,
        max_transcription_seconds=DEFAULT_MAX_TRANSCRIPTION_SECONDS,
        clock=time.monotonic,
    ):
        """音声入力状態、認識 worker、結果 queue を初期化する。

        Params:
        - recorder: 録音実装。`None` の場合は `SoundDeviceRecorder` を作る。
        - transcriber: 文字起こし実装。`None` の場合は `FasterWhisperTranscriber` を作る。
        - status_text_limit: UI に表示する認識結果/エラー文の最大文字数。
        - max_transcription_seconds: 認識 timeout 秒数。`None` は timeout しない。
        - clock: timeout 判定に使う単調時刻関数。

        Caller:
        - pygame state はここでは持たない。ゲーム本体との通信は event queue 経由に限定する。
        """
        self.recorder = recorder if recorder is not None else SoundDeviceRecorder()
        self.transcriber = transcriber if transcriber is not None else FasterWhisperTranscriber()
        self.status_text_limit = status_text_limit
        self.max_transcription_seconds = max_transcription_seconds
        self._clock = clock
        self.state = VOICE_STATE_IDLE
        self.last_recognized_text = None
        self.last_error_message = None
        self._event_queue = queue.Queue()
        self._lock = threading.Lock()
        self._worker_thread = None
        self._active_transcription_id = 0
        self._transcription_started_at = None

    def start_recording(self):
        """録音を開始する。

        Returns:
        - 開始できた場合は `True`。録音中または認識中なら `False`。

        Caller:
        - `False` の場合は既存状態を維持するため、追加の stop は呼ばない。
        """
        self._expire_transcription_if_needed()
        with self._lock:
            if self.state != VOICE_STATE_IDLE:
                return False
            self.last_recognized_text = None
            self.last_error_message = None

        try:
            self.recorder.start()
        except Exception as err:
            self._publish_error(str(err))
            return False

        with self._lock:
            self.state = VOICE_STATE_RECORDING
        return True

    def stop_recording_and_transcribe(self):
        """録音を止め、認識 worker を開始する。

        Returns:
        - worker を開始できた場合は `True`。録音中でない場合や録音データがない場合は `False`。

        Caller:
        - `True` の後は `poll_event()` で結果を受け取る。
        """
        with self._lock:
            if self.state != VOICE_STATE_RECORDING:
                return False

        try:
            audio_path = self.recorder.stop_to_wav_file()
        except Exception as err:
            self._publish_error(str(err))
            return False

        if audio_path is None:
            self._publish_error("録音データがありません")
            return False

        with self._lock:
            self.state = VOICE_STATE_TRANSCRIBING
            self._active_transcription_id += 1
            transcription_id = self._active_transcription_id
            self._transcription_started_at = self._clock()

        worker_thread = threading.Thread(
            target=self._transcribe_worker,
            args=(audio_path, transcription_id),
            daemon=True,
        )
        self._worker_thread = worker_thread
        worker_thread.start()
        return True

    def poll_event(self):
        """認識 worker からの結果イベントを 1 件取り出す。

        Returns:
        - `VoiceInputEvent`。未処理イベントがない場合は `None`。

        Caller:
        - pygame main thread で毎フレーム呼ぶ。戻り値が `recognized_text` の時だけ `eval_text()` へ渡す。
        """
        self._expire_transcription_if_needed()
        try:
            return self._event_queue.get_nowait()
        except queue.Empty:
            return None

    def wait_for_pending_transcription(self, timeout_seconds=None):
        """テストや終了処理用に認識 worker の終了を待つ。

        Params:
        - timeout_seconds: 最大待機秒数。`None` の場合は無制限に待つ。

        Returns:
        - worker が存在しない、または終了した場合は `True`。timeout でまだ動作中なら `False`。

        Caller:
        - 通常のゲームループでは呼ばない。テストと shutdown 用の同期境界。
        """
        worker_thread = self._worker_thread
        if worker_thread is None:
            return True
        worker_thread.join(timeout=timeout_seconds)
        return not worker_thread.is_alive()

    def shutdown(self, timeout_seconds=1.0):
        """音声入力で保持している録音 stream と worker 待機境界を閉じる。

        Params:
        - timeout_seconds: 認識 worker の終了を待つ最大秒数。`None` は無制限待機。

        Returns:
        - worker が存在しない、または待機時間内に終了した場合は `True`。
        - timeout 後も認識 worker が動いている場合は `False`。

        Caller:
        - ゲーム終了時に main thread から呼ぶ。
        - 認識処理自体は外部ライブラリ内でキャンセルできないため、長時間待たない。
        """
        should_stop_recording = False
        with self._lock:
            if self.state == VOICE_STATE_RECORDING:
                should_stop_recording = True

        if should_stop_recording:
            try:
                audio_path = self.recorder.stop_to_wav_file()
                self._remove_audio_file(audio_path)
            except Exception as err:
                print(f"音声入力終了エラー: {err}")
            with self._lock:
                if self.state == VOICE_STATE_RECORDING:
                    self.state = VOICE_STATE_IDLE

        return self.wait_for_pending_transcription(timeout_seconds=timeout_seconds)

    def get_status_text(self):
        """現在の音声入力 UI 文言を返す。

        Returns:
        - `録音しています`、`音声を認識しています`、認識結果、エラー、または待機文言。
        """
        self._expire_transcription_if_needed()
        with self._lock:
            state = self.state
            last_recognized_text = self.last_recognized_text
            last_error_message = self.last_error_message

        if state == VOICE_STATE_RECORDING:
            return "録音しています"
        if state == VOICE_STATE_TRANSCRIBING:
            return "音声を認識しています"
        if last_error_message is not None:
            return "音声入力エラー: " + self._clip_status_value(last_error_message)
        if last_recognized_text is not None:
            return "認識: " + self._clip_status_value(last_recognized_text)
        return "Vキーで音声入力"

    def _transcribe_worker(self, audio_path, transcription_id):
        """WAV を文字起こしし、現在有効な認識だけ queue へ発行する。

        Params:
        - audio_path: worker が所有する一時 WAV ファイルパス。finally で削除する。
        - transcription_id: 開始時点の認識 ID。timeout や次回認識で古くなった結果を捨てる。

        Caller:
        - worker thread の entry point。pygame state は直接変更しない。
        """
        try:
            recognized_text = self.transcriber.transcribe(audio_path)
            recognized_text = normalize_ascii_width(recognized_text.strip())
            if recognized_text == "":
                if self._is_active_transcription(transcription_id):
                    self._publish_error("音声を認識できませんでした")
                return

            with self._lock:
                if transcription_id != self._active_transcription_id:
                    return
                self.state = VOICE_STATE_IDLE
                self.last_recognized_text = recognized_text
                self.last_error_message = None
                self._transcription_started_at = None
            print(f"音声認識結果: {recognized_text}")
            self._event_queue.put(VoiceInputEvent(kind=VOICE_EVENT_RECOGNIZED_TEXT, text=recognized_text))
        except Exception as err:
            if self._is_active_transcription(transcription_id):
                self._publish_error(str(err))
        finally:
            self._remove_audio_file(audio_path)

    def _is_active_transcription(self, transcription_id):
        """指定 ID が現在有効な認識 worker か返す。

        Params:
        - transcription_id: worker 開始時に割り当てた ID。

        Returns:
        - `True`: 現在の active ID と一致する。
        - `False`: timeout または次回認識で古くなった。
        """
        with self._lock:
            return transcription_id == self._active_transcription_id

    def _expire_transcription_if_needed(self):
        """認識 worker が timeout を超えていれば状態を解放する。

        Caller:
        - main thread 側の状態取得前に呼ぶ。古い worker の結果は ID 不一致で捨てる。
        """
        if self.max_transcription_seconds is None:
            return

        should_publish_timeout = False
        with self._lock:
            if self.state != VOICE_STATE_TRANSCRIBING or self._transcription_started_at is None:
                return
            elapsed_seconds = self._clock() - self._transcription_started_at
            if elapsed_seconds <= self.max_transcription_seconds:
                return

            self._active_transcription_id += 1
            self.state = VOICE_STATE_IDLE
            self.last_error_message = "音声認識がタイムアウトしました"
            self.last_recognized_text = None
            self._transcription_started_at = None
            should_publish_timeout = True

        if should_publish_timeout:
            print("音声入力エラー: 音声認識がタイムアウトしました")
            self._event_queue.put(
                VoiceInputEvent(kind=VOICE_EVENT_ERROR, message="音声認識がタイムアウトしました")
            )

    def _publish_error(self, message):
        """音声入力エラーを状態、UI 用文言、event queue に反映する。

        Params:
        - message: 詳細エラー。空文字列の場合は汎用メッセージへ置き換える。

        Caller:
        - main thread / worker thread の両方から呼ばれるため、共有状態は lock 内で更新する。
        """
        error_message = message if message != "" else "音声入力に失敗しました"
        with self._lock:
            self.state = VOICE_STATE_IDLE
            self.last_error_message = error_message
            self.last_recognized_text = None
            self._transcription_started_at = None
        print(f"音声入力エラー: {error_message}")
        self._event_queue.put(VoiceInputEvent(kind=VOICE_EVENT_ERROR, message=error_message))

    def _clip_status_value(self, value):
        """UI 表示用に長い音声入力文言を切り詰める。

        Params:
        - value: 認識結果またはエラー文字列。

        Returns:
        - `status_text_limit` 以下の文字列。

        Caller:
        - 内部状態は変更しない。描画前の文字列整形だけを行う。
        """
        if len(value) <= self.status_text_limit:
            return value
        if self.status_text_limit <= 3:
            return value[:self.status_text_limit]
        return value[: self.status_text_limit - 3] + "..."

    def _remove_audio_file(self, audio_path):
        """一時 WAV ファイルを存在する場合だけ削除する。

        Params:
        - audio_path: 削除対象ファイルパス。`None` は何もしない。

        Caller:
        - 削除失敗は録音/認識結果より優先しないため、標準出力へ出して握りつぶす。
        """
        if audio_path is None:
            return
        try:
            if os.path.exists(audio_path):
                os.unlink(audio_path)
        except OSError as err:
            print(f"音声一時ファイル削除エラー: {err}")

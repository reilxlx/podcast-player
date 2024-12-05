
import time
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
import assemblyai as aai
import logging
from translation import translate_text

class SubtitleUpdateThread(QThread):
    update_signal = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.paused = False
        self._force_update = False

    def force_update(self):
        """强制触发一次更新"""
        self._force_update = True

    def run(self):
        while self.running:
            if not self.paused or self._force_update:
                current_time = self.parent().media_player.position()
                self.update_signal.emit(current_time)
                self._force_update = False
            time.sleep(0.1)

    def stop(self):
        self.running = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

class TranscriptionThread(QThread):
    transcription_done = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, audio_file, api_key):
        super().__init__()
        self.audio_file = audio_file
        self.api_key = api_key

    def run(self):
        try:
            aai.settings.api_key = self.api_key
            transcriber = aai.Transcriber()
            config = aai.TranscriptionConfig(speaker_labels=True)
            transcript = transcriber.transcribe(self.audio_file, config=config)
            self.transcription_done.emit(transcript)
        except Exception as e:
            self.error_occurred.emit(str(e))

class TranslationThread(QThread):
    translation_done = pyqtSignal(int, str, str)                                       
    error_occurred = pyqtSignal(str)


    _last_request_time = 0
    _request_lock = QMutex()
    _min_interval = 0.1              

    def __init__(self, text, index, translator_type='google', api_key=None):
        super().__init__()
        self.text = text
        self.index = index
        self.translator_type = translator_type
        self.api_key = api_key
        self._is_running = True

    def run(self):
        try:
            if not self._is_running:
                return


            if self.translator_type == 'silicon_cloud':

                TranslationThread._request_lock.lock()
                try:

                    current_time = time.time()
                    elapsed = current_time - TranslationThread._last_request_time
                    if elapsed < TranslationThread._min_interval:
                        time.sleep(TranslationThread._min_interval - elapsed)


                    TranslationThread._last_request_time = time.time()
                finally:

                    TranslationThread._request_lock.unlock()


            translation = translate_text(
                self.text,
                translator_type=self.translator_type,
                api_key=self.api_key
            )

            if translation and self._is_running:
                self.translation_done.emit(self.index, translation, self.translator_type)
            else:
                self.error_occurred.emit(f"翻译失败 [ID:{self.index}]")

        except Exception as e:
            if self._is_running:
                self.error_occurred.emit(f"翻译错误 [ID:{self.index}]: {str(e)}")

    def stop(self):
        self._is_running = False

class ASRThread(QThread):
    """语音识别线程"""
    progress_signal = pyqtSignal(float)                
    finished = pyqtSignal(list)                 
    error_signal = pyqtSignal(str)          

    def __init__(self, audio_file):
        super().__init__()
        self.audio_file = audio_file
        self._is_running = True

    def run(self):
        try:


            total_chunks = 100
            subtitles = []

            for i in range(total_chunks):
                if not self._is_running:
                    break


                time.sleep(0.1)
                progress = (i + 1) / total_chunks
                self.progress_signal.emit(progress)


                subtitle = {
                    'start_time': i * 1000,
                    'end_time': (i + 1) * 1000,
                    'text': f'示例字幕 {i+1}',
                    'words': [
                        {
                            'text': f'词{j}',
                            'start': i * 1000 + j * 100,
                            'end': i * 1000 + (j + 1) * 100
                        } for j in range(5)
                    ]
                }
                subtitles.append(subtitle)

            self.finished.emit(subtitles)

        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        """停止线程"""
        self._is_running = False

class DisplayThread(QThread):
    """处理字幕显示的线程"""
    progress_signal = pyqtSignal(float)          

    def __init__(self, subtitles):
        super().__init__()
        self.subtitles = subtitles
        self._is_running = True

    def run(self):
        """执行字幕显示处理"""
        try:
            total = len(self.subtitles)
            for i in range(total):
                if not self._is_running:
                    break


                progress = (i + 1) / total
                self.progress_signal.emit(progress)


                self.msleep(10)               

        except Exception as e:
            print(f"字幕显示处理时出错: {e}")

    def stop(self):
        """停止线程"""
        self._is_running = False

import sys
import bisect
import os
import json
import hashlib
import time
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QFileDialog, QMessageBox, QVBoxLayout, QHBoxLayout,
    QLabel, QTextBrowser, QPushButton, QSlider, QStyle, QButtonGroup, QLineEdit
)
from PyQt5.QtCore import (
    QUrl, QTimer, Qt, pyqtSignal, QSemaphore, QEvent, QPoint, QCoreApplication
)
from PyQt5.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QFont, QPainter, QPainterPath
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

from ui_components import (
    ModernMacTextBrowser, ModernMacButton, ModernMacSlider,
    ModernMacToggleButton, ScrollingLabel, ModernProgressBar, ModernMacLineEdit
)
from threads import (
    SubtitleUpdateThread, TranscriptionThread, TranslationThread
)
from translation import translate_text
from utils import get_file_hash, format_time
from config import load_config, save_config

class PodcastPlayer(QWidget):
    def __init__(self):
        super().__init__()

        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


        self.show_translation = True          


        self._is_programmatic_change = False


        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)           


        self.setWindowTitle('播客播放器')
        self.setFixedSize(900, 700)            
        self.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                font-family: ".AppleSystemUIFont";
            }
            QLabel {
                color: #1D1D1F;
                font-size: 14px;
            }
        """)


        self.media_player = QMediaPlayer()
        self.media_player.error.connect(self.handle_media_error)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)


        self.subtitles = []
        self.subtitle_times = []
        self.subtitle_positions = []
        self.current_subtitle_index = -1
        self.total_duration = 0
        self.word_positions = []
        self.current_word_index = -1
        self.api_key = ""
        self.gemini_api_key = ""
        self.silicon_cloud_api_key = ""
        self._last_selected_radio = None


        self.data_dir = Path("podcast_data")
        self.data_dir.mkdir(exist_ok=True)
        self.subtitle_cache_dir = self.data_dir / "subtitles"
        self.subtitle_cache_dir.mkdir(exist_ok=True)
        self.audio_index_file = self.data_dir / "audio_index.json"


        self.load_audio_index()


        self.translations = {}          
        self.translation_thread = None


        self.update_thread = None
        self.last_update_time = 0
        self.update_interval = 100              
        self.last_subtitle_index = -1
        self.last_word_index = -1


        self.config_file = self.data_dir / "config.json"


        self.load_saved_config()


        self.init_ui()


        self.setup_saved_api_key()


        self.initialize_update_thread()

        self.translation_threads = []           
        self.current_translation_count = 0
        self.total_translation_count = 0


        self.subtitle_display.mousePressEvent = self.on_subtitle_clicked

        self.subtitle_blocks = []              
        self.pending_translations = {}              

        self.current_display_index = 0             
        self.display_timer = QTimer()
        self.display_timer.timeout.connect(self.display_next_subtitle)
        self.display_interval = 100               


        self.translation_semaphore = QSemaphore(5)                


        self.silicon_cloud_api_key = ""


        self.is_seeking = False

        self.translation_progress = {}            
        self.translation_semaphore = QSemaphore(3)           

    def load_audio_index(self):
        """加载音文件"""
        if self.audio_index_file.exists():
            with open(self.audio_index_file, 'r', encoding='utf-8') as f:
                self.audio_index = json.load(f)
        else:
            self.audio_index = {}
            self.save_audio_index()

    def save_audio_index(self):
        """保存音频索引文件"""
        with open(self.audio_index_file, 'w', encoding='utf-8') as f:
            json.dump(self.audio_index, f, ensure_ascii=False, indent=2)

    def get_file_hash(self, file_path):
        """计算文件的MD5哈希值"""
        return get_file_hash(file_path)

    def load_config(self):
        """加载配置文件"""
        config = load_config(self.config_file)
        if config:
            self.gemini_api_key = config.get('gemini_api_key', '')
            self.silicon_cloud_api_key = config.get('silicon_cloud_api_key', '')
            self.api_key = config.get('asr_api_key', '')

            from translation.translationGemini import api_key as gemini_api
            from translation.translationSiliconCloud import api_key as silicon_api
            gemini_api = self.gemini_api_key
            silicon_api = self.silicon_cloud_api_key

    def save_config(self):
        """保存配置文件"""
        try:

            config = {
                'gemini_api_key': self.gemini_api_key or '',
                'silicon_cloud_api_key': self.silicon_cloud_api_key or '',
                'asr_api_key': self.api_key or ''
            }


            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    current_config = json.load(f)
                    if (current_config.get('gemini_api_key') == config['gemini_api_key'] and
                        current_config.get('silicon_cloud_api_key') == config['silicon_cloud_api_key'] and
                        current_config.get('asr_api_key') == config['asr_api_key']):
                        return


            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            logging.info(f"配置已保存 - gemini_key: {self.gemini_api_key}, silicon_key: {self.silicon_cloud_api_key}, asr_key: {self.api_key}")

        except Exception as e:
            logging.error(f"保存配置文件时出错: {e}")

    def init_ui(self):
        """初始化UI"""

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)


        top_controls = QHBoxLayout()
        top_controls.setSpacing(16)


        self.select_audio_btn = ModernMacButton('选择音频', accent=True)
        self.select_audio_btn.clicked.connect(self.load_audio)


        self.audio_file_label = ScrollingLabel('未选择音频文件')
        self.audio_file_label.setFixedHeight(32)
        self.audio_file_label.setStyleSheet("""
            QLabel {
                background-color: #F5F5F7;
                border-radius: 6px;
                color: #666666;
                padding: 0 12px;
                font-family: ".AppleSystemUIFont";
            }
        """)

        top_controls.addWidget(self.select_audio_btn)
        top_controls.addWidget(self.audio_file_label, 1)


        playback_controls = QHBoxLayout()
        playback_controls.setSpacing(16)

        self.play_button = ModernMacButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.play_pause)
        self.play_button.setEnabled(False)
        self.play_button.setFixedWidth(32)


        self.translation_toggle = ModernMacToggleButton("显示中文")
        self.translation_toggle.setChecked(True)
        self.translation_toggle.clicked.connect(self.toggle_translation)

        self.position_slider = ModernMacSlider(Qt.Horizontal)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.position_slider.sliderPressed.connect(self.slider_pressed)
        self.position_slider.sliderReleased.connect(self.slider_released)

        self.time_label = QLabel('00:00 / 00:00')
        self.time_label.setStyleSheet("color: #666666;")

        playback_controls.addWidget(self.play_button)
        playback_controls.addWidget(self.position_slider)
        playback_controls.addWidget(self.time_label)
        playback_controls.addWidget(self.translation_toggle)


        translation_controls = QHBoxLayout()
        translation_controls.setSpacing(16)

        self.google_radio = ModernMacButton('Google翻译', checkable=True)
        self.gemini_radio = ModernMacButton('Gemini翻译', checkable=True)
        self.silicon_cloud_radio = ModernMacButton('SiliconCloud翻译', checkable=True)
        self.google_radio.setChecked(True)              

        button_group = QButtonGroup(self)
        button_group.addButton(self.google_radio)
        button_group.addButton(self.gemini_radio)
        button_group.addButton(self.silicon_cloud_radio)
        button_group.buttonClicked.connect(self.on_translation_option_changed)


        self.api_key_widget = QWidget()
        api_key_layout = QHBoxLayout(self.api_key_widget)
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        api_key_layout.setSpacing(8)

        api_key_label = QLabel('API Key:')
        api_key_label.setStyleSheet("""
            QLabel {
                color: #1D1D1F;
                font-size: 14px;
                font-family: ".AppleSystemUIFont";
            }
        """)


        self.api_key_input = ModernMacLineEdit()
        self.api_key_input.setPlaceholderText("Google翻译无需API Key")
        self.api_key_input.setEnabled(False)                        
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.textChanged.connect(self.on_api_key_changed)
        self.api_key_input.installEventFilter(self)

        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.api_key_input, 1)              

        translation_controls.addWidget(self.google_radio)
        translation_controls.addWidget(self.gemini_radio)
        translation_controls.addWidget(self.silicon_cloud_radio)
        translation_controls.addWidget(self.api_key_widget)
        translation_controls.addStretch()


        self.progress_bar = ModernProgressBar()
        self.progress_bar.setVisible(False)           


        content_area = QVBoxLayout()          
        content_area.setSpacing(8)          


        subtitle_history_layout = QHBoxLayout()
        subtitle_history_layout.setSpacing(20)


        subtitle_container = QVBoxLayout()
        subtitle_container.setSpacing(8)

        subtitle_label = QLabel('字幕')
        subtitle_label.setStyleSheet('font-weight: 600;')

        self.subtitle_display = ModernMacTextBrowser()

        subtitle_container.addWidget(subtitle_label)
        subtitle_container.addWidget(self.subtitle_display)


        history_container = QVBoxLayout()
        history_container.setSpacing(8)

        history_label = QLabel('历史文件')
        history_label.setStyleSheet('font-weight: 600;')

        self.file_list = ModernMacTextBrowser()
        self.file_list.setMaximumWidth(240)
        self.file_list.anchorClicked.connect(self.load_cached_audio)

        history_container.addWidget(history_label)
        history_container.addWidget(self.file_list)


        subtitle_history_layout.addLayout(subtitle_container, 7)
        subtitle_history_layout.addLayout(history_container, 3)


        content_area.addLayout(subtitle_history_layout)
        content_area.addWidget(self.progress_bar)


        main_layout.addLayout(top_controls)
        main_layout.addLayout(playback_controls)
        main_layout.addLayout(translation_controls)
        main_layout.addLayout(content_area)


        self.setLayout(main_layout)


        self.was_playing = False
        self.is_seeking = False


        self.update_thread = SubtitleUpdateThread(self)
        self.update_thread.update_signal.connect(self.update_subtitle_efficient)


        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)


        self.display_cached_files()

    def display_cached_files(self):
        """显示已缓存的音频文件列表"""
        self.file_list.clear()
        html_content = []
        for file_hash, info in self.audio_index.items():
            file_name = Path(info['file_path']).name
            html_content.append(f'<p><a href="{file_hash}">{file_name}</a></p>')
        self.file_list.setHtml('\n'.join(html_content))

    def load_cached_audio(self, url):
        """加载已缓存的音频文件"""
        try:

            was_playing = self.media_player.state() == QMediaPlayer.PlayingState


            if was_playing:
                self.media_player.pause()
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))


            current_gemini_key = self.gemini_api_key
            current_silicon_key = self.silicon_cloud_api_key


            if self.update_thread and self.update_thread.isRunning():
                self.update_thread.stop()
                self.update_thread.wait()


            self.clear_all_highlights()


            self.current_subtitle_index = -1
            self.current_word_index = -1
            self.last_subtitle_index = -1
            self.last_word_index = -1

            file_hash = url.toString()
            if file_hash in self.audio_index:
                audio_info = self.audio_index[file_hash]
                relative_path = audio_info['file_path']
                self.audio_file = os.path.abspath(relative_path)
                self.current_file_hash = file_hash
                subtitle_file = Path(audio_info['subtitle_file'])

                if subtitle_file.exists():

                    self.load_cached_subtitles(subtitle_file)


                    self.gemini_api_key = current_gemini_key
                    self.silicon_cloud_api_key = current_silicon_key


                    self.setup_audio_playback()


                    self.audio_file_label.setText(os.path.basename(self.audio_file))
                    self.audio_file_label.scroll_pos = 0
                    self.audio_file_label.update()


                    self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
                    self.play_button.setEnabled(True)


                    self.update_thread = SubtitleUpdateThread(self)
                    self.update_thread.update_signal.connect(self.update_subtitle_efficient)


                    self.display_cached_files()


                    cursor = self.subtitle_display.textCursor()
                    cursor.movePosition(QTextCursor.Start)
                    self.subtitle_display.setTextCursor(cursor)


                    QCoreApplication.processEvents()


                    self.subtitle_display.verticalScrollBar().setValue(0)


                    if was_playing:

                        self.media_player.setPosition(0)
                        self.media_player.play()
                        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))


                        if not self.update_thread.isRunning():
                            self.update_thread.start()
                else:
                    QMessageBox.warning(self, "错误", "字幕文件不存在")
        except Exception as e:
            logging.error(f"加载缓存音频时出错: {e}")
            QMessageBox.warning(self, "错误", f"加载文件出错: {e}")

    def load_audio(self):
        """选择并加载音频文件"""
        audio_file, _ = QFileDialog.getOpenFileName(self, "选择音频文件", "", "音频文件 (*.wav *.mp3)")
        if audio_file:

            self.translation_toggle.setEnabled(False)

            self._translation_type_set = False


            self.translations = {}
            self.subtitles = []
            self.subtitle_times = []
            self.word_positions = []
            self.current_subtitle_index = -1
            self.current_word_index = -1


            self.audio_file = os.path.abspath(audio_file)

            self.audio_file_label.setText(os.path.basename(audio_file))

            file_hash = self.get_file_hash(audio_file)


            if file_hash in self.audio_index:
                subtitle_file = self.subtitle_cache_dir / f"{file_hash}.json"
                if subtitle_file.exists():
                    self.load_cached_subtitles(subtitle_file)
                    self.setup_audio_playback()

                    self.translation_toggle.setEnabled(True)
                    return


            url = QUrl.fromLocalFile(audio_file)
            content = QMediaContent(url)
            self.media_player.setMedia(content)
            self.play_button.setEnabled(False)

            self.subtitle_display.clear()
            self.subtitle_display.setHtml('<p style="font-size:16px; color:gray;">正在转录音频，请稍候...</p>')

            self.current_file_hash = file_hash
            self.thread = TranscriptionThread(self.audio_file, self.api_key)
            self.thread.transcription_done.connect(self.on_transcription_done)
            self.thread.error_occurred.connect(self.on_transcription_error)
            self.thread.start()

    def setup_audio_playback(self):
        """设置音频播放"""
        try:

            abs_path = os.path.abspath(self.audio_file)
            url = QUrl.fromLocalFile(abs_path)
            content = QMediaContent(url)
            self.media_player.setMedia(content)
            self.play_button.setEnabled(True)


            self.last_subtitle_index = -1
            self.last_word_index = -1
            self.last_update_time = 0


            if self.update_thread is None:
                self.update_thread = SubtitleUpdateThread(self)
                self.update_thread.update_signal.connect(self.update_subtitle_efficient)
            else:
                if not self.update_thread.isRunning():
                    self.update_thread.start()
        except Exception as e:
            print(f"设置音频播放时出错: {e}")

    def load_cached_subtitles(self, subtitle_file):
        """加载缓存的字幕数据，包括翻译结果"""
        try:

            current_gemini_key = self.gemini_api_key
            current_silicon_key = self.silicon_cloud_api_key

            with open(subtitle_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)


            self.subtitles = cached_data['subtitles']
            self.translations = cached_data.get('translations', {})
            self.subtitle_times = [sub['start_time'] for sub in self.subtitles]
            self.word_start_times = []
            self.subtitle_blocks = []
            self.word_positions = []
            self.current_subtitle_index = -1
            self.current_word_index = -1
            self.last_subtitle_index = -1
            self.last_word_index = -1


            for subtitle in self.subtitles:
                for word in subtitle['words']:
                    self.word_start_times.append(word['start'])


            if self.translations:
                first_translation = next(iter(self.translations.values()))
                translator_type = first_translation.get('translator', 'google')


                config = load_config(self.config_file)
                if config:
                    if translator_type == 'gemini':
                        self.gemini_api_key = config.get('gemini_api_key', '')
                    elif translator_type == 'silicon_cloud':
                        self.silicon_cloud_api_key = config.get('silicon_cloud_api_key', '')


                self._is_programmatic_change = True
                self.update_translator_button_state(translator_type)


                if translator_type == 'gemini':
                    self.api_key_input.setText(self.gemini_api_key)
                elif translator_type == 'silicon_cloud':
                    self.api_key_input.setText(self.silicon_cloud_api_key)
                self._is_programmatic_change = False


            self.display_subtitles()


            cursor = self.subtitle_display.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.subtitle_display.setTextCursor(cursor)


            QCoreApplication.processEvents()


            self.subtitle_display.verticalScrollBar().setValue(0)

        except Exception as e:
            logging.error(f"加载缓存字幕时出错: {e}")
            raise e

    def on_transcription_done(self, transcript):
        """处理转录完成"""
        try:

            self.parse_transcript(transcript)


            self.save_subtitle_cache()


            self.audio_index[self.current_file_hash] = {
                'file_path': self.audio_file,
                'subtitle_file': str(self.subtitle_cache_dir / f"{self.current_file_hash}.json")
            }
            self.save_audio_index()
            self.display_cached_files()


            self.play_button.setEnabled(True)


            self.initialize_subtitle_positions()


            self.initialize_update_thread()


            current_position = self.media_player.position()
            self.update_subtitle_efficient(current_position)
            if self.update_thread:
                self.update_thread.force_update()


            self.translation_toggle.setEnabled(True)

        except Exception as e:
            logging.error(f"处理转录完成时错: {e}")
            self.subtitle_display.setHtml(
                '<p style="color:red;">处理转录结果时出错，请重试。</p>'
            )
            self.translation_toggle.setEnabled(True)

    def initialize_subtitle_positions(self):
        """初始化字幕位置信息"""
        try:
            self.subtitle_positions = []
            self.word_positions = []
            self.word_start_times = []

            cursor = self.subtitle_display.textCursor()
            cursor.movePosition(QTextCursor.Start)

            for idx, subtitle in enumerate(self.subtitles):
                block_start = cursor.position()
                self.subtitle_positions.append(block_start)


                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, 3)


                for word in subtitle['words']:
                    word_start = cursor.position()
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor,
                                     len(word['text']))
                    self.word_positions.append({
                        'start_pos': word_start,
                        'end_pos': cursor.position(),
                        'start_time': word['start'],
                        'end_time': word['end'],
                        'subtitle_index': idx
                    })
                    self.word_start_times.append(word['start'])


                    cursor.movePosition(QTextCursor.Right)


                cursor.movePosition(QTextCursor.NextBlock)
                if self.show_translation and idx < len(self.subtitles) - 1:
                    cursor.movePosition(QTextCursor.NextBlock)         


            self.last_subtitle_index = -1
            self.last_word_index = -1

            logging.debug(f"字幕位置初始化完成 - 字幕数: {len(self.subtitle_positions)}, 单词数: {len(self.word_positions)}")

        except Exception as e:
            logging.error(f"初始化字幕位置信息时出错: {e}")

    def start_translation(self):
        """开始译处理"""
        try:

            texts_to_translate = []
            for idx, subtitle in enumerate(self.subtitles):
                text = subtitle.get('text', '').strip()
                if text:           
                    texts_to_translate.append((idx, text))

            if not texts_to_translate:
                logging.warning("没有找到可翻译的字幕")
                QMessageBox.warning(self, "警告", "没有找到可翻译的字幕文本")
                return


            self.total_translation_count = len(texts_to_translate)
            self.current_translation_count = 0
            self.translation_progress.clear()


            if self.silicon_cloud_radio.isChecked():
                translator_type = 'silicon_cloud'
                api_key = self.silicon_cloud_api_key
                if not api_key:
                    QMessageBox.warning(self, "警告", "请先设置SiliconCloud API Key")
                    return
            elif self.gemini_radio.isChecked():
                translator_type = 'gemini'
                api_key = self.gemini_api_key
                if not api_key:
                    QMessageBox.warning(self, "警告", "请先设置Gemini API Key")
                    return
            else:
                translator_type = 'google'
                api_key = None

            logging.info(f"开始批量翻译任务 - 使用{translator_type}翻译器，共{self.total_translation_count}条")


            self.progress_bar.setVisible(True)
            self.progress_bar.set_progress(0, self.total_translation_count, "准备翻译...")


            self.translation_threads = []
            for idx, text in texts_to_translate:
                thread = TranslationThread(
                    text=text,
                    index=idx,
                    translator_type=translator_type,
                    api_key=api_key
                )
                thread.translation_done.connect(self.on_translation_done)
                thread.error_occurred.connect(self.on_translation_error)
                self.translation_threads.append(thread)
                thread.start()
                logging.info(f"启动翻译线程 [ID:{idx}] - 文本: {text[:50]}...")

        except Exception as e:
            logging.error(f"启动翻译任务失败: {e}")
            QMessageBox.critical(self, "错误", f"启动翻译任务失败: {e}")

    def on_translation_done(self, index, translation, translator_type):
        """处理单个翻译完成"""
        try:
            if not hasattr(self, 'total_translation_count') or self.total_translation_count <= 0:
                logging.error("翻译总数未正确初始化")
                return


            self.translations[str(index)] = {
                'text': translation,
                'translator': translator_type
            }


            logging.debug(f"翻译结果 [ID:{index}]: {translation[:50]}...")


            self.current_translation_count += 1
            progress = int((self.current_translation_count / self.total_translation_count) * 100)


            self.progress_bar.set_progress(
                self.current_translation_count,
                self.total_translation_count,
                f"翻译进度: {progress}%"
            )

            logging.info(f"翻译进度: {self.current_translation_count}/{self.total_translation_count}")


            if self.current_translation_count >= self.total_translation_count:
                logging.info("所有翻译任务完成")
                self.progress_bar.setVisible(False)
                self.save_translation_cache()             
                self.save_subtitle_cache()                     
                self.display_subtitles()               

        except Exception as e:
            logging.error(f"处理翻译结果时出错 [ID:{index}]: {str(e)}")

    def initialize_update_thread(self):
        """初始化更新线程"""
        if self.update_thread is None:
            self.update_thread = SubtitleUpdateThread(self)
            self.update_thread.update_signal.connect(self.update_subtitle_efficient)
            self.update_thread.start()

    def on_transcription_error(self, error_message):
        self.subtitle_display.clear()
        self.subtitle_display.setHtml(f'<p style="font-size:16px; color:red;">获取转录结果时出错：{error_message}</p>')
        QMessageBox.critical(self, "错误", f"获取转录结果时出错{error_message}")
        self.play_button.setEnabled(False)

    def parse_transcript(self, transcript):
        """解析转录结果"""
        try:
            self.subtitles = []
            self.subtitle_times = []
            self.word_positions = []
            self.current_subtitle_index = -1
            self.word_start_times = []
            self.current_display_index = 0          

            for utterance in transcript.utterances:
                words = []
                for word in utterance.words:
                    words.append({
                        'text': word.text,
                        'start': word.start,
                        'end': word.end
                    })


                self.subtitles.append({
                    'speaker': utterance.speaker,
                    'start_time': utterance.start,
                    'end_time': utterance.end,
                    'text': utterance.text,
                    'words': words
                })
                self.subtitle_times.append(utterance.start)

                for word in words:
                    self.word_start_times.append(word['start'])


            self.start_progressive_display()


            if self.subtitles:
                self.start_translation()
            else:
                logging.warning("转录结果为空，无法开始翻译")

        except Exception as e:
            logging.error(f"解析转录结果时出错: {e}")
            raise

    def start_progressive_display(self):
        """开始逐条显示字幕"""
        self.subtitle_display.clear()
        self.current_display_index = 0
        self.subtitle_positions = []
        self.word_positions = []
        self.subtitle_blocks = []
        self.progress_bar.show()
        self.progress_bar.set_progress(0, len(self.subtitles), "正显示字幕...")
        self.display_timer.start(self.display_interval)

    def display_next_subtitle(self):
        """显示下一条字幕，确保按顺序显示并保持对应关系"""
        try:
            if self.current_display_index >= len(self.subtitles):
                self.display_timer.stop()
                return

            cursor = self.subtitle_display.textCursor()
            current_scroll = self.subtitle_display.verticalScrollBar().value()


            cursor.movePosition(QTextCursor.End)
            block_start = cursor.position()


            subtitle = self.subtitles[self.current_display_index]
            str_index = str(self.current_display_index)


            subtitle_block = {
                'index': self.current_display_index,
                'start': block_start,
                'content_start': 0,
                'translation_start': 0,
                'translation_end': 0,
                'end': 0,
                'speaker': subtitle['speaker']
            }


            color = '#2196F3' if subtitle['speaker'] == 'A' else '#4CAF50'
            speaker_fmt = QTextCharFormat()
            speaker_fmt.setForeground(QColor(color))


            cursor.insertText(f"{subtitle['speaker']}: ", speaker_fmt)


            subtitle_block['content_start'] = cursor.position()
            content_fmt = QTextCharFormat()
            content_fmt.setForeground(QColor(color))


            word_positions = []
            for word in subtitle['words']:
                word_start_pos = cursor.position()
                cursor.insertText(word['text'] + ' ', content_fmt)
                word_end_pos = cursor.position()
                word_positions.append({
                    'start_pos': word_start_pos,
                    'end_pos': word_end_pos,
                    'start_time': word['start'],
                    'end_time': word['end']
                })

            cursor.insertBlock()


            subtitle_block['translation_start'] = cursor.position()
            translation_text = ""
            if str_index in self.translations:
                translation_text = self.translations[str_index]['text']

            trans_fmt = QTextCharFormat()
            trans_fmt.setForeground(QColor('#000000'))
            cursor.insertText(translation_text, trans_fmt)
            subtitle_block['translation_end'] = cursor.position()


            if self.current_display_index < len(self.subtitles) - 1:
                cursor.insertBlock()


            subtitle_block['end'] = cursor.position()


            self.subtitle_blocks.append(subtitle_block)


            self.word_positions.extend(word_positions)


            total_subtitles = len(self.subtitles)
            progress = ((self.current_display_index + 1) / total_subtitles) * 100
            self.progress_bar.set_progress(
                self.current_display_index + 1,
                total_subtitles,
                f"正在显示字幕... ({self.current_display_index + 1}/{total_subtitles}, {progress:.1f}%)"
            )


            self.current_display_index += 1


            self.subtitle_display.verticalScrollBar().setValue(current_scroll)

        except Exception as e:
            print(f"显示下一条字幕时出错: {e}")

    def save_subtitle_cache(self):
        """保存字幕和翻译缓存，确保按顺序保存"""
        try:

            sorted_translations = {}
            for idx in range(len(self.subtitles)):
                str_idx = str(idx)
                if str_idx in self.translations:
                    sorted_translations[str_idx] = self.translations[str_idx]

            cache_data = {
                'subtitles': self.subtitles,
                'translations': sorted_translations,
                'file_path': self.audio_file
            }

            subtitle_file = self.subtitle_cache_dir / f"{self.current_file_hash}.json"
            with open(subtitle_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"保存字幕缓存时出错: {e}")

    def display_subtitles(self):
        """显示双语字幕"""
        try:
            self.subtitle_display.clear()
            self.subtitle_blocks = []
            self.word_positions = []            
            cursor = self.subtitle_display.textCursor()


            if not self.subtitles:
                self.translation_toggle.setEnabled(False)
                self.subtitle_display.setHtml('<p style="font-size:16px; color:gray;">暂无字幕信息</p>')
                return


            self.translation_toggle.setEnabled(True)

            for idx, subtitle in enumerate(self.subtitles):

                block_start = cursor.position()


                subtitle_block = {
                    'index': idx,
                    'start': block_start,
                    'content_start': 0,
                    'translation_start': 0,
                    'translation_end': 0,
                    'end': 0,
                    'speaker': subtitle['speaker']
                }


                color = '#2196F3' if subtitle['speaker'] == 'A' else '#4CAF50'
                speaker_fmt = QTextCharFormat()
                speaker_fmt.setForeground(QColor(color))
                cursor.insertText(f"{subtitle['speaker']}: ", speaker_fmt)


                subtitle_block['content_start'] = cursor.position()


                content_fmt = QTextCharFormat()
                content_fmt.setForeground(QColor(color))


                for i, word in enumerate(subtitle['words']):

                    if i > 0:
                        cursor.insertText(' ', content_fmt)


                    word_start_pos = cursor.position()
                    cursor.insertText(word['text'], content_fmt)
                    word_end_pos = cursor.position()


                    self.word_positions.append({
                        'start_pos': word_start_pos,
                        'end_pos': word_end_pos,
                        'start_time': word['start'],
                        'end_time': word['end'],
                        'subtitle_index': idx,
                        'text': word['text']
                    })


                cursor.insertBlock()


                subtitle_block['translation_start'] = cursor.position()


                if self.show_translation:
                    trans_fmt = QTextCharFormat()
                    trans_fmt.setForeground(QColor('#000000'))

                    translation_text = ""
                    if str(idx) in self.translations:
                        translation_text = self.translations[str(idx)]['text']
                    elif str(idx) in self.pending_translations:
                        translation_text = self.pending_translations[str(idx)]

                    if translation_text:
                        cursor.insertText(translation_text, trans_fmt)
                        cursor.insertBlock()            


                subtitle_block['translation_end'] = cursor.position()
                subtitle_block['end'] = cursor.position()


                self.subtitle_blocks.append(subtitle_block)
                self.subtitle_positions.append(block_start)


                if idx < len(self.subtitles) - 1:
                    cursor.insertBlock()


            cursor.movePosition(QTextCursor.Start)
            self.subtitle_display.setTextCursor(cursor)


            self.subtitle_display.verticalScrollBar().setValue(0)


            self.word_start_times = [word['start_time'] for word in self.word_positions]

            logging.debug(f"字幕显示完成 - 字幕数: {len(self.subtitle_blocks)}, 单词数: {len(self.word_positions)}")

        except Exception as e:
            logging.error(f"显示字幕时出错: {e}")

    def update_translator_button_state(self, translator_type):
        """更新翻译器按钮状态"""
        try:

            current_gemini_key = self.gemini_api_key
            current_silicon_key = self.silicon_cloud_api_key


            self.google_radio.blockSignals(True)
            self.gemini_radio.blockSignals(True)
            self.silicon_cloud_radio.blockSignals(True)


            if translator_type == 'google':
                self.google_radio.setChecked(True)
                self.api_key_input.setEnabled(False)
                self.api_key_input.setPlaceholderText("Google翻译无需API Key")
            elif translator_type == 'gemini':
                self.gemini_radio.setChecked(True)
                self.api_key_input.setEnabled(True)
                self.api_key_input.setText(self.gemini_api_key)
                self.api_key_input.setPlaceholderText("输入Gemini API Key")
            elif translator_type == 'silicon_cloud':
                self.silicon_cloud_radio.setChecked(True)
                self.api_key_input.setEnabled(True)
                self.api_key_input.setText(self.silicon_cloud_api_key)
                self.api_key_input.setPlaceholderText("输入SiliconCloud API Key")


            self.google_radio.blockSignals(False)
            self.gemini_radio.blockSignals(False)
            self.silicon_cloud_radio.blockSignals(False)


            self.gemini_api_key = current_gemini_key
            self.silicon_cloud_api_key = current_silicon_key


            if self.google_radio.isChecked():
                self._last_selected_radio = self.google_radio
            elif self.gemini_radio.isChecked():
                self._last_selected_radio = self.gemini_radio
            elif self.silicon_cloud_radio.isChecked():
                self._last_selected_radio = self.silicon_cloud_radio

            logging.info(f"更新翻译按钮状态: {translator_type}")

        except Exception as e:
            logging.error(f"更新翻译器按钮状态时出错: {e}")

    def set_api_key_for_translator(self, translator_type):
        """设置对应翻译器的API Key"""
        try:
            if translator_type == 'silicon_cloud':
                self.api_key_input.setText(self.silicon_cloud_api_key)
            elif translator_type == 'gemini':
                self.api_key_input.setText(self.gemini_api_key)
            else:          
                self.api_key_input.clear()
        except Exception as e:
            logging.error(f"设置API Key时出错: {e}")

    def update_translation(self, index, translation):
        """新单个翻结果"""
        try:

            block = next((b for b in self.subtitle_blocks if b['index'] == index), None)
            if not block:
                self.pending_translations[str(index)] = translation
                return


            current_scroll = self.subtitle_display.verticalScrollBar().value()

            cursor = self.subtitle_display.textCursor()


            if block['translation_start'] >= 0 and block['translation_end'] >= block['translation_start']:

                old_length = block['translation_end'] - block['translation_start']


                cursor.setPosition(block['translation_start'])
                cursor.setPosition(block['translation_end'], QTextCursor.KeepAnchor)


                fmt = QTextCharFormat()
                fmt.setForeground(QColor('#000000'))
                cursor.mergeCharFormat(fmt)
                cursor.insertText(translation)


                new_length = len(translation)
                length_diff = new_length - old_length


                block['translation_end'] = block['translation_start'] + new_length
                block['end'] = block['translation_end']


                for later_block in self.subtitle_blocks:
                    if later_block['index'] > index:
                        later_block['start'] += length_diff
                        later_block['content_start'] += length_diff
                        later_block['translation_start'] += length_diff
                        later_block['translation_end'] += length_diff
                        later_block['end'] += length_diff


                for i in range(index + 1, len(self.subtitle_positions)):
                    self.subtitle_positions[i] += length_diff


                for word_pos in self.word_positions:
                    if word_pos['start_pos'] > block['translation_start']:
                        word_pos['start_pos'] += length_diff
                        word_pos['end_pos'] += length_diff


            self.subtitle_display.verticalScrollBar().setValue(current_scroll)

        except Exception as e:
            print(f"更新翻译时出错: {e}")
            self.pending_translations[str(index)] = translation

    def play_pause(self):
        """处理播放/暂停按钮点击事件"""
        try:
            if not self.media_player.media().isNull():
                if self.media_player.state() == QMediaPlayer.PlayingState:
                    self.media_player.pause()
                    self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
                    if self.update_thread:
                        self.update_thread.pause()
                else:
                    self.media_player.play()
                    self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))


                    if self.update_thread is None:
                        self.initialize_update_thread()
                    else:
                        self.update_thread.resume()
                        if not self.update_thread.isRunning():
                            self.update_thread.start()


                    current_position = self.media_player.position()
                    self.update_subtitle_efficient(current_position)
                    if self.update_thread:
                        self.update_thread.force_update()
        except Exception as e:
            print(f"播放控制出错: {e}")

    def position_changed(self, position):
        """处理播放位置变化"""
        try:
            self.position_slider.setValue(position)
            self.update_time_label(position)


            if (self.media_player.state() == QMediaPlayer.PlayingState and
                self.update_thread and not self.update_thread.isRunning()):
                self.update_thread.resume()
                self.update_thread.start()

        except Exception as e:
            print(f"处理位置变化时出错: {e}")

    def duration_changed(self, duration):
        self.position_slider.setRange(0, duration)
        self.total_duration = duration
        self.update_time_label(self.media_player.position())

    def set_position(self, position):
        """处理进度条拖动事件"""
        try:
            self.media_player.setPosition(position)


            self.clear_all_highlights()
            self.last_subtitle_index = -1
            self.last_word_index = -1


            self.update_subtitle_efficient(position)


            self.scroll_to_current_subtitle(position)


            if self.update_thread:
                self.update_thread.force_update()

        except Exception as e:
            print(f"设置位置时出错: {e}")

    def scroll_to_current_subtitle(self, position):
        """改进的滚动到当前字幕位置方法"""
        try:

            subtitle_idx = bisect.bisect_right(self.subtitle_times, position) - 1
            if 0 <= subtitle_idx < len(self.subtitle_blocks):
                block = self.subtitle_blocks[subtitle_idx]


                cursor = self.subtitle_display.textCursor()
                cursor.setPosition(block['start'])


                block_rect = self.subtitle_display.document().documentLayout().blockBoundingRect(cursor.block())


                block_center = block_rect.center().y()


                viewport_height = self.subtitle_display.viewport().height()
                viewport_center = viewport_height / 2


                target_scroll = block_center - viewport_center


                self.subtitle_display.smooth_scroll_to_position(int(target_scroll))

        except Exception as e:
            print(f"滚动到当前字幕位置时出错: {e}")

    def update_time_label(self, position):
        current_time_str = format_time(position)
        total_time_str = format_time(self.total_duration)
        self.time_label.setText(f'{current_time_str} / {total_time_str}')

    def update_subtitle_efficient(self, current_time):
        """改进的字幕更新方法"""
        try:

            if not self.subtitle_positions or not self.word_positions:
                return


            is_seeking = abs(current_time - self.last_update_time) > 1000
            if not is_seeking and current_time - self.last_update_time < self.update_interval:
                return

            self.last_update_time = current_time


            subtitle_idx = bisect.bisect_right(self.subtitle_times, current_time) - 1


            if subtitle_idx >= len(self.subtitle_blocks):
                subtitle_idx = len(self.subtitle_blocks) - 1


            if subtitle_idx != self.last_subtitle_index:

                if 0 <= self.last_subtitle_index < len(self.subtitle_blocks):
                    self.highlight_subtitle(self.last_subtitle_index, False)


                if 0 <= subtitle_idx < len(self.subtitle_blocks):
                    self.highlight_subtitle(subtitle_idx, True)

                    self.scroll_to_current_subtitle(current_time)

                self.last_subtitle_index = subtitle_idx


            word_idx = bisect.bisect_right(self.word_start_times, current_time) - 1


            if word_idx >= len(self.word_positions):
                word_idx = len(self.word_positions) - 1


            if word_idx != self.last_word_index:

                if 0 <= self.last_word_index < len(self.word_positions):
                    self.highlight_word(self.last_word_index, False)


                if 0 <= word_idx < len(self.word_positions):
                    self.highlight_word(word_idx, True)

                self.last_word_index = word_idx

        except Exception as e:
            print(f"更新字幕时出错: {e}")

    def clear_all_highlights(self):
        """清除所有高亮"""
        try:

            cursor = QTextCursor(self.subtitle_display.document())
            cursor.select(QTextCursor.Document)
            fmt = QTextCharFormat()
            fmt.setBackground(Qt.transparent)
            cursor.mergeCharFormat(fmt)
        except Exception as e:
            print(f"清除高亮时出错: {e}")

    def highlight_subtitle(self, idx, highlight):
        """优化的字幕高亮方法"""
        try:
            if not (0 <= idx < len(self.subtitle_blocks)):
                return

            block = self.subtitle_blocks[idx]
            cursor = QTextCursor(self.subtitle_display.document())


            start_pos = block['start']
            end_pos = block['end']


            doc_length = self.subtitle_display.document().characterCount()
            start_pos = max(0, min(start_pos, doc_length - 1))
            end_pos = max(start_pos, min(end_pos, doc_length - 1))

            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.KeepAnchor)

            fmt = QTextCharFormat()
            if highlight:
                fmt.setBackground(QColor('#FFFF99'))
            else:
                fmt.setBackground(Qt.transparent)

            cursor.mergeCharFormat(fmt)

            if highlight:

                cursor.setPosition(start_pos)
                self.subtitle_display.setTextCursor(cursor)
                self.subtitle_display.ensureCursorVisible()

        except Exception as e:
            print(f"高亮字幕时出错: {e}")

    def highlight_word(self, idx, highlight):
        """优化的单词高亮方法"""
        try:
            if 0 <= idx < len(self.word_positions):
                word_info = self.word_positions[idx]
                cursor = QTextCursor(self.subtitle_display.document())


                doc_length = self.subtitle_display.document().characterCount()
                start_pos = max(0, min(word_info['start_pos'], doc_length - 1))
                end_pos = max(start_pos, min(word_info['end_pos'], doc_length - 1))


                subtitle_idx = word_info['subtitle_index']


                cursor.setPosition(start_pos)
                cursor.setPosition(end_pos, QTextCursor.KeepAnchor)

                fmt = QTextCharFormat()
                if highlight:

                    fmt.setBackground(QColor('#FFCC66'))
                else:

                    if self.last_subtitle_index == subtitle_idx:

                        fmt.setBackground(QColor('#FFFF99'))
                    else:

                        fmt.setBackground(Qt.transparent)

                cursor.mergeCharFormat(fmt)


                if highlight and logging.getLogger().isEnabledFor(logging.DEBUG):
                    debug_info = {
                        'index': idx,
                        'text': word_info.get('text', '<no text>'),
                        'position': f"{start_pos}-{end_pos}",
                        'subtitle_index': subtitle_idx
                    }
                    logging.debug(
                        f"高亮单词 - 索引: {debug_info['index']}, "
                        f"文本: {debug_info['text']}, "
                        f"位置: {debug_info['position']}, "
                        f"字幕索引: {debug_info['subtitle_index']}"
                    )

        except Exception as e:

            logging.error(f"单词高亮更新错误: {str(e)}, word_info: {word_info if 'word_info' in locals() else 'N/A'}")

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        try:

            if hasattr(self, 'media_player'):
                self.media_player.stop()


            if hasattr(self, 'update_thread') and self.update_thread:
                self.update_thread.stop()
                self.update_thread.wait()


            if hasattr(self, 'translation_thread') and self.translation_thread:
                self.translation_thread.stop()
                self.translation_thread.wait()


            if hasattr(self, 'audio_file_label'):
                self.audio_file_label.scroll_timer.stop()

            event.accept()
        except Exception as e:
            print(f"关闭程序时出错: {e}")
            event.accept()

    def toggle_api_key_visibility(self):
        """切换API Key的显示/隐藏状态"""
        if self.api_key_input.echoMode() == QLineEdit.Password:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
            self.toggle_visibility_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogNoButton))
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)
            self.toggle_visibility_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogYesButton))

    def on_translation_option_changed(self, button):
        """理翻译选项改变"""
        try:
            self._is_programmatic_change = True               

            if button == self.google_radio:
                self.api_key_input.setEnabled(False)
                self.api_key_input.setPlaceholderText("Google翻译无需API Key")
                self.api_key_input.clear()
            elif button == self.gemini_radio or button == self.silicon_cloud_radio:

                config = load_config(self.config_file)

                self.api_key_input.setEnabled(True)
                if button == self.gemini_radio:
                    self.api_key_input.setPlaceholderText("输入Gemini API Key")

                    api_key = config.get('gemini_api_key', '') if config else ''
                    self.gemini_api_key = api_key
                    self.api_key_input.setText(api_key)
                else:                       
                    self.api_key_input.setPlaceholderText("输入SiliconCloud API Key")

                    api_key = config.get('silicon_cloud_api_key', '') if config else ''
                    self.silicon_cloud_api_key = api_key
                    self.api_key_input.setText(api_key)

            self._is_programmatic_change = False               

        except Exception as e:
            logging.error(f"切换翻译选项时出错: {e}")

    def on_api_key_changed(self, text):
        """处理API Key变化"""
        if self._is_programmatic_change:                   
            return


        if self.api_key_input.hasFocus():
            text = text.strip()
            if self.gemini_radio.isChecked():
                self.gemini_api_key = text
            elif self.silicon_cloud_radio.isChecked():
                self.silicon_cloud_api_key = text
            self.save_config()                   
            logging.info(f"API Key已更新 - gemini_key: {self.gemini_api_key}, silicon_key: {self.silicon_cloud_api_key}")

    def eventFilter(self, obj, event):
        """事件过滤器处理鼠标悬停事件"""
        if obj == self.api_key_input:
            if event.type() == QEvent.Enter:

                try:
                    self.hover_timer.timeout.disconnect()
                except TypeError:
                    pass               


                if self.gemini_radio.isChecked():
                    self.hover_timer.timeout.connect(lambda: self.show_api_key("gemini"))
                elif self.silicon_cloud_radio.isChecked():
                    self.hover_timer.timeout.connect(lambda: self.show_api_key("silicon_cloud"))
                self.hover_timer.start(1000)           

            elif event.type() == QEvent.Leave:
                self.hover_timer.stop()
                self.api_key_input.setEchoMode(QLineEdit.Password)

                try:
                    self.hover_timer.timeout.disconnect()
                except TypeError:
                    pass               

        return super().eventFilter(obj, event)

    def show_api_key(self, key_type):
        """显示API Key明文"""
        try:

            config = load_config(self.config_file)
            if config:
                if key_type == "gemini" and self.gemini_radio.isChecked():
                    api_key = config.get('gemini_api_key', '')
                    if api_key:
                        self.gemini_api_key = api_key
                        self.api_key_input.setText(api_key)
                elif key_type == "silicon_cloud" and self.silicon_cloud_radio.isChecked():
                    api_key = config.get('silicon_cloud_api_key', '')
                    if api_key:
                        self.silicon_cloud_api_key = api_key
                        self.api_key_input.setText(api_key)

            self.api_key_input.setEchoMode(QLineEdit.Normal)
            logging.debug(f"显示API Key - type: {key_type}, key: {self.api_key_input.text()}")
        except Exception as e:
            logging.error(f"显示API Key时出错: {e}")

    def start_filename_scroll(self, event):
        """开始自动滚动文件名"""
        if self.audio_file_label.text() != '未选择音频文件':

            content_width = self.audio_file_label.sizeHint().width()
            visible_width = self.filename_scroll_area.width()
            if content_width > visible_width:
                self.scroll_timer.start(50)              

    def stop_filename_scroll(self, event):
        """停止自动滚动文件名"""
        self.scroll_timer.stop()

        QTimer.singleShot(100, lambda: self.filename_scroll_area.horizontalScrollBar().setValue(0))

    def auto_scroll_filename(self):
        """执行文件名自动滚动"""
        scrollbar = self.filename_scroll_area.horizontalScrollBar()
        content_width = self.audio_file_label.sizeHint().width()
        visible_width = self.filename_scroll_area.width()
        max_scroll = content_width - visible_width

        if max_scroll <= 0:
            return


        self.scroll_position += self.scroll_direction * 2


        if self.scroll_position >= max_scroll:
            self.scroll_position = max_scroll
            self.scroll_direction = -1
        elif self.scroll_position <= 0:
            self.scroll_position = 0
            self.scroll_direction = 1

        scrollbar.setValue(self.scroll_position)

    def update_filename_display(self, filename):
        """更新文件名显示"""
        display_name = os.path.basename(filename)
        self.audio_file_label.setText(display_name)

        self.audio_file_label.adjustSize()

    def toggle_translation(self):
        """切换中文字幕显示状态"""
        try:
            self.show_translation = self.translation_toggle.isChecked()


            current_position = self.media_player.position()
            was_playing = self.media_player.state() == QMediaPlayer.PlayingState


            if self.update_thread:
                self.update_thread.pause()


            self.clear_all_highlights()


            self.last_subtitle_index = -1
            self.last_word_index = -1


            self.display_subtitles()


            self.initialize_subtitle_positions()


            self.update_subtitle_efficient(current_position)
            if self.update_thread:
                self.update_thread.force_update()


            if self.update_thread:
                if was_playing:
                    self.update_thread.resume()
                self.update_thread.force_update()


            self.scroll_to_current_subtitle(current_position)

            logging.info(f"切换翻译显示状态: {self.show_translation}")

        except Exception as e:
            logging.error(f"切换翻译显示时出错: {e}")

    def handle_media_error(self, error):
        """处理媒体播放错误"""
        error_messages = {
            QMediaPlayer.NoError: "无错误",
            QMediaPlayer.ResourceError: "媒体资源无法访问",
            QMediaPlayer.FormatError: "不支持的媒体格式",
            QMediaPlayer.NetworkError: "网络错误",
            QMediaPlayer.AccessDeniedError: "访问被拒绝",
            QMediaPlayer.ServiceMissingError: "未找到所需服务"
        }

        error_message = error_messages.get(error, "未知错误")
        QMessageBox.critical(self, "媒体播放错误", f"播放出错: {error_message}")


        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.setEnabled(False)

    def slider_pressed(self):
        """处理滑块按下事件"""
        self.is_seeking = True

        self.was_playing = self.media_player.state() == QMediaPlayer.PlayingState
        if self.was_playing:
            self.media_player.pause()

    def slider_released(self):
        """处理滑块释放事件"""
        self.is_seeking = False

        if self.was_playing:
            self.media_player.play()
            if self.update_thread:
                self.update_thread.resume()
                if not self.update_thread.isRunning():
                    self.update_thread.start()
                self.update_thread.force_update()

    def on_subtitle_clicked(self, event):
        """处理字幕点击事件"""
        try:

            cursor = self.subtitle_display.cursorForPosition(event.pos())
            click_pos = cursor.position()


            clicked_block = None
            for block in self.subtitle_blocks:
                if block['start'] <= click_pos <= block['end']:
                    clicked_block = block
                    break

            if clicked_block:

                subtitle_idx = clicked_block['index']
                if 0 <= subtitle_idx < len(self.subtitles):

                    start_time = self.subtitles[subtitle_idx]['start_time']
                    self.media_player.setPosition(int(start_time))


                    if self.media_player.state() != QMediaPlayer.PlayingState:
                        self.play_pause()


                    self.update_subtitle_efficient(start_time)
                    if self.update_thread:
                        self.update_thread.force_update()

        except Exception as e:
            print(f"处理字幕点击事件时出错: {e}")

    def save_translation_cache(self):
        """保存翻译缓存到本地"""
        try:

            self.subtitle_cache_dir.mkdir(exist_ok=True)


            cache_file = self.subtitle_cache_dir / f"{self.current_file_hash}.json"


            cache_data = {
                'subtitles': self.subtitles,
                'translations': self.translations,
                'file_path': os.path.relpath(self.audio_file)
            }


            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            logging.info(f"翻译缓存已保存到: {cache_file}")
        except Exception as e:
            logging.error(f"保存翻译缓存时出错: {e}")

    def load_saved_config(self):
        """加载保存的配置"""
        try:
            config = load_config(self.config_file)
            if config:

                self.gemini_api_key = config.get('gemini_api_key', '') or ''
                self.silicon_cloud_api_key = config.get('silicon_cloud_api_key', '') or ''
                self.api_key = config.get('asr_api_key', '') or ''

                logging.info(f"配置加载成功 - gemini_key: {self.gemini_api_key}, silicon_key: {self.silicon_cloud_api_key}, asr_key: {self.api_key}")

        except Exception as e:
            logging.error(f"加载配置文件时出错: {e}")
            self.gemini_api_key = ''
            self.silicon_cloud_api_key = ''
            self.api_key = ''

    def setup_saved_api_key(self):
        """设置保存的API Key和选择状态"""
        try:

            config = load_config(self.config_file)
            if config:
                self.gemini_api_key = config.get('gemini_api_key', '')
                self.silicon_cloud_api_key = config.get('silicon_cloud_api_key', '')
                self.api_key = config.get('asr_api_key', '')


            self._is_programmatic_change = True
            self.google_radio.setChecked(True)
            self.api_key_input.clear()
            self.api_key_input.setEnabled(False)
            self.api_key_input.setPlaceholderText("Google翻译无需API Key")
            self._is_programmatic_change = False

            logging.info("已加载API Keys并设置Google翻译为默认选项")

        except Exception as e:
            logging.error(f"设置API Key和选择状态时出错: {e}")

    def on_translation_error(self, index, error_message):
        """处理翻译错误"""
        try:

            if hasattr(self, 'total_translation_count'):
                self.current_translation_count += 1
                progress = int((self.current_translation_count / self.total_translation_count) * 100)
                self.progress_bar.set_progress(
                    self.current_translation_count,
                    self.total_translation_count,
                    f"翻译进度: {progress}% (有错误发生)"
                )


            logging.error(f"翻译错误 [ID:{index}]: {error_message}")


            if self.current_translation_count >= self.total_translation_count:
                self.progress_bar.setVisible(False)

                self.save_translation_cache()
                self.save_subtitle_cache()
                self.display_subtitles()


            QMessageBox.warning(
                self,
                "翻译错误",
                f"翻译第 {index + 1} 条字幕时出错：{error_message}"
            )

        except Exception as e:
            logging.error(f"处理翻译错误时发生异常: {e}")
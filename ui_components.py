
from PyQt5.QtWidgets import QTextBrowser, QPushButton, QSlider, QStyle, QLineEdit, QLabel
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QTextCursor, QTextCharFormat
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QRect, QSize, QRectF

class ModernMacTextBrowser(QTextBrowser):
    """macOS 风格文本浏览器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QTextBrowser {
                background-color: #FFFFFF;
                border: 1px solid #E5E5E5;
                border-radius: 8px;
                padding: 12px;
                selection-background-color: #007AFF40;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 8px;
                margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #9999A5;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #666666;
            }
            QScrollBar::add-line:vertical, 
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }
        """)


        font = self.font()
        font.setFamily(".AppleSystemUIFont")
        font.setPointSize(13)
        self.setFont(font)


        self.last_scroll_position = 0


        self.smooth_scroll_timer = QTimer(self)
        self.smooth_scroll_timer.timeout.connect(self.smooth_scroll_step)
        self.target_scroll_position = 0
        self.current_scroll_position = 0
        self.scroll_step_size = 10

    def save_scroll_position(self):
        """保存当前滚动位置"""
        self.last_scroll_position = self.verticalScrollBar().value()

    def restore_scroll_position(self):
        """恢复之前的滚动位置"""
        self.verticalScrollBar().setValue(self.last_scroll_position)

    def smooth_scroll_to_position(self, position):
        """平滑滚动到指定位置"""
        self.target_scroll_position = position
        self.current_scroll_position = self.verticalScrollBar().value()

        if not self.smooth_scroll_timer.isActive():
            self.smooth_scroll_timer.start(16)          

    def smooth_scroll_step(self):
        """执行平滑滚动的单个步骤"""
        if abs(self.current_scroll_position - self.target_scroll_position) < 1:
            self.smooth_scroll_timer.stop()
            self.verticalScrollBar().setValue(self.target_scroll_position)
            return


        self.current_scroll_position += (self.target_scroll_position - self.current_scroll_position) * 0.2
        self.verticalScrollBar().setValue(int(self.current_scroll_position))

    def get_visible_block_range(self):
        """获取当前可见的文本块范围"""
        viewport_height = self.viewport().height()
        first_visible = self.firstVisibleBlock()
        last_visible = self.cursorForPosition(QPoint(0, viewport_height)).block()

        return first_visible.blockNumber(), last_visible.blockNumber()

class ModernMacButton(QPushButton):
    """macOS 风格按钮"""
    def __init__(self, text="", parent=None, accent=False, checkable=False):
        super().__init__(text, parent)
        self.accent = accent
        self.setFixedHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(checkable)
        self.setStyleSheet(self._get_style())

    def _get_style(self):
        if self.accent:
            return """
                QPushButton {
                    background-color: #007AFF;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 0 16px;
                    font-family: "SF Pro Text";
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #0051D5;
                }
                QPushButton:pressed, QPushButton:checked {
                    background-color: #0040A8;
                }
                QPushButton:disabled {
                    background-color: #E5E5E5;
                    color: #999999;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #F5F5F7;
                    color: #1D1D1F;
                    border: none;
                    border-radius: 6px;
                    padding: 0 16px;
                    font-family: "SF Pro Text";
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #E5E5E7;
                }
                QPushButton:pressed, QPushButton:checked {
                    background-color: #D5D5D7;
                    color: #007AFF;
                }
                QPushButton:disabled {
                    color: #999999;
                }
            """

class ModernMacSlider(QSlider):
    """macOS 风格滑块"""
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setStyleSheet("""
            QSlider {
                min-height: 24px;  /* 增加高显示完整的滑块 */
            }
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: #E5E5E5;
                border-radius: 2px;
                margin: 0 0;  /* 移除上下边距 */
            }
            QSlider::handle:horizontal {
                background: #007AFF;
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #0051D5;
            }
        """)

    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        if event.button() == Qt.LeftButton:
            value = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(),
                event.x(), self.width()
            )
            self.setValue(value)
            self.sliderMoved.emit(value)
        super().mousePressEvent(event)

class ModernMacToggleButton(QPushButton):
    """macOS 风格开关按钮"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFixedHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F7;
                color: #1D1D1F;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-family: "SF Pro Text";
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #E5E5E7;
            }
            QPushButton:checked {
                background-color: #007AFF;
                color: white;
            }
            QPushButton:checked:hover {
                background-color: #0051D5;
            }
        """)

class ScrollingLabel(QLabel):
    """可滚动的标签，实现鼠标悬停触发循环滚动效果"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.scroll_pos = 0
        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.update_scroll)
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self.start_scrolling)
        self.hover_timer.setSingleShot(True)           
        self.is_scrolling = False
        self.scroll_speed = 2        
        self.gap_width = 50               
        self.setMinimumWidth(200)          
        self.setFixedHeight(32)          
        self.setStyleSheet("""
            QLabel {
                color: #666666;
                padding: 0 12px;
                font-family: ".AppleSystemUIFont";
                background-color: #F5F5F7;
                border-radius: 6px;
            }
        """)

    def setText(self, text):
        """重写setText方法"""
        super().setText(text)
        self.scroll_pos = 0
        self.is_scrolling = False
        self.update()

    def needs_scroll(self):
        """检查是否需要滚动"""
        return self.fontMetrics().horizontalAdvance(self.text()) > self.width() - 24

    def start_scrolling(self):
        """开始滚动"""
        if self.needs_scroll():
            self.is_scrolling = True
            self.scroll_timer.start(30)

    def stop_scrolling(self):
        """停止滚动"""
        self.is_scrolling = False
        self.scroll_timer.stop()
        self.scroll_pos = 0
        self.update()

    def update_scroll(self):
        """更新滚动位置"""
        if not self.text() or not self.is_scrolling:
            return

        text_width = self.fontMetrics().horizontalAdvance(self.text())


        self.scroll_pos += self.scroll_speed


        if self.scroll_pos >= text_width + self.gap_width:
            self.scroll_pos = 0

        self.update()

    def paintEvent(self, event):
        """自定义绘制事件"""
        if not self.text():
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)


            rect = QRectF(self.rect())
            path = QPainterPath()
            path.addRoundedRect(rect, 6.0, 6.0)
            painter.setClipPath(path)


            painter.setFont(self.font())
            painter.setPen(QColor("#666666"))


            text_rect = rect.adjusted(12, 0, -12, 0)
            text_width = self.fontMetrics().horizontalAdvance(self.text())
            label_width = self.width() - 24

            if self.is_scrolling and self.needs_scroll():

                first_text_pos = text_rect.left() - self.scroll_pos
                painter.drawText(
                    text_rect.adjusted(-self.scroll_pos, 0, text_width, 0),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    self.text()
                )


                if first_text_pos + text_width < text_rect.right():
                    second_text_pos = first_text_pos + text_width + self.gap_width
                    painter.drawText(
                        text_rect.adjusted(
                            second_text_pos - text_rect.left(),
                            0,
                            second_text_pos - text_rect.left() + text_width,
                            0
                        ),
                        Qt.AlignVCenter | Qt.AlignLeft,
                        self.text()
                    )
            else:

                painter.drawText(
                    text_rect,
                    Qt.AlignVCenter | Qt.AlignLeft,
                    self.text()
                )
        finally:
            painter.end()

    def enterEvent(self, event):
        """鼠标进入事件"""
        if self.needs_scroll():
            self.hover_timer.start(1000)           

    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.hover_timer.stop()
        self.stop_scrolling()

    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        if not self.needs_scroll():
            self.stop_scrolling()

class ModernProgressBar(QWidget):
    """macOS风格进度条"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.progress = 0
        self.total = 0
        self.message = ""

    def set_progress(self, current, total, message=""):
        self.progress = current
        self.total = total
        self.message = message
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)


        bg_rect = self.rect().adjusted(0, 8, 0, -8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#F5F5F7"))
        painter.drawRoundedRect(bg_rect, 8, 8)


        if self.total > 0:
            progress_width = int((self.progress / self.total) * bg_rect.width())
            progress_rect = QRect(bg_rect.x(), bg_rect.y(), progress_width, bg_rect.height())
            painter.setBrush(QColor("#007AFF"))
            painter.drawRoundedRect(progress_rect, 8, 8)


        if self.message:
            painter.setPen(QColor("#1D1D1F"))
            painter.setFont(QFont(".AppleSystemUIFont", 12))
            painter.drawText(self.rect(), Qt.AlignCenter, self.message)

class ModernMacLineEdit(QLineEdit):
    """macOS风格输入框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #F5F5F7;
                border: none;
                border-radius: 6px;
                padding: 0 12px;
                color: #1D1D1F;
                font-family: ".AppleSystemUIFont";
                font-size: 13px;
            }
            QLineEdit:focus {
                background-color: #FFFFFF;
                border: 2px solid #007AFF;
            }
            QLineEdit:disabled {
                background-color: #E5E5E5;
                color: #999999;
            }
            QLineEdit::placeholder {
                color: #999999;
            }
        """)

"""ATLAS Overlay — Opak tam yan panel, sohbet arayüzü ve otomasyon kontrolü."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from status_border import StatusColorController


# ─────────────────────────────────────────────────────────────────────────────
class _Bubble(QFrame):
    """Tek bir sohbet balonu."""
    def __init__(self, role: str, text: str, parent=None):
        super().__init__(parent)
        self.role = role
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        if role == "user":
            bg, fg = "#1a3a5c", "#a8d8ff"
            self._label.setFont(QFont("Consolas", 10))
        elif role == "jarvis":
            bg, fg = "#0d2010", "#00ffaa"
            self._label.setFont(QFont("Consolas", 10))
        else:  # log
            bg, fg = "#1a1a0a", "#ffd166"
            self._label.setFont(QFont("Consolas", 8))

        self._label.setStyleSheet(
            f"color:{fg}; background:transparent; padding:2px 4px;"
        )
        self.setStyleSheet(
            f"background:{bg}; border-radius:12px; margin:2px 4px;"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 5, 8, 5)
        if role == "user":
            row.addStretch()
        row.addWidget(self._label)
        if role != "user":
            row.addStretch()

    def append_text(self, extra: str):
        self._label.setText(self._label.text() + extra)


# ─────────────────────────────────────────────────────────────────────────────
class AtlasOverlay(QWidget):
    pause_requested  = Signal()
    resume_requested = Signal()
    stop_requested   = Signal()
    close_requested  = Signal()      # Kullanıcı ✕ ile ATLAS'ı kapattı
    message_sent     = Signal(str)   # Kullanıcı overlay'den mesaj gönderdi
    research_mode_changed = Signal(str)  # Özellik 3: Flash/Pro model seçimi

    def __init__(self, state_controller: StatusColorController | None = None):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        # Tam opak — TranslucentBackground KULLANILMIYOR
        self.setAutoFillBackground(True)

        # Özellik 7: JARVIS ile aynı durum controller'ını paylaş (yoksa kendi üretir).
        self._state_controller = state_controller or StatusColorController(self)
        self._state_controller.color_changed.connect(self._on_state_color)
        self._border_color = self._state_controller.color

        self._build_ui()

    def _on_state_color(self, color) -> None:
        """Durum çerçevesi rengi değişti → kenar çizimi yenile."""
        self._border_color = QColor(color)
        self.update()

    # ── UI inşası ─────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Başlık çubuğu ────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet("background:#0d1520; border-bottom:1px solid #00b4ff40;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 12, 0)

        title = QLabel("⚡  ATLAS")
        title.setStyleSheet("color:#00b4ff; font:bold 15px Consolas; background:transparent;")

        self._status_lbl = QLabel("HAZIR")
        self._status_lbl.setStyleSheet(
            "color:#00ffaa; font:bold 10px Consolas; background:transparent;"
        )

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setToolTip("ATLAS'ı kapat (JARVIS'e dön)")
        close_btn.setStyleSheet(
            "QPushButton{background:transparent; color:#8fa8c8;"
            "border:1px solid #00b4ff30; border-radius:15px;"
            "font:bold 13px Consolas;}"
            "QPushButton:hover{background:#ff557740; color:#ff5577;"
            "border:1px solid #ff5577;}"
        )
        close_btn.clicked.connect(self.close_requested)

        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self._status_lbl)
        hl.addSpacing(8)
        hl.addWidget(close_btn)
        root.addWidget(header)

        # ── Chat alanı (kaydırılabilir) ───────────────────────────────────
        self._chat_inner = QWidget()
        self._chat_inner.setStyleSheet("background:#0a0f1a;")
        self._chat_layout = QVBoxLayout(self._chat_inner)
        self._chat_layout.setContentsMargins(4, 6, 4, 6)
        self._chat_layout.setSpacing(3)
        self._chat_layout.addStretch()   # mesajlar aşağıdan yukarı büyüsün

        scroll = QScrollArea()
        scroll.setWidget(self._chat_inner)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea{background:#0a0f1a; border:none;}"
            "QScrollBar:vertical{background:#0a0f1a; width:6px;}"
            "QScrollBar::handle:vertical{background:#1a3050; border-radius:3px;}"
        )
        self._scroll = scroll
        root.addWidget(scroll, 1)

        # ── Giriş alanı ──────────────────────────────────────────────────
        input_bar = QWidget()
        input_bar.setStyleSheet(
            "background:#0d1520; border-top:1px solid #00b4ff30;"
        )
        input_bar.setFixedHeight(52)
        il = QHBoxLayout(input_bar)
        il.setContentsMargins(10, 8, 10, 8)
        il.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Jarvis'e yaz...")
        self._input.setStyleSheet(
            "QLineEdit{background:#0a0f1a; color:#c8d8f0; border:1px solid #1a3050;"
            "border-radius:16px; padding:4px 14px; font:11px Consolas;}"
            "QLineEdit:focus{border:1px solid #00b4ff60;}"
        )
        self._input.returnPressed.connect(self._send_message)

        send_btn = QPushButton("▶")
        send_btn.setFixedSize(34, 34)
        send_btn.setStyleSheet(
            "QPushButton{background:#00b4ff; color:#050810; border:none;"
            "border-radius:17px; font:bold 12px Consolas;}"
            "QPushButton:hover{background:#00d4ff;}"
        )
        send_btn.clicked.connect(self._send_message)

        il.addWidget(self._input)
        il.addWidget(send_btn)
        root.addWidget(input_bar)

        # ── Otomasyon kontrol butonları ───────────────────────────────────
        ctrl_bar = QWidget()
        ctrl_bar.setFixedHeight(52)
        ctrl_bar.setStyleSheet(
            "background:#0d1520; border-top:1px solid #00b4ff30;"
        )
        cl = QHBoxLayout(ctrl_bar)
        cl.setContentsMargins(10, 8, 10, 8)
        cl.setSpacing(8)
        cl.setAlignment(Qt.AlignCenter)

        BTN_STYLE = (
            "QPushButton{{background:#16213b; color:{fg}; border:1px solid {bd};"
            "border-radius:16px; font:bold 13px Consolas; min-width:42px;}}"
            "QPushButton:hover{{background:{bd}; color:#050810;}}"
        )
        # Özellik 3: araştırma modeli seçici (Flash varsayılan → Pro).
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("⚡ Flash", "flash")
        self._mode_combo.addItem("⭐ Pro", "pro")
        self._mode_combo.setFixedHeight(34)
        self._mode_combo.setFixedWidth(104)
        self._mode_combo.setToolTip("Araştırma modeli (Özellik 3/10)")
        self._mode_combo.setStyleSheet(
            "QComboBox{background:#16213b; color:#c8d8f0; border:1px solid #00b4ff40;"
            "border-radius:12px; padding:2px 8px; font:bold 11px Consolas;}"
            "QComboBox:hover{border:1px solid #00b4ff;}"
            "QComboBox QAbstractItemView{background:#0d1520; color:#c8d8f0;"
            "selection-background-color:#00b4ff40;}")
        self._mode_combo.currentIndexChanged.connect(
            lambda: self.research_mode_changed.emit(
                self._mode_combo.currentData() or "flash"))
        cl.addWidget(self._mode_combo)
        pause_btn  = QPushButton("⏸")
        resume_btn = QPushButton("▶")
        stop_btn   = QPushButton("■")

        pause_btn.setStyleSheet(BTN_STYLE.format(fg="#ffd166", bd="#ffd16660"))
        resume_btn.setStyleSheet(BTN_STYLE.format(fg="#00ffaa", bd="#00ffaa60"))
        stop_btn.setStyleSheet(BTN_STYLE.format(fg="#ff5577", bd="#ff557760"))

        pause_btn.setToolTip("Durdur")
        resume_btn.setToolTip("Devam Et")
        stop_btn.setToolTip("Bitir")

        pause_btn.clicked.connect(self.pause_requested)
        resume_btn.clicked.connect(self.resume_requested)
        stop_btn.clicked.connect(self.stop_requested)

        for b in (pause_btn, resume_btn, stop_btn):
            b.setFixedHeight(34)
            cl.addWidget(b)

        root.addWidget(ctrl_bar)

    # ── Mesaj ekleme API'si ──────────────────────────────────────────────
    def add_message(self, role: str, text: str):
        """Chat alanına balon ekle. role: 'user' | 'jarvis' | 'log'"""
        if not text:
            return
        bubble = _Bubble(role, text)
        # stretch'ten önce ekle
        count = self._chat_layout.count()
        self._chat_layout.insertWidget(count - 1, bubble)
        # Kaydır
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def add_log(self, text: str):
        self.add_message("log", text)

    def update_state(self, state: str, detail: str = ""):
        labels = {
            "RUNNING":                 ("ÇALIŞIYOR",         "#00ffaa"),
            "PAUSED_BY_USER":          ("DURAKLATILDI",      "#ffd166"),
            "PAUSED_BY_VERIFICATION":  ("DOĞRULAMA BEKL.",   "#ff9f43"),
            "STOPPED":                 ("DURDU",             "#ff5577"),
            # Özellik 3: arıza akışı durumları
            "WAITING":                 ("PROBLEM BEK.",      "#c8d8f0"),
            "RESEARCHING":             ("ARAŞTIRILIYOR",     "#3d8bfd"),
            "APPLYING":                ("UYGULANIYOR",       "#ffd166"),
            "TESTING":                 ("TEST EDİLİYOR",     "#3d8bfd"),
            "CONFIRMING":              ("ONAY BEKLİYOR",     "#ffd166"),
            "DONE":                    ("ÇÖZÜLDÜ",           "#00ffaa"),
            "EXHAUSTED":               ("TÜKENDİ",           "#ff5577"),
        }
        label, color = labels.get(state, (state, "#c8d8f0"))
        self._status_lbl.setText(label)
        self._status_lbl.setStyleSheet(
            f"color:{color}; font:bold 10px Consolas; background:transparent;"
        )
        if detail:
            self.add_log(detail)

    # ── Giriş gönder ────────────────────────────────────────────────────
    def _send_message(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.add_message("user", text)
        self.message_sent.emit(text)

    # ── Boyutlandırma & boyama ─────────────────────────────────────────
    def showEvent(self, event):
        handle = self.windowHandle()
        screen = self.screen() or (handle.screen() if handle else None)
        if screen:
            geo   = screen.availableGeometry()
            w     = int(geo.width() * 0.20)
            self.setGeometry(geo.right() - w + 1, geo.top(), w, geo.height())
        super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        # Özellik 7: tamamen oval köşeler + duruma göre yumuşak renkli çerçeve.
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 14, 14)
        painter.fillPath(path, QColor("#0a0f1a"))   # TAM OPAK — saydam değil
        painter.setPen(QPen(QColor(self._border_color), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        super().paintEvent(event)

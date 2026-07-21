"""
Interfaz gráfica (Front-End v1.0) para el widget de vocabulario japonés.

Requisitos:
    pip install PyQt6 requests

Ejecutar en Windows para efecto Acrylic/Mica nativo (ctypes + DWM).
En otros sistemas, cae automáticamente a un fondo translúcido estándar (QSS).
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from Motor_datos import VocabItem, VocabRepository, VocabSelector

# ---------------------------------------------------------------------------
# Configuración global
# ---------------------------------------------------------------------------
UPDATE_INTERVAL_MS = 3_600_000  # refresco automático cada 60 segundos
WINDOW_SIZE = (420, 380)


# ---------------------------------------------------------------------------
# Efecto Acrylic/Mica (Windows) vía DWM API
# ---------------------------------------------------------------------------
class AcrylicEffect:
    """
    Aplica un efecto de vidrio translúcido (Acrylic/Mica) a una ventana
    de Windows usando llamadas nativas a dwmapi.dll / user32.dll.

    En sistemas no-Windows, apply() no hace nada (fallback silencioso);
    el efecto visual se logra entonces solo con QSS (ver MainWindow.build_ui).
    """

    ACCENT_ENABLE_BLURBEHIND = 3
    ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
    WCA_ACCENT_POLICY = 19

    class ACCENTPOLICY(ctypes.Structure):
        _fields_ = [
            ("AccentState", ctypes.c_int),
            ("AccentFlags", ctypes.c_int),
            ("GradientColor", ctypes.c_int),
            ("AnimationId", ctypes.c_int),
        ]

    class WINCOMPATTRDATA(ctypes.Structure):
        _fields_ = [
            ("Attribute", ctypes.c_int),
            ("Data", ctypes.POINTER(ctypes.c_int)),
            ("SizeOfData", ctypes.c_size_t),
        ]

    @classmethod
    def apply(cls, hwnd: int, tint_rgba: tuple[int, int, int, int] = (18, 18, 22, 180)) -> bool:
        if not sys.platform.startswith("win"):
            return False

        try:
            user32 = ctypes.windll.user32
            r, g, b, a = tint_rgba
            gradient_color = (a << 24) | (b << 16) | (g << 8) | r

            accent = cls.ACCENTPOLICY()
            accent.AccentState = cls.ACCENT_ENABLE_ACRYLICBLURBEHIND
            accent.AccentFlags = 2
            accent.GradientColor = gradient_color
            accent.AnimationId = 0

            data = cls.WINCOMPATTRDATA()
            data.Attribute = cls.WCA_ACCENT_POLICY
            data.SizeOfData = ctypes.sizeof(accent)
            data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.POINTER(ctypes.c_int))

            user32.SetWindowCompositionAttribute(wintypes.HWND(hwnd), ctypes.pointer(data))
            return True
        except (AttributeError, OSError):
            # SetWindowCompositionAttribute no disponible en esta build de Windows.
            return False


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------
class MainWindow(QWidget):
    """
    Widget de escritorio frameless que muestra vocabulario japonés
    aleatorio, con fondo tipo vidrio translúcido.
    """

    def __init__(self) -> None:
        super().__init__()

        # --- Motor de datos ---
        self._repository = VocabRepository()
        self._selector: VocabSelector | None = None

        # --- Estado para arrastre de ventana (frameless) ---
        self._drag_position: QPoint | None = None

        self._configure_window()
        self._build_ui()
        self._load_data_and_start()

    # -- Configuración de ventana -----------------------------------------
    def _configure_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnBottomHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(*WINDOW_SIZE)

    # -- Construcción de la UI ----------------------------------------------
    def _build_ui(self) -> None:
        # Fondo base oscuro semi-opaco; el blur real lo aporta AcrylicEffect
        # en Windows. El radio de borde simula una tarjeta de "vidrio".
        self.setStyleSheet(
            """
            QWidget#root {
                background-color: rgba(15, 15, 20, 190);
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 25);
            }
            QLabel { color: #FFFFFF; background: transparent; }
            """
        )
        self.setObjectName("root")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        # Kanji / término principal — protagonista visual
        self.label_termino = QLabel("…")
        self.label_termino.setFont(QFont("Yu Gothic UI", 64, QFont.Weight.Bold))
        self.label_termino.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_termino.setStyleSheet("color: #FFFFFF;")

        # Pronunciación (kana)
        self.label_pronunciacion = QLabel("")
        self.label_pronunciacion.setFont(QFont("Yu Gothic UI", 18))
        self.label_pronunciacion.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_pronunciacion.setStyleSheet("color: rgba(255,255,255,180);")

        # Significados
        self.label_significados = QLabel("")
        self.label_significados.setFont(QFont("Segoe UI", 12))
        self.label_significados.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_significados.setWordWrap(True)
        self.label_significados.setStyleSheet("color: rgba(255,255,255,210);")

        # Ejemplo (JP + traducción)
        self.label_ejemplo_jp = QLabel("")
        self.label_ejemplo_jp.setFont(QFont("Yu Gothic UI", 13))
        self.label_ejemplo_jp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_ejemplo_jp.setWordWrap(True)
        self.label_ejemplo_jp.setStyleSheet("color: rgba(255,255,255,225);")

        self.label_ejemplo_es = QLabel("")
        self.label_ejemplo_es.setFont(QFont("Segoe UI", 11))
        self.label_ejemplo_es.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_ejemplo_es.setWordWrap(True)
        self.label_ejemplo_es.setStyleSheet("color: rgba(255,255,255,140); font-style: italic;")

        layout.addStretch(1)
        layout.addWidget(self.label_termino)
        layout.addWidget(self.label_pronunciacion)
        layout.addSpacing(10)
        layout.addWidget(self.label_significados)
        layout.addSpacing(14)
        layout.addWidget(self.label_ejemplo_jp)
        layout.addWidget(self.label_ejemplo_es)
        layout.addStretch(2)

    # -- Carga de datos y arranque del temporizador --------------------------
    def _load_data_and_start(self) -> None:
        try:
            self._repository.load()
        except RuntimeError as exc:
            self.label_termino.setText("⚠")
            self.label_pronunciacion.setText("Error de conexión")
            self.label_significados.setText(str(exc))
            return

        self._selector = VocabSelector(self._repository)
        self._refresh_content()  # muestra un elemento al iniciar

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_content)
        self._timer.start(UPDATE_INTERVAL_MS)

    def _refresh_content(self) -> None:
        if self._selector is None:
            return
        item: VocabItem = self._selector.pick()
        self.label_termino.setText(item.termino)
        self.label_pronunciacion.setText(item.pronunciacion)
        self.label_significados.setText(" · ".join(item.significados))
        self.label_ejemplo_jp.setText(item.ejemplo.get("oracion", ""))
        self.label_ejemplo_es.setText(item.ejemplo.get("traduccion", ""))

    # -- Aplicar efecto Acrylic tras mostrar la ventana -----------------------
    def showEvent(self, event) -> None:  # noqa: N802 (nombre requerido por Qt)
        super().showEvent(event)
        hwnd = int(self.winId())
        AcrylicEffect.apply(hwnd)

    # ------------------------------------------------------------------
    # Arrastre de ventana sin bordes:
    # Como la ventana es frameless, no existe una barra de título nativa
    # que el sistema operativo pueda usar para mover la ventana. Por eso
    # capturamos manualmente los eventos del mouse sobre el widget:
    #
    #   1) mousePressEvent   -> guarda el offset entre el click y la
    #                           esquina superior-izquierda de la ventana.
    #   2) mouseMoveEvent    -> mientras el botón izquierdo esté presionado,
    #                           reposiciona la ventana según el movimiento
    #                           del cursor menos ese offset.
    #   3) mouseReleaseEvent -> limpia el offset guardado.
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_position is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_position = None
        event.accept()

    # -- Salir con Escape (conveniencia, ya que no hay botón de cerrar) ----
    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
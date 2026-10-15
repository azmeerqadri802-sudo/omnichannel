import os
import math
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QLinearGradient, QRadialGradient,
    QFont, QPainterPath
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QFileDialog, QStackedWidget, QListWidget,
    QListWidgetItem, QComboBox, QDialog
)


class NeonToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=True, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self.setFixedSize(52, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, val: bool):
        self._checked = bool(val)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.toggled.emit(self._checked)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        grad = QLinearGradient(rect.topLeft(), rect.topRight())
        if self._checked:
            grad.setColorAt(0.0, QColor(0, 180, 215, 210))
            grad.setColorAt(1.0, QColor(0, 240, 175, 240))
            border_col = QColor(0, 255, 200, 230)
        else:
            grad.setColorAt(0.0, QColor(30, 35, 55, 210))
            grad.setColorAt(1.0, QColor(45, 52, 75, 210))
            border_col = QColor(110, 120, 150, 150)

        p.setPen(QPen(border_col, 1.4))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(rect, 11, 11)

        knob_x = self.width() - 22 if self._checked else 5
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(235, 255, 250) if self._checked else QColor(145, 155, 180))
        p.drawEllipse(QRectF(knob_x, 4.5, 17, 17))


class AIOrbVisualizerWidget(QWidget):
    mic_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(310)
        self.phase = 0.0
        self.energy = 0.28
        self.status_text = "AWAITING VOICE COMMAND..."
        self.ingestion_mode = False
        self.ingestion_pct = 73

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(35)

    def _tick(self):
        self.phase += 0.09
        self.update()

    def set_status(self, text: str):
        self.status_text = text
        self.update()

    def set_ingestion_overlay(self, active: bool, pct: int = 73):
        self.ingestion_mode = active
        self.ingestion_pct = pct
        self.status_text = "PROCESSING SHEET DATA..." if active else "AWAITING VOICE COMMAND..."
        self.update()

    def mousePressEvent(self, event):
        cx, cy = self.width() / 2, self.height() - 28
        if math.hypot(event.position().x() - cx, event.position().y() - cy) <= 28:
            self.mic_clicked.emit()
        elif math.hypot(event.position().x() - self.width() / 2, event.position().y() - (self.height() / 2 - 20)) <= 95:
            self.mic_clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0 - 22.0

        bg_glow = QRadialGradient(QPointF(cx, cy), 170)
        bg_glow.setColorAt(0.0, QColor(0, 220, 255, 55))
        bg_glow.setColorAt(0.5, QColor(165, 35, 255, 35))
        bg_glow.setColorAt(1.0, QColor(10, 15, 35, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg_glow)
        p.drawEllipse(QPointF(cx, cy), 170, 170)

        num_bars = 36
        bar_area_w = (w / 2.0) - 95
        if bar_area_w > 30:
            for side in (-1, 1):
                for i in range(num_bars):
                    ratio = i / float(num_bars)
                    x = cx + side * (92 + ratio * bar_area_w)
                    wave = math.sin(self.phase * 2.2 - i * 0.35) * math.cos(self.phase + i * 0.15)
                    amp = (1.0 - ratio * 0.75) * (12 + 34 * self.energy * abs(wave))
                    col = QColor(0, 240, 255, int(210 * (1.0 - ratio * 0.7)))
                    p.setPen(QPen(col, 2.0))
                    p.drawLine(QPointF(x, cy - amp), QPointF(x, cy + amp))

        for idx, radius in enumerate([102, 88, 74, 58]):
            pen_col = QColor(0, 242, 254, 190) if idx % 2 == 0 else QColor(195, 40, 255, 190)
            p.setPen(QPen(pen_col, 2.5 if idx < 2 else 3.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            start_angle = int((self.phase * (45 if idx % 2 == 0 else -38) + idx * 50) * 16) % (360 * 16)
            p.drawArc(QRectF(cx - radius, cy - radius, radius * 2, radius * 2), start_angle, int(230 * 16))

        core_grad = QRadialGradient(QPointF(cx - 12, cy - 12), 54)
        core_grad.setColorAt(0.0, QColor(25, 95, 165, 245))
        core_grad.setColorAt(0.65, QColor(18, 35, 85, 250))
        core_grad.setColorAt(1.0, QColor(0, 240, 255, 220))
        p.setPen(QPen(QColor(0, 245, 255, 230), 2.5))
        p.setBrush(core_grad)
        p.drawEllipse(QPointF(cx, cy), 48, 48)

        p.setPen(QColor(225, 252, 255))
        p.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 48, cy - 48, 96, 96), Qt.AlignmentFlag.AlignCenter, "AI")

        if self.ingestion_mode:
            bx, by = 52.0, 48.0
            p.setPen(QPen(QColor(30, 80, 90, 180), 4.0))
            p.setBrush(QColor(10, 25, 40, 200))
            p.drawEllipse(QPointF(bx, by), 32, 32)
            arc_rect = QRectF(bx - 32, by - 32, 64, 64)
            p.setPen(QPen(QColor(0, 255, 170), 4.5))
            p.drawArc(arc_rect, 90 * 16, -int((self.ingestion_pct / 100.0) * 360 * 16))
            p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            p.setPen(QColor(220, 255, 240))
            p.drawText(arc_rect, Qt.AlignmentFlag.AlignCenter, f"{self.ingestion_pct}%")

        p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        p.setPen(QColor(145, 235, 255))
        p.drawText(QRectF(0, cy + 112, w, 28), Qt.AlignmentFlag.AlignCenter, self.status_text)

        mx, my = cx, h - 24
        mic_grad = QLinearGradient(mx - 20, my - 20, mx + 20, my + 20)
        mic_grad.setColorAt(0.0, QColor(0, 210, 255, 190))
        mic_grad.setColorAt(1.0, QColor(155, 40, 255, 190))
        p.setPen(QPen(QColor(0, 245, 255, 220), 1.5))
        p.setBrush(mic_grad)
        p.drawEllipse(QPointF(mx, my), 19, 19)
        p.setPen(QPen(QColor(255, 255, 255), 2.0))
        p.drawRoundedRect(QRectF(mx - 4, my - 9, 8, 12), 4, 4)
        p.drawArc(QRectF(mx - 7, my - 6, 14, 12), 0, -180 * 16)
        p.drawLine(QPointF(mx, my + 6), QPointF(mx, my + 10))


class MultiStoreAnalyticsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(330)
        self.sales_series = [28, 82, 68, 115, 98, 210, 152, 225, 242]
        self.pred_series = [18, 45, 58, 92, 80, 155, 125, 175, 195]
        self.bar_cyan = [14, 24, 22, 32, 26, 36, 33, 39, 44]
        self.bar_purple = [10, 18, 16, 25, 20, 28, 24, 30, 35]
        self.months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]

    def record_live_activity(self, boost: int = 12):
        self.sales_series[-1] = min(250, self.sales_series[-1] + boost)
        self.bar_cyan[-1] = min(50, self.bar_cyan[-1] + max(2, boost // 5))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(QPen(QColor(0, 210, 255, 95), 1.2))
        p.setBrush(QColor(13, 18, 36, 195))
        p.drawRoundedRect(QRectF(2, 2, w - 4, h - 4), 12, 12)

        p.setPen(QColor(235, 245, 255))
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.drawText(QRectF(16, 12, w - 32, 22), Qt.AlignmentFlag.AlignLeft, "LIVE MULTI-STORE ANALYTICS")

        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.drawText(QRectF(16, 34, 90, 20), Qt.AlignmentFlag.AlignLeft, "Sales")

        p.setBrush(QColor(0, 245, 212))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(w - 135, 42), 4, 4)
        p.setPen(QColor(180, 200, 230))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(w - 126, 34, 45, 16), Qt.AlignmentFlag.AlignLeft, "Sales")

        p.setBrush(QColor(185, 45, 255))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(w - 82, 42), 4, 4)
        p.setPen(QColor(180, 200, 230))
        p.drawText(QRectF(w - 73, 34, 68, 16), Qt.AlignmentFlag.AlignLeft, "AI Predicted")

        chart1_left, chart1_top = 44.0, 58.0
        chart1_w, chart1_h = w - 62.0, (h * 0.42) - 52.0

        y_labels = ["250", "200", "150", "100", "50", "0"]
        p.setFont(QFont("Segoe UI", 7))
        for idx, lbl in enumerate(y_labels):
            yy = chart1_top + (idx / (len(y_labels) - 1)) * chart1_h
            p.setPen(QColor(130, 150, 180))
            p.drawText(QRectF(8, yy - 7, 30, 14), Qt.AlignmentFlag.AlignRight, lbl)
            p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
            p.drawLine(QPointF(chart1_left, yy), QPointF(chart1_left + chart1_w, yy))

        self._draw_smooth_curve(
            p, self.pred_series, 250.0, chart1_left, chart1_top, chart1_w, chart1_h,
            QColor(185, 45, 255, 230), QColor(185, 45, 255, 65)
        )
        self._draw_smooth_curve(
            p, self.sales_series, 250.0, chart1_left, chart1_top, chart1_w, chart1_h,
            QColor(0, 245, 212, 240), QColor(0, 245, 212, 65)
        )

        p.setPen(QColor(145, 165, 195))
        for i, m in enumerate(self.months):
            xx = chart1_left + (i / (len(self.months) - 1)) * chart1_w
            p.drawText(QRectF(xx - 14, chart1_top + chart1_h + 4, 28, 16), Qt.AlignmentFlag.AlignCenter, m)

        sec2_top = chart1_top + chart1_h + 30.0
        p.setPen(QColor(235, 245, 255))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.drawText(QRectF(16, sec2_top, w - 32, 20), Qt.AlignmentFlag.AlignLeft, "AI Inventory Forecasts")

        chart2_top = sec2_top + 26.0
        chart2_h = h - chart2_top - 30.0
        if chart2_h > 40:
            y2_labels = ["50", "40", "30", "20", "10", "0"]
            p.setFont(QFont("Segoe UI", 7))
            for idx, lbl in enumerate(y2_labels):
                yy = chart2_top + (idx / (len(y2_labels) - 1)) * chart2_h
                p.setPen(QColor(130, 150, 180))
                p.drawText(QRectF(8, yy - 7, 30, 14), Qt.AlignmentFlag.AlignRight, lbl)
                p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
                p.drawLine(QPointF(chart1_left, yy), QPointF(chart1_left + chart1_w, yy))

            slot_w = chart1_w / len(self.months)
            bar_w = max(5.0, slot_w * 0.28)
            for i, m in enumerate(self.months):
                base_x = chart1_left + i * slot_w + slot_w * 0.18
                h1 = (self.bar_purple[i] / 50.0) * chart2_h
                r1 = QRectF(base_x, chart2_top + chart2_h - h1, bar_w, h1)
                g1 = QLinearGradient(r1.topLeft(), r1.bottomLeft())
                g1.setColorAt(0.0, QColor(0, 210, 255))
                g1.setColorAt(1.0, QColor(145, 40, 255))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(g1)
                p.drawRoundedRect(r1, 2, 2)

                h2 = (self.bar_cyan[i] / 50.0) * chart2_h
                r2 = QRectF(base_x + bar_w + 3, chart2_top + chart2_h - h2, bar_w, h2)
                g2 = QLinearGradient(r2.topLeft(), r2.bottomLeft())
                g2.setColorAt(0.0, QColor(0, 255, 210))
                g2.setColorAt(1.0, QColor(115, 45, 245))
                p.setBrush(g2)
                p.drawRoundedRect(r2, 2, 2)

                p.setPen(QColor(145, 165, 195))
                p.drawText(QRectF(base_x - 6, chart2_top + chart2_h + 4, slot_w, 16), Qt.AlignmentFlag.AlignCenter, m)

    def _draw_smooth_curve(self, p, series, max_val, left, top, w, h, line_col, fill_col):
        pts = [QPointF(left + (i / (len(series) - 1)) * w, top + h - (val / max_val) * h) for i, val in enumerate(series)]
        path = QPainterPath(pts[0])
        for i in range(len(pts) - 1):
            mid_x = (pts[i].x() + pts[i + 1].x()) / 2.0
            path.cubicTo(QPointF(mid_x, pts[i].y()), QPointF(mid_x, pts[i + 1].y()), pts[i + 1])

        fill_path = QPainterPath(path)
        fill_path.lineTo(pts[-1].x(), top + h)
        fill_path.lineTo(pts[0].x(), top + h)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, top, 0, top + h)
        grad.setColorAt(0.0, fill_col)
        grad.setColorAt(1.0, QColor(fill_col.red(), fill_col.green(), fill_col.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPath(fill_path)

        p.setPen(QPen(line_col, 2.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)


class BulkDropZoneWidget(QFrame):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(195)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ingesting = False
        self.pct = 0
        self.current_rows = 0
        self.total_rows = 2500
        self.filename = "bulk_inventory_data.xlsx"

    def set_ingestion_state(self, active: bool, pct=0, current=0, total=2500, filename=""):
        self.ingesting = active
        self.pct = pct
        self.current_rows = current
        self.total_rows = total
        if filename:
            self.filename = filename
        self.update()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].toLocalFile():
            self.file_dropped.emit(urls[0].toLocalFile())

    def mousePressEvent(self, event):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Bulk Inventory Sheet", "", "Spreadsheets (*.xlsx *.xls *.csv);;All Files (*)"
        )
        if file_path:
            self.file_dropped.emit(file_path)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        border_col = QColor(0, 255, 190, 210) if self.ingesting else QColor(0, 210, 255, 105)
        p.setPen(QPen(border_col, 1.4))
        p.setBrush(QColor(13, 18, 36, 195))
        p.drawRoundedRect(QRectF(2, 2, w - 4, h - 4), 12, 12)

        p.setPen(QPen(QColor(95, 120, 175, 110), 1.2, Qt.PenStyle.DashLine))
        p.setBrush(QColor(18, 25, 48, 120))
        p.drawRoundedRect(QRectF(12, 36, w - 24, h - 48), 8, 8)

        p.setPen(QColor(235, 245, 255))
        p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        p.drawText(QRectF(16, 10, w - 32, 24), Qt.AlignmentFlag.AlignLeft, "Bulk Processing")

        cx, cy = w / 2.0, h / 2.0 - 4.0
        if not self.ingesting:
            grad = QLinearGradient(cx - 28, cy - 28, cx + 28, cy + 20)
            grad.setColorAt(0.0, QColor(0, 240, 255, 220))
            grad.setColorAt(1.0, QColor(155, 50, 255, 220))
            p.setPen(QPen(QColor(0, 255, 255), 1.8))
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(cx - 22, cy - 22, 44, 34), 8, 8)

            p.setPen(QPen(QColor(255, 255, 255), 2.6))
            p.drawLine(QPointF(cx, cy + 5), QPointF(cx, cy - 13))
            p.drawLine(QPointF(cx, cy - 13), QPointF(cx - 7, cy - 6))
            p.drawLine(QPointF(cx, cy - 13), QPointF(cx + 7, cy - 6))

            p.setPen(QColor(235, 245, 255))
            p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            p.drawText(QRectF(16, cy + 22, w - 32, 20), Qt.AlignmentFlag.AlignCenter, "Drag & Drop Bulk File")
            p.setPen(QColor(150, 170, 205))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(QRectF(16, cy + 42, w - 32, 18), Qt.AlignmentFlag.AlignCenter, "Excel, CSV, Docs, or Google Sheets")
        else:
            cube_grad = QLinearGradient(cx - 35, cy - 35, cx + 35, cy + 25)
            cube_grad.setColorAt(0.0, QColor(0, 255, 170, 180))
            cube_grad.setColorAt(1.0, QColor(0, 160, 130, 90))
            p.setPen(QPen(QColor(80, 255, 200), 2.0))
            p.setBrush(cube_grad)
            p.drawRoundedRect(QRectF(cx - 26, cy - 30, 52, 44), 6, 6)

            p.setPen(QColor(220, 255, 240))
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            p.drawText(QRectF(12, cy + 16, w - 24, 16), Qt.AlignmentFlag.AlignCenter, self.filename)
            p.setPen(QColor(0, 255, 195))
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            p.drawText(QRectF(12, cy + 33, w - 24, 18), Qt.AlignmentFlag.AlignCenter, f"INGESTING FILE... ({self.pct}%)")
            p.setPen(QColor(160, 210, 195))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(QRectF(12, cy + 50, w - 24, 16), Qt.AlignmentFlag.AlignCenter, f"ROWS READ: {self.current_rows:,} / {self.total_rows:,}")


class TabbedSettingsModal(QDialog):
    credentials_saved = pyqtSignal(dict)

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("SETTINGS (TABBED)")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(750, 470)
        self._drag_pos = None
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)

        self.container = QFrame(self)
        self.container.setObjectName("SettingsModalFrame")
        self.container.setStyleSheet("""
            QFrame#SettingsModalFrame {
                background-color: rgba(16, 22, 44, 242);
                border: 1.5px solid rgba(0, 225, 255, 150);
                border-radius: 14px;
            }
            QLabel { color: #dbe8ff; font-family: 'Segoe UI'; }
            QLineEdit, QComboBox {
                background-color: rgba(12, 17, 34, 210);
                border: 1px solid rgba(90, 130, 210, 140);
                border-radius: 7px;
                padding: 7px 12px;
                color: #eaf4ff;
                font-size: 12px;
            }
            QLineEdit:focus { border: 1.5px solid #00f2fe; }
        """)
        root_layout.addWidget(self.container)

        vbox = QVBoxLayout(self.container)
        vbox.setContentsMargins(18, 14, 18, 18)
        vbox.setSpacing(12)

        header = QHBoxLayout()
        title_lbl = QLabel("SETTINGS (TABBED)")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; letter-spacing: 1px;")
        header.addWidget(title_lbl)
        header.addStretch()

        close_btn = QPushButton("X")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("QPushButton { background: transparent; color: #9ab0d6; font-size: 13px; border: none; } QPushButton:hover { color: #00f2fe; }")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        vbox.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(16)

        self.tab_list = QListWidget()
        self.tab_list.setFixedWidth(185)
        self.tab_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(10, 14, 28, 170);
                border: 1px solid rgba(70, 100, 160, 90);
                border-radius: 10px;
                padding: 6px;
                color: #b8cae8;
                font-size: 13px;
                outline: none;
            }
            QListWidget::item { padding: 9px 12px; border-radius: 7px; margin-bottom: 3px; }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 230, 215, 160), stop:1 rgba(165, 55, 255, 170));
                border: 1px solid #00f2fe;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        for t in ["General", "Shopify", "Daraz", "Amazon (SP-API)", "eBay", "WooCommerce", "TikTok", "Google API"]:
            self.tab_list.addItem(QListWidgetItem(t))
        body.addWidget(self.tab_list)

        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)

        self._create_general_page()
        self._create_shopify_page()
        self._create_daraz_page()
        self._create_amazon_page()
        self._create_ebay_page()
        self._create_woocommerce_page()
        self._create_tiktok_page()
        self._create_google_page()

        self.tab_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.tab_list.setCurrentRow(3)
        vbox.addLayout(body, 1)

    @staticmethod
    def _build_status_toggle_row(initial_state: bool):
        row = QHBoxLayout()
        toggle = NeonToggleSwitch(initial_state)
        lbl = QLabel("CONNECTED / ACTIVE (ON)" if initial_state else "DISCONNECTED / INACTIVE (OFF)")
        lbl.setStyleSheet(
            "color: #00ffa6; font-weight: bold; font-size: 12px;"
            if initial_state else
            "color: #ff6b81; font-weight: bold; font-size: 12px;"
        )

        def _on_toggle(state: bool):
            lbl.setText("CONNECTED / ACTIVE (ON)" if state else "DISCONNECTED / INACTIVE (OFF)")
            lbl.setStyleSheet(
                "color: #00ffa6; font-weight: bold; font-size: 12px;"
                if state else
                "color: #ff6b81; font-weight: bold; font-size: 12px;"
            )

        toggle.toggled.connect(_on_toggle)
        row.addWidget(toggle)
        row.addSpacing(10)
        row.addWidget(lbl)
        row.addStretch()
        return row, toggle, lbl

    def _create_general_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 6, 12, 6)
        cfg = self.db.config.get("general", {})

        hdr = QLabel("General, Gemini AI & Supabase Cloud")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        layout.addWidget(hdr)

        grid = QGridLayout()
        grid.addWidget(QLabel("File name / Group"), 0, 0)
        self.gen_group = QLineEdit(cfg.get("group_name", "Omnichannel AI Manager Group"))
        grid.addWidget(self.gen_group, 0, 1)

        grid.addWidget(QLabel("Keyword"), 1, 0)
        self.gen_keyword = QComboBox()
        self.gen_keyword.addItems(["Google API", "Amazon SP-API", "Shopify GraphQL", "Supabase Cloud"])
        grid.addWidget(self.gen_keyword, 1, 1)

        grid.addWidget(QLabel("Supabase URL"), 2, 0)
        self.gen_supa_url = QLineEdit(cfg.get("supabase_url", ""))
        self.gen_supa_url.setPlaceholderText("https://xyzcompany.supabase.co")
        grid.addWidget(self.gen_supa_url, 2, 1)

        grid.addWidget(QLabel("Supabase Key"), 3, 0)
        self.gen_supa_key = QLineEdit(cfg.get("supabase_key", ""))
        self.gen_supa_key.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.gen_supa_key, 3, 1)

        grid.addWidget(QLabel("Gemini API Key"), 4, 0)
        self.gen_gemini_key = QLineEdit(cfg.get("gemini_api_key", ""))
        self.gen_gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.gen_gemini_key, 4, 1)

        grid.addWidget(QLabel("Webcam Gesture AI"), 5, 0)
        self.gen_gesture_toggle = NeonToggleSwitch(cfg.get("gesture_control_enabled", False))
        grid.addWidget(self.gen_gesture_toggle, 5, 1)

        layout.addLayout(grid)
        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._create_save_button())
        layout.addLayout(btn_row)
        self.stack.addWidget(page)

    def _create_shopify_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 6, 12, 6)
        cfg = self.db.config.get("shopify", {})

        hdr = QLabel("Shopify Admin API Configuration")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        layout.addWidget(hdr)

        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.addWidget(QLabel("Store URL"), 0, 0)
        self.shop_url = QLineEdit(cfg.get("shop_url", ""))
        self.shop_url.setPlaceholderText("https://your-store.myshopify.com")
        grid.addWidget(self.shop_url, 0, 1)

        grid.addWidget(QLabel("Access Token"), 1, 0)
        self.shop_token = QLineEdit(cfg.get("access_token", ""))
        self.shop_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.shop_token.setPlaceholderText("shpat_xxxxxxxxxxxxxxxxxxxxxxxx")
        grid.addWidget(self.shop_token, 1, 1)

        grid.addWidget(QLabel("Status"), 2, 0)
        row, self.shop_toggle, _ = self._build_status_toggle_row(cfg.get("status", True))
        grid.addLayout(row, 2, 1)

        layout.addLayout(grid)
        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._create_save_button())
        layout.addLayout(btn_row)
        self.stack.addWidget(page)

    def _create_daraz_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 6, 12, 6)
        cfg = self.db.config.get("daraz", {})

        hdr = QLabel("Daraz Open Platform Configuration")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        layout.addWidget(hdr)

        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.addWidget(QLabel("App Key"), 0, 0)
        self.drz_key = QLineEdit(cfg.get("app_key", ""))
        grid.addWidget(self.drz_key, 0, 1)

        grid.addWidget(QLabel("App Secret"), 1, 0)
        self.drz_secret = QLineEdit(cfg.get("app_secret", ""))
        self.drz_secret.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.drz_secret, 1, 1)

        grid.addWidget(QLabel("Seller ID"), 2, 0)
        self.drz_seller = QLineEdit(cfg.get("seller_id", ""))
        grid.addWidget(self.drz_seller, 2, 1)

        grid.addWidget(QLabel("Status"), 3, 0)
        row, self.drz_toggle, _ = self._build_status_toggle_row(cfg.get("status", True))
        grid.addLayout(row, 3, 1)

        layout.addLayout(grid)
        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._create_save_button())
        layout.addLayout(btn_row)
        self.stack.addWidget(page)

    def _create_amazon_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)

        hdr = QLabel("Amazon (SP-API) Configuration")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        layout.addWidget(hdr)

        cfg = self.db.config.get("amazon", {})
        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.setHorizontalSpacing(16)

        grid.addWidget(QLabel("Client ID (SP-API)"), 0, 0)
        self.amz_client_id = QLineEdit(cfg.get("client_id", ""))
        self.amz_client_id.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.amz_client_id, 0, 1)

        grid.addWidget(QLabel("Client Secret"), 1, 0)
        self.amz_client_secret = QLineEdit(cfg.get("client_secret", ""))
        self.amz_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.amz_client_secret, 1, 1)

        grid.addWidget(QLabel("IAM Role ARN"), 2, 0)
        self.amz_arn = QLineEdit(cfg.get("iam_role_arn", ""))
        grid.addWidget(self.amz_arn, 2, 1)

        grid.addWidget(QLabel("Seller ID"), 3, 0)
        self.amz_seller = QLineEdit(cfg.get("seller_id", ""))
        grid.addWidget(self.amz_seller, 3, 1)

        grid.addWidget(QLabel("Status"), 4, 0)
        row, self.amz_toggle, _ = self._build_status_toggle_row(cfg.get("status", True))
        grid.addLayout(row, 4, 1)
        layout.addLayout(grid)

        note = QLabel("Authorize SP-API credentials for real-time inventory and sales synchronization.")
        note.setStyleSheet("color: #8fa5cc; font-size: 11px;")
        layout.addWidget(note)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._create_save_button())
        layout.addLayout(btn_row)
        self.stack.addWidget(page)

    def _create_ebay_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 6, 12, 6)
        cfg = self.db.config.get("ebay", {})

        hdr = QLabel("eBay REST & Fulfillment API")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        layout.addWidget(hdr)

        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.addWidget(QLabel("App ID"), 0, 0)
        self.ebay_app = QLineEdit(cfg.get("app_id", ""))
        grid.addWidget(self.ebay_app, 0, 1)

        grid.addWidget(QLabel("Cert ID"), 1, 0)
        self.ebay_cert = QLineEdit(cfg.get("cert_id", ""))
        self.ebay_cert.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.ebay_cert, 1, 1)

        grid.addWidget(QLabel("OAuth Token"), 2, 0)
        self.ebay_token = QLineEdit(cfg.get("oauth_token", ""))
        self.ebay_token.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.ebay_token, 2, 1)

        grid.addWidget(QLabel("Status"), 3, 0)
        row, self.ebay_toggle, _ = self._build_status_toggle_row(cfg.get("status", True))
        grid.addLayout(row, 3, 1)

        layout.addLayout(grid)
        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._create_save_button())
        layout.addLayout(btn_row)
        self.stack.addWidget(page)

    def _create_woocommerce_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 6, 12, 6)
        cfg = self.db.config.get("woocommerce", {})

        hdr = QLabel("WooCommerce REST v3 Configuration")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        layout.addWidget(hdr)

        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.addWidget(QLabel("Store URL"), 0, 0)
        self.woo_url = QLineEdit(cfg.get("store_url", ""))
        grid.addWidget(self.woo_url, 0, 1)

        grid.addWidget(QLabel("Consumer Key"), 1, 0)
        self.woo_ck = QLineEdit(cfg.get("consumer_key", ""))
        grid.addWidget(self.woo_ck, 1, 1)

        grid.addWidget(QLabel("Consumer Secret"), 2, 0)
        self.woo_cs = QLineEdit(cfg.get("consumer_secret", ""))
        self.woo_cs.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.woo_cs, 2, 1)

        grid.addWidget(QLabel("Status"), 3, 0)
        row, self.woo_toggle, _ = self._build_status_toggle_row(cfg.get("status", True))
        grid.addLayout(row, 3, 1)

        layout.addLayout(grid)
        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._create_save_button())
        layout.addLayout(btn_row)
        self.stack.addWidget(page)

    def _create_tiktok_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 6, 12, 6)
        cfg = self.db.config.get("tiktok", {})

        hdr = QLabel("TikTok Shop & Studio Partner API")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        layout.addWidget(hdr)

        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.addWidget(QLabel("App Key"), 0, 0)
        self.tts_key = QLineEdit(cfg.get("app_key", ""))
        grid.addWidget(self.tts_key, 0, 1)

        grid.addWidget(QLabel("App Secret"), 1, 0)
        self.tts_secret = QLineEdit(cfg.get("app_secret", ""))
        self.tts_secret.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.tts_secret, 1, 1)

        grid.addWidget(QLabel("Shop ID"), 2, 0)
        self.tts_shop = QLineEdit(cfg.get("shop_id", ""))
        grid.addWidget(self.tts_shop, 2, 1)

        grid.addWidget(QLabel("Status"), 3, 0)
        row, self.tts_toggle, _ = self._build_status_toggle_row(cfg.get("status", True))
        grid.addLayout(row, 3, 1)

        layout.addLayout(grid)
        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._create_save_button())
        layout.addLayout(btn_row)
        self.stack.addWidget(page)

    def _create_google_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 6, 12, 6)
        cfg = self.db.config.get("google_api", {})

        hdr = QLabel("Gmail API, WhatsApp Cloud & Twilio Voice")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        layout.addWidget(hdr)

        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.addWidget(QLabel("Gmail Token Path"), 0, 0)
        self.goog_token = QLineEdit(cfg.get("token_json", "token.json"))
        grid.addWidget(self.goog_token, 0, 1)

        grid.addWidget(QLabel("WhatsApp Token"), 1, 0)
        self.wa_token = QLineEdit(cfg.get("whatsapp_token", ""))
        self.wa_token.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.wa_token, 1, 1)

        grid.addWidget(QLabel("Twilio SID"), 2, 0)
        self.tw_sid = QLineEdit(cfg.get("twilio_sid", ""))
        grid.addWidget(self.tw_sid, 2, 1)

        grid.addWidget(QLabel("Twilio Token"), 3, 0)
        self.tw_token = QLineEdit(cfg.get("twilio_token", ""))
        self.tw_token.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.tw_token, 3, 1)

        layout.addLayout(grid)
        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._create_save_button())
        layout.addLayout(btn_row)
        self.stack.addWidget(page)

    def _create_save_button(self):
        btn = QPushButton("SAVE CREDENTIALS")
        btn.setFixedSize(195, 40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 185, 215, 220), stop:1 rgba(0, 245, 190, 220));
                border: 2px solid #55ffff;
                border-radius: 8px;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 215, 245, 255), stop:1 rgba(0, 255, 210, 255));
            }
        """)
        btn.clicked.connect(self._save_all)
        return btn

    def _save_all(self):
        cfg = self.db.config
        cfg["general"]["group_name"] = self.gen_group.text().strip()
        cfg["general"]["keyword"] = self.gen_keyword.currentText()
        cfg["general"]["supabase_url"] = self.gen_supa_url.text().strip()
        cfg["general"]["supabase_key"] = self.gen_supa_key.text().strip()
        cfg["general"]["gemini_api_key"] = self.gen_gemini_key.text().strip()
        cfg["general"]["gesture_control_enabled"] = self.gen_gesture_toggle.isChecked()

        cfg["shopify"]["shop_url"] = self.shop_url.text().strip()
        cfg["shopify"]["access_token"] = self.shop_token.text().strip()
        cfg["shopify"]["status"] = self.shop_toggle.isChecked()

        cfg["daraz"]["app_key"] = self.drz_key.text().strip()
        cfg["daraz"]["app_secret"] = self.drz_secret.text().strip()
        cfg["daraz"]["seller_id"] = self.drz_seller.text().strip()
        cfg["daraz"]["status"] = self.drz_toggle.isChecked()

        cfg["amazon"]["client_id"] = self.amz_client_id.text().strip()
        cfg["amazon"]["client_secret"] = self.amz_client_secret.text().strip()
        cfg["amazon"]["iam_role_arn"] = self.amz_arn.text().strip()
        cfg["amazon"]["seller_id"] = self.amz_seller.text().strip()
        cfg["amazon"]["status"] = self.amz_toggle.isChecked()

        cfg["ebay"]["app_id"] = self.ebay_app.text().strip()
        cfg["ebay"]["cert_id"] = self.ebay_cert.text().strip()
        cfg["ebay"]["oauth_token"] = self.ebay_token.text().strip()
        cfg["ebay"]["status"] = self.ebay_toggle.isChecked()

        cfg["woocommerce"]["store_url"] = self.woo_url.text().strip()
        cfg["woocommerce"]["consumer_key"] = self.woo_ck.text().strip()
        cfg["woocommerce"]["consumer_secret"] = self.woo_cs.text().strip()
        cfg["woocommerce"]["status"] = self.woo_toggle.isChecked()

        cfg["tiktok"]["app_key"] = self.tts_key.text().strip()
        cfg["tiktok"]["app_secret"] = self.tts_secret.text().strip()
        cfg["tiktok"]["shop_id"] = self.tts_shop.text().strip()
        cfg["tiktok"]["status"] = self.tts_toggle.isChecked()

        cfg["google_api"]["token_json"] = self.goog_token.text().strip()
        cfg["google_api"]["whatsapp_token"] = self.wa_token.text().strip()
        cfg["google_api"]["twilio_sid"] = self.tw_sid.text().strip()
        cfg["google_api"]["twilio_token"] = self.tw_token.text().strip()

        self.db.save_config(cfg)
        self.credentials_saved.emit(cfg)
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

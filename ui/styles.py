DARK_STYLESHEET = """
/* ── Global ─────────────────────────────────────────────── */
QWidget {
    background-color: #050508;
    color: #e8eaf6;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #050508;
    border: none;
}

/* remove any qt-internal frame borders */
QWidget#qt_scrollarea_viewport, QAbstractScrollArea {
    border: none;
}

/* Title bar divider line — invisible */
QFrame[frameShape="4"] {
    border: none;
    background: transparent;
}

/* ── Panels / Frames — fully transparent, no surrounding box ── */
QFrame#controlPanel, QFrame#analyticsPanel {
    background-color: transparent;
    border: none;
}

/* ── Collapsible card panels (control panel sections) ────────── */
QFrame#cardPanel {
    background-color: rgba(14, 14, 26, 190);
    border: 1px solid rgba(80, 100, 230, 45);
    border-radius: 10px;
}

/* ── Analytics QGroupBox — floating card look ────────────────── */
QGroupBox {
    background-color: rgba(14, 14, 26, 190);
    border: 1px solid rgba(80, 100, 230, 45);
    border-radius: 10px;
    margin-top: 14px;
    padding: 8px;
    font-weight: bold;
    font-size: 12px;
    color: #7986cb;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    top: -2px;
    padding: 0 4px;
}

/* ── Collapsible section header button ───────────────────── */
QPushButton#sectionHeader {
    background-color: rgba(25, 25, 50, 200);
    color: #90caf9;
    border: 1px solid rgba(100, 140, 255, 70);
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: bold;
    font-size: 13px;
    text-align: left;
}
QPushButton#sectionHeader:hover {
    background-color: rgba(40, 40, 80, 230);
    border-color: rgba(130, 170, 255, 120);
    color: #bbdefb;
}
QPushButton#sectionHeader:pressed {
    background-color: rgba(20, 20, 55, 255);
}

/* ── Action Buttons ──────────────────────────────────────── */
QPushButton {
    background-color: rgba(20, 30, 80, 200);
    color: #e8eaf6;
    border: 1px solid rgba(100, 130, 255, 80);
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: rgba(35, 55, 130, 220);
    border-color: rgba(150, 180, 255, 160);
}
QPushButton:pressed {
    background-color: rgba(15, 25, 70, 255);
}
QPushButton:disabled {
    background-color: rgba(20, 20, 35, 140);
    color: rgba(180, 180, 220, 90);
    border-color: rgba(60, 60, 100, 80);
}

QPushButton#btnRun {
    background-color: rgba(15, 100, 60, 200);
    border-color: rgba(80, 230, 160, 100);
    color: #e8f5e9;
}
QPushButton#btnRun:hover {
    background-color: rgba(25, 140, 85, 220);
    border-color: #55efc4;
}

QPushButton#btnPause {
    background-color: rgba(100, 80, 10, 180);
    border-color: rgba(255, 210, 80, 90);
}
QPushButton#btnPause:hover {
    background-color: rgba(150, 120, 15, 210);
    border-color: #fdcb6e;
}

QPushButton#btnReset {
    background-color: rgba(100, 20, 20, 180);
    border-color: rgba(255, 90, 90, 90);
}
QPushButton#btnReset:hover {
    background-color: rgba(160, 35, 35, 210);
    border-color: #ff7675;
}

/* ── Sliders ─────────────────────────────────────────────── */
QSlider::groove:horizontal {
    height: 5px;
    background: rgba(60, 70, 140, 160);
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
        fx:0.5, fy:0.5, stop:0 #82b1ff, stop:1 #448aff);
    border: none;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3949ab, stop:1 #5c6bc0);
    border-radius: 3px;
}
QSlider::groove:horizontal:disabled {
    background: rgba(40, 40, 70, 100);
}
QSlider::handle:horizontal:disabled {
    background: rgba(80, 80, 120, 120);
}

/* ── SpinBox ─────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: rgba(15, 20, 55, 200);
    border: 1px solid rgba(80, 110, 220, 100);
    border-radius: 5px;
    padding: 4px 7px;
    color: #e8eaf6;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: rgba(50, 70, 180, 140);
    border: none;
    border-radius: 2px;
    width: 14px;
}

/* ── Title label ─────────────────────────────────────────── */
QLabel#labelTitle {
    font-size: 20px;
    font-weight: bold;
    color: #90caf9;
    padding: 4px 0;
    letter-spacing: 1px;
}
QLabel#labelQber {
    font-size: 28px;
    font-weight: bold;
}

/* ── Progress Bar (QBER meter) ───────────────────────────── */
QProgressBar {
    border: 1px solid rgba(60, 80, 200, 80);
    border-radius: 6px;
    background-color: rgba(5, 5, 20, 200);
    text-align: center;
    color: #e8eaf6;
    font-weight: bold;
    height: 22px;
}
QProgressBar::chunk {
    border-radius: 5px;
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0.0  #00b894,
        stop:0.44 #fdcb6e,
        stop:1.0  #d63031
    );
}

/* ── Text / Log ─────────────────────────────────────────── */
QPlainTextEdit {
    background-color: rgba(5, 5, 18, 220);
    color: #90caf9;
    border: 1px solid rgba(60, 80, 200, 80);
    border-radius: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
}

/* ── Toggle / Check ─────────────────────────────────────── */
QCheckBox {
    color: #e8eaf6;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 5px;
    border: 1px solid rgba(100, 130, 255, 120);
    background-color: rgba(15, 20, 55, 200);
}
QCheckBox::indicator:checked {
    background-color: #e94560;
    border-color: #ff7675;
    image: none;
}

/* ── Scroll bars ─────────────────────────────────────────── */
QScrollBar:vertical {
    background: rgba(5, 5, 15, 150);
    width: 7px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: rgba(70, 100, 220, 150);
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* ── Splitter — invisible, seamless ─────────────────────── */
QSplitter::handle {
    background-color: transparent;
    width: 1px;
    border: none;
}
"""

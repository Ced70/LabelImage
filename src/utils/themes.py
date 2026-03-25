"""Theme definitions for LabelImage."""
from __future__ import annotations

DARK_THEME = """
    QMainWindow { background-color: #2b2b2b; }
    QDockWidget { color: #ddd; }
    QDockWidget::title { background-color: #3c3c3c; padding: 6px; }
    QListWidget { background-color: #1e1e1e; color: #ddd; border: none; font-size: 13px; }
    QListWidget::item:selected { background-color: #264f78; }
    QListWidget::item:hover { background-color: #333333; }
    QLabel { color: #ddd; }
    QPushButton { background-color: #3c3c3c; color: #ddd; border: 1px solid #555; padding: 4px 12px; border-radius: 3px; }
    QPushButton:hover { background-color: #4a4a4a; }
    QToolBar { background-color: #2b2b2b; border: none; spacing: 4px; padding: 2px; }
    QToolBar QToolButton { color: #ddd; padding: 4px 8px; }
    QMenuBar { background-color: #2b2b2b; color: #ddd; }
    QMenuBar::item:selected { background-color: #3c3c3c; }
    QMenu { background-color: #2b2b2b; color: #ddd; }
    QMenu::item:selected { background-color: #264f78; }
    QStatusBar { background-color: #007acc; color: white; }
    QScrollBar:vertical { background-color: #1e1e1e; width: 12px; }
    QScrollBar::handle:vertical { background-color: #555; border-radius: 4px; min-height: 20px; }
    QScrollBar:horizontal { background-color: #1e1e1e; height: 12px; }
    QScrollBar::handle:horizontal { background-color: #555; border-radius: 4px; min-width: 20px; }
    QLineEdit { background-color: #1e1e1e; color: #ddd; border: 1px solid #555; padding: 4px; border-radius: 3px; }
    QComboBox { background-color: #1e1e1e; color: #ddd; border: 1px solid #555; padding: 4px; }
    QComboBox QAbstractItemView { background-color: #2b2b2b; color: #ddd; selection-background-color: #264f78; }
    QSpinBox, QDoubleSpinBox { background-color: #1e1e1e; color: #ddd; border: 1px solid #555; padding: 2px; }
    QSlider::groove:horizontal { background: #555; height: 4px; border-radius: 2px; }
    QSlider::handle:horizontal { background: #007acc; width: 14px; margin: -5px 0; border-radius: 7px; }
    QCheckBox { color: #ddd; }
    QRadioButton { color: #ddd; }
    QGroupBox { color: #ddd; border: 1px solid #555; border-radius: 4px; margin-top: 8px; padding-top: 16px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
    QTableWidget { background-color: #1e1e1e; color: #ddd; gridline-color: #444; }
    QHeaderView::section { background-color: #3c3c3c; color: #ddd; padding: 4px; border: 1px solid #555; }
    QProgressBar { background-color: #1e1e1e; border: 1px solid #555; border-radius: 3px; text-align: center; color: white; }
    QProgressBar::chunk { background-color: #007acc; }
    QTabWidget::pane { border: 1px solid #555; }
    QTabBar::tab { background-color: #3c3c3c; color: #ddd; padding: 6px 12px; }
    QTabBar::tab:selected { background-color: #264f78; }
    QDialog { background-color: #2b2b2b; color: #ddd; }
"""

LIGHT_THEME = """
    QMainWindow { background-color: #f0f0f0; }
    QDockWidget { color: #333; }
    QDockWidget::title { background-color: #e0e0e0; padding: 6px; }
    QListWidget { background-color: #fff; color: #333; border: 1px solid #ccc; font-size: 13px; }
    QListWidget::item:selected { background-color: #0078d7; color: white; }
    QListWidget::item:hover { background-color: #e8e8e8; }
    QLabel { color: #333; }
    QPushButton { background-color: #e0e0e0; color: #333; border: 1px solid #bbb; padding: 4px 12px; border-radius: 3px; }
    QPushButton:hover { background-color: #d0d0d0; }
    QToolBar { background-color: #f0f0f0; border: none; spacing: 4px; padding: 2px; }
    QToolBar QToolButton { color: #333; padding: 4px 8px; }
    QMenuBar { background-color: #f0f0f0; color: #333; }
    QMenuBar::item:selected { background-color: #e0e0e0; }
    QMenu { background-color: #fff; color: #333; }
    QMenu::item:selected { background-color: #0078d7; color: white; }
    QStatusBar { background-color: #0078d7; color: white; }
    QScrollBar:vertical { background-color: #f0f0f0; width: 12px; }
    QScrollBar::handle:vertical { background-color: #bbb; border-radius: 4px; min-height: 20px; }
    QScrollBar:horizontal { background-color: #f0f0f0; height: 12px; }
    QScrollBar::handle:horizontal { background-color: #bbb; border-radius: 4px; min-width: 20px; }
    QLineEdit { background-color: #fff; color: #333; border: 1px solid #bbb; padding: 4px; border-radius: 3px; }
    QComboBox { background-color: #fff; color: #333; border: 1px solid #bbb; padding: 4px; }
    QSpinBox, QDoubleSpinBox { background-color: #fff; color: #333; border: 1px solid #bbb; padding: 2px; }
    QSlider::groove:horizontal { background: #bbb; height: 4px; border-radius: 2px; }
    QSlider::handle:horizontal { background: #0078d7; width: 14px; margin: -5px 0; border-radius: 7px; }
    QCheckBox { color: #333; }
    QRadioButton { color: #333; }
    QGroupBox { color: #333; border: 1px solid #bbb; border-radius: 4px; margin-top: 8px; padding-top: 16px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
    QTableWidget { background-color: #fff; color: #333; gridline-color: #ddd; }
    QHeaderView::section { background-color: #e0e0e0; color: #333; padding: 4px; border: 1px solid #ccc; }
    QProgressBar { background-color: #e0e0e0; border: 1px solid #bbb; border-radius: 3px; text-align: center; }
    QProgressBar::chunk { background-color: #0078d7; }
    QDialog { background-color: #f0f0f0; color: #333; }
"""

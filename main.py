import sys
import os
import json
import re
from collections import deque
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QFileDialog, QTabWidget, QMessageBox, QLabel, QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QPalette, QColor

# ==========================================
# سیستم مدیریت زبان با اسکن پوشه محلی
# ==========================================
class LangManager(QObject):
    lang_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.available_langs = {}
        self.translations = {}
        self.current_lang = "fa"
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.locales_dir = os.path.join(base_dir, "locales")
        
        self.scan_languages()
        self.load_language(self.current_lang)

    def scan_languages(self):
        if not os.path.exists(self.locales_dir):
            os.makedirs(self.locales_dir)
            return

        for filename in os.listdir(self.locales_dir):
            if filename.endswith(".json"):
                lang_code = filename[:-5]
                filepath = os.path.join(self.locales_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        lang_name = data.get("lang_name", lang_code.upper())
                        self.available_langs[lang_code] = lang_name
                except Exception as e:
                    print(f"Error reading {filename}: {e}")

    def load_language(self, lang_code):
        filepath = os.path.join(self.locales_dir, f"{lang_code}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    self.translations = json.load(f)
                self.current_lang = lang_code
            except Exception as e:
                print(f"Error loading {filepath}: {e}")

    def set_lang(self, lang_code):
        if lang_code != self.current_lang:
            self.load_language(lang_code)
            direction = Qt.RightToLeft if lang_code in ["fa", "ar", "he"] else Qt.LeftToRight
            QApplication.instance().setLayoutDirection(direction)
            self.lang_changed.emit(self.current_lang)

    def t(self, key):
        return self.translations.get(key, key)

lang_mgr = LangManager()

# ==========================================
# تب استخراج (با پشتیبانی از Drag & Drop و Validation)
# ==========================================
class ExtractQuotesTab(QWidget):
    def __init__(self):
        super().__init__()
        self.lines_out = []
        self.error_lines = []
        
        self.setAcceptDrops(True)
        self.setup_ui()
        lang_mgr.lang_changed.connect(self.update_texts)
        self.update_texts()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 5px;")
        main_layout.addWidget(self.title)
        
        self.desc = QLabel()
        self.desc.setStyleSheet("font-size: 11px; color: #888888;")
        main_layout.addWidget(self.desc)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.load_btn = QPushButton()
        self.save_btn = QPushButton()
        
        for btn in [self.load_btn, self.save_btn]:
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db; color: white; border: none;
                    padding: 12px; font-size: 13px; border-radius: 6px;
                }
                QPushButton:hover { background-color: #2980b9; }
            """)
        
        self.save_btn.setStyleSheet("""
            QPushButton { 
                background-color: #9b59b6; color: white; border: none;
                padding: 12px; font-size: 13px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #8e44ad; }
        """)
        
        btn_layout.addWidget(self.load_btn, 1)
        btn_layout.addWidget(self.save_btn, 1)
        main_layout.addLayout(btn_layout)
        
        self.text_area = QTextEdit()
        self.text_area.setStyleSheet("""
            QTextEdit {
                border: 2px solid #3d3d3d; border-radius: 6px; padding: 8px; font-size: 13px;
            }
            QTextEdit:focus { border-color: #3498db; }
        """)
        main_layout.addWidget(self.text_area, 1)
        
        self.setLayout(main_layout)
        
        self.load_btn.clicked.connect(self.load_file_dialog)
        self.save_btn.clicked.connect(self.save_file)

    def update_texts(self):
        self.title.setText(lang_mgr.t("extract_title"))
        self.desc.setText(lang_mgr.t("extract_desc"))
        self.load_btn.setText(lang_mgr.t("open_file_btn"))
        self.save_btn.setText(lang_mgr.t("save_out_btn"))
        self.text_area.setPlaceholderText(lang_mgr.t("extract_placeholder"))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                self.process_file(file_path)
                break

    def is_valid_line(self, line):
        return line.count('"') % 2 == 0

    def extract_last_quoted(self, line):
        matches = list(re.finditer(r'"([^"]*)"', line))
        if matches:
            return matches[-1].group(1)
        return None

    def load_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, lang_mgr.t("select_file"), "", "Text Files (*.txt *.json *.xml);;All Files (*)"
        )
        if path:
            self.process_file(path)

    def process_file(self, path):
        self.lines_out = []
        self.error_lines = []
        display_lines = []
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line_num, raw_line in enumerate(f, start=1):
                    line = raw_line.rstrip("\n")
                    if line.startswith("\ufeff"):
                        line = line.lstrip("\ufeff")
                    
                    # بخش Validation (اعتبارسنجی ساختار کوتیشن‌ها)
                    if not self.is_valid_line(line):
                        self.error_lines.append(line_num)
                        self.lines_out.append("")
                        display_lines.append(f"[Line {line_num} Error: Invalid Quotes] -> {line}")
                        continue
                    
                    quoted_text = self.extract_last_quoted(line)
                    if quoted_text is not None:
                        self.lines_out.append(quoted_text)
                        display_lines.append(quoted_text)
                    else:
                        self.lines_out.append("")
                        display_lines.append("")
            
            self.text_area.setPlainText("\n".join(display_lines))
            
            if self.error_lines:
                QMessageBox.warning(
                    self, lang_mgr.t("error_title"),
                    f"{lang_mgr.t('error_lines')} {', '.join(map(str, self.error_lines))}"
                )
            else:
                QMessageBox.information(
                    self, lang_mgr.t("success_title"), 
                    lang_mgr.t("done_lines").format(len(self.lines_out))
                )
                
        except Exception as e:
            QMessageBox.critical(self, lang_mgr.t("error_title"), lang_mgr.t("error_msg").format(str(e)))

    def save_file(self):
        if not self.lines_out:
            QMessageBox.warning(self, lang_mgr.t("warning_title"), lang_mgr.t("load_file_first"))
            return
            
        path, _ = QFileDialog.getSaveFileName(self, lang_mgr.t("save_dialog"), "", "Text Files (*.txt)")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.lines_out))
            QMessageBox.information(self, lang_mgr.t("success_title"), lang_mgr.t("saved_success"))
        except Exception as e:
            QMessageBox.critical(self, lang_mgr.t("error_title"), lang_mgr.t("error_msg").format(str(e)))

# ==========================================
# تب جایگذاری (با پشتیبانی از Live Preview و Validation)
# ==========================================
class ReplaceQuotesTab(QWidget):
    def __init__(self):
        super().__init__()
        self.file1_lines = []
        self.file2_lines = []
        self.error_lines = []
        
        self.setAcceptDrops(True)
        self.setup_ui()
        lang_mgr.lang_changed.connect(self.update_texts)
        self.update_texts()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 5px;")
        main_layout.addWidget(self.title)
        
        self.desc = QLabel()
        self.desc.setStyleSheet("font-size: 11px; color: #888888;")
        main_layout.addWidget(self.desc)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.load_file1_btn = QPushButton()
        self.load_file2_btn = QPushButton()
        
        for btn in [self.load_file1_btn, self.load_file2_btn]:
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            
        self.load_file1_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; color: white; border: none;
                padding: 12px; font-size: 13px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)
        
        self.load_file2_btn.setStyleSheet("""
            QPushButton {
                background-color: #1abc9c; color: white; border: none;
                padding: 12px; font-size: 13px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #16a085; }
        """)
        
        btn_layout.addWidget(self.load_file1_btn, 1)
        btn_layout.addWidget(self.load_file2_btn, 1)
        main_layout.addLayout(btn_layout)
        
        self.process_btn = QPushButton()
        self.process_btn.setCursor(Qt.PointingHandCursor)
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white; border: none;
                padding: 12px; font-size: 14px; font-weight: bold; border-radius: 6px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        main_layout.addWidget(self.process_btn)
        
        # لایوت افقی برای بخش محتوا و پیش‌نویس زنده (Live Preview)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)
        
        self.text_area = QTextEdit()
        self.text_area.setStyleSheet("""
            QTextEdit {
                border: 2px solid #3d3d3d; border-radius: 6px; padding: 8px; font-size: 13px;
            }
            QTextEdit:focus { border-color: #e74c3c; }
        """)
        content_layout.addWidget(self.text_area, 3) # ضریب ۳ برای باکس اصلی
        
        # باکس پیش‌نمایش زنده (Live Preview Panel)
        self.preview_area = QTextEdit()
        self.preview_area.setReadOnly(True)
        self.preview_area.setStyleSheet("""
            QTextEdit {
                border: 1px dashed #7f8c8d; border-radius: 6px; padding: 6px;
                font-size: 11px; color: #7f8c8d; background-color: rgba(0,0,0,0.05);
            }
        """)
        content_layout.addWidget(self.preview_area, 1) # ضریب ۱ برای کوچک بودن باکس پیش‌نمایش
        
        main_layout.addLayout(content_layout, 1)
        
        self.save_btn = QPushButton()
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6; color: white; border: none;
                padding: 12px; font-size: 13px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #8e44ad; }
        """)
        main_layout.addWidget(self.save_btn)
        
        self.setLayout(main_layout)
        
        self.load_file1_btn.clicked.connect(self.load_file1_dialog)
        self.load_file2_btn.clicked.connect(self.load_file2_dialog)
        self.process_btn.clicked.connect(self.replace_quotes)
        self.save_btn.clicked.connect(self.save_file)

    def update_texts(self):
        self.title.setText(lang_mgr.t("replace_title"))
        self.desc.setText(lang_mgr.t("replace_desc"))
        self.load_file1_btn.setText(lang_mgr.t("template_file_btn"))
        self.load_file2_btn.setText(lang_mgr.t("text_file_btn"))
        self.process_btn.setText(lang_mgr.t("process_btn"))
        self.save_btn.setText(lang_mgr.t("save_out_btn"))
        self.text_area.setPlaceholderText(lang_mgr.t("replace_placeholder"))
        self.preview_area.setPlaceholderText("Live Preview (Top 5 lines)...")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) >= 1:
            file1 = urls[0].toLocalFile()
            if os.path.isfile(file1): self.process_file1(file1)
        if len(urls) >= 2:
            file2 = urls[1].toLocalFile()
            if os.path.isfile(file2): self.process_file2(file2)

    def is_valid_line(self, line):
        return line.count('"') % 2 == 0

    def update_live_preview(self):
        """به‌روزرسانی کادر پیش‌نمایش متنی کوچک به صورت زنده"""
        preview_text = "--- Template Preview ---\n"
        preview_text += "".join(self.file1_lines[:5])
        preview_text += "\n\n--- Text Replacement Preview ---\n"
        preview_text += "\n".join(self.file2_lines[:5])
        self.preview_area.setPlainText(preview_text)

    def load_file1_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, lang_mgr.t("template_dialog"), "", "Text Files (*.txt *.json)")
        if path: self.process_file1(path)

    def process_file1(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.file1_lines = f.readlines()
                if self.file1_lines and self.file1_lines[0].startswith("\ufeff"):
                    self.file1_lines[0] = self.file1_lines[0].lstrip("\ufeff")
            QMessageBox.information(self, lang_mgr.t("success_title"), lang_mgr.t("loaded_lines").format(len(self.file1_lines)))
            self.update_live_preview()
        except Exception as e:
            QMessageBox.critical(self, lang_mgr.t("error_title"), lang_mgr.t("error_msg").format(str(e)))

    def load_file2_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, lang_mgr.t("text_dialog"), "", "Text Files (*.txt)")
        if path: self.process_file2(path)

    def process_file2(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.file2_lines = [line.rstrip("\n").lstrip("\ufeff") for line in f]
            QMessageBox.information(self, lang_mgr.t("success_title"), lang_mgr.t("loaded_lines").format(len(self.file2_lines)))
            self.update_live_preview()
        except Exception as e:
            QMessageBox.critical(self, lang_mgr.t("error_title"), lang_mgr.t("error_msg").format(str(e)))

    def replace_last_quote(self, line, replacement):
        matches = list(re.finditer(r'"([^"]*)"', line))
        if not matches: return line
        last_match = matches[-1]
        start, end = last_match.start(), last_match.end()
        return line[:start] + f'"{replacement}"' + line[end:]

    def replace_quotes(self):
        if not self.file1_lines:
            QMessageBox.warning(self, lang_mgr.t("warning_title"), lang_mgr.t("load_template_first"))
            return
        if not self.file2_lines:
            QMessageBox.warning(self, lang_mgr.t("warning_title"), lang_mgr.t("load_text_first"))
            return
        
        file2_queue = deque(self.file2_lines)
        output_lines = []
        self.error_lines = []
        
        for line_num, raw_line in enumerate(self.file1_lines, start=1):
            line = raw_line.rstrip("\n")
            
            if line.strip() == "":
                output_lines.append("")
                continue
            
            # بخش Validation در حین عملیات جایگذاری
            if not self.is_valid_line(line):
                self.error_lines.append(line_num)
                output_lines.append(f"[Line {line_num} Structural Error] -> {line}")
                continue
            
            if file2_queue:
                rep = file2_queue.popleft()
                if rep.strip() != "":
                    line = self.replace_last_quote(line, rep)
            
            output_lines.append(line)
        
        self.text_area.setPlainText("\n".join(output_lines))
        
        if self.error_lines:
            QMessageBox.warning(self, lang_mgr.t("error_title"), f"{lang_mgr.t('error_lines')} {', '.join(map(str, self.error_lines))}")
        else:
            QMessageBox.information(self, lang_mgr.t("success_title"), lang_mgr.t("done_lines").format(len(output_lines)))

    def save_file(self):
        if not self.text_area.toPlainText():
            QMessageBox.warning(self, lang_mgr.t("warning_title"), lang_mgr.t("replace_first"))
            return
            
        path, _ = QFileDialog.getSaveFileName(self, lang_mgr.t("save_dialog"), "", "Text Files (*.txt)")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text_area.toPlainText())
            QMessageBox.information(self, lang_mgr.t("success_title"), lang_mgr.t("saved_success"))
        except Exception as e:
            QMessageBox.critical(self, lang_mgr.t("error_title"), lang_mgr.t("error_msg").format(str(e)))

# ==========================================
# پنجره اصلی (به همراه سیستم تغییر تم چشمی)
# ==========================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(750, 550)
        self.is_dark_mode = True
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(15, 10, 15, 0)
        top_bar.setSpacing(10)
        
        self.theme_btn = QPushButton("☀️ Light")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; border: 1px solid #7f8c8d;
                border-radius: 4px; padding: 4px 10px; font-weight: bold;
            }
            QPushButton:hover { background-color: #7f8c8d; color: white; }
        """)
        self.theme_btn.clicked.connect(self.toggle_theme)
        
        self.lang_combo = QComboBox()
        self.lang_combo.setCursor(Qt.PointingHandCursor)
        self.lang_combo.setStyleSheet("""
            QComboBox {
                background-color: #2d2d2d; color: #ffffff; border: 1px solid #3498db;
                border-radius: 4px; padding: 4px 10px; font-weight: bold; min-width: 100px;
            }
            QComboBox::drop-down { border: none; }
        """)
        
        for code, name in lang_mgr.available_langs.items():
            self.lang_combo.addItem(name, code)
            
        index = self.lang_combo.findData(lang_mgr.current_lang)
        if index >= 0:
            self.lang_combo.setCurrentIndex(index)
            
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        
        top_bar.addStretch()
        top_bar.addWidget(self.theme_btn)
        top_bar.addWidget(self.lang_combo)
        main_layout.addLayout(top_bar)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                padding: 12px 25px; font-size: 13px; font-weight: bold;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 3px;
            }
            QTabBar::tab:selected { border-bottom: 3px solid #3498db; }
        """)
        
        self.tabs.addTab(ExtractQuotesTab(), "")
        self.tabs.addTab(ReplaceQuotesTab(), "")
        
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
        
        lang_mgr.lang_changed.connect(self.update_texts)
        self.update_texts()
        self.apply_theme()

    def change_language(self, index):
        lang_code = self.lang_combo.itemData(index)
        if lang_code:
            lang_mgr.set_lang(lang_code)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.theme_btn.setText("🌙 Dark" if not self.is_dark_mode else "☀️ Light")
        self.apply_theme()

    def apply_theme(self):
        palette = QPalette()
        if self.is_dark_mode:
            palette.setColor(QPalette.Window, QColor("#1e1e1e"))
            palette.setColor(QPalette.WindowText, QColor("#ffffff"))
            palette.setColor(QPalette.Base, QColor("#2d2d2d"))
            palette.setColor(QPalette.Text, QColor("#ffffff"))
            palette.setColor(QPalette.Button, QColor("#3d3d3d"))
            palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
            
            tab_bg, tab_fg, pane_bg = "#2d2d2d", "#b0b0b0", "#1e1e1e"
            self.lang_combo.setStyleSheet("QComboBox { background-color: #2d2d2d; color: #ffffff; border: 1px solid #3498db; border-radius: 4px; padding: 4px 10px; font-weight: bold; min-width: 100px; } QComboBox::drop-down { border: none; }")
            self.theme_btn.setStyleSheet("QPushButton { background-color: transparent; color: #ffffff; border: 1px solid #7f8c8d; border-radius: 4px; padding: 4px 10px; font-weight: bold; } QPushButton:hover { background-color: #7f8c8d; color: white; }")
        else:
            palette.setColor(QPalette.Window, QColor("#f5f5f5"))
            palette.setColor(QPalette.WindowText, QColor("#000000"))
            palette.setColor(QPalette.Base, QColor("#ffffff"))
            palette.setColor(QPalette.Text, QColor("#000000"))
            palette.setColor(QPalette.Button, QColor("#e0e0e0"))
            palette.setColor(QPalette.ButtonText, QColor("#000000"))
            
            tab_bg, tab_fg, pane_bg = "#e0e0e0", "#555555", "#f5f5f5"
            self.lang_combo.setStyleSheet("QComboBox { background-color: #ffffff; color: #000000; border: 1px solid #3498db; border-radius: 4px; padding: 4px 10px; font-weight: bold; min-width: 100px; } QComboBox::drop-down { border: none; }")
            self.theme_btn.setStyleSheet("QPushButton { background-color: transparent; color: #000000; border: 1px solid #7f8c8d; border-radius: 4px; padding: 4px 10px; font-weight: bold; } QPushButton:hover { background-color: #7f8c8d; color: white; }")

        QApplication.instance().setPalette(palette)
        
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background-color: {pane_bg}; }}
            QTabBar::tab {{
                background-color: {tab_bg}; color: {tab_fg};
                padding: 12px 25px; font-size: 13px; font-weight: bold;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 3px;
            }}
            QTabBar::tab:selected {{
                background-color: {pane_bg}; color: #3498db; border-bottom: 3px solid #3498db;
            }}
        """)

    def update_texts(self):
        self.setWindowTitle(lang_mgr.t("app_title"))
        self.tabs.setTabText(0, lang_mgr.t("tab_extract"))
        self.tabs.setTabText(1, lang_mgr.t("tab_replace"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    initial_direction = Qt.RightToLeft if lang_mgr.current_lang in ["fa", "ar", "he"] else Qt.LeftToRight
    app.setLayoutDirection(initial_direction)
    
    window = MainWindow()
    window.resize(850, 600)
    window.show()
    sys.exit(app.exec())
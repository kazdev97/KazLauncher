from functools import partial
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QDialog, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QCheckBox, QComboBox, QColorDialog, QProgressBar
from kaz_launcher.config import resources
from .widgets import AnimatedButton
class FixErrorDialog(QDialog):
    def __init__(self, error_title, error_desc, fix_suggestion, lang_dict, parent=None, icon_svg=None):
        super().__init__(parent)
        self.lang_dict = lang_dict
        self.old_pos = None
        self.icon_data = icon_svg if icon_svg is not None else resources.ALERT_ICON_SVG
        self.init_ui(error_title, error_desc, fix_suggestion)
        self.apply_styles(parent.current_accent_color if parent else '#1DB954')
        self.setWindowOpacity(0)
        self.fade_in_animation = QPropertyAnimation(self, b'windowOpacity')
        self.fade_in_animation.setDuration(300)
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1)
        self.fade_in_animation.setEasingCurve(QEasingCurve.OutCubic)
    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in_animation.start()
    def init_ui(self, error_title, error_desc, fix_suggestion):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(480, 280)
        container = QFrame(self)
        container.setObjectName('dialogContainer')
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 20)
        main_layout.setSpacing(15)
        self.header_frame = QFrame()
        self.header_frame.setObjectName('headerFrame')
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(20, 15, 20, 15)
        icon_pixmap = QPixmap()
        icon_pixmap.loadFromData(self.icon_data)
        icon_label = QLabel()
        icon_label.setPixmap(icon_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        dialog_title_label = QLabel(self.lang_dict.get('error_dialog_title', 'Error Detected'))
        dialog_title_label.setObjectName('dialogTitle')
        header_layout.addWidget(icon_label)
        header_layout.addSpacing(10)
        header_layout.addWidget(dialog_title_label)
        header_layout.addStretch()
        body_layout = QVBoxLayout()
        body_layout.setContentsMargins(25, 0, 25, 0)
        body_layout.setSpacing(10)
        error_title_label = QLabel(error_title)
        error_title_label.setObjectName('errorTitle')
        error_title_label.setWordWrap(True)
        error_desc_label = QLabel(error_desc)
        error_desc_label.setObjectName('errorDesc')
        error_desc_label.setWordWrap(True)
        fix_suggestion_label = QLabel(fix_suggestion)
        fix_suggestion_label.setObjectName('fixSuggestion')
        fix_suggestion_label.setWordWrap(True)
        body_layout.addWidget(error_title_label)
        body_layout.addWidget(error_desc_label)
        body_layout.addSpacing(5)
        body_layout.addWidget(fix_suggestion_label)
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(25, 0, 25, 0)
        self.cancel_button = AnimatedButton(self.lang_dict.get('cancel_button', 'Cancel'))
        self.cancel_button.setObjectName('cancelButton')
        self.cancel_button.clicked.connect(self.reject)
        self.fix_button = AnimatedButton(self.lang_dict.get('fix_button', 'Fix It'))
        self.fix_button.setObjectName('fixButton')
        self.fix_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.fix_button)
        main_layout.addWidget(self.header_frame)
        main_layout.addLayout(body_layout)
        main_layout.addStretch()
        main_layout.addLayout(button_layout)
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(container)
    def apply_styles(self, accent_color):
        from kaz_launcher.ui.themes import accent_rgba, lighten_color
        accent_hover = lighten_color(accent_color, 0.12)
        glass = 'rgba(255, 255, 255, 0.07)'
        border = 'rgba(255, 255, 255, 0.1)'
        self.setStyleSheet(f'\n            QDialog {{ background: transparent; }}\n            #dialogContainer {{\n                background-color: rgba(14, 14, 20, 0.92);\n                border: 1px solid {border};\n                border-radius: 14px;\n            }}\n            #headerFrame {{\n                background-color: {glass};\n                border-bottom: 1px solid rgba(255, 255, 255, 0.06);\n                border-top-left-radius: 14px;\n                border-top-right-radius: 14px;\n            }}\n            #dialogTitle {{ font-size: 14pt; color: #EEEEF2; font-weight: bold; }}\n            #errorTitle {{ font-size: 11pt; color: {accent_color}; font-weight: bold; }}\n            #errorDesc, #fixSuggestion {{ font-size: 10pt; color: #A8A8B8; }}\n            #fixSuggestion {{ color: #EEEEF2; }}\n            #cancelButton, #fixButton {{ padding: 10px 20px; border-radius: 10px; font-weight: bold; }}\n            #cancelButton {{\n                background-color: {glass};\n                color: #EEEEF2;\n                border: 1px solid {border};\n            }}\n            #fixButton {{ background-color: {accent_color}; color: #0c0c10; border: none; }}\n            #fixButton:hover {{ background-color: {accent_hover}; }}\n        ')
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.header_frame.underMouse():
                self.old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event):
        self.old_pos = None
    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
class UpdateDialog(QDialog):
    update_requested = Signal()
    def __init__(self, status_info, fonts, lang_dict, parent=None):
        super().__init__(parent)
        self.status_info = status_info
        self.fonts = fonts
        self.lang_dict = lang_dict
        self._update_started = False
        self.icons = {'check': b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="#78f542" viewBox="0 0 256 256"><path d="M229.66,77.66l-128,128a8,8,0,0,1-11.32,0l-56-56a8,8,0,0,1,11.32-11.32L96,188.69,218.34,66.34a8,8,0,0,1,11.32,11.32Z"></path></svg>', 'download': b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="#ff5555" viewBox="0 0 256 256"><path d="M208,152v48a8,8,0,0,1-8,8H56a8,8,0,0,1-8-8V152a8,8,0,0,1,16,0v40H192V152a8,8,0,0,1,16,0Zm-85.66,5.66a8,8,0,0,0,11.32,0l48-48a8,8,0,0,0-11.32-11.32L136,132.69V40a8,8,0,0,0-16,0v92.69L85.66,98.34a8,8,0,0,0-11.32,11.32Z"></path></svg>'}
        self.init_ui()
        self.setWindowOpacity(0)
        self.fade_in_animation = QPropertyAnimation(self, b'windowOpacity')
        self.fade_in_animation.setDuration(300)
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1)
        self.fade_in_animation.setEasingCurve(QEasingCurve.OutCubic)
    def showEvent(self, event):
        super().showEvent(event)
        self.fade_in_animation.start()
    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(420, 275)
        container = QFrame(self)
        container.setObjectName('updateDialogContainer')
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        title_label = QLabel(self.lang_dict.get('update_status_title', 'Update Status'))
        title_label.setObjectName('updateDialogTitle')
        title_label.setFont(self.fonts['subtitle'])
        info_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_pixmap = QPixmap()
        icon_data = self.icons['download'] if self.status_info['is_update_available'] else self.icons['check']
        icon_pixmap.loadFromData(icon_data)
        icon_label.setPixmap(icon_pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        message_label = QLabel(self.status_info['text'])
        message_label.setObjectName('updateDialogMessage')
        message_label.setFont(self.fonts['main'])
        message_label.setWordWrap(True)
        info_layout.addWidget(icon_label)
        info_layout.addWidget(message_label, 1)
        # Zona de progreso (oculta hasta que se inicia la descarga).
        self.progress_label = QLabel('')
        self.progress_label.setObjectName('updateProgressLabel')
        self.progress_label.setFont(self.fonts['main'])
        self.progress_label.setWordWrap(True)
        self.progress_label.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName('updateProgressBar')
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(22)
        self.progress_bar.setVisible(False)
        button_layout = QHBoxLayout()
        self.update_button = AnimatedButton(self.lang_dict.get('update_button', 'Update'))
        self.update_button.setObjectName('updateButton')
        self.update_button.setFont(self.fonts['main'])
        self.update_button.setVisible(self.status_info['is_update_available'])
        self.update_button.clicked.connect(self.start_update)
        self.close_button = AnimatedButton(self.lang_dict.get('close', 'Close'))
        self.close_button.setObjectName('closeButton')
        self.close_button.setFont(self.fonts['main'])
        self.close_button.clicked.connect(self.close)
        button_layout.addStretch()
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.close_button)
        main_layout.addWidget(title_label)
        main_layout.addLayout(info_layout)
        main_layout.addWidget(self.progress_label)
        main_layout.addWidget(self.progress_bar)
        main_layout.addStretch()
        main_layout.addLayout(button_layout)
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(container)
        self.set_styles()
    def start_update(self):
        """El usuario pulsa «Actualizar»: muestra la barra de progreso y avisa al launcher."""
        if self._update_started:
            return
        self._update_started = True
        self.update_button.setVisible(False)
        self.close_button.setEnabled(False)
        self.progress_label.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText(self.lang_dict.get('update_downloading', 'Descargando actualización... {pct}%').format(pct=0))
        self.update_requested.emit()
    def set_progress(self, pct: int):
        """Actualiza la barra de progreso de la descarga."""
        pct = max(0, min(100, int(pct)))
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(pct)
        self.progress_label.setText(self.lang_dict.get('update_downloading', 'Descargando actualización... {pct}%').format(pct=pct))
    def set_status(self, message: str):
        """Texto de estado (descargando / verificando integridad...)."""
        self.progress_label.setText(message)
        self.progress_bar.setVisible(message != 'Verificando integridad...')
    def show_download_failed(self, message: str):
        """Vuelve al estado inicial y muestra el error para reintentar o cerrar."""
        self._update_started = False
        self.progress_label.setText(message)
        self.progress_bar.setVisible(False)
        self.close_button.setEnabled(True)
        self.close_button.setVisible(True)
        if self.status_info.get('is_update_available'):
            self.update_button.setVisible(True)
    def set_styles(self):
        accent = self.parent().current_accent_color if self.parent() else '#1DB954'
        # Contraste automático: texto oscuro sobre acentos claros (p. ej. botón blanco).
        color = QColor(accent)
        luminance = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
        button_text = '#0c0c10' if luminance > 150 else '#f8f8f2'
        hover_color = color.lighter(112).name() if luminance > 150 else color.darker(112).name()
        self.setStyleSheet(f'\n            #updateDialogContainer {{ background-color: #282a36; border-radius: 10px; border: 1px solid #44475a; }}\n            #updateDialogTitle {{ color: #f8f8f2; }}\n            #updateDialogMessage {{ color: #bd93f9; }}\n            #updateProgressLabel {{ color: #f8f8f2; font-size: 9pt; }}\n            #updateProgressBar {{ background-color: #44475a; border: 1px solid #6272a4; border-radius: 5px; text-align: center; }}\n            #updateProgressBar::chunk {{ background-color: {accent}; border-radius: 5px; }}\n            QPushButton {{ outline: none; }}\n            #updateButton, #closeButton {{ padding: 8px 16px; border-radius: 5px; font-weight: bold; }}\n            #updateButton {{ background-color: {accent}; color: {button_text}; }}\n            #updateButton:hover {{ background-color: {hover_color}; }}\n            #closeButton {{ background-color: #6272a4; color: #f8f8f2; }}\n        ')
class VersionSelectionDialog(QDialog):
    def __init__(self, title, prompt, versions, action_text, lang_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.lang_dict = lang_dict
        self.versions = versions
        self.selected_version = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(prompt))
        self.list_widget = QListWidget()
        self.list_widget.addItems(self.versions)
        layout.addWidget(self.list_widget)
        button_box = QHBoxLayout()
        ok_button = QPushButton(action_text)
        ok_button.clicked.connect(self.on_accept)
        cancel_button = QPushButton(lang_dict.get('cancel', 'Cancel'))
        cancel_button.clicked.connect(self.reject)
        button_box.addStretch()
        button_box.addWidget(cancel_button)
        button_box.addWidget(ok_button)
        layout.addLayout(button_box)
    def on_accept(self):
        if self.list_widget.currentItem():
            self.selected_version = self.list_widget.currentItem().text()
            self.accept()
    def get_selected_version(self):
        return self.selected_version
class PasswordDialog(QDialog):
    def __init__(self, title, prompt, lang_dict, parent=None):
        super().__init__(parent)
        self.lang_dict = lang_dict
        self.password = None
        self.init_ui(title, prompt)
        self.apply_styles(parent.current_accent_color if parent else '#1DB954')
    def init_ui(self, title, prompt):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(400, 200)
        container = QFrame(self)
        container.setObjectName('dialogContainer')
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        title_label = QLabel(title)
        title_label.setObjectName('dialogTitle')
        title_label.setStyleSheet('font-weight: bold; font-size: 12pt; color: #f8f8f2;')
        prompt_label = QLabel(prompt)
        prompt_label.setWordWrap(True)
        prompt_label.setStyleSheet('color: #bd93f9;')
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText(self.lang_dict.get('enter_password', 'Introduce la contraseña'))
        self.password_input.returnPressed.connect(self.on_accept)
        button_layout = QHBoxLayout()
        cancel_btn = AnimatedButton(self.lang_dict.get('cancel', 'Cancelar'))
        cancel_btn.setObjectName('cancelButton')
        cancel_btn.clicked.connect(self.reject)
        ok_btn = AnimatedButton(self.lang_dict.get('ok', 'Aceptar'))
        ok_btn.setObjectName('okButton')
        ok_btn.clicked.connect(self.on_accept)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addWidget(title_label)
        layout.addWidget(prompt_label)
        layout.addWidget(self.password_input)
        layout.addLayout(button_layout)
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(container)
    def on_accept(self):
        self.password = self.password_input.text()
        self.accept()
    def get_password(self):
        return self.password
    def apply_styles(self, accent_color):
        self.setStyleSheet(f'\n            QDialog {{ background: transparent; }}\n            #dialogContainer {{ background-color: #282a36; border: 1px solid #44475a; border-radius: 12px; }}\n            QLineEdit {{\n                background-color: #44475a;\n                color: #f8f8f2;\n                border: 1px solid #6272a4;\n                border-radius: 5px;\n                padding: 8px;\n            }}\n            #cancelButton, #okButton {{ color: #f8f8f2; padding: 8px 16px; border-radius: 5px; font-weight: bold; }}\n            #cancelButton {{ background-color: #6272a4; }}\n            #okButton {{ background-color: {accent_color}; }}\n        ')
class GlassGradientDialog(QDialog):
    """Editor del degradado de fondo del tema Glass."""
    DEFAULT_COLORS = ['#1E1B4B', '#312E81', '#0E7490', '#134E4A']
    def __init__(self, parent, lang_dict, initial_colors=None):
        super().__init__(parent)
        self.lang_dict = lang_dict
        self.colors = list(initial_colors or self.DEFAULT_COLORS)
        if len(self.colors) < 4:
            self.colors = (self.colors + self.DEFAULT_COLORS)[:4]
        self.colors = self.colors[:4]
        self.init_ui()
        self.apply_styles(parent.current_accent_color if parent else '#1DB954')
    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(440, 340)
        container = QFrame(self)
        container.setObjectName('dialogContainer')
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        title_label = QLabel(self.lang_dict.get('glass_gradient_title', 'Degradado de fondo (Glass)'))
        title_label.setObjectName('dialogTitle')
        hint_label = QLabel(self.lang_dict.get('glass_gradient_hint', 'Elige un color para cada punto del degradado.'))
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet('color: #bd93f9;')
        self.preview_label = QLabel()
        self.preview_label.setFixedHeight(46)
        self.color_buttons = []
        for index in range(4):
            row = QHBoxLayout()
            color_label = QLabel(self.lang_dict.get('glass_gradient_stop', 'Color {n}').format(n=index + 1))
            color_label.setStyleSheet('color: #f8f8f2;')
            btn = QPushButton()
            btn.setFixedHeight(34)
            btn.clicked.connect(partial(self._pick_color, index))
            self.color_buttons.append(btn)
            row.addWidget(color_label)
            row.addWidget(btn, 1)
            layout.addLayout(row)
        self._update_preview()
        button_layout = QHBoxLayout()
        restore_btn = AnimatedButton(self.lang_dict.get('restore_defaults', 'Restaurar'))
        restore_btn.setObjectName('cancelButton')
        restore_btn.clicked.connect(self._restore_defaults)
        cancel_btn = AnimatedButton(self.lang_dict.get('cancel_button', 'Cancelar'))
        cancel_btn.setObjectName('cancelButton')
        cancel_btn.clicked.connect(self.reject)
        ok_btn = AnimatedButton(self.lang_dict.get('ok', 'Aceptar'))
        ok_btn.setObjectName('okButton')
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(restore_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addWidget(title_label)
        layout.addWidget(hint_label)
        layout.addWidget(self.preview_label)
        layout.addStretch()
        layout.addLayout(button_layout)
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(container)
    def _pick_color(self, index: int):
        color = QColorDialog.getColor(QColor(self.colors[index]), self, 'Color')
        if color.isValid():
            self.colors[index] = color.name()
            self._update_preview()
    def _restore_defaults(self):
        self.colors = list(self.DEFAULT_COLORS)
        self._update_preview()
    def _update_preview(self):
        c0, c1, c2, c3 = self.colors
        gradient = f'qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 {c0}, stop: 0.45 {c1}, stop: 0.72 {c2}, stop: 1 {c3})'
        self.preview_label.setStyleSheet(f'border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.25); background: {gradient};')
        for index, btn in enumerate(self.color_buttons):
            btn.setText(self.colors[index].upper())
            btn.setStyleSheet(f'background-color: {self.colors[index]}; color: #ffffff; border: 1px solid rgba(255, 255, 255, 0.35); border-radius: 6px;')
    def get_colors(self) -> list:
        return list(self.colors)
    def apply_styles(self, accent_color):
        self.setStyleSheet(f'\n            QDialog {{ background: transparent; }}\n            #dialogContainer {{ background-color: #282a36; border: 1px solid #44475a; border-radius: 12px; }}\n            #dialogTitle {{ color: #f8f8f2; font-weight: bold; font-size: 12pt; }}\n            QPushButton {{ outline: none; }}\n            #cancelButton, #okButton {{ color: #f8f8f2; padding: 8px 16px; border-radius: 5px; font-weight: bold; }}\n            #cancelButton {{ background-color: #6272a4; }}\n            #okButton {{ background-color: {accent_color}; color: #0c0c10; }}\n        ')
class AdvancedSettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.lang_dict = resources.LANGUAGES[self.parent_window.current_language]
        self.setWindowTitle(self.lang_dict.get('advanced_settings', 'Advanced Settings'))
        self.setMinimumWidth(500)
        self.java_opt_enabled = bool(self.parent_window.settings.get('java_opt_enabled', True))
        self.java_opt_checkbox = QCheckBox(self.lang_dict.get('optimize_java', 'Optimizar Java (recomendado)'))
        self.java_opt_checkbox.setChecked(self.java_opt_enabled)
        java_path_from_settings = self.parent_window.settings.get('java_path', '')
        self.java_path_input = QLineEdit(java_path_from_settings)
        self.java_path_input.setPlaceholderText('Auto (Recommended)')
        self.init_ui()
        self.apply_styles()
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        java_opt_label = QLabel(self.lang_dict.get('java_optimization', 'Optimización de Java'))
        java_opt_label.setFont(self.parent_window.subtitle_font)
        java_path_label = QLabel(self.lang_dict.get('java_path', 'Java Executable Path'))
        java_path_label.setFont(self.parent_window.subtitle_font)
        java_path_button = QPushButton()
        java_path_button.setIcon(self.parent_window.folder_icon)
        java_path_button.setFixedSize(36, 36)
        java_path_button.setIconSize(QSize(24, 24))
        java_path_button.clicked.connect(self.open_java_path_dialog)
        java_path_layout = QHBoxLayout()
        java_path_layout.addWidget(self.java_path_input)
        java_path_layout.addWidget(java_path_button)
        layout.addWidget(java_opt_label)
        layout.addWidget(self.java_opt_checkbox)
        layout.addSpacing(10)
        layout.addWidget(java_path_label)
        layout.addLayout(java_path_layout)
        layout.addStretch()
        close_button = AnimatedButton(self.lang_dict.get('save_and_close', 'Save & Close'))
        close_button.setObjectName('closeButton')
        close_button.setFont(self.parent_window.minecraft_font)
        close_button.clicked.connect(self.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
    def accept(self):
        self.parent_window.settings['java_opt_enabled'] = self.java_opt_checkbox.isChecked()
        self.parent_window.settings['java_path'] = self.java_path_input.text()
        self.parent_window.save_settings()
        super().accept()
    def open_java_path_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Java Executable', '', 'Executables (java.exe);;All files (*)')
        if file_path:
            self.java_path_input.setText(file_path)
    def apply_styles(self):
        accent = self.parent_window.current_accent_color
        self.setStyleSheet(f'\n            QDialog {{ background-color: #282a36; border: 1px solid #44475a; }}\n            QLabel {{ color: #f8f8f2; }}\n            QLineEdit {{\n                background-color: #44475a;\n                color: #f8f8f2;\n                border: 1px solid #6272a4;\n                border-radius: 5px;\n                padding: 8px;\n                font-size: 10pt;\n            }}\n            QCheckBox {{\n                color: #f8f8f2;\n                font-size: 10pt;\n            }}\n            QPushButton {{\n                background-color: #44475a;\n                border: 1px solid #6272a4;\n                border-radius: 5px;\n            }}\n            #closeButton {{ \n                color: #282a36; \n                padding: 8px 16px; \n                border-radius: 5px; \n                background-color: {accent}; \n                font-weight: bold;\n            }}\n        ')
class NewInstallationDialog(QDialog):
    """Diálogo para instalar Vanilla / Forge / NeoForge / Fabric."""
    def __init__(self, parent_window, lang_dict):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.lang_dict = lang_dict
        self._loading_mc = False
        self.setWindowTitle(lang_dict.get('new_installation_title', 'Nueva instalación'))
        self.setMinimumWidth(420)
        self._build_ui()
        self._apply_styles()
        self.loader_combo.currentIndexChanged.connect(self._on_loader_changed)
        self.mc_version_combo.currentIndexChanged.connect(self._on_mc_version_changed)
        self._on_loader_changed(self.loader_combo.currentIndex())
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        title = QLabel(self.lang_dict.get('new_installation_title', 'Nueva instalación'))
        title.setObjectName('dialogTitle')
        layout.addWidget(title)
        self.loader_combo = QComboBox()
        for key, label in [('vanilla', self.lang_dict.get('vanilla', 'Vanilla')), ('forge', self.lang_dict.get('forge', 'Forge')), ('neoforge', self.lang_dict.get('neoforge', 'NeoForge')), ('fabric', self.lang_dict.get('fabric', 'Fabric'))]:
            self.loader_combo.addItem(label, key)
        self.mc_version_combo = QComboBox()
        self.loader_version_combo = QComboBox()
        self.loader_version_label = QLabel(self.lang_dict.get('loader_version_label', 'Versión del mod loader'))
        layout.addWidget(QLabel(self.lang_dict.get('version_type', 'Tipo')))
        layout.addWidget(self.loader_combo)
        layout.addWidget(QLabel(self.lang_dict.get('version', 'Versión de Minecraft')))
        layout.addWidget(self.mc_version_combo)
        layout.addWidget(self.loader_version_label)
        layout.addWidget(self.loader_version_combo)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = AnimatedButton(self.lang_dict.get('cancel_button', 'Cancelar'))
        cancel_btn.clicked.connect(self.reject)
        self.install_btn = AnimatedButton(self.lang_dict.get('install_button', 'Instalar'))
        self.install_btn.setObjectName('installButton')
        self.install_btn.clicked.connect(self.accept)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(self.install_btn)
        layout.addLayout(buttons)
    def _apply_styles(self):
        accent = self.parent_window.current_accent_color
        self.setStyleSheet(f'\n            QDialog {{ background-color: #282a36; }}\n            QLabel {{ color: #f8f8f2; }}\n            QComboBox {{\n                background-color: #44475a;\n                color: #f8f8f2;\n                border: 1px solid #6272a4;\n                border-radius: 5px;\n                padding: 6px;\n                min-height: 28px;\n            }}\n            #installButton {{\n                background-color: {accent};\n                color: #282a36;\n                font-weight: bold;\n                padding: 8px 16px;\n                border-radius: 5px;\n            }}\n        ')
    def _current_loader(self) -> str:
        return self.loader_combo.currentData() or 'vanilla'
    def _on_loader_changed(self, _index: int):
        loader = self._current_loader()
        show_loader_ver = loader != 'vanilla'
        self.loader_version_label.setVisible(show_loader_ver)
        self.loader_version_combo.setVisible(show_loader_ver)
        self._populate_mc_versions(loader)
    def _populate_mc_versions(self, loader: str):
        from kaz_launcher.core.manual_install import get_minecraft_versions_for_loader
        self.mc_version_combo.blockSignals(True)
        self.mc_version_combo.clear()
        self.mc_version_combo.addItem(self.lang_dict.get('loading_versions', 'Cargando versiones...'), '')
        self.mc_version_combo.blockSignals(False)
        class McVersionLoader:
            def __init__(self, loader_id):
                self.loader_id = loader_id
                self.versions = []
            def run(self):
                self.versions = get_minecraft_versions_for_loader(self.loader_id)
        versions = get_minecraft_versions_for_loader(loader)
        self.mc_version_combo.blockSignals(True)
        self.mc_version_combo.clear()
        if not versions:
            self.mc_version_combo.addItem(self.lang_dict.get('no_versions_found', 'Sin versiones'), '')
        else:
            for ver in versions:
                self.mc_version_combo.addItem(ver, ver)
        self.mc_version_combo.blockSignals(False)
        self._on_mc_version_changed(self.mc_version_combo.currentIndex())
    def _on_mc_version_changed(self, _index: int):
        loader = self._current_loader()
        mc_version = self.mc_version_combo.currentData() or ''
        self.loader_version_combo.clear()
        if loader == 'vanilla' or not mc_version:
            return None
        else:
            from kaz_launcher.core.manual_install import get_loader_versions_for
            versions = get_loader_versions_for(loader, mc_version)
            if not versions:
                self.loader_version_combo.addItem(self.lang_dict.get('no_loader_versions', 'Sin versiones'), '')
                return
            else:
                for ver in versions:
                    self.loader_version_combo.addItem(ver, ver)
    def get_selection(self) -> dict:
        loader = self._current_loader()
        mc_version = self.mc_version_combo.currentData() or ''
        loader_version = ''
        if loader != 'vanilla':
            loader_version = self.loader_version_combo.currentData() or self.loader_version_combo.currentText() or ''
        return {'loader': loader, 'minecraft_version': mc_version, 'loader_version': loader_version}
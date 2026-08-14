from PySide6.QtGui import QColor
def lighten_color(hex_color, amount=0.15):
    try:
        color = QColor(hex_color)
        h, s, l, a = color.getHslF()
        l = min(1.0, l + amount)
        return QColor.fromHslF(h, s, l, a).name()
    except Exception:
        return hex_color
def accent_rgba(hex_color, alpha=0.35):
    try:
        c = QColor(hex_color)
        return f'rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})'
    except Exception:
        return f'rgba(29, 185, 84, {alpha})'
def get_dark_theme(accent_color='#1DB954', glass_opacity=88, secondary_accent=None):
    """glass_opacity: 50–100 (%). Más alto = paneles más opacos.
    secondary_accent: color para bordes/brillos (sombra) de los botones.
    """
    accent_hover = lighten_color(accent_color, 0.12)
    accent_soft = accent_rgba(accent_color, 0.22)
    accent_glow = accent_rgba(secondary_accent or accent_color, 0.45)
    secondary_soft = accent_rgba(secondary_accent or accent_color, 0.3)
    accent_muted = accent_rgba(accent_color, 0.12)
    t = max(50, min(100, int(glass_opacity))) / 100.0
    shell_alpha = 0.72 + (t - 0.5) * 0.46
    panel_alpha = 0.78 + (t - 0.5) * 0.38
    glass_mix = 0.04 + (t - 0.5) * 0.07
    glass_panel = f'rgba(26, 26, 34, {panel_alpha:.2f})'
    glass_panel_strong = f'rgba(34, 34, 44, {min(0.98, panel_alpha + 0.06):.2f})'
    shell_bg = f'rgba(14, 14, 20, {shell_alpha:.2f})'
    glass_border = f'rgba(255, 255, 255, {0.08 + glass_mix:.2f})'
    glass_border_soft = f'rgba(255, 255, 255, {0.04 + glass_mix * 0.5:.2f})'
    neumo_highlight = f'rgba(255, 255, 255, {0.06 + glass_mix:.2f})'
    neumo_shadow = 'rgba(0, 0, 0, 0.38)'
    inset_field = f'rgba(0, 0, 0, {0.22 + (1 - t) * 0.12:.2f})'
    text_primary = '#EEEEF2'
    text_secondary = '#A8A8B8'
    text_muted = '#6E6E82'
    return f'''\n        /* —— Ventana principal (glass) —— */\n        #container {{\n            background-color: {shell_bg};\n            border-radius: 18px;\n            border: 1px solid {glass_border};\n            border-top: 1px solid {neumo_highlight};\n            border-bottom: 1px solid {neumo_shadow};\n        }}\n        #titleBar {{\n            background-color: rgba(255, 255, 255, 0.04);\n            border-top-left-radius: 17px;\n            border-top-right-radius: 17px;\n            border-bottom: 1px solid {glass_border_soft};\n        }}\n        #titleLabel {{\n            color: {text_primary};\n            font-weight: bold;\n        }}\n        #mainPanel {{\n            background-color: {glass_panel};\n            border-radius: 14px;\n            border: 1px solid {glass_border_soft};\n            border-top: 1px solid {neumo_highlight};\n            border-bottom: 1px solid {neumo_shadow};\n        }}\n        #sectionLabel {{\n            color: {accent_color};\n            font-weight: bold;\n        }}\n        QLabel, QRadioButton, QCheckBox {{\n            color: {text_secondary};\n        }}\n        #loginStatusLabel {{\n            color: {text_muted};\n            font-size: 9pt;\n        }}\n        #versionStatusLabel {{\n            color: {text_muted};\n            font-size: 8pt;\n        }}\n\n        /* —— Campos (neumorfismo inset) —— */\n        QComboBox, QLineEdit {{\n            background-color: {inset_field};\n            border: 1px solid {glass_border_soft};\n            border-top: 1px solid rgba(0, 0, 0, 0.35);\n            border-bottom: 1px solid {neumo_highlight};\n            border-radius: 10px;\n            padding: 10px 12px;\n            color: {text_primary};\n        }}\n        QComboBox:hover, QLineEdit:hover {{\n            border: 1px solid {glass_border};\n            background-color: rgba(0, 0, 0, 0.32);\n        }}\n        QLineEdit:focus, QComboBox:focus {{\n            border: 1px solid {secondary_soft};\n            background-color: rgba(0, 0, 0, 0.34);\n        }}\n        QComboBox::drop-down {{\n            border: none;\n            width: 28px;\n        }}\n        QComboBox QAbstractItemView {{\n            background-color: rgba(22, 22, 30, 0.96);\n            border: 1px solid {glass_border};\n            border-radius: 8px;\n            color: {text_primary};\n            selection-background-color: {accent_muted};\n            selection-color: {text_primary};\n        }}\n\n        /* —— Botones primarios (color de acento del usuario) —— */\n        QPushButton {{\n            background-color: {accent_color};\n            color: #0c0c10;\n            border: none;\n            border-radius: 10px;\n            padding: 12px 16px;\n            font-weight: bold;\n        }}\n        QPushButton:hover {{\n            background-color: {accent_hover};\n        }}\n        QPushButton:pressed {{\n            background-color: {accent_hover};\n        }}\n        #launchButton {{\n            background-color: {accent_color};\n            border-radius: 12px;\n            border: 1px solid {accent_glow};\n            padding: 10px 16px;\n            margin: 0;\n        }}\n        #launchButton:hover {{\n            background-color: {accent_hover};\n        }}\n        #launchButtonWrap {{\n            background: transparent;\n        }}\n        #colorPickerButton {{\n            padding: 5px;\n            background-color: {glass_panel_strong};\n            color: {text_primary};\n            border: 1px solid {glass_border_soft};\n        }}\n        #colorPickerButton:hover {{\n            border: 1px solid {secondary_soft};\n        }}\n        #colorPreview {{\n            border: 2px solid {glass_border};\n            border-radius: 10px;\n        }}\n\n        /* —— Botones secundarios / cristal —— */\n        #advancedButton, #openModsFolderButton, #openModpacksFolderButton,\n        #newInstallationButton, #remoteInstanceVerifyButton {{\n            background-color: {glass_panel_strong};\n            color: {text_primary};\n            border: 1px solid {glass_border_soft};\n            border-top: 1px solid {neumo_highlight};\n            font-weight: normal;\n        }}\n        #advancedButton:hover, #openModsFolderButton:hover, #openModpacksFolderButton:hover,\n        #newInstallationButton:hover, #remoteInstanceVerifyButton:hover {{\n            background-color: rgba(255, 255, 255, 0.1);\n            border: 1px solid {secondary_soft};\n            color: {text_primary};\n        }}\n        #advancedButton:checked {{\n            background-color: {accent_muted};\n            border: 1px solid {secondary_soft};\n        }}\n\n        #closeButton, #minimizeButton {{\n            font-size: 12pt;\n            font-weight: bold;\n            border-radius: 15px;\n            border: none;\n        }}\n        #closeButton {{\n            background-color: rgba(226, 61, 40, 0.88);\n            color: white;\n        }}\n        #closeButton:hover {{\n            background-color: rgba(248, 79, 57, 0.95);\n        }}\n        #minimizeButton {{\n            background-color: rgba(248, 179, 57, 0.88);\n            color: white;\n        }}\n        #minimizeButton:hover {{\n            background-color: rgba(255, 193, 78, 0.95);\n        }}\n\n        QProgressBar {{\n            border: 1px solid {glass_border_soft};\n            border-radius: 10px;\n            text-align: center;\n            background-color: {inset_field};\n            color: {text_primary};\n            font-weight: bold;\n        }}\n        QProgressBar::chunk {{\n            background-color: {accent_color};\n            border-radius: 8px;\n        }}\n\n        /* —— Listas y tarjetas —— */\n        #modList, #newsList {{\n            background-color: {inset_field};\n            border: 1px solid {glass_border_soft};\n            border-radius: 12px;\n        }}\n        QListWidget {{\n            background-color: transparent;\n            border: none;\n            outline: none;\n        }}\n        QListWidget::item {{\n            background: transparent;\n            border: none;\n            padding: 4px 2px;\n        }}\n        QListWidget::item:selected {{\n            background: transparent;\n        }}\n        #modList::item:selected {{\n            background-color: {accent_muted};\n            border-radius: 10px;\n        }}\n        #modList::item:hover {{\n            background-color: rgba(255, 255, 255, 0.04);\n            border-radius: 10px;\n        }}\n\n        #modpackCard {{\n            background-color: {glass_panel};\n            border-radius: 10px;\n            border: 1px solid {glass_border_soft};\n        }}\n        #modpackCard[selected="true"] {{\n            background-color: {accent_muted};\n            border: 2px solid {accent_color};\n        }}\n        #modpackSelectIndicator {{\n            color: {text_muted};\n            font-size: 14px;\n            font-weight: bold;\n        }}\n        #modpackCard[selected="true"] #modpackSelectIndicator {{\n            color: {accent_color};\n        }}\n\n        #modCard, #versionCard, #installedModCard, #newsCard {{\n            background-color: {glass_panel};\n            border-radius: 12px;\n            border: 1px solid {glass_border_soft};\n            border-top: 1px solid {neumo_highlight};\n            border-bottom: 1px solid rgba(0, 0, 0, 0.25);\n            padding: 8px;\n        }}\n        #modCard:hover, #versionCard:hover, #installedModCard:hover, #newsCard:hover {{\n            background-color: {glass_panel_strong};\n            border: 1px solid {glass_border};\n        }}\n        #modTitle, #modName, #versionIdLabel {{\n            color: {text_primary};\n            font-weight: bold;\n        }}\n        #modAuthor, #modStats, #modDetails, #modDescription, #modFilename,\n        #versionTypeLabel, #versionSizeLabel {{\n            color: {text_secondary};\n        }}\n        #versionBadge {{\n            background-color: rgba(255, 255, 255, 0.08);\n            color: {text_primary};\n            border: 1px solid {glass_border_soft};\n            border-radius: 6px;\n            padding: 3px 8px;\n        }}\n        #modInstallButton {{\n            background-color: {accent_color};\n            color: #0c0c10;\n            font-weight: bold;\n            border: none;\n            border-radius: 8px;\n            padding: 8px 12px;\n            min-width: 90px;\n        }}\n        #modInstallButton:hover {{\n            background-color: {accent_hover};\n        }}\n        #modDeleteButton, #deleteButton {{\n            background-color: rgba(244, 67, 54, 0.85);\n            color: white;\n        }}\n        #modDeleteButton:hover, #deleteButton:hover {{\n            background-color: rgba(246, 92, 81, 0.95);\n        }}\n        #versionCard QPushButton {{\n            background-color: {glass_panel_strong};\n            color: {text_primary};\n            border: 1px solid {glass_border_soft};\n            padding: 5px 10px;\n            border-radius: 8px;\n            font-weight: normal;\n        }}\n        #versionCard #deleteButton {{\n            background-color: rgba(244, 67, 54, 0.85);\n            color: white;\n            border: none;\n        }}\n        #versionCard #deleteButton:hover {{\n            background-color: rgba(246, 92, 81, 0.95);\n        }}\n        #versionCard QPushButton:hover {{\n            border: 1px solid {secondary_soft};\n            background-color: rgba(255, 255, 255, 0.1);\n        }}\n        #versionIdLabel {{\n            font-size: 14pt;\n        }}\n        #toggleSwitch {{\n            font-family: "Segoe UI Symbol";\n            font-weight: bold;\n            border-radius: 12px;\n            border: 1px solid {glass_border_soft};\n            background-color: {inset_field};\n            color: {text_secondary};\n        }}\n        #toggleSwitch:checked {{\n            background-color: {accent_color};\n            color: #0c0c10;\n            border: 1px solid {accent_glow};\n        }}\n\n        QScrollBar:vertical {{\n            border: none;\n            background: transparent;\n            width: 10px;\n            margin: 4px 2px;\n        }}\n        QScrollBar::handle:vertical {{\n            background: rgba(255, 255, 255, 0.12);\n            min-height: 30px;\n            border-radius: 5px;\n        }}\n        QScrollBar::handle:vertical:hover {{\n            background: {secondary_soft};\n        }}\n        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{\n            height: 0;\n            border: none;\n            background: none;\n        }}\n\n        #errorLabel {{\n            color: #ff6b6b;\n            font-weight: bold;\n        }}\n\n        /* —— Pestañas (glass) —— */\n        QTabWidget::pane {{\n            border: 1px solid {glass_border_soft};\n            border-radius: 12px;\n            background-color: {glass_panel};\n            margin-top: -1px;\n        }}\n        QTabBar::tab {{\n            background-color: transparent;\n            color: {text_muted};\n            padding: 10px 16px;\n            margin-right: 4px;\n            border-top-left-radius: 10px;\n            border-top-right-radius: 10px;\n            border: 1px solid transparent;\n        }}\n        QTabBar::tab:selected {{\n            background-color: {glass_panel_strong};\n            color: {text_primary};\n            border: 1px solid {glass_border_soft};\n            border-bottom: 2px solid {accent_color};\n        }}\n        QTabBar::tab:hover {{\n            background-color: rgba(255, 255, 255, 0.05);\n            color: {text_primary};\n        }}\n\n        QCheckBox, QRadioButton {{\n            spacing: 8px;\n        }}\n        QCheckBox::indicator, QRadioButton::indicator {{\n            width: 18px;\n            height: 18px;\n            border: 1px solid {glass_border};\n            background-color: {inset_field};\n        }}\n        QCheckBox::indicator {{\n            border-radius: 5px;\n        }}\n        QRadioButton::indicator {{\n            border-radius: 9px;\n        }}\n        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{\n            background-color: {accent_color};\n            border: 1px solid {accent_glow};\n        }}\n\n        QSlider::groove:horizontal {{\n            border: none;\n            height: 5px;\n            background-color: {inset_field};\n            border-radius: 3px;\n        }}\n        QSlider::handle:horizontal {{\n            background-color: {text_primary};\n            border: 2px solid {accent_color};\n            width: 16px;\n            margin: -7px 0;\n            border-radius: 8px;\n        }}\n\n        QTextEdit, #consoleOutput {{\n            background-color: rgba(0, 0, 0, 0.45);\n            border: 1px solid {glass_border_soft};\n            border-radius: 10px;\n            color: #5ee87a;\n            padding: 10px;\n            font-family: 'Consolas', 'Courier New', monospace;\n        }}\n\n        #advancedFrame {{\n            background-color: rgba(0, 0, 0, 0.2);\n            border: 1px solid {glass_border_soft};\n            border-radius: 10px;\n            padding: 10px;\n        }}\n        #totalSizeLabel {{\n            color: {text_secondary};\n            font-size: 9pt;\n        }}\n    '''


def get_neumorphism_theme(accent_color='#1DB954', secondary_accent=None):
    """Tema Neumorfismo (Soft UI) sobre fondo claro.
    Conserva get_dark_theme() intacto para poder volver al estilo original.
    """
    accent_hover = lighten_color(accent_color, 0.12)
    accent_soft = accent_rgba(accent_color, 0.35)
    secondary_soft = accent_rgba(secondary_accent or accent_color, 0.35)
    accent_muted = accent_rgba(accent_color, 0.15)
    base = '#E3E8F0'
    base_input = '#DDE3EE'
    base_hover = '#EDF1F8'
    text_primary = '#3A4354'
    text_secondary = '#6B7488'
    text_muted = '#8A93A6'
    light_edge = '#FFFFFF'
    dark_edge = '#A9B4C6'
    return f'''
        /* —— Ventana principal —— */
        #container {{
            background-color: {base};
            border-radius: 18px;
        }}
        #titleBar {{
            background-color: rgba(255, 255, 255, 0.35);
            border-top-left-radius: 17px;
            border-top-right-radius: 17px;
            border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        }}
        #titleLabel {{
            color: {text_primary};
            font-weight: bold;
        }}
        #mainPanel {{
            background-color: {base};
            border: 2px solid {base};
            border-top-color: {light_edge};
            border-left-color: {light_edge};
            border-bottom-color: {dark_edge};
            border-right-color: {dark_edge};
            border-radius: 14px;
        }}
        #sectionLabel {{
            color: {accent_color};
            font-weight: bold;
        }}
        QLabel, QRadioButton, QCheckBox {{
            color: {text_secondary};
        }}
        #loginStatusLabel {{
            color: {text_muted};
            font-size: 9pt;
        }}
        #versionStatusLabel {{
            color: {text_muted};
            font-size: 8pt;
        }}
        #updateLinkButton {{
            background: transparent;
            border: none;
            color: {text_muted};
            text-decoration: underline;
            font-size: 8pt;
            padding: 2px 4px;
        }}
        #updateLinkButton:hover {{
            color: {accent_color};
        }}
        #updateLinkButton[updateAvailable="true"] {{
            color: {accent_color};
            font-weight: bold;
        }}

        /* —— Campos (inset) —— */
        QComboBox, QLineEdit {{
            background-color: {base_input};
            border: 2px solid {base_input};
            border-top-color: {dark_edge};
            border-left-color: {dark_edge};
            border-bottom-color: {light_edge};
            border-right-color: {light_edge};
            border-radius: 10px;
            padding: 10px 12px;
            color: {text_primary};
        }}
        QComboBox:hover, QLineEdit:hover {{
            background-color: {base_hover};
        }}
        QLineEdit:focus, QComboBox:focus {{
            background-color: {base_hover};
            border: 2px solid {secondary_soft};
            border-radius: 10px;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        QComboBox QAbstractItemView {{
            background-color: #F0F3F9;
            border: 2px solid #F0F3F9;
            border-top-color: #FFFFFF;
            border-left-color: #FFFFFF;
            border-bottom-color: {dark_edge};
            border-right-color: {dark_edge};
            border-radius: 8px;
            color: {text_primary};
            selection-background-color: {accent_muted};
            selection-color: {text_primary};
        }}

        /* —— Botones primarios (acento) —— */
        QPushButton {{
            background-color: {accent_color};
            color: #FFFFFF;
            border: none;
            border-radius: 10px;
            padding: 12px 16px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {accent_hover};
        }}
        QPushButton:pressed {{
            background-color: {accent_hover};
        }}
        #launchButton {{
            background-color: {accent_color};
            color: #FFFFFF;
            border-radius: 12px;
            padding: 10px 16px;
            margin: 0;
        }}
        #launchButton:hover {{
            background-color: {accent_hover};
        }}
        #launchButtonWrap {{
            background: transparent;
        }}
        #colorPickerButton {{
            padding: 5px;
            background-color: {base};
            color: {text_primary};
            border: 2px solid {base};
            border-top-color: #FFFFFF;
            border-left-color: #FFFFFF;
            border-bottom-color: {dark_edge};
            border-right-color: {dark_edge};
        }}
        #colorPickerButton:hover {{
            border: 2px solid {secondary_soft};
        }}
        #colorPreview {{
            border: 2px solid {dark_edge};
            border-radius: 10px;
        }}

        /* —— Botones secundarios / elevados —— */
        #advancedButton, #openModsFolderButton, #openModpacksFolderButton,
        #newInstallationButton, #remoteInstanceVerifyButton {{
            background-color: {base};
            color: {text_primary};
            border: 2px solid {base};
            border-top-color: #FFFFFF;
            border-left-color: #FFFFFF;
            border-bottom-color: {dark_edge};
            border-right-color: {dark_edge};
            font-weight: normal;
        }}
        #advancedButton:hover, #openModsFolderButton:hover, #openModpacksFolderButton:hover,
        #newInstallationButton:hover, #remoteInstanceVerifyButton:hover {{
            background-color: {base_hover};
            border: 2px solid {secondary_soft};
            color: {text_primary};
        }}
        #advancedButton:checked {{
            background-color: {accent_muted};
            border: 2px solid {secondary_soft};
        }}

        #closeButton, #minimizeButton {{
            font-size: 12pt;
            font-weight: bold;
            border-radius: 15px;
            border: none;
        }}
        #closeButton {{
            background-color: rgba(226, 61, 40, 0.9);
            color: white;
        }}
        #closeButton:hover {{
            background-color: rgba(248, 79, 57, 1);
        }}
        #minimizeButton {{
            background-color: rgba(248, 179, 57, 0.9);
            color: white;
        }}
        #minimizeButton:hover {{
            background-color: rgba(255, 193, 78, 1);
        }}

        QProgressBar {{
            border: 2px solid {base};
            border-top-color: {dark_edge};
            border-left-color: {dark_edge};
            border-bottom-color: #FFFFFF;
            border-right-color: #FFFFFF;
            border-radius: 10px;
            text-align: center;
            background-color: {base_input};
            color: {text_primary};
            font-weight: bold;
        }}
        QProgressBar::chunk {{
            background-color: {accent_color};
            border-radius: 8px;
        }}

        /* —— Listas y tarjetas —— */
        #modList, #newsList {{
            background-color: {base_input};
            border: 2px solid {base_input};
            border-top-color: {dark_edge};
            border-left-color: {dark_edge};
            border-bottom-color: #FFFFFF;
            border-right-color: #FFFFFF;
            border-radius: 12px;
        }}
        QListWidget {{
            background-color: transparent;
            border: none;
            outline: none;
        }}
        QListWidget::item {{
            background: transparent;
            border: none;
            padding: 4px 2px;
        }}
        QListWidget::item:selected {{
            background: transparent;
        }}
        #modList::item:selected {{
            background-color: {accent_muted};
            border-radius: 10px;
        }}
        #modList::item:hover {{
            background-color: rgba(255, 255, 255, 0.35);
            border-radius: 10px;
        }}

        #modpackCard {{
            background-color: {base};
            border: 2px solid {base};
            border-top-color: #FFFFFF;
            border-left-color: #FFFFFF;
            border-bottom-color: {dark_edge};
            border-right-color: {dark_edge};
            border-radius: 10px;
        }}
        #modpackCard[selected="true"] {{
            background-color: {accent_muted};
            border: 2px solid {accent_color};
        }}
        #modpackSelectIndicator {{
            color: {text_muted};
            font-size: 14px;
            font-weight: bold;
        }}
        #modpackCard[selected="true"] #modpackSelectIndicator {{
            color: {accent_color};
        }}

        #modCard, #versionCard, #installedModCard, #newsCard {{
            background-color: {base};
            border: 2px solid {base};
            border-top-color: #FFFFFF;
            border-left-color: #FFFFFF;
            border-bottom-color: {dark_edge};
            border-right-color: {dark_edge};
            border-radius: 12px;
            padding: 8px;
        }}
        #modCard:hover, #versionCard:hover, #installedModCard:hover, #newsCard:hover {{
            background-color: {base_hover};
            border: 2px solid {secondary_soft};
        }}
        #modTitle, #modName, #versionIdLabel {{
            color: {text_primary};
            font-weight: bold;
        }}
        #modAuthor, #modStats, #modDetails, #modDescription, #modFilename,
        #versionTypeLabel, #versionSizeLabel {{
            color: {text_secondary};
        }}
        #versionBadge {{
            background-color: rgba(255, 255, 255, 0.6);
            color: {text_primary};
            border: 1px solid {dark_edge};
            border-radius: 6px;
            padding: 3px 8px;
        }}
        #modInstallButton {{
            background-color: {accent_color};
            color: #FFFFFF;
            font-weight: bold;
            border: none;
            border-radius: 8px;
            padding: 8px 12px;
            min-width: 90px;
        }}
        #modInstallButton:hover {{
            background-color: {accent_hover};
        }}
        #modDeleteButton, #deleteButton {{
            background-color: rgba(244, 67, 54, 0.9);
            color: white;
        }}
        #modDeleteButton:hover, #deleteButton:hover {{
            background-color: rgba(246, 92, 81, 1);
        }}
        #versionCard QPushButton {{
            background-color: {base};
            color: {text_primary};
            border: 2px solid {base};
            border-top-color: #FFFFFF;
            border-left-color: #FFFFFF;
            border-bottom-color: {dark_edge};
            border-right-color: {dark_edge};
            padding: 5px 10px;
            border-radius: 8px;
            font-weight: normal;
        }}
        #versionCard #deleteButton {{
            background-color: rgba(244, 67, 54, 0.9);
            color: white;
            border: none;
        }}
        #versionCard #deleteButton:hover {{
            background-color: rgba(246, 92, 81, 1);
        }}
        #versionCard QPushButton:hover {{
            border: 2px solid {secondary_soft};
            background-color: {base_hover};
        }}
        #versionIdLabel {{
            font-size: 14pt;
        }}
        #toggleSwitch {{
            font-family: "Segoe UI Symbol";
            font-weight: bold;
            border-radius: 12px;
            border: 2px solid {base};
            border-top-color: #FFFFFF;
            border-left-color: #FFFFFF;
            border-bottom-color: {dark_edge};
            border-right-color: {dark_edge};
            background-color: {base};
            color: {text_secondary};
        }}
        #toggleSwitch:checked {{
            background-color: {accent_color};
            color: #FFFFFF;
            border: 2px solid {secondary_soft};
        }}

        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 10px;
            margin: 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(90, 100, 120, 0.25);
            min-height: 30px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {secondary_soft};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            border: none;
            background: none;
        }}

        #errorLabel {{
            color: #E23D28;
            font-weight: bold;
        }}

        /* —— Pestañas —— */
        QTabWidget::pane {{
            border: 2px solid {base};
            border-top-color: #FFFFFF;
            border-left-color: #FFFFFF;
            border-bottom-color: {dark_edge};
            border-right-color: {dark_edge};
            border-radius: 12px;
            background-color: {base};
            margin-top: -1px;
        }}
        QTabBar::tab {{
            background-color: transparent;
            color: {text_muted};
            padding: 10px 16px;
            margin-right: 4px;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            border: 1px solid transparent;
        }}
        QTabBar::tab:selected {{
            background-color: {base_hover};
            color: {text_primary};
            border: 1px solid {dark_edge};
            border-bottom: 2px solid {accent_color};
        }}
        QTabBar::tab:hover {{
            background-color: rgba(255, 255, 255, 0.4);
            color: {text_primary};
        }}

        QCheckBox, QRadioButton {{
            spacing: 8px;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {base};
            border-top-color: {dark_edge};
            border-left-color: {dark_edge};
            border-bottom-color: #FFFFFF;
            border-right-color: #FFFFFF;
            background-color: {base_input};
        }}
        QCheckBox::indicator {{
            border-radius: 5px;
        }}
        QRadioButton::indicator {{
            border-radius: 9px;
        }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background-color: {accent_color};
            border: 2px solid {secondary_soft};
        }}

        QSlider::groove:horizontal {{
            border: none;
            height: 5px;
            background-color: {base_input};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background-color: #FFFFFF;
            border: 2px solid {accent_color};
            width: 16px;
            margin: -7px 0;
            border-radius: 8px;
        }}

        QTextEdit, #consoleOutput {{
            background-color: rgba(20, 24, 32, 0.85);
            border: 2px solid {dark_edge};
            border-radius: 10px;
            color: #5ee87a;
            padding: 10px;
            font-family: 'Consolas', 'Courier New', monospace;
        }}

        #advancedFrame {{
            background-color: rgba(255, 255, 255, 0.5);
            border: 2px solid {base};
            border-top-color: #FFFFFF;
            border-left-color: #FFFFFF;
            border-bottom-color: {dark_edge};
            border-right-color: {dark_edge};
            border-radius: 10px;
            padding: 10px;
        }}
        #totalSizeLabel {{
            color: {text_secondary};
            font-size: 9pt;
        }}
    '''


def get_skeuomorphism_theme(accent_color='#1DB954', secondary_accent=None):
    """Tema Skeuomorfismo: relieve 3D, biseles y gradientes brillantes (estilo físico).
    Conserva get_dark_theme() y get_neumorphism_theme() intactos.
    """
    secondary = secondary_accent or accent_color
    try:
        accent_dark = QColor(accent_color).darker(150).name()
        accent_darker = QColor(secondary).darker(230).name()
        bevel_hi = lighten_color(secondary, 0.42)
        bevel_hi_hover = lighten_color(secondary, 0.55)
        bevel_side = lighten_color(secondary, 0.08)
        bevel_dark = QColor(secondary).darker(320).name()
        bevel_mid = QColor(secondary).darker(180).name()
        accent_hover_dark = QColor(accent_color).darker(140).name()
    except Exception:
        accent_dark = '#15823E'
        accent_darker = '#0B401D'
        bevel_hi = '{bevel_hi}'
        bevel_hi_hover = '{bevel_hi_hover}'
        bevel_side = '{bevel_side}'
        bevel_dark = '{bevel_dark}'
        bevel_mid = '{bevel_mid}'
        accent_hover_dark = '{accent_hover_dark}'
    gloss_top = lighten_color(secondary, 0.18)
    gloss_hover = lighten_color(secondary, 0.32)
    accent_hover = lighten_color(accent_color, 0.12)
    accent_soft = accent_rgba(accent_color, 0.4)
    secondary_soft = accent_rgba(secondary, 0.4)
    accent_muted = accent_rgba(accent_color, 0.18)
    text_primary = '#F0E9DC'
    text_secondary = '#B8AE9C'
    text_muted = '#8A8171'
    return f'''
        /* —— Ventana principal: piedra oscura con viñeta —— */
        #container {{
            background: qradialgradient(cx: 0.5, cy: 0.35, radius: 1.5, fx: 0.5, fy: 0.3,
                                       stop: 0 #3D4251, stop: 0.55 #2B2F3B, stop: 1 #1B1E26);
            border-radius: 18px;
            border: 2px solid #14161C;
            border-top-color: #555D6E;
            border-left-color: #3F4553;
            border-bottom-color: #0C0E12;
            border-right-color: #262A34;
        }}
        #titleBar {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #5C4A35, stop: 1 #3A2D20);
            border-top-left-radius: 17px;
            border-top-right-radius: 17px;
            border-bottom: 2px solid #1F160D;
        }}
        #titleLabel {{
            color: #F3E3C3;
            font-weight: bold;
        }}
        #mainPanel {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #363B49, stop: 1 #242833);
            border: 2px solid #1A1D25;
            border-top-color: #4C5365;
            border-left-color: #3A4050;
            border-bottom-color: #0E1015;
            border-right-color: #262B35;
            border-radius: 14px;
        }}
        #sectionLabel {{
            color: {accent_color};
            font-weight: bold;
        }}
        QLabel, QRadioButton, QCheckBox {{
            color: {text_secondary};
        }}
        #loginStatusLabel {{
            color: {text_muted};
            font-size: 9pt;
        }}
        #versionStatusLabel {{
            color: {text_muted};
            font-size: 8pt;
        }}
        #updateLinkButton {{
            background: transparent;
            border: none;
            color: {text_muted};
            text-decoration: underline;
            font-size: 8pt;
            padding: 2px 4px;
        }}
        #updateLinkButton:hover {{
            color: {accent_color};
        }}
        #updateLinkButton[updateAvailable="true"] {{
            color: {accent_color};
            font-weight: bold;
        }}

        /* —— Campos tallados en piedra (inset) —— */
        QComboBox, QLineEdit {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #14171D, stop: 1 #1E222B);
            border: 2px solid #0E1015;
            border-top-color: #07080B;
            border-left-color: #0A0C10;
            border-bottom-color: #3A4050;
            border-right-color: #2A2F3A;
            border-radius: 8px;
            padding: 10px 12px;
            color: {text_primary};
            selection-background-color: {accent_color};
        }}
        QComboBox:hover, QLineEdit:hover {{
            border-top-color: #0C0E12;
        }}
        QLineEdit:focus, QComboBox:focus {{
            border: 2px solid {secondary_soft};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        QComboBox QAbstractItemView {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #22262F, stop: 1 #191C24);
            border: 2px solid #14161C;
            border-top-color: #3A4050;
            border-left-color: #2E3340;
            border-bottom-color: #0C0E12;
            border-right-color: #232731;
            border-radius: 8px;
            color: {text_primary};
            selection-background-color: {accent_muted};
            selection-color: {text_primary};
        }}

        /* —— Botones: piedra biselada 3D —— */
        QPushButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #596170, stop: 0.48 #3D4351, stop: 1 #262B35);
            border: 2px solid #14161C;
            border-top-color: #6E7789;
            border-left-color: #515968;
            border-bottom-color: #0D0F13;
            border-right-color: #2B303B;
            border-radius: 8px;
            padding: 12px 16px;
            color: {text_primary};
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #6E7789, stop: 0.48 #4A5160, stop: 1 #2E333F);
            border-top-color: #8A93A5;
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #262B35, stop: 0.52 #3D4351, stop: 1 #596170);
            padding-top: 13px;
            padding-bottom: 11px;
        }}
        QPushButton:disabled {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #333846, stop: 1 #232731);
            color: #6E7483;
            border-top-color: #3A4050;
        }}

        /* —— Botón primario (acento, brillante) —— */
        #launchButton, #modInstallButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.45 {accent_color}, stop: 1 {accent_dark});
            border: 2px solid {accent_darker};
            border-top-color: {bevel_hi};
            border-left-color: {bevel_side};
            border-bottom-color: {bevel_dark};
            border-right-color: {bevel_mid};
            color: #06220F;
            font-weight: bold;
        }}
        #launchButton:hover, #modInstallButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_hover}, stop: 0.45 {accent_hover}, stop: 1 {accent_hover_dark});
            border-top-color: {bevel_hi_hover};
        }}
        #launchButton:pressed, #modInstallButton:pressed {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {accent_dark}, stop: 0.55 {accent_color}, stop: 1 {gloss_top});
            padding-top: 11px;
            padding-bottom: 9px;
        }}
        #launchButtonWrap {{
            background: transparent;
        }}
        #colorPickerButton {{
            padding: 5px;
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #4A5160, stop: 1 #2E333F);
            border: 2px solid #14161C;
            border-top-color: #6E7789;
            border-bottom-color: #0D0F13;
            color: {text_primary};
        }}
        #colorPickerButton:hover {{
            border: 2px solid {secondary_soft};
        }}
        #colorPreview {{
            border: 2px solid #14161C;
            border-top-color: #0D0F13;
            border-bottom-color: #3A4050;
            border-radius: 10px;
        }}

        /* —— Botones secundarios —— */
        #advancedButton, #openModsFolderButton, #openModpacksFolderButton,
        #newInstallationButton, #remoteInstanceVerifyButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #596170, stop: 0.48 #3D4351, stop: 1 #262B35);
            border: 2px solid #14161C;
            border-top-color: #6E7789;
            border-left-color: #515968;
            border-bottom-color: #0D0F13;
            border-right-color: #2B303B;
            color: {text_primary};
            font-weight: normal;
        }}
        #advancedButton:hover, #openModsFolderButton:hover, #openModpacksFolderButton:hover,
        #newInstallationButton:hover, #remoteInstanceVerifyButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #6E7789, stop: 0.48 #4A5160, stop: 1 #2E333F);
            border: 2px solid {secondary_soft};
        }}
        #advancedButton:checked {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {bevel_side}, stop: 1 {accent_dark});
            border: 2px solid {accent_darker};
            color: #06220F;
        }}

        #closeButton, #minimizeButton {{
            font-size: 12pt;
            font-weight: bold;
            border-radius: 15px;
            padding: 0;
        }}
        #closeButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF7A66, stop: 0.5 #E23D28, stop: 1 #A82312);
            border: 2px solid #7A150A;
            border-top-color: #FFB3A6;
            border-bottom-color: #57100A;
            color: white;
        }}
        #closeButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF9888, stop: 0.5 #F2472F, stop: 1 #C02A16);
        }}
        #minimizeButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FFD27A, stop: 0.5 #F8B339, stop: 1 #C07F16);
            border: 2px solid #8A5C0F;
            border-top-color: #FFE3A8;
            border-bottom-color: #5E3E0A;
            color: white;
        }}
        #minimizeButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FFE0A0, stop: 0.5 #FAC44F, stop: 1 #D08F1C);
        }}

        QProgressBar {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #13151B, stop: 1 #1B1E26);
            border: 2px solid #0E1015;
            border-top-color: #08090C;
            border-left-color: #0A0C10;
            border-bottom-color: #333846;
            border-right-color: #262A34;
            border-radius: 8px;
            text-align: center;
            color: {text_primary};
            font-weight: bold;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.5 {accent_color}, stop: 1 {accent_dark});
            border-radius: 6px;
        }}

        /* —— Listas y tarjetas —— */
        #modList, #newsList {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #181B22, stop: 1 #1F232C);
            border: 2px solid #101218;
            border-top-color: #0B0D11;
            border-left-color: #0D0F14;
            border-bottom-color: #3A4050;
            border-right-color: #2A2F3A;
            border-radius: 10px;
        }}
        QListWidget {{
            background-color: transparent;
            border: none;
            outline: none;
        }}
        QListWidget::item {{
            background: transparent;
            border: none;
            padding: 4px 2px;
        }}
        QListWidget::item:selected {{
            background: transparent;
        }}
        #modList::item:selected {{
            background-color: {accent_muted};
            border-radius: 8px;
        }}
        #modList::item:hover {{
            background-color: rgba(255, 255, 255, 0.06);
            border-radius: 8px;
        }}

        #modpackCard {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #434A5C, stop: 1 #2B303D);
            border: 2px solid #1C1F28;
            border-top-color: #5A6275;
            border-left-color: #474E60;
            border-bottom-color: #101218;
            border-right-color: #2E3340;
            border-radius: 10px;
        }}
        #modpackCard[selected="true"] {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #2F5C40, stop: 1 #244A33);
            border: 2px solid {accent_color};
        }}
        #modpackSelectIndicator {{
            color: {text_muted};
            font-size: 14px;
            font-weight: bold;
        }}
        #modpackCard[selected="true"] #modpackSelectIndicator {{
            color: {accent_color};
        }}

        #modCard, #versionCard, #installedModCard, #newsCard {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #434A5C, stop: 1 #2B303D);
            border: 2px solid #1C1F28;
            border-top-color: #5A6275;
            border-left-color: #474E60;
            border-bottom-color: #101218;
            border-right-color: #2E3340;
            border-radius: 10px;
            padding: 8px;
        }}
        #modCard:hover, #versionCard:hover, #installedModCard:hover, #newsCard:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #4C5468, stop: 1 #323846);
            border: 2px solid {secondary_soft};
        }}
        #modTitle, #modName, #versionIdLabel {{
            color: {text_primary};
            font-weight: bold;
        }}
        #modAuthor, #modStats, #modDetails, #modDescription, #modFilename,
        #versionTypeLabel, #versionSizeLabel {{
            color: {text_secondary};
        }}
        #versionBadge {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #6E7789, stop: 1 #3D4351);
            border: 1px solid #101218;
            border-top-color: #8A93A5;
            border-bottom-color: #262B35;
            color: {text_primary};
            border-radius: 6px;
            padding: 3px 8px;
        }}
        #modDeleteButton, #deleteButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF7A66, stop: 0.5 #E23D28, stop: 1 #A82312);
            border: 2px solid #7A150A;
            border-top-color: #FFB3A6;
            border-bottom-color: #57100A;
            color: white;
        }}
        #modDeleteButton:hover, #deleteButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF9888, stop: 0.5 #F2472F, stop: 1 #C02A16);
        }}
        #versionCard QPushButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #596170, stop: 0.48 #3D4351, stop: 1 #262B35);
            border: 2px solid #14161C;
            border-top-color: #6E7789;
            border-left-color: #515968;
            border-bottom-color: #0D0F13;
            border-right-color: #2B303B;
            padding: 5px 10px;
            border-radius: 8px;
            color: {text_primary};
            font-weight: normal;
        }}
        #versionCard #deleteButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF7A66, stop: 0.5 #E23D28, stop: 1 #A82312);
            border: 2px solid #7A150A;
            border-top-color: #FFB3A6;
            border-bottom-color: #57100A;
            color: white;
        }}
        #versionCard #deleteButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF9888, stop: 0.5 #F2472F, stop: 1 #C02A16);
        }}
        #versionCard QPushButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #6E7789, stop: 0.48 #4A5160, stop: 1 #2E333F);
            border: 2px solid {secondary_soft};
        }}
        #versionIdLabel {{
            font-size: 14pt;
        }}
        #toggleSwitch {{
            font-family: "Segoe UI Symbol";
            font-weight: bold;
            border-radius: 12px;
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #4A5160, stop: 1 #262B35);
            border: 2px solid #14161C;
            border-top-color: #6E7789;
            border-bottom-color: #0D0F13;
            color: {text_secondary};
        }}
        #toggleSwitch:checked {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.5 {accent_color}, stop: 1 {accent_dark});
            border: 2px solid {accent_darker};
            border-top-color: {bevel_hi};
            border-bottom-color: {bevel_dark};
            color: #06220F;
        }}

        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 10px;
            margin: 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #596170, stop: 1 #3D4351);
            min-height: 30px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {secondary_soft};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            border: none;
            background: none;
        }}

        #errorLabel {{
            color: #FF8A7A;
            font-weight: bold;
        }}

        /* —— Pestañas: pestañas de piedra —— */
        QTabWidget::pane {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #262B35, stop: 1 #1D212A);
            border: 2px solid #15171D;
            border-top-color: #454C5C;
            border-left-color: #363C4A;
            border-bottom-color: #0C0E12;
            border-right-color: #232731;
            border-radius: 12px;
            margin-top: -1px;
        }}
        QTabBar::tab {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #2E3340, stop: 1 #22262F);
            border: 2px solid #16181E;
            border-top-color: #3F4553;
            border-left-color: #333846;
            border-bottom-color: #101218;
            border-right-color: #262A34;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            color: {text_muted};
            padding: 10px 16px;
            margin-right: 4px;
        }}
        QTabBar::tab:selected {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #4A5162, stop: 1 #2F3542);
            color: {text_primary};
            border-bottom: 3px solid {accent_color};
        }}
        QTabBar::tab:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #3A4050, stop: 1 #2A2F3A);
            color: {text_primary};
        }}

        QCheckBox, QRadioButton {{
            spacing: 8px;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid #101218;
            border-top-color: #08090C;
            border-left-color: #0A0C10;
            border-bottom-color: #3A4050;
            border-right-color: #2A2F3A;
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #14171D, stop: 1 #1E222B);
        }}
        QCheckBox::indicator {{
            border-radius: 5px;
        }}
        QRadioButton::indicator {{
            border-radius: 9px;
        }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.5 {accent_color}, stop: 1 {accent_dark});
            border: 2px solid {accent_darker};
            border-top-color: {bevel_hi};
        }}

        QSlider::groove:horizontal {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #101218, stop: 1 #2A2F3A);
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #8A93A5, stop: 0.5 #5A6275, stop: 1 #333846);
            border: 2px solid #14161C;
            border-top-color: #9AA3B5;
            border-bottom-color: #101218;
            width: 18px;
            margin: -8px 0;
            border-radius: 9px;
        }}

        QTextEdit, #consoleOutput {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #0C0E12, stop: 1 #14171D);
            border: 2px solid #0E1015;
            border-top-color: #07080B;
            border-left-color: #0A0C10;
            border-bottom-color: #2A2F3A;
            border-right-color: #1E222B;
            border-radius: 10px;
            color: #5ee87a;
            padding: 10px;
            font-family: 'Consolas', 'Courier New', monospace;
        }}

        #advancedFrame {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #191C24, stop: 1 #1F232C);
            border: 2px solid #101218;
            border-top-color: #0B0D11;
            border-left-color: #0D0F14;
            border-bottom-color: #333846;
            border-right-color: #262A34;
            border-radius: 10px;
            padding: 10px;
        }}
        #totalSizeLabel {{
            color: {text_secondary};
            font-size: 9pt;
        }}
    '''


def get_skeuomorphism_dark_theme(accent_color='#1DB954', glass_opacity=88, secondary_accent=None):
    """Relieve 3D físico (skeuomorfismo) con la paleta original de cristal oscuro.
    secondary_accent: color para bordes/brillos (sombra) de los botones.
    Conserva los demás temas intactos.
    """
    accent_hover = lighten_color(accent_color, 0.12)
    accent_soft = accent_rgba(accent_color, 0.22)
    accent_glow = accent_rgba(secondary_accent or accent_color, 0.45)
    accent_muted = accent_rgba(accent_color, 0.12)
    secondary = secondary_accent or accent_color
    gloss_top = lighten_color(secondary, 0.18)
    gloss_hover = lighten_color(secondary, 0.32)
    secondary_soft = accent_rgba(secondary, 0.35)
    try:
        accent_dark = QColor(accent_color).darker(150).name()
        accent_darker = QColor(secondary).darker(230).name()
        bevel_hi = lighten_color(secondary, 0.42)
        bevel_hi_hover = lighten_color(secondary, 0.55)
        bevel_side = lighten_color(secondary, 0.08)
        bevel_dark = QColor(secondary).darker(320).name()
        bevel_mid = QColor(secondary).darker(180).name()
        accent_hover_dark = QColor(accent_color).darker(140).name()
    except Exception:
        accent_dark = '#15823E'
        accent_darker = '#0B401D'
        bevel_hi = '{bevel_hi}'
        bevel_hi_hover = '{bevel_hi_hover}'
        bevel_side = '{bevel_side}'
        bevel_dark = '{bevel_dark}'
        bevel_mid = '{bevel_mid}'
        accent_hover_dark = '{accent_hover_dark}'
    t = max(50, min(100, int(glass_opacity))) / 100.0
    shell_alpha = 0.72 + (t - 0.5) * 0.46
    panel_alpha = 0.78 + (t - 0.5) * 0.38
    glass_mix = 0.04 + (t - 0.5) * 0.07
    glass_panel = f'rgba(26, 26, 34, {panel_alpha:.2f})'
    glass_panel_strong = f'rgba(34, 34, 44, {min(0.98, panel_alpha + 0.06):.2f})'
    shell_bg = f'rgba(14, 14, 20, {shell_alpha:.2f})'
    shell_center = f'rgba(38, 38, 48, {shell_alpha:.2f})'
    glass_border = f'rgba(255, 255, 255, {0.08 + glass_mix:.2f})'
    glass_border_soft = f'rgba(255, 255, 255, {0.04 + glass_mix * 0.5:.2f})'
    neumo_highlight = f'rgba(255, 255, 255, {0.06 + glass_mix:.2f})'
    neumo_shadow = 'rgba(0, 0, 0, 0.38)'
    inset_field = f'rgba(0, 0, 0, {0.22 + (1 - t) * 0.12:.2f})'
    inset_deep = f'rgba(0, 0, 0, {0.32 + (1 - t) * 0.12:.2f})'
    text_primary = '#EEEEF2'
    text_secondary = '#A8A8B8'
    text_muted = '#6E6E82'
    light_bevel = 'rgba(255, 255, 255, 0.12)'
    light_bevel_soft = 'rgba(255, 255, 255, 0.05)'
    dark_bevel = 'rgba(0, 0, 0, 0.5)'
    dark_bevel_soft = 'rgba(0, 0, 0, 0.28)'
    return f'''
        /* —— Ventana principal: cristal oscuro con relieve 3D —— */
        #container {{
            background: qradialgradient(cx: 0.5, cy: 0.35, radius: 1.5, fx: 0.5, fy: 0.3,
                                       stop: 0 {shell_center}, stop: 0.55 {shell_bg}, stop: 1 rgba(8, 8, 12, 0.9));
            border-radius: 18px;
            border: 2px solid rgba(0, 0, 0, 0.5);
            border-top-color: {light_bevel};
            border-left-color: {light_bevel_soft};
            border-bottom-color: rgba(0, 0, 0, 0.6);
            border-right-color: {dark_bevel_soft};
        }}
        #titleBar {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(255, 255, 255, 0.09), stop: 1 rgba(255, 255, 255, 0.03));
            border-top-left-radius: 17px;
            border-top-right-radius: 17px;
            border-bottom: 2px solid rgba(0, 0, 0, 0.4);
        }}
        #titleLabel {{
            color: {text_primary};
            font-weight: bold;
        }}
        #mainPanel {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {glass_panel_strong}, stop: 1 {glass_panel});
            border: 2px solid rgba(0, 0, 0, 0.45);
            border-top-color: {light_bevel};
            border-left-color: {light_bevel_soft};
            border-bottom-color: {dark_bevel};
            border-right-color: {dark_bevel_soft};
            border-radius: 14px;
        }}
        #sectionLabel {{
            color: {accent_color};
            font-weight: bold;
        }}
        QLabel, QRadioButton, QCheckBox {{
            color: {text_secondary};
        }}
        #loginStatusLabel {{
            color: {text_muted};
            font-size: 9pt;
        }}
        #versionStatusLabel {{
            color: {text_muted};
            font-size: 8pt;
        }}
        #updateLinkButton {{
            background: transparent;
            border: none;
            color: {text_muted};
            text-decoration: underline;
            font-size: 8pt;
            padding: 2px 4px;
        }}
        #updateLinkButton:hover {{
            color: {accent_color};
        }}
        #updateLinkButton[updateAvailable="true"] {{
            color: {accent_color};
            font-weight: bold;
        }}

        /* —— Campos tallados (inset) —— */
        QComboBox, QLineEdit {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {inset_field}, stop: 1 {inset_deep});
            border: 2px solid rgba(0, 0, 0, 0.5);
            border-top-color: rgba(0, 0, 0, 0.6);
            border-left-color: rgba(0, 0, 0, 0.5);
            border-bottom-color: {neumo_highlight};
            border-right-color: {light_bevel_soft};
            border-radius: 8px;
            padding: 10px 12px;
            color: {text_primary};
            selection-background-color: {accent_color};
        }}
        QComboBox:hover, QLineEdit:hover {{
            border-bottom-color: {glass_border};
        }}
        QLineEdit:focus, QComboBox:focus {{
            border: 2px solid {secondary_soft};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        QComboBox QAbstractItemView {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {glass_panel_strong}, stop: 1 {glass_panel});
            border: 2px solid rgba(0, 0, 0, 0.5);
            border-top-color: {light_bevel};
            border-left-color: {light_bevel_soft};
            border-bottom-color: {dark_bevel};
            border-right-color: {dark_bevel_soft};
            border-radius: 8px;
            color: {text_primary};
            selection-background-color: {accent_muted};
            selection-color: {text_primary};
        }}

        /* —— Botones: cristal biselado 3D —— */
        QPushButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(58, 60, 76, 0.92), stop: 0.48 rgba(30, 30, 40, 0.9), stop: 1 rgba(14, 14, 22, 0.88));
            border: 2px solid rgba(0, 0, 0, 0.55);
            border-top-color: {light_bevel};
            border-left-color: rgba(255, 255, 255, 0.06);
            border-bottom-color: rgba(0, 0, 0, 0.55);
            border-right-color: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            padding: 12px 16px;
            color: {text_primary};
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(72, 74, 92, 0.95), stop: 0.48 rgba(38, 38, 50, 0.93), stop: 1 rgba(18, 18, 28, 0.9));
            border-top-color: rgba(255, 255, 255, 0.18);
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(14, 14, 22, 0.88), stop: 0.52 rgba(30, 30, 40, 0.9), stop: 1 rgba(58, 60, 76, 0.92));
            border-top-color: rgba(0, 0, 0, 0.5);
            border-bottom-color: {light_bevel_soft};
            padding-top: 13px;
            padding-bottom: 11px;
        }}
        QPushButton:disabled {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(38, 38, 48, 0.8), stop: 1 rgba(20, 20, 28, 0.8));
            color: #70707e;
            border-top-color: rgba(255, 255, 255, 0.04);
        }}

        /* —— Botón primario (acento brillante, como el original) —— */
        #launchButton, #modInstallButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.45 {accent_color}, stop: 1 {accent_dark});
            border: 2px solid {accent_darker};
            border-top-color: {bevel_hi};
            border-left-color: {bevel_side};
            border-bottom-color: {bevel_dark};
            border-right-color: {bevel_mid};
            color: #0c0c10;
            font-weight: bold;
        }}
        #launchButton:hover, #modInstallButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_hover}, stop: 0.45 {accent_hover}, stop: 1 {accent_hover_dark});
            border-top-color: {bevel_hi_hover};
        }}
        #launchButton:pressed, #modInstallButton:pressed {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {accent_dark}, stop: 0.55 {accent_color}, stop: 1 {gloss_top});
            padding-top: 11px;
            padding-bottom: 9px;
        }}
        #launchButtonWrap {{
            background: transparent;
        }}
        #colorPickerButton {{
            padding: 5px;
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {glass_panel_strong}, stop: 1 {glass_panel});
            border: 2px solid rgba(0, 0, 0, 0.45);
            border-top-color: {light_bevel};
            border-bottom-color: {dark_bevel};
            color: {text_primary};
        }}
        #colorPickerButton:hover {{
            border: 2px solid {secondary_soft};
        }}
        #colorPreview {{
            border: 2px solid rgba(0, 0, 0, 0.5);
            border-top-color: {light_bevel};
            border-bottom-color: {dark_bevel};
            border-radius: 10px;
        }}

        /* —— Botones secundarios —— */
        #advancedButton, #openModsFolderButton, #openModpacksFolderButton,
        #newInstallationButton, #remoteInstanceVerifyButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(58, 60, 76, 0.92), stop: 0.48 rgba(30, 30, 40, 0.9), stop: 1 rgba(14, 14, 22, 0.88));
            border: 2px solid rgba(0, 0, 0, 0.55);
            border-top-color: {light_bevel};
            border-left-color: rgba(255, 255, 255, 0.06);
            border-bottom-color: rgba(0, 0, 0, 0.55);
            border-right-color: rgba(0, 0, 0, 0.3);
            color: {text_primary};
            font-weight: normal;
        }}
        #advancedButton:hover, #openModsFolderButton:hover, #openModpacksFolderButton:hover,
        #newInstallationButton:hover, #remoteInstanceVerifyButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(72, 74, 92, 0.95), stop: 0.48 rgba(38, 38, 50, 0.93), stop: 1 rgba(18, 18, 28, 0.9));
            border: 2px solid {secondary_soft};
        }}
        #advancedButton:checked {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {bevel_side}, stop: 1 {accent_dark});
            border: 2px solid {accent_darker};
            color: #0c0c10;
        }}

        #closeButton, #minimizeButton {{
            font-size: 12pt;
            font-weight: bold;
            border-radius: 15px;
            padding: 0;
        }}
        #closeButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF7A66, stop: 0.5 #E23D28, stop: 1 #A82312);
            border: 2px solid #7A150A;
            border-top-color: #FFB3A6;
            border-bottom-color: #57100A;
            color: white;
        }}
        #closeButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF9888, stop: 0.5 #F2472F, stop: 1 #C02A16);
        }}
        #minimizeButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FFD27A, stop: 0.5 #F8B339, stop: 1 #C07F16);
            border: 2px solid #8A5C0F;
            border-top-color: #FFE3A8;
            border-bottom-color: #5E3E0A;
            color: white;
        }}
        #minimizeButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FFE0A0, stop: 0.5 #FAC44F, stop: 1 #D08F1C);
        }}

        QProgressBar {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {inset_field}, stop: 1 {inset_deep});
            border: 2px solid rgba(0, 0, 0, 0.5);
            border-top-color: rgba(0, 0, 0, 0.6);
            border-left-color: rgba(0, 0, 0, 0.5);
            border-bottom-color: {neumo_highlight};
            border-right-color: {light_bevel_soft};
            border-radius: 8px;
            text-align: center;
            color: {text_primary};
            font-weight: bold;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.5 {accent_color}, stop: 1 {accent_dark});
            border-radius: 6px;
        }}

        /* —— Listas y tarjetas —— */
        #modList, #newsList {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {inset_field}, stop: 1 {inset_deep});
            border: 2px solid rgba(0, 0, 0, 0.5);
            border-top-color: rgba(0, 0, 0, 0.6);
            border-left-color: rgba(0, 0, 0, 0.5);
            border-bottom-color: {neumo_highlight};
            border-right-color: {light_bevel_soft};
            border-radius: 10px;
        }}
        QListWidget {{
            background-color: transparent;
            border: none;
            outline: none;
        }}
        QListWidget::item {{
            background: transparent;
            border: none;
            padding: 4px 2px;
        }}
        QListWidget::item:selected {{
            background: transparent;
        }}
        #modList::item:selected {{
            background-color: {accent_muted};
            border-radius: 8px;
        }}
        #modList::item:hover {{
            background-color: rgba(255, 255, 255, 0.04);
            border-radius: 8px;
        }}

        #modpackCard {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {glass_panel_strong}, stop: 1 {glass_panel});
            border: 2px solid rgba(0, 0, 0, 0.4);
            border-top-color: {light_bevel};
            border-left-color: {light_bevel_soft};
            border-bottom-color: {dark_bevel};
            border-right-color: {dark_bevel_soft};
            border-radius: 10px;
        }}
        #modpackCard[selected="true"] {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(30, 60, 42, 0.9), stop: 1 rgba(22, 44, 32, 0.9));
            border: 2px solid {accent_color};
        }}
        #modpackSelectIndicator {{
            color: {text_muted};
            font-size: 14px;
            font-weight: bold;
        }}
        #modpackCard[selected="true"] #modpackSelectIndicator {{
            color: {accent_color};
        }}

        #modCard, #versionCard, #installedModCard, #newsCard {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {glass_panel_strong}, stop: 1 {glass_panel});
            border: 2px solid rgba(0, 0, 0, 0.4);
            border-top-color: {light_bevel};
            border-left-color: {light_bevel_soft};
            border-bottom-color: {dark_bevel};
            border-right-color: {dark_bevel_soft};
            border-radius: 10px;
            padding: 8px;
        }}
        #modCard:hover, #versionCard:hover, #installedModCard:hover, #newsCard:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(44, 44, 58, 0.95), stop: 1 rgba(30, 30, 40, 0.92));
            border: 2px solid {secondary_soft};
        }}
        #modTitle, #modName, #versionIdLabel {{
            color: {text_primary};
            font-weight: bold;
        }}
        #modAuthor, #modStats, #modDetails, #modDescription, #modFilename,
        #versionTypeLabel, #versionSizeLabel {{
            color: {text_secondary};
        }}
        #versionBadge {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(58, 60, 76, 0.9), stop: 1 rgba(26, 26, 34, 0.9));
            border: 1px solid rgba(0, 0, 0, 0.45);
            border-top-color: {light_bevel};
            border-bottom-color: {dark_bevel_soft};
            color: {text_primary};
            border-radius: 6px;
            padding: 3px 8px;
        }}
        #modDeleteButton, #deleteButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF7A66, stop: 0.5 #E23D28, stop: 1 #A82312);
            border: 2px solid #7A150A;
            border-top-color: #FFB3A6;
            border-bottom-color: #57100A;
            color: white;
        }}
        #modDeleteButton:hover, #deleteButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF9888, stop: 0.5 #F2472F, stop: 1 #C02A16);
        }}
        #versionCard QPushButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(58, 60, 76, 0.92), stop: 0.48 rgba(30, 30, 40, 0.9), stop: 1 rgba(14, 14, 22, 0.88));
            border: 2px solid rgba(0, 0, 0, 0.55);
            border-top-color: {light_bevel};
            border-left-color: rgba(255, 255, 255, 0.06);
            border-bottom-color: rgba(0, 0, 0, 0.55);
            border-right-color: rgba(0, 0, 0, 0.3);
            padding: 5px 10px;
            border-radius: 8px;
            color: {text_primary};
            font-weight: normal;
        }}
        #versionCard #deleteButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF7A66, stop: 0.5 #E23D28, stop: 1 #A82312);
            border: 2px solid #7A150A;
            border-top-color: #FFB3A6;
            border-bottom-color: #57100A;
            color: white;
        }}
        #versionCard #deleteButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF9888, stop: 0.5 #F2472F, stop: 1 #C02A16);
        }}
        #versionCard QPushButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(72, 74, 92, 0.95), stop: 0.48 rgba(38, 38, 50, 0.93), stop: 1 rgba(18, 18, 28, 0.9));
            border: 2px solid {secondary_soft};
        }}
        #versionIdLabel {{
            font-size: 14pt;
        }}
        #toggleSwitch {{
            font-family: "Segoe UI Symbol";
            font-weight: bold;
            border-radius: 12px;
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {glass_panel_strong}, stop: 1 {glass_panel});
            border: 2px solid rgba(0, 0, 0, 0.45);
            border-top-color: {light_bevel};
            border-bottom-color: {dark_bevel};
            color: {text_secondary};
        }}
        #toggleSwitch:checked {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.5 {accent_color}, stop: 1 {accent_dark});
            border: 2px solid {accent_darker};
            border-top-color: {bevel_hi};
            border-bottom-color: {bevel_dark};
            color: #0c0c10;
        }}

        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 10px;
            margin: 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(58, 60, 76, 0.9), stop: 1 rgba(26, 26, 34, 0.9));
            min-height: 30px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {secondary_soft};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            border: none;
            background: none;
        }}

        #errorLabel {{
            color: #ff6b6b;
            font-weight: bold;
        }}

        /* —— Pestañas: cristal biselado —— */
        QTabWidget::pane {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {glass_panel}, stop: 1 {shell_bg});
            border: 2px solid rgba(0, 0, 0, 0.4);
            border-top-color: {light_bevel};
            border-left-color: {light_bevel_soft};
            border-bottom-color: {dark_bevel};
            border-right-color: {dark_bevel_soft};
            border-radius: 12px;
            margin-top: -1px;
        }}
        QTabBar::tab {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(40, 40, 52, 0.85), stop: 1 rgba(20, 20, 28, 0.85));
            border: 2px solid rgba(0, 0, 0, 0.4);
            border-top-color: {light_bevel_soft};
            border-left-color: rgba(255, 255, 255, 0.04);
            border-bottom-color: rgba(0, 0, 0, 0.45);
            border-right-color: rgba(0, 0, 0, 0.25);
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            color: {text_muted};
            padding: 10px 16px;
            margin-right: 4px;
        }}
        QTabBar::tab:selected {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {glass_panel_strong}, stop: 1 rgba(26, 26, 34, 0.92));
            color: {text_primary};
            border-bottom: 3px solid {accent_color};
        }}
        QTabBar::tab:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(50, 50, 64, 0.9), stop: 1 rgba(26, 26, 34, 0.9));
            color: {text_primary};
        }}

        QCheckBox, QRadioButton {{
            spacing: 8px;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid rgba(0, 0, 0, 0.5);
            border-top-color: rgba(0, 0, 0, 0.6);
            border-left-color: rgba(0, 0, 0, 0.5);
            border-bottom-color: {neumo_highlight};
            border-right-color: {light_bevel_soft};
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {inset_field}, stop: 1 {inset_deep});
        }}
        QCheckBox::indicator {{
            border-radius: 5px;
        }}
        QRadioButton::indicator {{
            border-radius: 9px;
        }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.5 {accent_color}, stop: 1 {accent_dark});
            border: 2px solid {accent_darker};
            border-top-color: {bevel_hi};
        }}

        QSlider::groove:horizontal {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(0, 0, 0, 0.55), stop: 1 rgba(0, 0, 0, 0.3));
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(200, 204, 216, 0.95), stop: 0.5 rgba(120, 124, 140, 0.95), stop: 1 rgba(70, 72, 88, 0.95));
            border: 2px solid rgba(0, 0, 0, 0.5);
            border-top-color: {light_bevel};
            border-bottom-color: rgba(0, 0, 0, 0.5);
            width: 18px;
            margin: -8px 0;
            border-radius: 9px;
        }}

        QTextEdit, #consoleOutput {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 rgba(0, 0, 0, 0.5), stop: 1 rgba(0, 0, 0, 0.4));
            border: 2px solid rgba(0, 0, 0, 0.5);
            border-top-color: rgba(0, 0, 0, 0.6);
            border-left-color: rgba(0, 0, 0, 0.5);
            border-bottom-color: {neumo_highlight};
            border-right-color: {light_bevel_soft};
            border-radius: 10px;
            color: #5ee87a;
            padding: 10px;
            font-family: 'Consolas', 'Courier New', monospace;
        }}

        #advancedFrame {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {inset_field}, stop: 1 {inset_deep});
            border: 2px solid rgba(0, 0, 0, 0.5);
            border-top-color: rgba(0, 0, 0, 0.6);
            border-left-color: rgba(0, 0, 0, 0.5);
            border-bottom-color: {neumo_highlight};
            border-right-color: {light_bevel_soft};
            border-radius: 10px;
            padding: 10px;
        }}
        #totalSizeLabel {{
            color: {text_secondary};
            font-size: 9pt;
        }}
    '''


def get_glassmorphism_theme(accent_color='#1DB954', glass_opacity=88, gradient_colors=None, secondary_accent=None):
    """Tema Glassmorfismo: cristal esmerilado sobre gradiente de colores.
    gradient_colors: lista de 4 colores hex para el degradado del fondo.
    secondary_accent: color para bordes/brillos (sombra) de los botones.
    Conserva los demás temas intactos.
    """
    colors = list(gradient_colors or [])
    if len(colors) < 4:
        colors = (colors + ['#1E1B4B', '#312E81', '#0E7490', '#134E4A'])[:4]
    c0, c1, c2, c3 = colors[0], colors[1], colors[2], colors[3]
    accent_hover = lighten_color(accent_color, 0.12)
    accent_soft = accent_rgba(accent_color, 0.35)
    accent_muted = accent_rgba(accent_color, 0.18)
    secondary = secondary_accent or accent_color
    gloss_top = lighten_color(secondary, 0.18)
    gloss_hover = lighten_color(secondary, 0.32)
    secondary_soft = accent_rgba(secondary, 0.4)
    try:
        accent_dark = QColor(accent_color).darker(150).name()
        accent_darker = QColor(secondary).darker(230).name()
        bevel_side = lighten_color(secondary, 0.08)
        accent_hover_dark = QColor(accent_color).darker(140).name()
    except Exception:
        accent_dark = '#15823E'
        accent_darker = '#0B401D'
        bevel_side = '{bevel_side}'
        accent_hover_dark = '{accent_hover_dark}'
    t = max(50, min(100, int(glass_opacity))) / 100.0
    panel_alpha = 0.08 + (t - 0.5) * 0.12
    card_alpha = 0.10 + (t - 0.5) * 0.14
    border_alpha = 0.16 + (t - 0.5) * 0.08
    glass_panel = f'rgba(255, 255, 255, {panel_alpha:.2f})'
    glass_card = f'rgba(255, 255, 255, {card_alpha:.2f})'
    glass_border = f'rgba(255, 255, 255, {border_alpha:.2f})'
    glass_border_hi = f'rgba(255, 255, 255, {min(0.5, border_alpha + 0.14):.2f})'
    text_primary = '#FFFFFF'
    text_secondary = 'rgba(255, 255, 255, 0.78)'
    text_muted = 'rgba(255, 255, 255, 0.5)'
    return f'''
        /* —— Ventana principal: gradiente de colores —— */
        #container {{
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                       stop: 0 {c0}, stop: 0.45 {c1}, stop: 0.72 {c2}, stop: 1 {c3});
            border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.28);
        }}
        #titleBar {{
            background: rgba(255, 255, 255, 0.06);
            border-top-left-radius: 17px;
            border-top-right-radius: 17px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.12);
        }}
        #titleLabel {{
            color: {text_primary};
            font-weight: bold;
        }}
        #mainPanel {{
            background: {glass_panel};
            border: 1px solid {glass_border};
            border-top: 1px solid {glass_border_hi};
            border-radius: 16px;
        }}
        #sectionLabel {{
            color: {accent_color};
            font-weight: bold;
        }}
        QLabel, QRadioButton, QCheckBox {{
            color: {text_secondary};
        }}
        #loginStatusLabel {{
            color: {text_muted};
            font-size: 9pt;
        }}
        #versionStatusLabel {{
            color: {text_muted};
            font-size: 8pt;
        }}
        #updateLinkButton {{
            background: transparent;
            border: none;
            color: {text_muted};
            text-decoration: underline;
            font-size: 8pt;
            padding: 2px 4px;
        }}
        #updateLinkButton:hover {{
            color: {accent_color};
        }}
        #updateLinkButton[updateAvailable="true"] {{
            color: {accent_color};
            font-weight: bold;
        }}

        /* —— Campos de cristal esmerilado —— */
        QComboBox, QLineEdit {{
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid {glass_border};
            border-top: 1px solid rgba(255, 255, 255, 0.28);
            border-radius: 10px;
            padding: 10px 12px;
            color: {text_primary};
            selection-background-color: {accent_color};
        }}
        QComboBox:hover, QLineEdit:hover {{
            background: rgba(255, 255, 255, 0.16);
        }}
        QLineEdit:focus, QComboBox:focus {{
            border: 1px solid {accent_color};
            background: rgba(255, 255, 255, 0.18);
        }}
        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        QComboBox QAbstractItemView {{
            background: rgba(24, 26, 44, 0.95);
            border: 1px solid {glass_border};
            border-radius: 10px;
            color: {text_primary};
            selection-background-color: {accent_muted};
            selection-color: {text_primary};
        }}

        /* —— Botones primarios (acento) —— */
        QPushButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.45 {accent_color}, stop: 1 {accent_dark});
            border: 1px solid {accent_darker};
            border-top: 1px solid rgba(255, 255, 255, 0.45);
            border-radius: 10px;
            padding: 12px 16px;
            color: #0c0c10;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_hover}, stop: 0.45 {accent_hover}, stop: 1 {accent_hover_dark});
            border-top: 1px solid rgba(255, 255, 255, 0.6);
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {accent_dark}, stop: 0.55 {accent_color}, stop: 1 {gloss_top});
        }}
        QPushButton:disabled {{
            background: rgba(255, 255, 255, 0.18);
            color: rgba(255, 255, 255, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.15);
        }}
        #launchButton, #modInstallButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.45 {accent_color}, stop: 1 {accent_dark});
            border: 1px solid {accent_darker};
            border-top: 1px solid rgba(255, 255, 255, 0.5);
            border-radius: 12px;
            padding: 10px 16px;
            color: #0c0c10;
            font-weight: bold;
        }}
        #launchButton:hover, #modInstallButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_hover}, stop: 0.45 {accent_hover}, stop: 1 {accent_hover_dark});
            border-top: 1px solid rgba(255, 255, 255, 0.65);
        }}
        #launchButtonWrap {{
            background: transparent;
        }}
        #colorPickerButton {{
            padding: 5px;
            background: {glass_card};
            border: 1px solid {glass_border};
            color: {text_primary};
        }}
        #colorPickerButton:hover {{
            border: 1px solid {secondary_soft};
        }}
        #colorPreview {{
            border: 1px solid {glass_border};
            border-radius: 10px;
        }}

        /* —— Botones secundarios (cristal) —— */
        #advancedButton, #openModsFolderButton, #openModpacksFolderButton,
        #newInstallationButton, #remoteInstanceVerifyButton {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid {glass_border};
            border-top: 1px solid rgba(255, 255, 255, 0.28);
            color: {text_primary};
            font-weight: normal;
        }}
        #advancedButton:hover, #openModsFolderButton:hover, #openModpacksFolderButton:hover,
        #newInstallationButton:hover, #remoteInstanceVerifyButton:hover {{
            background: rgba(255, 255, 255, 0.16);
            border: 1px solid {secondary_soft};
        }}
        #advancedButton:checked {{
            background: {accent_muted};
            border: 1px solid {secondary_soft};
        }}

        #closeButton, #minimizeButton {{
            font-size: 12pt;
            font-weight: bold;
            border-radius: 15px;
            padding: 0;
        }}
        #closeButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF7A66, stop: 0.5 #E23D28, stop: 1 #A82312);
            border: 1px solid #7A150A;
            border-top: 1px solid #FFB3A6;
            color: white;
        }}
        #closeButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF9888, stop: 0.5 #F2472F, stop: 1 #C02A16);
        }}
        #minimizeButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FFD27A, stop: 0.5 #F8B339, stop: 1 #C07F16);
            border: 1px solid #8A5C0F;
            border-top: 1px solid #FFE3A8;
            color: white;
        }}
        #minimizeButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FFE0A0, stop: 0.5 #FAC44F, stop: 1 #D08F1C);
        }}

        QProgressBar {{
            background: rgba(0, 0, 0, 0.28);
            border: 1px solid {glass_border};
            border-radius: 8px;
            text-align: center;
            color: {text_primary};
            font-weight: bold;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.5 {accent_color}, stop: 1 {accent_dark});
            border-radius: 6px;
        }}

        /* —— Listas y tarjetas de cristal —— */
        #modList, #newsList {{
            background: rgba(0, 0, 0, 0.22);
            border: 1px solid {glass_border};
            border-radius: 12px;
        }}
        QListWidget {{
            background-color: transparent;
            border: none;
            outline: none;
        }}
        QListWidget::item {{
            background: transparent;
            border: none;
            padding: 4px 2px;
        }}
        QListWidget::item:selected {{
            background: transparent;
        }}
        #modList::item:selected {{
            background-color: {accent_muted};
            border-radius: 10px;
        }}
        #modList::item:hover {{
            background-color: rgba(255, 255, 255, 0.06);
            border-radius: 10px;
        }}

        #modpackCard {{
            background: {glass_card};
            border: 1px solid {glass_border};
            border-top: 1px solid {glass_border_hi};
            border-radius: 12px;
        }}
        #modpackCard[selected="true"] {{
            background: {accent_muted};
            border: 1px solid {accent_color};
        }}
        #modpackSelectIndicator {{
            color: {text_muted};
            font-size: 14px;
            font-weight: bold;
        }}
        #modpackCard[selected="true"] #modpackSelectIndicator {{
            color: {accent_color};
        }}

        #modCard, #versionCard, #installedModCard, #newsCard {{
            background: {glass_card};
            border: 1px solid {glass_border};
            border-top: 1px solid {glass_border_hi};
            border-radius: 12px;
            padding: 8px;
        }}
        #modCard:hover, #versionCard:hover, #installedModCard:hover, #newsCard:hover {{
            background: rgba(255, 255, 255, 0.18);
            border: 1px solid {secondary_soft};
        }}
        #modTitle, #modName, #versionIdLabel {{
            color: {text_primary};
            font-weight: bold;
        }}
        #modAuthor, #modStats, #modDetails, #modDescription, #modFilename,
        #versionTypeLabel, #versionSizeLabel {{
            color: {text_secondary};
        }}
        #versionBadge {{
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid {glass_border};
            color: {text_primary};
            border-radius: 6px;
            padding: 3px 8px;
        }}
        #modDeleteButton, #deleteButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF7A66, stop: 0.5 #E23D28, stop: 1 #A82312);
            border: 1px solid #7A150A;
            border-top: 1px solid #FFB3A6;
            color: white;
        }}
        #modDeleteButton:hover, #deleteButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF9888, stop: 0.5 #F2472F, stop: 1 #C02A16);
        }}
        #versionCard QPushButton {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid {glass_border};
            border-top: 1px solid rgba(255, 255, 255, 0.28);
            padding: 5px 10px;
            border-radius: 8px;
            color: {text_primary};
            font-weight: normal;
        }}
        #versionCard #deleteButton {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF7A66, stop: 0.5 #E23D28, stop: 1 #A82312);
            border: 1px solid #7A150A;
            border-top: 1px solid #FFB3A6;
            color: white;
        }}
        #versionCard #deleteButton:hover {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 #FF9888, stop: 0.5 #F2472F, stop: 1 #C02A16);
        }}
        #versionCard QPushButton:hover {{
            background: rgba(255, 255, 255, 0.16);
            border: 1px solid {secondary_soft};
        }}
        #versionIdLabel {{
            font-size: 14pt;
        }}
        #toggleSwitch {{
            font-family: "Segoe UI Symbol";
            font-weight: bold;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid {glass_border};
            border-top: 1px solid rgba(255, 255, 255, 0.28);
            color: {text_secondary};
        }}
        #toggleSwitch:checked {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.5 {accent_color}, stop: 1 {accent_dark});
            border: 1px solid {accent_darker};
            border-top: 1px solid rgba(255, 255, 255, 0.45);
            color: #0c0c10;
        }}

        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 10px;
            margin: 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 0.25);
            min-height: 30px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {secondary_soft};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            border: none;
            background: none;
        }}

        #errorLabel {{
            color: #ff8080;
            font-weight: bold;
        }}

        /* —— Pestañas de cristal —— */
        QTabWidget::pane {{
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid {glass_border};
            border-radius: 14px;
            margin-top: -1px;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {text_muted};
            padding: 10px 16px;
            margin-right: 4px;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            border: 1px solid transparent;
        }}
        QTabBar::tab:selected {{
            background: rgba(255, 255, 255, 0.14);
            color: {text_primary};
            border: 1px solid {glass_border};
            border-bottom: 2px solid {accent_color};
        }}
        QTabBar::tab:hover {{
            background: rgba(255, 255, 255, 0.08);
            color: {text_primary};
        }}

        QCheckBox, QRadioButton {{
            spacing: 8px;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {glass_border};
            border-top: 1px solid rgba(255, 255, 255, 0.3);
            background: rgba(255, 255, 255, 0.14);
        }}
        QCheckBox::indicator {{
            border-radius: 5px;
        }}
        QRadioButton::indicator {{
            border-radius: 9px;
        }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {gloss_top}, stop: 0.5 {accent_color}, stop: 1 {accent_dark});
            border: 1px solid {accent_darker};
            border-top: 1px solid rgba(255, 255, 255, 0.45);
        }}

        QSlider::groove:horizontal {{
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid {glass_border};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: #FFFFFF;
            border: 2px solid {accent_color};
            width: 18px;
            margin: -8px 0;
            border-radius: 9px;
        }}

        QTextEdit, #consoleOutput {{
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid {glass_border};
            border-radius: 10px;
            color: #5ee87a;
            padding: 10px;
            font-family: 'Consolas', 'Courier New', monospace;
        }}

        #advancedFrame {{
            background: rgba(0, 0, 0, 0.22);
            border: 1px solid {glass_border};
            border-radius: 10px;
            padding: 10px;
        }}
        #totalSizeLabel {{
            color: {text_secondary};
            font-size: 9pt;
        }}
    '''

import math
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QCheckBox
from PySide6.QtGui import QIcon
class VersionListItemWidget(QWidget):
    delete_requested = Signal(str)
    repair_requested = Signal(str)
    open_folder_requested = Signal(str)
    rename_requested = Signal(str)
    selection_changed = Signal(str, bool)
    def __init__(self, base_version, version_types, icons, lang_dict, parent=None, can_rename=True):
        super().__init__(parent)
        self.base_version = base_version
        self.version_types = version_types
        self.icons = icons
        self.lang_dict = lang_dict
        self.can_rename = can_rename
        self.init_ui()
        self.apply_styles()
    def get_main_icon(self):
        lower_types = [v.lower() for v in self.version_types]
        if 'fabric' in lower_types:
            return self.icons.get('fabric', self.icons['vanilla'])
        else:
            if 'forge' in lower_types:
                return self.icons.get('forge', self.icons['vanilla'])
            else:
                return self.icons['vanilla']
    def init_ui(self):
        self.setObjectName('versionCard')
        self.setMinimumHeight(80)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        self.checkbox = QCheckBox()
        self.checkbox.setFixedSize(20, 20)
        self.checkbox.clicked.connect(self.on_selection_changed)
        main_layout.addWidget(self.checkbox)
        main_layout.addSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(self.get_main_icon().pixmap(QSize(36, 36)))
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignCenter)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.id_label = QLabel(self.base_version)
        self.id_label.setObjectName('versionIdLabel')
        details_layout = QHBoxLayout()
        types_text = ', '.join(self.version_types)
        self.type_label = QLabel(self.lang_dict.get('version_type_label', 'Type: {type}').format(type=types_text))
        self.type_label.setObjectName('versionTypeLabel')
        self.size_label = QLabel(self.lang_dict.get('calculating_size_short', 'Size: ...'))
        self.size_label.setObjectName('versionSizeLabel')
        details_layout.addWidget(self.type_label)
        details_layout.addStretch()
        details_layout.addWidget(self.size_label)
        info_layout.addWidget(self.id_label)
        info_layout.addLayout(details_layout)
        info_layout.addStretch()
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        self.open_folder_button = self.create_button(self.lang_dict.get('open_folder', 'Folder'), self.icons['folder'], self.open_folder)
        self.repair_button = self.create_button(self.lang_dict.get('repair', 'Repair'), self.icons['repair'], self.repair_version)
        self.rename_button = self.create_button('', self.icons.get('edit'), self.rename_instance)
        self.rename_button.setToolTip(self.lang_dict.get('rename', 'Rename'))
        self.rename_button.setVisible(self.can_rename)
        self.delete_button = self.create_button(self.lang_dict.get('delete', 'Delete'), self.icons['delete'], self.delete_version)
        self.delete_button.setObjectName('deleteButton')
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.open_folder_button)
        buttons_layout.addWidget(self.repair_button)
        buttons_layout.addWidget(self.rename_button)
        buttons_layout.addWidget(self.delete_button)
        main_layout.addWidget(icon_label)
        main_layout.addSpacing(15)
        main_layout.addLayout(info_layout, 1)
        main_layout.addLayout(buttons_layout)
    def create_button(self, text, icon, on_click):
        button = QPushButton(text)
        if icon:
            button.setIcon(icon)
        button.setIconSize(QSize(16, 16))
        button.clicked.connect(on_click)
        return button
    def delete_version(self):
        self.delete_requested.emit(self.base_version)
    def repair_version(self):
        self.repair_requested.emit(self.base_version)
    def rename_instance(self):
        self.rename_requested.emit(self.base_version)
    def open_folder(self):
        self.open_folder_requested.emit(self.base_version)
    def on_selection_changed(self):
        self.selection_changed.emit(self.base_version, self.checkbox.isChecked())
    def is_selected(self):
        return self.checkbox.isChecked()
    @staticmethod
    def format_size(size_bytes):
        if size_bytes <= 0:
            return '0 B'
        else:
            size_name = ('B', 'KB', 'MB', 'GB', 'TB')
            try:
                i = int(math.floor(math.log(size_bytes, 1024)))
                p = math.pow(1024, i)
                s = round(size_bytes / p, 2)
                return f'{s} {size_name[i]}'
            except (ValueError, IndexError):
                return '0 B'
    def update_size(self, size_bytes):
        size_str = self.format_size(size_bytes)
        self.size_label.setText(self.lang_dict.get('version_size_label', 'Size: {size}').format(size=size_str))
    def apply_styles(self):
        return
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
class ModpackListItemWidget(QWidget):
    """Tarjeta compacta de modpack remoto con indicador de selección."""
    def __init__(self, manifest: dict, lang_dict: dict, parent=None):
        super().__init__(parent)
        self.manifest = manifest
        self.lang_dict = lang_dict
        self.setObjectName('modpackCard')
        self.setProperty('selected', 'false')
        self.setMinimumHeight(56)
        self._build_ui()
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        self.indicator = QLabel('○')
        self.indicator.setObjectName('modpackSelectIndicator')
        self.indicator.setFixedWidth(18)
        self.indicator.setAlignment(Qt.AlignCenter)
        info = QVBoxLayout()
        info.setSpacing(2)
        name = self.manifest.get('name', 'Modpack')
        ver = self.manifest.get('game_version', '?')
        loader = self.manifest.get('loader', '?')
        loader_ver = str(self.manifest.get('loader_version') or '').strip()
        loader_part = f'{loader} {loader_ver}' if loader_ver else str(loader)
        self.title_label = QLabel(name)
        self.title_label.setObjectName('modTitle')
        self.detail_label = QLabel(self.lang_dict.get('modpack_card_details', '{version} · {loader}').format(version=ver, loader=loader_part))
        self.detail_label.setObjectName('modDetails')
        info.addWidget(self.title_label)
        info.addWidget(self.detail_label)
        layout.addWidget(self.indicator)
        layout.addLayout(info, 1)
    def set_selected(self, selected: bool):
        self.setProperty('selected', 'true' if selected else 'false')
        self.indicator.setText('●' if selected else '○')
        self.style().unpolish(self)
        self.style().polish(self)
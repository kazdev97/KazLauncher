from PySide6.QtCore import QThread, Signal
class JavaEnsureWorker(QThread):
    """Descarga/instala Java en segundo plano antes de lanzar Minecraft."""
    status = Signal(str)
    finished = Signal(object, object)
    def __init__(self, mc_version: str, preferred_java: str | None=None, parent=None, min_major: int | None=None, versions_dir: str | None=None):
        super().__init__(parent)
        self.mc_version = mc_version
        self.preferred_java = preferred_java
        self.min_major = min_major
        self.versions_dir = versions_dir
    def run(self):
        from kaz_launcher.utils.java_installer import ensure_java_for_minecraft
        def on_status(msg: str):
            self.status.emit(msg)
        path, err = ensure_java_for_minecraft(self.mc_version, preferred_exe=self.preferred_java, on_status=on_status, min_major=self.min_major, versions_dir=self.versions_dir)
        self.finished.emit(path, err)
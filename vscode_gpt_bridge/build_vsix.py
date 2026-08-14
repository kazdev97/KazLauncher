import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent
vsix_path = root / 'kaz-gpt-bridge.vsix'
with zipfile.ZipFile(vsix_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    for p in root.rglob('*'):
        if p.is_file() and p.name != 'kaz-gpt-bridge.vsix':
            relative_path = p.relative_to(root).as_posix()
            zf.write(p, 'extension/' + relative_path)
print(vsix_path)

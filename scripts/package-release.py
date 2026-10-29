"""Package only the runnable app and maintained project files, never archive/test profiles."""
from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parents[1]
release = root / 'releases'
release.mkdir(exist_ok=True)
archive = release / 'FreshTray-Windows-and-Source.zip'
folders = ('app', 'src', 'tests', 'scripts')
files = [root / name for name in ('README.md', 'Run FreshTray.cmd', 'Preview.cmd', '.gitignore', 'LICENSE')]
files.extend(root/'docs'/name for name in ('SETUP.md','SECURITY.md','DEVELOPING.md','RELEASE_NOTES.md','THIRD_PARTY_NOTICES.md'))
files.extend(p for p in (root/'docs/licenses').rglob('*') if p.is_file())
for folder in folders:
    files.extend(p for p in (root / folder).rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts and p.suffix != '.pyc')
for file in files:
    if file.suffix == '.dpapi' or file.name == 'settings.json':
        raise RuntimeError('A local profile was found in the delivery folders.')
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for file in sorted(files):
        z.write(file, Path('FreshTray') / file.relative_to(root))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    names = z.namelist()
    for required in ('app/FreshTray/FreshTray.exe', 'src/main.pyw', 'src/freshtray/api.py',
                     'src/assets/freshtray.ico', 'README.md', 'docs/USER_GUIDE.md', 'scripts/build.ps1'):
        assert 'FreshTray/' + required in names, required
    assert not any('/archive/' in name or '/.build/' in name for name in names)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(release / 'FreshTray-Windows-and-Source.sha256.txt').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
print(f'Archive verified: {len(files)} files, {archive.stat().st_size / 1024 / 1024:.1f} MB')

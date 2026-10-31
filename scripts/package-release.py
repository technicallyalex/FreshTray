"""Prepare local release assets only; never publishes or includes account profiles."""
from pathlib import Path
import hashlib
import re
import shutil
import zipfile

root=Path(__file__).resolve().parents[1]
version=re.search(r'__version__ = "([0-9.]+)"',(root/'src/freshtray/__init__.py').read_text(encoding='utf-8')).group(1)
release=root/'releases';release.mkdir(exist_ok=True)
source=root/'app'/f'FreshTray-{version}.exe'
if not source.is_file():
    raise SystemExit(f'Build and verify app/FreshTray-{version}.exe first.')
exe=release/f'FreshTray-{version}.exe'
shutil.copy2(source,exe)
archive=release/f'FreshTray-{version}-Windows-x64.zip'
allowed=[root/'README.md',root/'LICENSE']
allowed.extend(root/'docs'/name for name in ('SETUP.md','USAGE.md','SECURITY.md','DEVELOPING.md','RELEASE_NOTES.md','THIRD_PARTY_NOTICES.md'))
allowed.extend(p for folder in ('docs/licenses','docs/images') for p in (root/folder).rglob('*') if p.is_file())
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    z.write(exe,exe.name)
    for path in sorted(allowed):
        assert path.suffix.lower() not in ('.dpapi','.log') and path.name!='settings.json'
        z.write(path,path.relative_to(root).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert {exe.name,'README.md','LICENSE','docs/SETUP.md','docs/USAGE.md','docs/images/reminder.png'} <= set(z.namelist())
for asset in (exe,archive):
    digest=hashlib.sha256(asset.read_bytes()).hexdigest()
    asset.with_name(asset.name+'.sha256.txt').write_text(f'{digest}  {asset.name}\n',encoding='ascii')
print(f'Prepared {exe.name} and {archive.name}, with SHA-256 checksums. Nothing uploaded.')

"""Official GitHub release discovery and transactional portable updates.

No credentials are sent. Download hashes protect integrity, not publisher identity.
"""
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit
import hashlib,json,os,re,shutil,struct,subprocess,tempfile,time,uuid

REPOSITORY='technicallyalex/FreshTray'
API=f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
WEB=f'https://github.com/{REPOSITORY}'
MAX_EXE=256*1024*1024
HOSTS={'api.github.com','github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}
class UpdateError(ValueError):pass
class Canceled(UpdateError):pass

def version(value):
    if not isinstance(value,str) or not re.fullmatch(r'v?\d{1,4}\.\d{1,4}(?:\.\d{1,4})?',value):
        raise UpdateError('The release version is not supported.')
    parts=tuple(map(int,value.lstrip('v').split('.')))
    return parts+(0,)*(3-len(parts))

def checked_url(url):
    u=urlsplit(url)
    if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password or u.port not in (None,443):
        raise UpdateError('The update download is not on an approved GitHub host.')
    return url
class Redirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        checked_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def open_url(url):
    req=Request(checked_url(url),headers={'User-Agent':'FreshTray-Updater','Accept':'application/vnd.github+json' if url==API else 'application/octet-stream'})
    return build_opener(Redirects()).open(req,timeout=10)

def small_get(url,limit,opener=open_url):
    with opener(url) as response:
        checked_url(response.geturl())
        data=response.read(limit+1)
    if len(data)>limit:raise UpdateError('The update response is too large.')
    return data

@dataclass(frozen=True)
class Release:
    version:str
    notes:str
    url:str
    asset:str
    checksum:str
    size:int
    digest:str

def parse_release(data,current):
    if not isinstance(data,dict) or data.get('draft') or data.get('prerelease'):return None
    tag=data.get('tag_name','');latest=version(tag)
    if latest<=version(current):return None
    number=tag.lstrip('v');page=f'{WEB}/releases/tag/{tag}'
    if data.get('html_url')!=page:raise UpdateError('The release does not belong to FreshTray.')
    filename=f'FreshTray-{number}.exe';assets=data.get('assets',[])
    def asset(name):
        found=[a for a in assets if a.get('name')==name and a.get('state')=='uploaded']
        if len(found)!=1:raise UpdateError('This release is missing its portable executable or checksum.')
        item=found[0];expected=f'{WEB}/releases/download/{tag}/{name}'
        if item.get('browser_download_url')!=expected:raise UpdateError('Unexpected release asset address.')
        return item
    exe=asset(filename);check=asset(filename+'.sha256.txt')
    size=exe.get('size')
    if type(size) is not int or not 1024<=size<=MAX_EXE:raise UpdateError('Invalid executable size.')
    digest=exe.get('digest') or ''
    if digest and not re.fullmatch('sha256:[0-9a-f]{64}',digest):raise UpdateError('Invalid release digest.')
    notes=data.get('body') or 'No release notes were provided.'
    if not isinstance(notes,str):raise UpdateError('Invalid release notes.')
    return Release(number,notes[:100000],page,exe['browser_download_url'],check['browser_download_url'],size,digest)

def latest_release(current,opener=open_url):
    try:return parse_release(json.loads(small_get(API,1024*1024,opener)),current)
    except (json.JSONDecodeError,UnicodeError) as exc:raise UpdateError('GitHub returned an invalid release response.') from exc

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

def executable(path):
    with Path(path).open('rb') as f:
        header=f.read(64)
        if len(header)!=64 or header[:2]!=b'MZ':raise UpdateError('The download is not a Windows executable.')
        offset=struct.unpack_from('<I',header,60)[0]
        if offset>1024*1024:raise UpdateError('Invalid executable header.')
        f.seek(offset)
        if f.read(6)!=b'PE\0\0\x64\x86':raise UpdateError('The download is not a Windows x64 executable.')

def staging_root():return Path(os.environ['LOCALAPPDATA'])/'FreshTray'/'updates'

def download(release,root,cancel,progress,opener=open_url):
    checksum=small_get(release.checksum,1024,opener).decode('ascii').strip()
    match=re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?(FreshTray-[0-9.]+\.exe)',checksum)
    if not match or match[2]!=f'FreshTray-{release.version}.exe':raise UpdateError('The release checksum is invalid.')
    expected=match[1].lower()
    if release.digest and release.digest!='sha256:'+expected:raise UpdateError('The release checksums disagree.')
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    stage=root/uuid.uuid4().hex;stage.mkdir()
    path=stage/'download.exe';total=0;started=time.monotonic()
    try:
        with opener(release.asset) as response,path.open('xb') as out:
            checked_url(response.geturl())
            while True:
                if cancel.is_set():raise Canceled('Download canceled.')
                if time.monotonic()-started>600:raise UpdateError('The download timed out. Try again later.')
                chunk=response.read(256*1024)
                if not chunk:break
                total+=len(chunk)
                if total>release.size:raise UpdateError('The download size does not match the release.')
                out.write(chunk);progress(int(total*100/release.size))
        if total!=release.size or sha(path)!=expected:raise UpdateError('The download failed its integrity check. Nothing was installed.')
        executable(path)
        return dict(stage=str(stage),download=str(path),digest=expected,version=release.version)
    except BaseException:
        path.unlink(missing_ok=True)
        stage.rmdir()
        raise

def spawn(args):
    env=dict(os.environ,PYINSTALLER_RESET_ENVIRONMENT='1')
    return subprocess.Popen(args,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0),close_fds=True)

def prepare_install(downloaded,target,args):
    target=Path(target).absolute();stage=Path(downloaded['stage'])
    if target.is_symlink() or not target.is_file() or target.suffix.lower()!='.exe':raise UpdateError('The current portable executable could not be located.')
    # Probe permissions before asking the app to exit. Never request elevation.
    with tempfile.NamedTemporaryFile(dir=target.parent,prefix='.FreshTray-write-test-'):pass
    if sha(downloaded['download'])!=downloaded['digest']:raise UpdateError('The staged download changed. Download it again.')
    helper=stage/'update-helper.exe';shutil.copy2(target,helper)
    plan=dict(downloaded,target=str(target),old_digest=sha(target),args=list(args),pid=os.getpid())
    path=stage/'plan.json';path.write_text(json.dumps(plan),encoding='utf-8')
    return str(path)

def read_plan(path,root=None):
    path=Path(path).absolute();root=Path(root or staging_root()).resolve()
    if path.name!='plan.json' or path.parent.parent.resolve()!=root or not re.fullmatch('[0-9a-f]{32}',path.parent.name) or path.is_symlink():raise UpdateError('Invalid update plan location.')
    if path.stat().st_size>32768:raise UpdateError('Invalid update plan size.')
    plan=json.loads(path.read_text(encoding='utf-8'))
    if Path(plan['stage']).resolve()!=path.parent.resolve() or Path(plan['download']).resolve()!=path.parent/'download.exe':raise UpdateError('Invalid staged download location.')
    if type(plan.get('pid')) is not int or plan['pid']<=0:raise UpdateError('Invalid update process.')
    target=Path(plan['target'])
    if not target.is_absolute() or target.suffix.lower()!='.exe' or target.is_symlink() or target.parent.resolve()==path.parent.resolve():raise UpdateError('Invalid portable executable location.')
    if not all(re.fullmatch('[0-9a-f]{64}',plan.get(k,'')) for k in ('digest','old_digest')):raise UpdateError('Invalid update hashes.')
    if not isinstance(plan.get('args'),list) or not all(isinstance(a,str) for a in plan['args']):raise UpdateError('Invalid restart arguments.')
    version(plan['version'])
    return path,plan

def mark_ready(path,target,root=None):
    path,plan=read_plan(path,root)
    if Path(target).resolve()!=Path(plan['target']).resolve() or sha(target)!=plan['digest']:raise UpdateError('The updated application could not be verified.')
    from . import __version__
    if version(plan['version'])!=version(__version__):raise UpdateError('The installed version does not match the update.')
    (path.parent/'ready.json').write_text(json.dumps({'version':plan['version']}),encoding='utf-8')

def terminate_child(child):
    if os.name=='nt':
        command=Path(os.environ['SystemRoot'])/'System32/taskkill.exe'
        subprocess.run([str(command),'/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,timeout=15)
    else:child.terminate()
    try:child.wait(timeout=10)
    except subprocess.TimeoutExpired:pass

def apply_plan(path,root=None,launch=spawn,timeout=90,health_timeout=45):
    """Runs in a copied EXE after the GUI exits. Retains backup on any failure."""
    path,plan=read_plan(path,root);target=Path(plan['target']);payload=Path(plan['download'])
    backup=target.with_name(target.stem+'.previous-'+path.parent.name+'.exe')
    incoming=target.with_name('.FreshTray-update-'+path.parent.name+'.tmp')
    result=path.parent/'result.json';moved=False;installed=False;child=None
    try:
        if os.name=='nt' and plan.get('pid')!=os.getpid():
            import ctypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.restype=ctypes.c_void_p
            handle=kernel.OpenProcess(0x100000,False,plan['pid'])
            if handle:
                try:
                    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
                    if kernel.WaitForSingleObject(handle,int(timeout*1000))!=0:raise UpdateError('FreshTray did not finish closing.')
                finally:
                    kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle)
        if sha(target)!=plan['old_digest'] or sha(payload)!=plan['digest']:raise UpdateError('The executable changed after update preparation.')
        executable(payload)
        shutil.copy2(payload,incoming)
        deadline=time.monotonic()+timeout
        while True:
            try:
                if backup.exists():raise UpdateError('An update backup already exists.')
                target.rename(backup);moved=True;break
            except PermissionError:
                if time.monotonic()>=deadline:raise UpdateError('FreshTray did not finish closing. Try the update again.')
                time.sleep(.25)
        incoming.rename(target);installed=True
        (path.parent/'ready.json').unlink(missing_ok=True)
        child=launch([str(target),*plan['args'],'--update-receipt',str(path)])
        deadline=time.monotonic()+health_timeout
        while not (path.parent/'ready.json').exists():
            if child.poll() is not None or time.monotonic()>=deadline:raise UpdateError('The new build did not start successfully. The previous build has been restored.')
            time.sleep(.2)
        receipt=json.loads((path.parent/'ready.json').read_text(encoding='utf-8'))
        if receipt.get('version')!=plan['version']:raise UpdateError('The new app did not confirm the expected version.')
        result.write_text(json.dumps({'ok':True,'version':plan['version']}),encoding='utf-8')
        try:
            backup.unlink(missing_ok=True);payload.unlink(missing_ok=True)
        except OSError:pass  # Cleanup cannot turn a healthy update into a rollback.
        return True
    except Exception:
        if child is not None and child.poll() is None:
            try:terminate_child(child)
            except (OSError,subprocess.TimeoutExpired):pass
        if moved:
            # Windows may briefly retain a lock while the one-file parent exits.
            deadline=time.monotonic()+30
            while True:
                try:
                    if installed:target.unlink(missing_ok=True)
                    backup.rename(target);break
                except PermissionError:
                    if time.monotonic()>=deadline:break  # Keep backup for manual recovery.
                    time.sleep(.25)
        result.write_text(json.dumps({'ok':False,'message':'The update could not finish. Your previous executable or its .previous backup has been retained. Account data was not changed.'}),encoding='utf-8')
        if target.is_file() and sha(target)==plan['old_digest']:
            launch([str(target),*plan['args']])
        return False
    finally:
        try:incoming.unlink(missing_ok=True)
        except OSError:pass


def prune_staging(root,keep=None,now=None):
    """Bounded cleanup of our old UUID directories, never arbitrary profile files."""
    root=Path(root)
    if not root.is_dir():return
    now=time.time() if now is None else now
    known={'download.exe','update-helper.exe','plan.json','ready.json','result.json'}
    from itertools import islice
    try:stages=list(islice(root.iterdir(),40))
    except OSError:return
    for stage in stages:
        if stage.is_symlink() or not stage.is_dir() or not re.fullmatch('[0-9a-f]{32}',stage.name):continue
        if keep and stage.resolve()==Path(keep).parent.resolve():continue
        try:
            if now-stage.stat().st_mtime<7*86400:continue
            files=list(stage.iterdir())
            if any(p.name not in known or not p.is_file() or p.is_symlink() for p in files):continue
            for p in files:p.unlink()
            stage.rmdir()
        except OSError:pass

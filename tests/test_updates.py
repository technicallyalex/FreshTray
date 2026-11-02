import io,json,tempfile,unittest,struct,threading
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from freshtray import updates as u
from freshtray import __version__

class Response(io.BytesIO):
    def __init__(self,data,url):super().__init__(data);self.url=url
    def geturl(self):return self.url

def pe(tail=b'new'):
    data=bytearray(2048);data[:2]=b'MZ';struct.pack_into('<I',data,60,128);data[128:134]=b'PE\0\0\x64\x86'
    return bytes(data)+tail

def release(number='0.3'):
    base=f'{u.WEB}/releases/download/v{number}/FreshTray-{number}.exe'
    return dict(tag_name='v'+number,html_url=f'{u.WEB}/releases/tag/v{number}',body='Patch notes',draft=False,prerelease=False,
      assets=[dict(name=f'FreshTray-{number}.exe',browser_download_url=base,state='uploaded',size=len(pe()),digest='sha256:'+u.hashlib.sha256(pe()).hexdigest()),dict(name=f'FreshTray-{number}.exe.sha256.txt',browser_download_url=base+'.sha256.txt',state='uploaded')])

class UpdateTests(unittest.TestCase):
    def test_numeric_versions(self):
        self.assertEqual(u.version('v0.2'),(0,2,0));self.assertGreater(u.version('0.10'),u.version('0.9.9'))
        for value in ('0.3-beta','../0.3','v0','0.2.1.4','https://evil.test'):
            with self.assertRaises(u.UpdateError):u.version(value)
    def test_no_downgrade_or_same_version(self):
        self.assertIsNone(u.parse_release(release('0.2'),'0.2.1'))
        self.assertIsNone(u.parse_release(release('0.2'),'0.2.0'))
    def test_release_candidate_upgrade_path(self):
        self.assertIsNone(u.parse_release(release('0.2'),'0.3.0-rc.1'))
        self.assertIsNotNone(u.parse_release(release('0.3'),'0.3.0-rc.1'))
        self.assertGreater(u.version_key('0.3.0'),u.version_key('0.3.0-rc.2'))
        self.assertGreater(u.version_key('0.3.0-rc.2'),u.version_key('0.3.0-rc.1'))
        candidate=release('0.3.0-rc.1');candidate['prerelease']=True
        self.assertIsNone(u.parse_release(candidate,'0.2'))
    def test_drafts_and_prereleases_excluded(self):
        for key in ('draft','prerelease'):
            data=release();data[key]=True;self.assertIsNone(u.parse_release(data,'0.2'))
    def test_official_release_and_notes(self):
        r=u.parse_release(release(),'0.2');self.assertEqual(r.notes,'Patch notes');self.assertEqual(r.version,'0.3')
    def test_host_checks(self):
        for url in ('http://github.com/a','https://github.com.evil.test/a','https://github.com@evil.test/a','file:///a','https://github.com:444/a'):
            with self.assertRaises(u.UpdateError):u.checked_url(url)
        with self.assertRaises(u.UpdateError):u.Redirects().redirect_request(None,None,302,'',{},'https://evil.test/payload')
    def test_wrong_repository_and_asset(self):
        for field in ('html_url','browser_download_url'):
            data=release()
            if field=='html_url':data[field]='https://github.com/other/FreshTray/releases/tag/v0.3'
            else:data['assets'][0][field]='https://github.com/other/FreshTray/releases/download/v0.3/test.exe'
            with self.assertRaises(u.UpdateError):u.parse_release(data,'0.2')
    def test_missing_duplicate_and_oversized_assets(self):
        variants=[release(),release(),release()]
        variants[0]['assets'].pop();variants[1]['assets'].append(variants[1]['assets'][0]);variants[2]['assets'][0]['size']=u.MAX_EXE+1
        for data in variants:
            with self.assertRaises(u.UpdateError):u.parse_release(data,'0.2')
    def download(self,folder,data=None,checksum=None,cancel=False,body=None):
        r=u.parse_release(data or release(),'0.2');body=body if body is not None else pe()
        checksum=checksum if checksum is not None else u.hashlib.sha256(pe()).hexdigest()+'  FreshTray-0.3.exe\n'
        def opener(url):return Response(checksum.encode() if url.endswith('.txt') else body,url)
        event=threading.Event()
        if cancel:event.set()
        progress=[];result=u.download(r,folder,event,progress.append,opener)
        return result,progress
    def test_verified_download(self):
        with tempfile.TemporaryDirectory() as d:
            result,progress=self.download(d);self.assertEqual(Path(result['download']).read_bytes(),pe());self.assertEqual(progress[-1],100)
    def test_corrupt_download_cleans_stage(self):
        for body in (pe(b'bad'),pe()[:-1],pe()+b'long'):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(u.UpdateError):self.download(d,body=body)
                self.assertEqual(list(Path(d).iterdir()),[])
    def test_checksum_disagreement_or_wrong_filename(self):
        for text in ('0'*64+'  FreshTray-0.3.exe',u.hashlib.sha256(pe()).hexdigest()+'  other.exe'):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(u.UpdateError):self.download(d,checksum=text)
    def test_download_cancellation(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(u.Canceled):self.download(d,cancel=True)
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_invalid_pe(self):
        with tempfile.TemporaryDirectory() as d:
            data=release();payload=b'html'*600;data['assets'][0].update(size=len(payload),digest='sha256:'+u.hashlib.sha256(payload).hexdigest())
            with self.assertRaises(u.UpdateError):self.download(d,data,checksum=u.hashlib.sha256(payload).hexdigest()+'  FreshTray-0.3.exe',body=payload)
    def setup_plan(self,folder):
        root=Path(folder)/'updates';target=Path(folder)/'Portable App.exe';target.write_bytes(pe(b'old'))
        data,_=self.download(root);data['version']=__version__
        plan=Path(u.prepare_install(data,target,[]));return root,target,plan
    def test_plan_path_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root,target,plan=self.setup_plan(d)
            self.assertEqual(u.read_plan(plan,root)[1]['target'],str(target))
            with self.assertRaises(u.UpdateError):u.read_plan(plan,Path(d)/'elsewhere')
            data=json.loads(plan.read_text());data['download']=str(target);plan.write_text(json.dumps(data))
            with self.assertRaises(u.UpdateError):u.read_plan(plan,root)
    def test_prepare_rechecks_staged_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root,target,plan=self.setup_plan(d);data=json.loads(plan.read_text());Path(data['download']).write_bytes(b'changed')
            with self.assertRaises(u.UpdateError):u.prepare_install(data,target,[])
    def test_successful_replacement_and_start_ack(self):
        with tempfile.TemporaryDirectory() as d:
            root,target,plan=self.setup_plan(d);launches=[]
            class Child:
                def poll(self):return None
            def launch(args):
                launches.append(args);u.mark_ready(plan,target,root);return Child()
            self.assertTrue(u.apply_plan(plan,root,launch=launch))
            self.assertEqual(target.read_bytes(),pe());self.assertEqual(len(launches),1)
            self.assertTrue(json.loads((plan.parent/'result.json').read_text())['ok'])
            self.assertFalse(list(target.parent.glob('*.previous-*.exe')))
    def test_start_failure_rolls_back_and_restarts_old(self):
        with tempfile.TemporaryDirectory() as d:
            root,target,plan=self.setup_plan(d);launches=[]
            class Failed:
                def poll(self):return 1
            def launch(args):launches.append(args);return Failed()
            self.assertFalse(u.apply_plan(plan,root,launch=launch,health_timeout=.01))
            self.assertEqual(target.read_bytes(),pe(b'old'));self.assertEqual(len(launches),2)
            self.assertFalse(json.loads((plan.parent/'result.json').read_text())['ok'])
    def test_changed_target_never_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            root,target,plan=self.setup_plan(d);target.write_bytes(b'user replaced file')
            self.assertFalse(u.apply_plan(plan,root,launch=lambda args:self.fail('Must not launch modified executable')))
            self.assertEqual(target.read_bytes(),b'user replaced file')
    def test_stale_readiness_cannot_bypass_failed_start(self):
        with tempfile.TemporaryDirectory() as d:
            root,target,plan=self.setup_plan(d)
            (plan.parent/'ready.json').write_text(json.dumps({'version':__version__}))
            class Failed:
                def poll(self):return 1
            self.assertFalse(u.apply_plan(plan,root,launch=lambda args:Failed(),health_timeout=.01))
            self.assertEqual(target.read_bytes(),pe(b'old'))
    def test_cleanup_only_touches_old_owned_stages(self):
        with tempfile.TemporaryDirectory() as d:
            root,target,plan=self.setup_plan(d)
            other=root/'personal';other.mkdir();(other/'note.txt').write_text('keep')
            u.prune_staging(root,now=u.time.time()+8*86400)
            self.assertFalse(plan.parent.exists());self.assertTrue((other/'note.txt').exists());self.assertTrue(target.exists())
    def test_readiness_requires_installed_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root,target,plan=self.setup_plan(d)
            with self.assertRaises(u.UpdateError):u.mark_ready(plan,target,root)

if __name__=='__main__':unittest.main()

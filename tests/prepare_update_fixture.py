"""Prepare an isolated, same-binary update for the packaged lifecycle check."""
from pathlib import Path
import sys,shutil,uuid
sys.path.insert(0,str(Path(sys.argv[1])/'src'))
from freshtray import updates as u,__version__
stage=u.staging_root()/uuid.uuid4().hex;stage.mkdir(parents=True)
target=Path(sys.argv[2]);payload=stage/'download.exe';shutil.copy2(target,payload)
print(u.prepare_install(dict(stage=str(stage),download=str(payload),digest=u.sha(payload),version=__version__),target,['--demo','--data-dir',sys.argv[3]]))

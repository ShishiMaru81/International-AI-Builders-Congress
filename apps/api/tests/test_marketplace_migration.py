"""A native compatibility-created database can adopt migrations without data loss."""
import os,subprocess
from pathlib import Path
from sqlalchemy import create_engine,text
from app.db import Base

def test_unversioned_existing_workspace_upgrade_is_additive(tmp_path):
    url='sqlite:///'+str(tmp_path/'existing.db').replace('\\','/')
    engine=create_engine(url);Base.metadata.create_all(engine)
    with engine.begin() as db:
        db.execute(text("INSERT INTO users (id,name,preferences,role,is_active) VALUES ('preserved','Existing farmer','{}','farmer',1)"))
        db.execute(text("INSERT INTO records (id,owner_id,kind,created_at,payload) VALUES ('original','preserved','farm','2026-11-17T00:00:00+00:00','{}')"))
    env={**os.environ,'DATABASE_URL':url}
    api=Path(__file__).resolve().parents[1];python=Path(__file__).resolve().parents[3]/'.venv/Scripts/python.exe'
    # sys.executable also works on Linux CI; local environment selection is not hardcoded.
    import sys
    for _ in range(2):
        result=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=api,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr+result.stdout
    with engine.connect() as db:
        assert db.scalar(text("SELECT name FROM users WHERE id='preserved'"))=='Existing farmer'
        assert db.scalar(text("SELECT id FROM records WHERE id='original'"))=='original'
        assert db.scalar(text('SELECT version_num FROM alembic_version'))=='0004'

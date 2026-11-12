"""Private input audit. No source records are published."""
import argparse, hashlib, io, json, stat, zipfile
from pathlib import Path, PurePosixPath
import pandas as pd

REQUIRED = ['competitions','teams','matches','competition_team_player_mapping','playing_eleven','ball_by_ball']

def read_pack(path):
    tables, manifest = {}, []
    expanded=0
    def visit(z,depth=0,prefix=''):
        nonlocal expanded
        if depth>3:raise ValueError('Nested archive depth exceeds three')
        for i in z.infolist():
            p = PurePosixPath(i.filename.replace('\\','/'))
            if p.is_absolute() or '..' in p.parts or ':' in str(p) or stat.S_ISLNK(i.external_attr >> 16):
                raise ValueError('Unsafe archive member')
            if '__MACOSX' in p.parts or p.name.startswith('.') or i.is_dir():
                continue
            expanded+=i.file_size
            if expanded>512*1024**2:raise ValueError('Expanded archive exceeds 512 MiB')
            raw = z.read(i)
            manifest.append({'name':prefix+str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
            if p.suffix.lower()=='.zip':
                with zipfile.ZipFile(io.BytesIO(raw)) as nested:visit(nested,depth+1,prefix+str(p)+'!/')
            if p.suffix == '.csv' and p.stem in REQUIRED:
                if p.stem in tables: raise ValueError('Ambiguous duplicate CSV')
                tables[p.stem] = pd.read_csv(io.BytesIO(raw))
            if p.suffix == '.pdf':
                from pypdf import PdfReader
                Path('artifacts/private/problem-statement.txt').write_text('\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages),encoding='utf-8')
    if Path(path).is_dir():
        # Convert input directory into an in-memory archive to apply identical checks.
        memory=io.BytesIO()
        with zipfile.ZipFile(memory,'w') as z:
            for f in Path(path).rglob('*'):
                if f.is_symlink():raise ValueError('Symlink input rejected')
                if f.is_file():z.write(f,f.relative_to(path).as_posix())
        memory.seek(0)
        with zipfile.ZipFile(memory) as z:visit(z)
    else:
        with zipfile.ZipFile(path) as z:visit(z)
    if set(REQUIRED)-tables.keys(): raise ValueError('Missing required tables')
    return tables, manifest

def main():
    p=argparse.ArgumentParser();inputs=p.add_mutually_exclusive_group();inputs.add_argument('--input-zip');inputs.add_argument('--input-dir');a=p.parse_args()
    source=a.input_dir or a.input_zip or 'data/incoming/pack.zip'
    if not Path(source).exists() and not (a.input_dir or a.input_zip):
        choices=list(Path('data/incoming').glob('*.zip'))
        if len(choices)==1:source=str(choices[0])
        else:raise FileNotFoundError('Supply data/incoming/pack.zip, --input-zip, or --input-dir')
    Path('artifacts/private').mkdir(parents=True,exist_ok=True)
    tables,manifest=read_pack(source)
    import duckdb
    con=duckdb.connect('artifacts/private/audit.duckdb')
    report={'manifest':manifest,'tables':{}}
    if Path(source).is_file():report['input_zip_sha256']=hashlib.sha256(Path(source).read_bytes()).hexdigest()
    for name,df in tables.items():
        con.register('input_table',df); con.execute(f'CREATE OR REPLACE TABLE {name} AS SELECT * FROM input_table')
        df.to_parquet(f'artifacts/private/{name}.parquet',index=False)
        report['tables'][name]={'rows':len(df),'columns':{c:str(t) for c,t in df.dtypes.items()},'nulls':{c:int(v) for c,v in df.isna().sum().items()},'duplicate_rows':int(df.duplicated().sum())}
    b=tables['ball_by_ball'];m=tables['matches']
    report['extras']=b.groupby('extras_type',dropna=False)[['runs','extras1_runs','extras_2_runs']].agg(['count','sum']).to_json()
    report['innings']=b.groupby(['match_id','innings']).size().describe().to_dict()
    report['unknown_match_rows']=int((~b.match_id.isin(m.match_id)).sum())
    report['duplicate_delivery_keys']=int(b.duplicated(['match_id','innings','innings_ball_num']).sum())
    report['key_conflicts']={name:int(tables[name].duplicated(keys).sum()) for name,keys in {'matches':['match_id'],'competitions':['comp_id'],'teams':['comp_id','team_id'],'competition_team_player_mapping':['comp_id','team_id','player_id'],'playing_eleven':['match_id','team_id','player_id']}.items()}
    mapping=tables['competition_team_player_mapping']
    report['player_aliases']={str(pid):sorted(g.player_name.dropna().unique().tolist()) for pid,g in mapping.groupby('player_id') if g.player_name.nunique()>1}
    teamkeys=set(zip(tables['teams'].comp_id,tables['teams'].team_id))
    report['missing_team_references']=sum((r.comp_id,r.home_team_id) not in teamkeys or (r.comp_id,r.away_team_id) not in teamkeys for r in m.itertuples())
    report['invalid_dates']=int(pd.to_datetime(m.match_date,errors='coerce').isna().sum())
    report['negative_runs']=int((b[['runs','extras1_runs','extras_2_runs']]<0).any(axis=1).sum())
    if report['duplicate_delivery_keys'] or report['unknown_match_rows'] or report['invalid_dates'] or report['negative_runs']:
        raise ValueError('Core input contract violated; inspect source data')
    report['date_range']=[str(m.match_date.min()),str(m.match_date.max())]
    Path('artifacts/private/audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'rows':len(b),'matches':len(m),'extras':b.extras_type.value_counts(dropna=False).to_dict(),'duplicate_delivery_keys':report['duplicate_delivery_keys'],'dates':report['date_range']},default=str))

if __name__=='__main__':main()

"""Fail closed if public output contains source delivery fields or unexpected files."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'analysis.json','methodology.pdf','Royals_Resolve_methodology.pdf'}
FORBIDDEN={'striker_id','non_striker_id','innings_ball_num','delivery_ist_time','stroke','delivery_style'}

def check(value):
    if isinstance(value,dict):
        assert not (set(value)&FORBIDDEN),'Source-record field in public JSON'
        for v in value.values():check(v)
    elif isinstance(value,list):
        for v in value:check(v)

if __name__=='__main__':
    public=ROOT/'results/public';assert {'analysis.json','methodology.pdf'} <= {p.name for p in public.iterdir()} <= ALLOWED
    check(json.loads((public/'analysis.json').read_text()))
    alias=public/'Royals_Resolve_methodology.pdf'
    if alias.exists():
        from pypdf import PdfReader
        extract=lambda p: ''.join(page.extract_text() for page in PdfReader(p).pages)
        assert extract(alias)==extract(public/'methodology.pdf'),'Renamed PDF differs from canonical report'
    dist=ROOT/'frontend/dist'
    for path in dist.rglob('*'):
        assert path.suffix not in {'.map','.csv','.zip','.parquet','.duckdb'},f'Forbidden static asset: {path}'
        if path.suffix=='.json':check(json.loads(path.read_text()))
    print('Publication allowlist passed; no source records or source maps.')

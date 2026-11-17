"""Local HTTP smoke test for released inference and optional weather connectivity."""
import csv,json,os
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1]
client=httpx.Client(base_url=os.getenv('AGROSPHERE_API_URL','http://127.0.0.1:8000/api/v1'),timeout=60)
session=client.post('/auth/demo',json={'name':'Disposable integration test'});session.raise_for_status();s=session.json();client.headers['Authorization']='Bearer '+s['token']
try:
    card=client.get('/doctor/models/current').json();assert card['available']
    row=next(r for r in csv.DictReader((root/'data/plantvillage/manifest.csv').open()) if r['split']=='test')
    path=root/'data/plantvillage/images'/row['path']
    with path.open('rb') as image:r=client.post('/doctor/cases',data={'plot_id':s['plot_id']},files={'image':(path.name,image,'image/jpeg')})
    r.raise_for_status();case=r.json();assert case['model']['version']==card['version'];assert case['classification']['score'] is not None
    weather='not_attempted'
    farm=client.post('/farms',json={'name':'Public Gazipur test point','district':'Gazipur','latitude':24.0,'longitude':90.4,'location_consent':True}).json()
    plot=client.post('/plots',json={'farm_id':farm['id'],'name':'Disposable test plot','area_acres':'1'}).json()
    rain=client.get(f"/flood/plots/{plot['id']}/outlook?mode=LIVE")
    weather={'status':rain.status_code,'source':rain.json().get('meta',{}).get('source_name'),'is_simulated':rain.json().get('meta',{}).get('is_simulated')}
    result={'actual_http_inference':case['classification'],'model_version':card['version'],'quality_flags':case['quality_flags'],'expected_dataset_label':row['label'],'live_weather_connectivity':weather}
    destination=root/'docs'/os.getenv('AGROSPHERE_SMOKE_REPORT','smoke-result.json')
    destination.write_text(json.dumps(result,indent=2));print(json.dumps(result))
finally:client.delete('/me')

"""Verify the isolated Compose stack, actual ML and PostgreSQL persistence.

Creates only disposable records; deliberately restarts this project's API to
prove the existing session, uploaded case and device reading survive restart.
"""
import csv,json,os,secrets,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
base=os.getenv('AGROSPHERE_API_URL','http://127.0.0.1:8100/api/v1')
client=httpx.Client(base_url=base,timeout=60)
session=client.post('/auth/demo',json={'name':'Disposable Docker verification'})
session.raise_for_status();s=session.json()
client.headers['Authorization']='Bearer '+s['token']
result={'verified_at':datetime.now(timezone.utc).isoformat(),'api_url':base}
try:
    model=client.get('/doctor/models/current');model.raise_for_status()
    assert model.json()['available'],'Approved model is not available in container'
    row=next(r for r in csv.DictReader((root/'data/plantvillage/manifest.csv').open()) if r['split']=='test')
    image=root/'data/plantvillage/images'/row['path']
    with image.open('rb') as f:response=client.post('/doctor/cases',data={'plot_id':s['plot_id']},files={'image':(image.name,f,'image/jpeg')})
    response.raise_for_status();case=response.json()
    assert case['classification']['score'] is not None
    result['model_version']=case['model']['version']
    result['real_image_inference']=case['classification']
    print('Verified real image inference inside Docker.',flush=True)
    rain=client.get(f"/flood/plots/{s['plot_id']}/outlook");rain.raise_for_status()
    assert rain.json()['meta']['is_simulated'] and rain.json()['is_flood_probability'] is False
    price=client.get('/market/prices').json()[0]
    compared=client.post('/market/compare',json={'price_id':price['id'],'harvested_kg':'400','loss_fraction':'0','transport_bdt':'500','handling_bdt':'100','fees_bdt':'0'})
    compared.raise_for_status();assert compared.json()['net_bdt'] in ('16200.00','17800.00')
    device=client.post('/devices',json={'name':'Disposable virtual ESP32','plot_id':s['plot_id']});device.raise_for_status();d=device.json()
    payload={'schema_version':'1.0','event_id':'docker-'+secrets.token_hex(6),'device_id':d['id'],'plot_id':s['plot_id'],'timestamp':datetime.now(timezone.utc).isoformat(),'source_type':'simulator','measurements':{'soil_moisture_adc':2150},'calibration_id':None}
    ingested=client.post('/device/readings',json=payload,headers={'X-Device-Key':d['key']});ingested.raise_for_status()
    assert not ingested.json()['duplicate']
    print('Verified rain, market and device workflows. Restarting only this stack API.',flush=True)
    subprocess.run(['docker','compose','restart','api'],cwd=root,check=True)
    for attempt in range(30):
        try:
            if client.get('/health',timeout=2).is_success:break
        except httpx.HTTPError:pass
        time.sleep(1)
    else:raise RuntimeError('API did not recover after restart')
    saved=client.get(f"/doctor/cases/{case['id']}");saved.raise_for_status()
    assert saved.json()['id']==case['id']
    assert client.get(f"/doctor/cases/{case['id']}/image").is_success
    persisted=client.get('/devices');persisted.raise_for_status()
    assert persisted.json()[0]['last_reading']['measurements']['soil_moisture_adc']==2150
    duplicate=client.post('/device/readings',json=payload,headers={'X-Device-Key':d['key']});duplicate.raise_for_status();assert duplicate.json()['duplicate']
    result.update(postgres_session_survived_restart=True,case_and_private_image_survived_restart=True,sensor_reading_survived_restart=True,device_retry_deduplicated=True,rainfall_scenario='passed',decimal_market_comparison='passed')
    print('Session, case, private image, device reading and deduplication survived restart.',flush=True)
    (root/'docs/docker-verification.json').write_text(json.dumps(result,indent=2))
finally:
    response=client.delete('/me')
    if not response.is_success:raise RuntimeError('Disposable Docker verification workspace cleanup failed')

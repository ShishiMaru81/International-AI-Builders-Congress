import io
from tests.conftest import configure_isolated_test_env
configure_isolated_test_env()
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.db import Base,engine
from app.test_guard import safe_reset_test_metadata
from app.services import calculate,preparedness,DemoWeatherProvider
import pytest

@pytest.fixture
def client():
    safe_reset_test_metadata(engine, Base.metadata)
    with TestClient(app) as c:yield c
@pytest.fixture
def session(client):
    result=client.post('/api/v1/auth/demo',json={}).json()
    client.headers['Authorization']='Bearer '+result['token']
    return result
def picture():
    out=io.BytesIO();Image.new('RGB',(250,250),(40,110,40)).save(out,'JPEG');return out.getvalue()
def test_private_sessions_and_farms(client,session):
    assert client.get('/api/v1/health').json()['status']=='ok'
    plot=client.get('/api/v1/plots').json()[0]
    other=client.post('/api/v1/auth/demo',json={'name':'Other'}).json()
    assert client.get('/api/v1/plots/'+plot['id'],headers={'Authorization':'Bearer '+other['token']}).status_code==404
    assert client.post('/api/v1/farms',json={'name':'Farm','district':'Dhaka','latitude':23,'longitude':90}).status_code==422
def test_upload_history_feedback_export_delete(client,session):
    r=client.post('/api/v1/doctor/cases',data={'plot_id':session['plot_id']},files={'image':('leaf.jpg',picture(),'image/jpeg')})
    assert r.status_code==200,r.text
    c=r.json();assert c['classification']['abstained'] and c['classification']['score'] is None
    assert c['meta']['mode']=='DEMO' and c['quality_flags']
    assert client.get('/api/v1/doctor/cases').json()['items'][0]['id']==c['id']
    assert client.get(f"/api/v1/doctor/cases/{c['id']}/image").headers['content-type']=='image/jpeg'
    assert client.post(f"/api/v1/doctor/cases/{c['id']}/feedback",json={'note':'Monitor tomorrow','request_review':True}).status_code==200
    assert 'unknown' in client.get(f"/api/v1/doctor/cases/{c['id']}/report").text
    from app.main import storage
    (storage/c['image_file']).unlink()
    assert client.get(f"/api/v1/doctor/cases/{c['id']}/image").status_code==410
    assert client.delete(f"/api/v1/doctor/cases/{c['id']}").status_code==200
    assert client.get(f"/api/v1/doctor/cases/{c['id']}").status_code==404
@pytest.mark.parametrize('name,data,status',[('bad.jpg',b'not an image',415),('leaf.svg',b'<svg/>',415),('big.jpg',b'x'*(8*1024*1024+1),413)])
def test_upload_validation(client,session,name,data,status):
    assert client.post('/api/v1/doctor/cases',data={'plot_id':session['plot_id']},files={'image':(name,data)}).status_code==status
def test_decimal_calculation_and_required_costs(client,session):
    assert calculate('42','400','0.1','500','100','0')['net_bdt']=='14520.00'
    assert calculate('.10','3','0','0','0','0')['net_bdt']=='0.30'
    price=client.get('/api/v1/market/prices').json()[0]
    assert client.post('/api/v1/market/compare',json={'price_id':price['id'],'harvested_kg':400}).status_code==422
    r=client.post('/api/v1/market/compare',json={'price_id':price['id'],'harvested_kg':400,'loss_fraction':0,'transport_bdt':500,'handling_bdt':0,'fees_bdt':0})
    assert r.status_code==200 and r.json()['meta']['is_simulated']
def test_rain_horizons_and_live_no_fallback(client,session):
    for h in (24,48,72):
        r=client.get(f"/api/v1/flood/plots/{session['plot_id']}/outlook?horizon_hours={h}")
        assert r.status_code==200
        assert r.json()['is_flood_probability'] is False and r.json()['meta']['is_simulated']
    assert client.get(f"/api/v1/flood/plots/{session['plot_id']}/outlook?mode=LIVE").status_code==422
    assert client.get(f"/api/v1/flood/plots/{session['plot_id']}/outlook?horizon_hours=10").status_code==422
    forecast=DemoWeatherProvider().forecast(24,90)
    assert preparedness(forecast,48)['total_mm']==sum(x['rain_mm'] for x in forecast['hourly'][:48])
def test_csv_atomic_validation_and_dedup(client,session):
    fields='market,commodity,price,unit,price_type,grade,observed_at\n'
    good='Permitted market,tomato,40,BDT/kg,wholesale,A,2026-01-01\n'
    def send(text):return client.post('/api/v1/market/imports',files={'file':('prices.csv',text)},data={'source_name':'Private report','source_url':'https://example.org/report','permission_confirmed':'true'})
    bad=send(fields+good+'Bad,tomato,-2,BDT/kg,wholesale,A,2026-01-01\n').json()
    assert bad['imported']==0 and len(bad['errors'])==1
    assert send(fields+good).json()['imported']==1
    assert send(fields+good).json()['duplicates']==1
def test_device_same_endpoint_dedup_auth_and_account_delete(client,session):
    d=client.post('/api/v1/devices',json={'name':'Virtual','plot_id':session['plot_id']}).json()
    from datetime import datetime,timezone
    event=dict(schema_version='1.0',event_id='test-1',device_id=d['id'],plot_id=session['plot_id'],timestamp=datetime.now(timezone.utc).isoformat(),source_type='simulator',measurements={'soil_moisture_adc':2150})
    assert client.post('/api/v1/device/readings',json=event,headers={'X-Device-Key':'bad'}).status_code==401
    r=client.post('/api/v1/device/readings',json=event,headers={'X-Device-Key':d['key']});assert r.status_code==200 and 'uncalibrated' in r.json()['quality_flags']
    assert client.post('/api/v1/device/readings',json=event,headers={'X-Device-Key':d['key']}).json()['duplicate']
    device=client.get('/api/v1/devices').json()[0];assert 'key_hash' not in device and device['status']=='SIMULATED_DATA'
    assert client.get('/api/v1/me/export').status_code==200
    assert client.delete('/api/v1/me').status_code==200
    assert client.get('/api/v1/me').status_code==401
def test_actions_are_shared_and_mutable(client,session):
    center=client.get(f"/api/v1/plots/{session['plot_id']}/action-center").json()
    assert {a['topic'] for a in center['actions']}=={'doctor','flood','market'}
    id=center['actions'][0]['id']
    assert client.patch('/api/v1/actions/'+id,json={'status':'done'}).json()['status']=='done'
    assert client.get('/api/v1/notifications').json()

def test_area_search_validation_and_provider_failure(client,session,monkeypatch):
    import httpx
    def success(url,params,timeout):
        assert url=='https://geocoding-api.open-meteo.com/v1/search'
        assert params['name']=='Sylhet' and params['language']=='en'
        return httpx.Response(200,request=httpx.Request('GET',url),json={'results':[{'id':1,'name':'Sylhet','admin1':'Sylhet Division','admin2':'Sylhet','country':'Bangladesh','latitude':24.8949,'longitude':91.8687}]})
    monkeypatch.setattr('app.services.httpx.get',success)
    r=client.get('/api/v1/locations/search?q=Sylhet')
    assert r.status_code==200 and r.json()['is_simulated'] is False
    assert r.json()['results'][0]['longitude']==91.8687
    assert client.get('/api/v1/locations/search?q=S').status_code==422
    assert client.get('/api/v1/locations/search?q=Sylhet',headers={'Authorization':''}).status_code==401
    def failure(*args,**kwargs):raise httpx.ConnectError('offline')
    monkeypatch.setattr('app.services.httpx.get',failure)
    assert client.get('/api/v1/locations/search?q=Dhaka').status_code==503

def test_area_change_consent_ownership_zero_coordinates_and_forecast_reset(client,session,monkeypatch):
    farm=client.get('/api/v1/farms').json()[0]
    assert client.get(f"/api/v1/flood/plots/{session['plot_id']}/outlook").status_code==200
    payload={'latitude':0,'longitude':0,'location_consent':True,'location_name':'Equator test point','district':'Selected area','country':''}
    assert client.patch(f"/api/v1/farms/{farm['id']}/location",json={**payload,'location_consent':False}).status_code==422
    assert client.patch(f"/api/v1/farms/{farm['id']}/location",json={**payload,'latitude':91}).status_code==422
    other=client.post('/api/v1/auth/demo',json={}).json()
    assert client.patch(f"/api/v1/farms/{farm['id']}/location",json=payload,headers={'Authorization':'Bearer '+other['token']}).status_code==404
    saved=client.patch(f"/api/v1/farms/{farm['id']}/location",json=payload)
    assert saved.status_code==200 and saved.json()['name']==farm['name']
    center=client.get(f"/api/v1/plots/{session['plot_id']}/action-center").json()
    assert not center['evidence']['weather']
    assert any('Refresh weather' in a['title'] for a in center['actions'])
    def forecast(self,lat,lon):
        assert (lat,lon)==(0,0)
        data=DemoWeatherProvider().forecast(lat,lon)
        data['meta'].update(mode='LIVE',is_simulated=False,source_name='test_provider')
        return data
    monkeypatch.setattr('app.services.OpenMeteoProvider.forecast',forecast)
    outlook=client.get(f"/api/v1/flood/plots/{session['plot_id']}/outlook?mode=LIVE")
    assert outlook.status_code==200 and outlook.json()['location']=={'lat':0,'lon':0}

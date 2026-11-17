"""HTTP regressions for crop identity, private photos and unavailable inference."""
import io
import pytest
from PIL import Image
from tests.test_platform import client, session, picture

def new_plot(client, crop):
    farm = client.get('/api/v1/farms').json()[0]
    response = client.post('/api/v1/plots', json=dict(farm_id=farm['id'],name=crop+' plot',crop=crop,area_acres='1'))
    assert response.status_code == 200, response.text
    return response.json()

def send(client, plot, data=None, crop=None, name='leaf.png'):
    form={'plot_id':plot}
    if crop is not None: form['crop']=crop
    return client.post('/api/v1/doctor/cases',data=form,files={'image':(name,data or picture(),'image/png')})

def test_catalog_and_crop_plots(client, session):
    response=client.get('/api/v1/doctor/capabilities')
    assert response.status_code==200
    crops=response.json()['crops']
    assert len(crops)==12 and all(not c['available'] for c in crops)
    for crop in ['potato','maize','rice']:
        assert new_plot(client,crop)['crop']==crop
    assert new_plot(client,'corn')['crop']=='maize'
    farm=client.get('/api/v1/farms').json()[0]['id']
    for crop in ['soybean','',None]:
        assert client.post('/api/v1/plots',json=dict(farm_id=farm,name='bad',crop=crop,area_acres=1)).status_code==422

def test_mismatch_and_ownership_before_decode(client, session):
    rice=new_plot(client,'rice')
    assert send(client,rice['id'],b'bad','potato').status_code==422
    other=client.post('/api/v1/auth/demo',json={}).json()
    client.headers['Authorization']='Bearer '+other['token']
    assert send(client,rice['id'],b'bad','rice').status_code==404

def test_quality_abstention_has_crop_snapshot_and_private_photo(client, session):
    rice=new_plot(client,'rice')
    response=send(client,rice['id'])
    assert response.status_code==200,response.text
    case=response.json()
    assert case['crop']=='rice' and case['plot_name']=='rice plot'
    assert case['classification']['rejection_reason']=='image_quality'
    assert case['image_available'] is True
    assert case['model']['model_id']=='rice' and case['classification']['score'] is None
    for note in ['First note','Latest note']:
        client.post(f"/api/v1/doctor/cases/{case['id']}/feedback",json={'note':note})
    detail=client.get(f"/api/v1/doctor/cases/{case['id']}").json()
    assert [f['note'] for f in detail['feedback']]==['Latest note','First note']
    assert 'rice' in client.get(f"/api/v1/doctor/cases/{case['id']}/report").text
    from app.main import storage
    (storage/case['image_file']).unlink()
    assert client.get(f"/api/v1/doctor/cases/{case['id']}").json()['image_available'] is False
    assert client.get('/api/v1/doctor/cases').json()['items'][0]['image_available'] is False

def test_good_quality_missing_model_is_503_and_does_not_save(client, session):
    rice=new_plot(client,'rice')
    image=Image.effect_noise((256,256),80).convert('RGB'); out=io.BytesIO();image.save(out,'PNG')
    response=send(client,rice['id'],out.getvalue())
    assert response.status_code==503,response.text
    assert client.get('/api/v1/doctor/cases').json()['total']==0

def test_plot_patch_rejects_null_and_preserves_old_case_crop(client, session):
    plot=new_plot(client,'potato')
    case=send(client,plot['id']).json()
    for field in ['crop','name','area_acres','stage','low_lying','farm_id']:
        assert client.patch('/api/v1/plots/'+plot['id'],json={field:None}).status_code==422
    assert client.patch('/api/v1/plots/'+plot['id'],json={'crop':'rice'}).status_code==200
    assert client.get('/api/v1/doctor/cases/'+case['id']).json()['crop']=='potato'

def test_transparent_photo_exif_and_animated_rejection(client, session):
    out=io.BytesIO();Image.new('RGBA',(200,250),(0,0,0,0)).save(out,'PNG')
    response=send(client,session['plot_id'],out.getvalue())
    assert response.status_code==200,response.text
    image=client.get('/api/v1/doctor/cases/'+response.json()['id']+'/image')
    decoded=Image.open(io.BytesIO(image.content))
    assert decoded.mode=='RGB' and decoded.getpixel((5,5))==(255,255,255)
    out=io.BytesIO();a=Image.new('RGB',(250,250),'green');a.save(out,'PNG',save_all=True,append_images=[Image.new('RGB',(250,250),'red')],duration=100)
    assert send(client,session['plot_id'],out.getvalue()).status_code==415

def test_readiness_uses_active_models_not_retired_tomato(client, session, monkeypatch):
    from app.doctor_models import DoctorRegistry
    monkeypatch.setattr(DoctorRegistry,'capabilities',lambda self:{'models':[
        {'model_id':'plantvillage','version':'plant-v1','available':True,'artifact_status':'ready'},
        {'model_id':'rice','version':'rice-v1','available':False,'artifact_status':'broken_artifact','artifact_error':'bad checksum'}]})
    response=client.get('/api/v1/health/ready')
    assert response.status_code==503
    assert response.json()['status']=='not_ready'
    assert response.json()['model_state']=='broken_artifact'
    monkeypatch.setattr(DoctorRegistry,'capabilities',lambda self:{'models':[
        {'model_id':'plantvillage','version':'plant-v1','available':True,'artifact_status':'ready'},
        {'model_id':'rice','version':'rice-v1','available':True,'artifact_status':'ready'}]})
    response=client.get('/api/v1/health/ready')
    assert response.status_code==200 and response.json()['model_state']=='ready'

def test_exif_orientation_and_failed_commit_do_not_leave_files(client, session, monkeypatch):
    import app.main as main
    out=io.BytesIO();source=Image.new('RGB',(180,250),'green');exif=source.getexif();exif[274]=6
    source.save(out,'JPEG',exif=exif)
    result=send(client,session['plot_id'],out.getvalue()).json()
    saved=Image.open(main.storage/result['image_file'])
    assert saved.size==(250,180) and not saved.getexif()
    before=set(main.storage.glob('*.jpg'))
    def fail(*args,**kwargs):raise RuntimeError('injected write failure')
    monkeypatch.setattr(main,'audit',fail)
    with pytest.raises(RuntimeError,match='injected write failure'):
        send(client,session['plot_id'])
    assert set(main.storage.glob('*.jpg'))==before
    assert client.get('/api/v1/doctor/cases').json()['total']==1

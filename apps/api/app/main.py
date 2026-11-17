import csv, hashlib, io, json, os, secrets, warnings
import httpx
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header, Request, Query
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator, AwareDatetime
from sqlalchemy import select, delete
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.exc import IntegrityError
from PIL import Image, UnidentifiedImageError
from .db import Base, engine, get_db, User, Token, Record, Reading, now
from .services import provenance, preparedness, DemoWeatherProvider, OpenMeteoProvider, LocationSearchProvider, calculate, ModelRegistry, SimulatorAdapter, Esp32HttpAdapter

storage=Path(os.getenv('IMAGE_STORAGE_PATH','storage')); storage.mkdir(parents=True,exist_ok=True)
Image.MAX_IMAGE_PIXELS=20_000_000
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield
app=FastAPI(title='ZYNTRIX AgroSphere AI',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:3000,http://127.0.0.1:3000').split(','),allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Authorization','Content-Type','X-Device-Key'])
@app.middleware('http')
async def headers(request, call_next):
    request.state.request_id=uuid4().hex
    response=await call_next(request)
    response.headers.update({'X-Request-ID':request.state.request_id,'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})
    return response
@app.exception_handler(HTTPException)
async def error(request, exc):
    return JSONResponse(status_code=exc.status_code,content={'code':f'HTTP_{exc.status_code}','message':str(exc.detail),'request_id':request.state.request_id})

Db=Annotated[DBSession,Depends(get_db)]
def current_user(db:Db, authorization:Annotated[str|None,Header()]=None):
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401,'Sign in first')
    token=db.get(Token,hashlib.sha256(authorization[7:].encode()).hexdigest())
    if not token or token.expires<now(): raise HTTPException(401,'Session expired')
    return db.get(User,token.user_id)
Who=Annotated[User,Depends(current_user)]
def records(db,user,kind,plot=None):
    q=select(Record).where(Record.owner_id==user.id,Record.kind==kind)
    if plot: q=q.where(Record.plot_id==plot)
    return list(db.scalars(q.order_by(Record.created_at.desc())))
def owned(db,user,id,kind=None):
    r=db.get(Record,id)
    if not r or r.owner_id!=user.id or (kind and r.kind!=kind): raise HTTPException(404,'Record not found')
    return r
def view(r): return dict(id=r.id,created_at=r.created_at,plot_id=r.plot_id,**r.payload)
def add(db,user,kind,payload,plot=None):
    r=Record(owner_id=user.id,kind=kind,payload=payload,plot_id=plot); db.add(r); db.flush(); return r
def audit(db,user,event,record_id): add(db,user,'audit',dict(event=event,record_id=record_id))
def action(db,user,plot,topic,title,reason,meta):
    existing=[r for r in records(db,user,'action',plot) if r.payload['topic']==topic and r.payload['status']=='open']
    if existing:
        a=existing[0];a.payload=dict(topic=topic,title=title,reason=reason,status='open',meta=meta)
        return a
    a=add(db,user,'action',dict(topic=topic,title=title,reason=reason,status='open',meta=meta),plot)
    add(db,user,'notification',dict(title=title,read=False,action_id=a.id),plot)
    return a
class DemoLogin(BaseModel): name:str=Field(default='Demo farmer',min_length=1,max_length=80)
@app.post('/api/v1/auth/demo')
def login(body:DemoLogin,db:Db):
    user=User(name=body.name,preferences={'language':'en','theme':'light','retraining_consent':False});db.add(user);db.flush()
    raw=secrets.token_urlsafe(40);db.add(Token(id=hashlib.sha256(raw.encode()).hexdigest(),user_id=user.id,expires=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()))
    farm=add(db,user,'farm',dict(name='Gazipur Demo Farm',district='Gazipur',latitude=None,longitude=None,location_consent=False,meta=provenance()))
    plot=add(db,user,'plot',dict(farm_id=farm.id,name='Tomato plot · A',crop='tomato',area_acres='1.2',stage='Vegetative',low_lying=False,meta=provenance()))
    for market,price in [('Gazipur demo wholesale','42.00'),('Dhaka demo wholesale','46.00')]:
        add(db,user,'price',dict(market=market,commodity='tomato',price=price,unit='BDT/kg',price_type='wholesale',grade='unspecified',observed_at='2026-11-15',meta=provenance(observed_at='2026-11-15')))
    action(db,user,plot.id,'doctor','Start your first crop screening','Upload a clear tomato leaf photo. Review model evidence and uncertainty.',provenance())
    action(db,user,plot.id,'flood','Review rain preparedness','Explore the clearly labeled simulated rain outlook.',provenance())
    action(db,user,plot.id,'market','Compare selling options','Enter all costs before comparing synthetic market quotes.',provenance())
    audit(db,user,'demo.created',farm.id);db.commit()
    return dict(token=raw,user_id=user.id,plot_id=plot.id)
@app.post('/api/v1/auth/logout')
def logout(user:Who,db:Db,authorization:Annotated[str,Header()]):
    db.execute(delete(Token).where(Token.id==hashlib.sha256(authorization[7:].encode()).hexdigest()));db.commit();return {'ok':True}
@app.get('/api/v1/health')
def health():return {'status':'ok','version':'1.0.0','mode':os.getenv('DATA_MODE','DEMO')}
@app.get('/api/v1/me')
def me(user:Who):return dict(id=user.id,name=user.name,role='farmer',preferences=user.preferences)
class Preferences(BaseModel):
    language:Literal['en','bn']='en'
    theme:Literal['light','dark']='light'
    retraining_consent:bool=False
@app.patch('/api/v1/me')
def preferences(body:Preferences,user:Who,db:Db): user.preferences=body.model_dump();db.commit();return user.preferences
class FarmInput(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    district:str=Field(min_length=1,max_length=80)
    latitude:float|None=Field(default=None,ge=-90,le=90)
    longitude:float|None=Field(default=None,ge=-180,le=180)
    location_consent:bool=False
    location_name:str|None=Field(default=None,max_length=200)
    country:str|None=Field(default=None,max_length=100)
    @model_validator(mode='after')
    def consent(self):
        if (self.latitude is not None or self.longitude is not None) and (not self.location_consent or self.latitude is None or self.longitude is None):raise ValueError('Coordinates require explicit consent and both values')
        return self
@app.get('/api/v1/farms')
def farms(user:Who,db:Db):return [view(r) for r in records(db,user,'farm')]
@app.post('/api/v1/farms')
def create_farm(body:FarmInput,user:Who,db:Db):
    r=add(db,user,'farm',dict(**body.model_dump(),meta=provenance('MIXED','farmer_entered')));audit(db,user,'farm.created',r.id);db.commit();return view(r)
@app.patch('/api/v1/farms/{id}')
def edit_farm(id:str,body:FarmInput,user:Who,db:Db):
    r=owned(db,user,id,'farm');r.payload=dict(**body.model_dump(),meta=provenance('MIXED','farmer_entered'));audit(db,user,'farm.updated',id);db.commit();return view(r)
@app.get('/api/v1/farms/{id}')
def farm(id:str,user:Who,db:Db):return view(owned(db,user,id,'farm'))

@app.get('/api/v1/locations/search')
def location_search(user:Who,q:Annotated[str,Query(min_length=2,max_length=100)],language:Literal['en','bn']='en'):
    if len(q.strip()) < 2:raise HTTPException(422,'Enter at least two characters for area search')
    try:return LocationSearchProvider().search(q.strip(),language)
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        raise HTTPException(503,'Area search is unavailable. Select a map point or enter coordinates instead.')

class FarmLocationInput(BaseModel):
    latitude:float=Field(ge=-90,le=90)
    longitude:float=Field(ge=-180,le=180)
    location_consent:Literal[True]
    location_name:str=Field(min_length=1,max_length=200)
    district:str=Field(min_length=1,max_length=80)
    country:str=Field(default='',max_length=100)

@app.patch('/api/v1/farms/{id}/location')
def update_location(id:str,body:FarmLocationInput,user:Who,db:Db):
    f=owned(db,user,id,'farm')
    f.payload={**f.payload,**body.model_dump(), 'meta':provenance('MIXED','farmer_selected_location')}
    for p in records(db,user,'plot'):
        if p.payload['farm_id']!=id:continue
        for old in records(db,user,'weather',p.id):db.delete(old)
        action(db,user,p.id,'flood','Refresh weather for your selected area',
            'Farm location changed. Retrieve a new outlook before making rain preparations.',
            provenance('MIXED','farmer_selected_location'))
    audit(db,user,'farm.location_updated',id);db.commit();return view(f)
class PlotInput(BaseModel):
    farm_id:str
    name:str=Field(min_length=1,max_length=100)
    crop:Literal['tomato']='tomato'
    area_acres:Decimal=Field(gt=0,le=10000)
    stage:str=Field(default='Vegetative',max_length=60)
    low_lying:bool=False
@app.get('/api/v1/plots')
def plots(user:Who,db:Db):return [view(r) for r in records(db,user,'plot')]
@app.post('/api/v1/plots')
def create_plot(body:PlotInput,user:Who,db:Db):
    owned(db,user,body.farm_id,'farm');r=add(db,user,'plot',dict(**body.model_dump(mode='json'),meta=provenance('MIXED','farmer_entered')));audit(db,user,'plot.created',r.id);db.commit();return view(r)
@app.get('/api/v1/plots/{id}')
def plot(id:str,user:Who,db:Db):return view(owned(db,user,id,'plot'))
@app.get('/api/v1/doctor/models/current')
def model():return ModelRegistry().card()
@app.get('/api/v1/doctor/conditions')
def conditions():return {'supported_model_labels':ModelRegistry().card()['labels'],'guidance':['Photograph both sides of leaves.','Record when symptoms began.','Seek local agronomic review.'],'source':'https://plantvillage.psu.edu/','disclaimer':'Educational guidance. No disease-specific treatment or pesticide prescription.'}
@app.post('/api/v1/doctor/cases')
def upload(user:Who,db:Db,plot_id:Annotated[str,Form()],image:Annotated[UploadFile,File()],symptoms:Annotated[str,Form(max_length=2000)]='',crop:Annotated[str,Form()]='tomato'):
    owned(db,user,plot_id,'plot')
    if crop!='tomato':raise HTTPException(422,'Only tomato screening is configured')
    recent=[r for r in records(db,user,'case') if r.created_at>(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()]
    if len(recent)>=6:raise HTTPException(429,'Upload limit: six images per minute')
    if Path(image.filename or '').suffix.lower() not in ('.jpg','.jpeg','.png','.webp'):raise HTTPException(415,'Use JPG, PNG or WebP')
    data=image.file.read(8*1024*1024+1)
    if len(data)>8*1024*1024:raise HTTPException(413,'Maximum upload is 8 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            im=Image.open(io.BytesIO(data));fmt=im.format
            if fmt not in ('JPEG','PNG','WEBP'):raise ValueError('Unsupported decoded image type')
            im.verify();im=Image.open(io.BytesIO(data)).convert('RGB')
            if im.width*im.height>20_000_000:raise ValueError('Image exceeds pixel limit')
            result=ModelRegistry().infer(im)
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):raise HTTPException(415,'Invalid image or excessive dimensions')
    filename=uuid4().hex+'.jpg';im.save(storage/filename,'JPEG',quality=90)
    meta=provenance('MIXED' if result['model'].get('available') else 'DEMO','user_upload; '+result['model']['version'])
    r=add(db,user,'case',dict(**result,crop=crop,symptoms=symptoms,image_file=filename,checksum=hashlib.sha256(data).hexdigest(),meta=meta),plot_id)
    action(db,user,plot_id,'doctor','Review your leaf screening',result['status']+': '+result['advice'][0],meta);audit(db,user,'diagnosis.created',r.id);db.commit();return view(r)
@app.get('/api/v1/doctor/cases')
def cases(user:Who,db:Db,offset:int=0,limit:int=20,plot_id:str|None=None):
    if plot_id:owned(db,user,plot_id,'plot')
    return [view(r) for r in records(db,user,'case',plot_id)[max(0,offset):max(0,offset)+max(1,min(limit,100))]]
@app.get('/api/v1/doctor/cases/{id}')
def case(id:str,user:Who,db:Db):return view(owned(db,user,id,'case'))
@app.get('/api/v1/doctor/cases/{id}/image')
def case_image(id:str,user:Who,db:Db):
    image_path=storage/owned(db,user,id,'case').payload['image_file']
    if not image_path.is_file():raise HTTPException(410,'This image is no longer available. Free demo hosts may clear photo files after a restart; case metadata can still be exported.')
    return Response(image_path.read_bytes(),media_type='image/jpeg')
class Feedback(BaseModel):
    note:str=Field(min_length=1,max_length=2000)
    request_review:bool=False
@app.post('/api/v1/doctor/cases/{id}/feedback')
def feedback(id:str,body:Feedback,user:Who,db:Db):
    c=owned(db,user,id,'case');r=add(db,user,'feedback',dict(case_id=id,**body.model_dump()),c.plot_id);audit(db,user,'doctor.review_requested' if body.request_review else 'doctor.feedback',id);db.commit();return view(r)
@app.get('/api/v1/doctor/cases/{id}/report')
def report(id:str,user:Who,db:Db):
    c=owned(db,user,id,'case');out=io.StringIO();writer=csv.writer(out);writer.writerow(['case_id','created_at','status','possible_condition','model','mode','limitations']);writer.writerow([c.id,c.created_at,c.payload['status'],c.payload['classification']['top_label'],c.payload['model']['version'],c.payload['meta']['mode'],c.payload['disclaimer']]);audit(db,user,'case.exported',id);db.commit();return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="agrodoctor-case.csv"'})
@app.delete('/api/v1/doctor/cases/{id}')
def delete_case(id:str,user:Who,db:Db):
    c=owned(db,user,id,'case');(storage/c.payload['image_file']).unlink(missing_ok=True);db.delete(c);audit(db,user,'case.deleted',id);db.commit();return {'ok':True}
@app.get('/api/v1/flood/plots/{plot_id}/outlook')
@app.get('/api/v1/weather/plots/{plot_id}/forecast')
def outlook(plot_id:str,user:Who,db:Db,horizon_hours:int=48,mode:Literal['DEMO','LIVE']='DEMO'):
    p=owned(db,user,plot_id,'plot');f=owned(db,user,p.payload['farm_id'],'farm')
    if horizon_hours not in (24,48,72):raise HTTPException(422,'Horizon must be 24, 48 or 72 hours')
    lat,lon=f.payload.get('latitude'),f.payload.get('longitude')
    if mode=='LIVE' and (lat is None or lon is None):raise HTTPException(422,'Add consented farm coordinates for live weather')
    provider=OpenMeteoProvider() if mode=='LIVE' else DemoWeatherProvider()
    try: data=preparedness(provider.forecast(lat if lat is not None else 24.0023,lon if lon is not None else 90.4264),horizon_hours,p.payload.get('low_lying',False))
    except (httpx.HTTPError,ValueError,KeyError):raise HTTPException(503,'Weather unavailable. No simulated data substituted for live data.')
    existing=records(db,user,'weather',plot_id)
    if existing:
        existing[0].payload=data
    else:add(db,user,'weather',data,plot_id)
    action(db,user,plot_id,'flood','Review rain preparedness',f"{data['total_mm']} mm / {horizon_hours} hours. {data['disclaimer']}",data['meta'])
    audit(db,user,'rainwatch.updated',plot_id);db.commit();return data
@app.get('/api/v1/flood/plots/{plot_id}/official-alerts')
def official(plot_id:str,user:Who,db:Db):owned(db,user,plot_id,'plot');return {'alerts':[],'status':'unavailable','source_url':'https://ww2.ffwc.gov.bd/','reason':'No authorized official bulletin feed configured'}
class Vulnerability(BaseModel): low_lying:bool
@app.post('/api/v1/flood/plots/{plot_id}/vulnerability')
def vulnerability(plot_id:str,body:Vulnerability,user:Who,db:Db):
    p=owned(db,user,plot_id,'plot');p.payload={**p.payload,**body.model_dump()};audit(db,user,'plot.vulnerability_updated',plot_id);db.commit();return view(p)
@app.get('/api/v1/market/prices')
def prices(user:Who,db:Db,commodity:str='tomato',price_type:str='wholesale',market:str|None=None):return [view(r) for r in records(db,user,'price') if r.payload['commodity']==commodity and r.payload['price_type']==price_type and (not market or r.payload['market']==market)]
class Comparison(BaseModel):
    price_id:str
    harvested_kg:Decimal=Field(gt=0,le=1000000)
    loss_fraction:Decimal=Field(default=0,ge=0,lt=1)
    transport_bdt:Decimal=Field(ge=0,le=100000000)
    handling_bdt:Decimal=Field(ge=0,le=100000000)
    fees_bdt:Decimal=Field(ge=0,le=100000000)
@app.post('/api/v1/market/compare')
def compare(body:Comparison,user:Who,db:Db):
    price=owned(db,user,body.price_id,'price');p=price.payload
    result=calculate(p['price'],body.harvested_kg,body.loss_fraction,body.transport_bdt,body.handling_bdt,body.fees_bdt)
    result.update(market=p['market'],meta=p['meta'],assumptions=body.model_dump(mode='json'),disclaimer='Illustrative expected proceeds, not a guaranteed sale price or profit.')
    add(db,user,'comparison',result)
    for plot_record in records(db,user,'plot'):
        if plot_record.payload['crop']==p['commodity']:
            action(db,user,plot_record.id,'market','Review your net selling comparison',f"{plot_record.payload['name']}: {result['market']} · illustrative net BDT {result['net_bdt']} after declared costs.",result['meta'])
    audit(db,user,'market.compared',price.id);db.commit();return result
@app.post('/api/v1/market/imports')
def import_prices(user:Who,db:Db,file:Annotated[UploadFile,File()],source_name:Annotated[str,Form()],source_url:Annotated[str,Form()],permission_confirmed:Annotated[bool,Form()]):
    if not permission_confirmed:raise HTTPException(422,'Confirm permission to use this private import')
    raw=file.file.read(1024*1024+1)
    if len(raw)>1024*1024:raise HTTPException(413,'CSV limit is 1 MB')
    try:rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    except UnicodeDecodeError:raise HTTPException(422,'CSV must be UTF-8')
    errors=[];valid=[];existing={r.payload.get('import_key') for r in records(db,user,'price')};duplicates=0
    for i,row in enumerate(rows,2):
        try:
            if not all(row.get(k) for k in ['market','commodity','price','unit','price_type','grade','observed_at']):raise ValueError('Missing required field')
            if row['unit']!='BDT/kg' or row['price_type'] not in ('wholesale','retail','farm-gate'):raise ValueError('Unsupported unit or price type')
            if not Decimal(row['price']).is_finite() or Decimal(row['price'])<=0:raise ValueError('Invalid price')
            date=datetime.strptime(row['observed_at'],'%Y-%m-%d').date()
            if date>datetime.now(timezone.utc).date():raise ValueError('Future observation')
            key=hashlib.sha256(json.dumps({k:row[k] for k in sorted(row)},sort_keys=True).encode()).hexdigest()
            if key in existing:duplicates+=1;continue
            existing.add(key);meta=provenance('HISTORICAL',source_name,row['observed_at']);meta.update(source_type='private_import',source_url=source_url,permission_confirmed=True,freshness='stale' if (datetime.now(timezone.utc).date()-date).days>3 else 'recent')
            valid.append(dict(**{k:row[k] for k in ['market','commodity','price','unit','price_type','grade','observed_at']},import_key=key,meta=meta))
        except (ValueError,ArithmeticError) as e:errors.append({'row':i,'message':str(e)})
    # Atomic validation: bad files import nothing; caller can correct and retry.
    if not errors:
        for item in valid:add(db,user,'price',item)
    r=add(db,user,'import',dict(imported=0 if errors else len(valid),errors=errors,duplicates=duplicates,source_name=source_name,source_url=source_url,checksum=hashlib.sha256(raw).hexdigest()));audit(db,user,'market_price.imported',r.id);db.commit();return view(r)
@app.get('/api/v1/market/imports/{id}')
def imported(id:str,user:Who,db:Db):return view(owned(db,user,id,'import'))
class Watch(BaseModel):
    market:str=Field(min_length=1,max_length=100)
    target_bdt:Decimal=Field(gt=0)
@app.get('/api/v1/market/watchlists')
def watches(user:Who,db:Db):return [view(r) for r in records(db,user,'watch')]
@app.post('/api/v1/market/watchlists')
def watch(body:Watch,user:Who,db:Db):r=add(db,user,'watch',body.model_dump(mode='json'));db.commit();return view(r)
@app.get('/api/v1/market/forecast')
def forecast_disabled():return {'enabled':False,'reason':'No licensed, backtested price time series available'}
@app.get('/api/v1/actions')
def actions(user:Who,db:Db,plot_id:str|None=None):
    if plot_id:owned(db,user,plot_id,'plot')
    return [view(r) for r in records(db,user,'action',plot_id)]
class ActionUpdate(BaseModel):
    status:Literal['open','done','snoozed']
    comment:str=Field(default='',max_length=2000)
@app.patch('/api/v1/actions/{id}')
def update_action(id:str,body:ActionUpdate,user:Who,db:Db):
    r=owned(db,user,id,'action');r.payload={**r.payload,**body.model_dump()};audit(db,user,'action.acknowledged',id);db.commit();return view(r)
@app.get('/api/v1/plots/{id}/action-center')
def center(id:str,user:Who,db:Db):
    owned(db,user,id,'plot');return dict(actions=[view(r) for r in records(db,user,'action',id)],evidence={kind:[view(r) for r in records(db,user,kind,id)[:1]] for kind in ('case','weather')},market_evidence=[view(r) for r in records(db,user,'price')[:2]],meta=provenance('MIXED','independent module evidence'))
@app.get('/api/v1/notifications')
def notifications(user:Who,db:Db):return [view(r) for r in records(db,user,'notification')]
@app.patch('/api/v1/notifications/{id}')
def read_notification(id:str,user:Who,db:Db):r=owned(db,user,id,'notification');r.payload={**r.payload,'read':True};db.commit();return view(r)
@app.get('/api/v1/history')
def history(user:Who,db:Db):return [view(r) for r in records(db,user,'audit')[:100]]
class DeviceInput(BaseModel): name:str=Field(min_length=1,max_length=80);plot_id:str
@app.post('/api/v1/devices')
def register_device(body:DeviceInput,user:Who,db:Db):
    owned(db,user,body.plot_id,'plot');key=secrets.token_urlsafe(32);r=add(db,user,'device',dict(name=body.name,key_hash=hashlib.sha256(key.encode()).hexdigest(),status='NO_LIVE_DEVICE_DATA'),body.plot_id);audit(db,user,'device.registered',r.id);db.commit();return {'id':r.id,'key':key,'plot_id':r.plot_id}
@app.get('/api/v1/devices')
def devices(user:Who,db:Db):return [{k:v for k,v in view(r).items() if k!='key_hash'} for r in records(db,user,'device')]
class Measurements(BaseModel):
    soil_moisture_adc:int|None=Field(default=None,ge=0,le=65535)
    air_temperature_c:float|None=Field(default=None,ge=-50,le=80)
    relative_humidity_pct:float|None=Field(default=None,ge=0,le=100)
    rainfall_mm_interval:float|None=Field(default=None,ge=0,le=2000)
class SensorInput(BaseModel):
    schema_version:Literal['1.0']
    event_id:str=Field(min_length=1,max_length=100)
    device_id:str
    plot_id:str
    timestamp:AwareDatetime
    source_type:Literal['simulator','esp32','historical']
    measurements:Measurements
    calibration_id:str|None=None
@app.post('/api/v1/device/readings')
def ingest(body:SensorInput,db:Db,x_device_key:Annotated[str,Header()]):
    d=db.get(Record,body.device_id)
    if not d or d.kind!='device' or not secrets.compare_digest(d.payload['key_hash'],hashlib.sha256(x_device_key.encode()).hexdigest()):raise HTTPException(401,'Invalid device credentials')
    if d.plot_id!=body.plot_id:raise HTTPException(403,'Device is not assigned to this plot')
    if body.timestamp>datetime.now(timezone.utc)+timedelta(minutes=5):raise HTTPException(422,'Future sensor timestamp')
    previous=db.scalar(select(Reading).where(Reading.device_id==body.device_id,Reading.event_id==body.event_id))
    if previous:return {'id':previous.id,'duplicate':True}
    payload=body.model_dump(mode='json');adapter=SimulatorAdapter() if body.source_type=='simulator' else Esp32HttpAdapter();payload=adapter.normalize(payload)
    r=Reading(device_id=d.id,event_id=body.event_id,payload=payload);db.add(r)
    d.payload={**d.payload,'status':'SIMULATED_DATA' if body.source_type=='simulator' else 'DEVICE_DATA_UNVALIDATED','last_reading':payload}
    try:db.commit()
    except IntegrityError:db.rollback();return {'duplicate':True}
    return {'id':r.id,'duplicate':False,'quality_flags':payload['quality_flags']}
@app.get('/api/v1/providers/status')
def providers():return {'weather':{'provider':'Open-Meteo','live_requires':'consented coordinates; network','demo':'scenario_simulated'},'flood':{'status':'official_feed_unavailable','url':'https://ww2.ffwc.gov.bd/'},'market':{'status':'private_csv_or_demo','url':'https://market.dam.gov.bd/'},'model':ModelRegistry().card()}
@app.get('/api/v1/models/evaluations')
def evaluations():return {'model':ModelRegistry().card(),'metrics':ModelRegistry().card().get('metrics'),'field_validation':'not_performed'}
@app.get('/api/v1/me/export')
def export(user:Who,db:Db):
    data=[view(r) for r in db.scalars(select(Record).where(Record.owner_id==user.id))]
    for item in data:item.pop('key_hash',None);item.pop('image_file',None)
    audit(db,user,'account.exported',user.id);db.commit();return {'user':{'id':user.id,'name':user.name},'records':data,'timezone':'UTC'}
@app.delete('/api/v1/me')
def delete_account(user:Who,db:Db):
    for c in records(db,user,'case'):(storage/c.payload['image_file']).unlink(missing_ok=True)
    device_ids=[d.id for d in records(db,user,'device')]
    if device_ids:db.execute(delete(Reading).where(Reading.device_id.in_(device_ids)))
    db.execute(delete(Record).where(Record.owner_id==user.id));db.execute(delete(Token).where(Token.user_id==user.id));db.delete(user);db.commit();return {'ok':True}

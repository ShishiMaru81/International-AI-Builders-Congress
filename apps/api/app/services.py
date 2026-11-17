from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol
import os, json, importlib.util
from pathlib import Path
import httpx
from PIL import Image, ImageStat, ImageFilter
from .db import now

def provenance(mode='DEMO', source='scenario_fixture', observed_at=None):
    return dict(mode=mode, source_type='scenario_simulated' if mode == 'DEMO' else 'user_reported',
        source_name=source, observed_at=observed_at, issued_at=None, retrieved_at=now(),
        is_simulated=mode == 'DEMO', quality_flags=['illustrative_only'] if mode == 'DEMO' else [],
        attribution='ZYNTRIX synthetic fixtures' if mode == 'DEMO' else source,
        freshness='not_applicable' if mode == 'DEMO' else 'unknown')

class WeatherProvider(Protocol):
    def forecast(self, lat: float, lon: float) -> dict: ...

class LocationSearchProvider:
    def search(self, query: str, language: str = 'en') -> dict:
        response = httpx.get('https://geocoding-api.open-meteo.com/v1/search',
            params={'name': query, 'count': 8, 'language': language, 'format': 'json'}, timeout=12)
        response.raise_for_status()
        places = []
        for item in response.json().get('results', []):
            lat, lon = float(item['latitude']), float(item['longitude'])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):continue
            label = ', '.join(dict.fromkeys(str(item[k]) for k in ('name', 'admin1', 'country') if item.get(k)))
            places.append({'id': str(item['id']), 'name': item['name'], 'label': label,
                'district': item.get('admin2') or item.get('admin1') or item['name'],
                'country': item.get('country', ''), 'latitude': lat, 'longitude': lon})
        return {'results': places, 'source_name': 'Open-Meteo Geocoding / GeoNames',
            'is_simulated': False, 'retrieved_at': now(),
            'limitations': ['Search results identify named places, not surveyed farm boundaries.']}
class DemoWeatherProvider:
    def forecast(self, lat, lon):
        start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        return dict(hourly=[dict(time=(start+timedelta(hours=i)).isoformat(), rain_mm=[0,0,1,2,5,7,3,1][i%8]) for i in range(72)],
            meta=provenance(), location={'lat':lat,'lon':lon})
class OpenMeteoProvider:
    def forecast(self, lat, lon):
        r = httpx.get('https://api.open-meteo.com/v1/forecast', params=dict(latitude=lat,longitude=lon,hourly='precipitation',forecast_days=4,timezone='UTC'), timeout=12)
        r.raise_for_status()
        data=r.json(); current=datetime.now(timezone.utc)
        hourly=[dict(time=t+'+00:00',rain_mm=v) for t,v in zip(data['hourly']['time'],data['hourly']['precipitation']) if datetime.fromisoformat(t).replace(tzinfo=timezone.utc)>=current]
        if len(hourly)<72 or any(x['rain_mm'] is None or x['rain_mm']<0 for x in hourly[:72]): raise ValueError('Incomplete forecast')
        meta=provenance('LIVE','Open-Meteo')
        meta.update(source_type='forecast',freshness='fresh',issued_at=None,attribution='Open-Meteo · CC BY 4.0',quality_flags=['model_issue_time_unavailable'])
        return dict(hourly=hourly[:72],meta=meta,location={'lat':lat,'lon':lon})

def preparedness(forecast, horizon=48, low_lying=False):
    if horizon not in (24,48,72): raise ValueError('Use 24, 48 or 72 hours')
    total=round(sum(x['rain_mm'] for x in forecast['hourly'][:horizon]),1)
    threshold=50 if low_lying else 75
    return dict(**forecast, total_mm=total,horizon_hours=horizon,threshold_mm=threshold,
        level='prepare' if total>=threshold else 'monitor',signal_type='rainfall_preparedness',
        is_flood_probability=False,method='configurable_precipitation_rule',
        reasons=[f'{total} mm over {horizon} hours; illustrative threshold {threshold} mm.', 'Vulnerability is farmer-reported.'],
        disclaimer='Rain preparedness only. Not an official flood warning or farm inundation forecast.',
        official_alert=None,official_url='https://ww2.ffwc.gov.bd/')

def money(value): return str(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
def calculate(price, quantity, loss, transport, handling, fees):
    q=Decimal(str(quantity))*(1-Decimal(str(loss)))
    gross=q*Decimal(str(price)); costs=sum(Decimal(str(x)) for x in (transport,handling,fees))
    return dict(saleable_kg=money(q),gross_bdt=money(gross),costs_bdt=money(costs),net_bdt=money(gross-costs),formula='kg × (1 − loss) × BDT/kg − transport − handling − fees')

class ModelRegistry:
    def __init__(self):
        self.path=Path(os.getenv('MODEL_DIR','../../ml/artifacts'))
    def card(self):
        card=self.path/'model.json'
        if card.exists() and (self.path/'model.pt').exists():
            data=json.loads(card.read_text())
            if data.get('release_approved') and data.get('metrics') and data.get('dataset') and importlib.util.find_spec('torch') and importlib.util.find_spec('torchvision'):
                return data
        return dict(version='abstaining-demo-v1',available=False,field_validated=False,labels=[],metrics=None,
            source='No verified trained artifact installed',limitations=['No disease inference in demo mode.','Not field-validated.','Image quality checks do not identify crops or diseases.'])
    def infer(self, image):
        gray=image.convert('L'); stats=ImageStat.Stat(gray)
        quality=[]
        if min(image.size)<160: quality.append('low_resolution')
        if stats.mean[0]<35: quality.append('underexposed')
        if stats.mean[0]>235: quality.append('overexposed')
        inner=gray.crop((2,2,max(3,gray.width-2),max(3,gray.height-2))) if min(gray.size)>6 else gray
        if stats.var[0]<8 or ImageStat.Stat(inner.filter(ImageFilter.FIND_EDGES)).var[0]<80: quality.append('possibly_blurred')
        card=self.card()
        base=dict(top_label='unknown',abstained=True,score=None,score_type='not_available',alternatives=[])
        if card.get('available') and not quality:
            import torch
            torch.set_num_threads(2)
            from torchvision import transforms
            model=torch.jit.load(str(self.path/'model.pt'),map_location='cpu').eval()
            transform=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
            with torch.inference_mode(): probs=model(transform(image).unsqueeze(0)).softmax(1)[0]
            indices=probs.argsort(descending=True)[:3].tolist()
            score=float(probs[indices[0]])
            base.update(top_label=card['labels'][indices[0]],abstained=score<card['threshold'],score=score,score_type='uncalibrated_model_score',alternatives=[{'label':card['labels'][i],'score':float(probs[i])} for i in indices])
            if base['abstained']: base['top_label']='unknown'
        return dict(classification=base,model=card,quality_flags=quality,
            status='unable_to_classify' if base['abstained'] else 'completed',
            advice=['Take sharp photographs in natural light, including both sides of several leaves.','Inspect nearby plants and monitor changes.','Consult a qualified local agronomist if symptoms spread.'],
            disclaimer='Image-assisted screening only; not a confirmed diagnosis.')

class SensorIngestionAdapter(Protocol):
    def normalize(self, payload: dict) -> dict: ...
class SimulatorAdapter:
    def normalize(self, payload): return {**payload,'quality_flags':['simulated','uncalibrated'] if not payload.get('calibration_id') else ['simulated']}
class Esp32HttpAdapter:
    def normalize(self, payload): return {**payload,'quality_flags':['uncalibrated'] if not payload.get('calibration_id') else []}
class HistoricalSensorAdapter(Esp32HttpAdapter): pass

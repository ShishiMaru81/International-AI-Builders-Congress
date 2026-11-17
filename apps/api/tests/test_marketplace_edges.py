from datetime import timedelta
from decimal import Decimal
import io
import pytest
from PIL import Image
from tests.test_platform import client
from tests.test_marketplace import actors,product,address,cart,checkout,account,API

def admin(client):
    headers,user=account(client,'customer','operator')
    from app.db import Session,User
    with Session() as db:db.get(User,user['id']).role='admin';db.commit()
    return headers

def test_multi_seller_totals_private_groups_and_cancellation_once(client,actors):
    f,_,c,_,other,_=actors;f2,_=account(client,'farmer','secondfarmer')
    p=product(client,f);p2=product(client,f2,price_bdt='12.35',quantity_step='.5',delivery_fee_bdt='20')
    a=address(client,c);cart(client,c,p['id'],'3');cart(client,c,p2['id'],'1.5')
    quote=client.get(API+'/market/cart',headers=c).json()
    r=client.post(API+'/market/orders',headers={**c,'Idempotency-Key':'multi'},json={'address_id':a['id'],'quote_hash':quote['quote_hash'],'fulfillment':{p['id']:'delivery',p2['id']:'pickup'}})
    assert r.status_code==200,r.text
    o=r.json();assert o['total_bdt']=='203.53' and len(o['seller_orders'])==2
    seller=client.get(API+'/market/orders/'+o['id'],headers=f).json();assert len(seller['seller_orders'])==1 and seller['total_bdt']=='185.00'
    pickup=next(s for s in o['seller_orders'] if s['fulfillment']=='pickup');assert 'line1' not in pickup['destination']
    assert client.get(API+'/market/addresses',headers=f).status_code==403
    for _ in range(2):assert client.post(API+'/market/orders/'+o['id']+'/cancel',headers=c,json={'reason':'Changed plans'}).status_code==200
    assert client.get(API+'/market/products/'+p['id']).json()['stock_quantity']=='100.000'
    assert client.get(API+'/market/products/'+p2['id']).json()['stock_quantity']=='100.000'

def test_stale_quote_conflicting_key_owner_and_order_transition(client,actors):
    f,_,c,_,other,_=actors;p=product(client,f);a=address(client,c);cart(client,c,p['id'],'2');quote=client.get(API+'/market/cart',headers=c).json()
    assert client.patch(API+'/market/products/'+p['id'],headers=other,json={'expected_version':p['version'],'name':'Stolen'}).status_code==403
    assert client.patch(API+'/market/products/'+p['id'],headers=f,json={'expected_version':p['version'],'price_bdt':'50'}).status_code==200
    r=client.post(API+'/market/orders',headers={**c,'Idempotency-Key':'stale'},json={'address_id':a['id'],'quote_hash':quote['quote_hash'],'fulfillment':{p['id']:'pickup'}})
    assert r.status_code==409
    result=checkout(client,c,a,p['id'],key='fresh',method='pickup');assert result.status_code==200
    so=result.json()['seller_orders'][0]
    assert client.patch(API+'/market/seller-orders/'+so['id'],headers=f,json={'status':'delivered','cash_received':True}).status_code==409
    replay=client.post(API+'/market/orders',headers={**c,'Idempotency-Key':'fresh'},json={'address_id':a['id'],'quote_hash':'different','fulfillment':{p['id']:'pickup'}})
    assert replay.status_code==409

def test_admin_moderation_policy_and_suspended_session(client,actors):
    f,fu,c,_,_,_=actors;p=product(client,f);op=admin(client)
    assert client.get(API+'/admin/market/dashboard',headers=c).status_code==403
    assert client.patch(API+'/admin/market/farmers/'+fu['id'],headers=op,json={'verification_status':'verified','reason':'Reviewed locally'}).status_code==200
    assert client.patch(API+'/admin/market/products/'+p['id'],headers=op,json={'moderation_status':'hidden','reason':'Review report'}).status_code==200
    assert client.get(API+'/market/products/'+p['id']).status_code==404
    assert client.get(API+'/admin/market/products',headers=op).json()['total']==1
    assert client.patch(API+'/admin/market/users/'+fu['id'],headers=op,json={'is_active':False,'reason':'Suspended for review'}).status_code==200
    assert client.get(API+'/me',headers=f).status_code==401
    assert client.patch(API+'/admin/market/policy',headers=op,json={'marketplace_enabled':False}).status_code==200
    assert client.get(API+'/admin/market/policy',headers=op).json()['marketplace_enabled'] is False
    assert client.post(API+'/market/orders',headers={**c,'Idempotency-Key':'paused'},json={'address_id':'x','quote_hash':'x','fulfillment':{}}).status_code==503

def test_real_image_upload_content_owner_and_archive_history(client,actors):
    f,_,c,_,_,_=actors;p=product(client,f);out=io.BytesIO();Image.new('RGBA',(200,200),(0,255,0,0)).save(out,'PNG')
    r=client.post(API+'/market/products/'+p['id']+'/images',headers=f,files={'image':('leaf.png',out.getvalue(),'image/png')});assert r.status_code==200,r.text
    url=r.json()['url'];image=client.get(url);assert image.status_code==200
    assert Image.open(io.BytesIO(image.content)).getpixel((0,0))==(255,255,255)
    assert client.post(API+'/market/products/'+p['id']+'/images',headers=c,files={'image':('leaf.png',out.getvalue(),'image/png')}).status_code==403
    assert client.post(API+'/market/products/'+p['id']+'/images',headers=f,files={'image':('bad.jpg',b'bad')}).status_code==415

def test_expiry_releases_orders_and_no_bid_reserve_auction(client,actors,monkeypatch):
    import app.market_service as service
    f,_,c,_,_,_=actors;p=product(client,f);a=address(client,c);cart(client,c,p['id'],'3');o=checkout(client,c,a,p['id'],method='pickup').json()
    initial=service.clock();monkeypatch.setattr(service,'clock',lambda:initial+timedelta(hours=49))
    expired=client.get(API+'/market/orders/'+o['id'],headers=c).json();assert expired['status']=='cancelled'
    assert client.get(API+'/market/products/'+p['id']).json()['stock_quantity']=='100.000'
    starts=service.clock();r=client.post(API+'/market/auctions',headers=f,json={'product_id':p['id'],'lot_quantity':'20','starting_bid_bdt':'700','minimum_increment_bdt':'50','starts_at':(starts-timedelta(seconds=1)).isoformat(),'ends_at':(starts+timedelta(seconds=3)).isoformat()});assert r.status_code==200,r.text
    monkeypatch.setattr(service,'clock',lambda:initial+timedelta(hours=49,seconds=4))
    assert client.get(API+'/market/auctions/'+r.json()['id']).json()['state']=='ended'
    assert client.get(API+'/market/products/'+p['id']).json()['stock_quantity']=='100.000'

def test_decimal_unit_roundtrip_and_geodesic(client,actors):
    f,_,c,_,_,_=actors
    for unit,step in [('kg','.001'),('g','1'),('piece','1'),('bundle','1'),('crate','1')]:
        p=product(client,f,unit=unit,quantity_step=step,price_bdt='45.15')
        assert p['price_bdt']=='45.15' and Decimal(p['quantity_step'])==Decimal(step)
    from app.market_service import distance_km
    assert distance_km(24,90,24,90)==0
    assert distance_km(24,90,24.1,90)==pytest.approx(11.1195,rel=.001)

def test_account_export_and_safe_deletion_of_commerce_history(client,actors):
    f,_,c,cu,_,_=actors;p=product(client,f);a=address(client,c);cart(client,c,p['id'],'2');o=checkout(client,c,a,p['id'],method='pickup').json()
    exported=client.get(API+'/me/export',headers=c).json()
    assert exported['marketplace']['orders'][0]['id']==o['id']
    assert 'password_hash' not in str(exported) and 'key_hash' not in str(exported)
    assert client.delete(API+'/me',headers=c).status_code==409
    assert client.post(API+'/market/orders/'+o['id']+'/cancel',headers=c,json={'reason':'Cancel before account deletion'}).status_code==200
    assert client.delete(API+'/me',headers=c).status_code==200
    assert client.get(API+'/me',headers=c).status_code==401
    from app.db import Session,User
    from app.market_models import Order,Address
    from sqlalchemy import select
    with Session() as db:
        user=db.get(User,cu['id']);assert user and not user.is_active and user.email is None and user.password_hash is None
        assert db.get(Order,o['id']) is not None
        assert not list(db.scalars(select(Address).where(Address.user_id==cu['id'])))

def test_farmer_cannot_bypass_bid_cancellation_rule_by_pausing_listing(client,actors):
    import app.market_service as service
    f,_,c,_,_,_=actors;p=product(client,f);current=service.clock()
    auction=client.post(API+'/market/auctions',headers=f,json={'product_id':p['id'],'lot_quantity':'20','starting_bid_bdt':'700','minimum_increment_bdt':'50','starts_at':(current-timedelta(seconds=1)).isoformat(),'ends_at':(current+timedelta(hours=1)).isoformat()}).json()
    assert client.post(API+'/market/auctions/'+auction['id']+'/bids',headers={**c,'Idempotency-Key':'pause-bid'},json={'amount_bdt':'700','confirm':True}).status_code==200
    fresh=client.get(API+'/market/products/'+p['id'],headers=f).json()
    assert client.patch(API+'/market/products/'+p['id'],headers=f,json={'expected_version':fresh['version'],'status':'paused'}).status_code==409

def test_profile_coordinates_cannot_be_half_null(client,actors):
    f,_,_,_,_,_=actors
    assert client.patch(API+'/market/profile',headers=f,json={'latitude':'24','longitude':None}).status_code==422
    assert client.patch(API+'/market/profile',headers=f,json={'latitude':None,'longitude':'90'}).status_code==422

def test_verification_policy_covers_already_published_listing(client,actors):
    f,fu,c,_,_,_=actors;p=product(client,f);op=admin(client)
    assert client.patch(API+'/admin/market/policy',headers=op,json={'require_verified_farmer':True}).status_code==200
    assert client.get(API+'/market/products/'+p['id']).status_code==404
    assert client.get(API+'/market/products').json()['total']==0
    assert client.patch(API+'/admin/market/farmers/'+fu['id'],headers=op,json={'verification_status':'verified','reason':'Documents reviewed'}).status_code==200
    assert client.get(API+'/market/products/'+p['id']).status_code==200

def test_successful_lot_does_not_block_future_auction_and_winner_timeout(client,actors,monkeypatch):
    import app.market_service as service
    f,_,c,_,_,_=actors;p=product(client,f);a=address(client,c);current=service.clock()
    def auction():return client.post(API+'/market/auctions',headers=f,json={'product_id':p['id'],'lot_quantity':'20','starting_bid_bdt':'700','minimum_increment_bdt':'50','starts_at':(service.clock()-timedelta(seconds=1)).isoformat(),'ends_at':(service.clock()+timedelta(seconds=3)).isoformat()})
    first=auction().json()
    assert client.post(API+'/market/auctions/'+first['id']+'/bids',headers={**c,'Idempotency-Key':'lot-bid'},json={'amount_bdt':'700','confirm':True}).status_code==200
    monkeypatch.setattr(service,'clock',lambda:current+timedelta(seconds=4))
    assert client.get(API+'/market/auctions/'+first['id'],headers=c).json()['state']=='awarded'
    assert client.post(API+'/market/auctions/'+first['id']+'/confirm',headers={**c,'Idempotency-Key':'lot-confirm'},json={'address_id':a['id'],'fulfillment':'pickup'}).status_code==200
    second=auction();assert second.status_code==200,second.text
    assert client.post(API+'/market/auctions/'+second.json()['id']+'/bids',headers={**c,'Idempotency-Key':'lot-bid-2'},json={'amount_bdt':'700','confirm':True}).status_code==200
    monkeypatch.setattr(service,'clock',lambda:current+timedelta(hours=25))
    ended=client.get(API+'/market/auctions/'+second.json()['id'],headers=c).json()
    assert ended['state']=='unfulfilled'
    assert client.get(API+'/market/products/'+p['id']).json()['auction_reserved']=='0.000'

def test_suspended_bidder_cannot_freeze_minimum_bid_and_last_admin_cannot_delete(client,actors):
    import app.market_service as service
    f,_,c,_,other,ou=actors;p=product(client,f);op=admin(client);current=service.clock()
    a=client.post(API+'/market/auctions',headers=f,json={'product_id':p['id'],'lot_quantity':'20','starting_bid_bdt':'700','minimum_increment_bdt':'50','starts_at':(current-timedelta(seconds=1)).isoformat(),'ends_at':(current+timedelta(hours=1)).isoformat()}).json()
    for headers,amount,key in [(c,'750','eligible'),(other,'999999999','blocked')]:
        assert client.post(API+'/market/auctions/'+a['id']+'/bids',headers={**headers,'Idempotency-Key':key},json={'amount_bdt':amount,'confirm':True}).status_code==200
    assert client.patch(API+'/admin/market/users/'+ou['id'],headers=op,json={'is_active':False,'reason':'Fraud review'}).status_code==200
    refreshed=client.get(API+'/market/auctions/'+a['id'],headers=c).json()
    assert refreshed['highest_bid_bdt']=='750.00'
    response=client.post(API+'/market/auctions/'+a['id']+'/bids',headers={**c,'Idempotency-Key':'already-best'},json={'amount_bdt':'800','confirm':True})
    assert response.status_code==409 and 'already' in response.json()['message']
    assert client.delete(API+'/me',headers=op).status_code==409

def test_farm_delete_requires_archiving_dependent_listing(client,actors):
    f,_,_,_,_,_=actors;p=product(client,f)
    assert client.delete(API+'/farms/'+p['farm_id'],headers=f).status_code==409
    assert client.patch(API+'/market/products/'+p['id'],headers=f,json={'expected_version':p['version'],'status':'archived'}).status_code==200
    assert client.delete(API+'/farms/'+p['farm_id'],headers=f).status_code==200
    archived=client.get(API+'/market/products/'+p['id'],headers=f).json();assert archived['farm_id'] is None

def test_simultaneous_bids_keep_highest_eligible_price_and_distinct_stock(client,actors):
    from concurrent.futures import ThreadPoolExecutor
    import app.market_service as service
    f,_,c,_,other,_=actors;p=product(client,f);current=service.clock()
    a=client.post(API+'/market/auctions',headers=f,json={'product_id':p['id'],'lot_quantity':'20','starting_bid_bdt':'700','minimum_increment_bdt':'50','starts_at':(current-timedelta(seconds=1)).isoformat(),'ends_at':(current+timedelta(hours=1)).isoformat()}).json()
    def submit(args):
        headers,amount,key=args
        return client.post(API+'/market/auctions/'+a['id']+'/bids',headers={**headers,'Idempotency-Key':key},json={'amount_bdt':amount,'confirm':True}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(submit,[(c,'750','parallel-one'),(other,'800','parallel-two')]))
    assert all(status in [200,422] for status in results) and 200 in results
    assert client.get(API+'/market/auctions/'+a['id']).json()['highest_bid_bdt']=='800.00'
    listing=client.get(API+'/market/products/'+p['id']).json();assert listing['stock_quantity']=='80.000' and listing['auction_reserved']=='20.000'

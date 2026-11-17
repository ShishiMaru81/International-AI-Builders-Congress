"""Commerce contract: real transactions, role isolation, geography and optional auctions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import pytest
from tests.test_platform import client

API='/api/v1'
def account(client,role,name):
    r=client.post(API+'/auth/register',json={'name':name,'email':name+'@example.test','password':'correct horse battery','role':role})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']},r.json()['user']

@pytest.fixture
def actors(client):
    farmer,fu=account(client,'farmer','farmer');customer,cu=account(client,'customer','customer');other,ou=account(client,'customer','other')
    return farmer,fu,customer,cu,other,ou

def product(client,farmer,**overrides):
    client.patch(API+'/market/profile',headers=farmer,json={'public_name':'Example farm','district':'Gazipur','area':'Example area','latitude':'24.00','longitude':'90.42'})
    farms=client.get(API+'/farms',headers=farmer).json()
    farm=farms[0] if farms else client.post(API+'/farms',headers=farmer,json={'name':'Test Farm','district':'Gazipur'}).json()
    body={'farm_id':farm['id'],'name':'Potatoes','category':'vegetables','description':'A test listing','price_bdt':'45.00','unit':'kg','quantity_step':'1','stock_quantity':'100','status':'published','pickup_enabled':True,'delivery_enabled':True,'nationwide_delivery':True,'delivery_fee_bdt':'50.00',**overrides}
    r=client.post(API+'/market/products',headers=farmer,json=body);assert r.status_code==200,r.text
    return r.json()

def address(client,customer,district='Dhaka'):
    r=client.post(API+'/market/addresses',headers=customer,json={'name':'Buyer','phone':'01700000000','line1':'Example collection address','district':district,'area':'Example','country':'Bangladesh'})
    assert r.status_code==200,r.text
    return r.json()

def cart(client,customer,pid,qty):
    return client.post(API+'/market/cart/items',headers=customer,json={'product_id':pid,'quantity':qty})

def checkout(client,customer,addr,pid,key='checkout-1',method='delivery'):
    quote=client.get(API+'/market/cart',headers=customer).json()['quote_hash']
    return client.post(API+'/market/orders',headers={**customer,'Idempotency-Key':key},json={'address_id':addr['id'],'quote_hash':quote,'fulfillment':{pid:method}})

def test_direct_purchase_without_bid_and_replay(client,actors):
    farmer,_,customer,_,other,_=actors;p=product(client,farmer);a=address(client,customer)
    assert p['minimum_order_quantity'] is None and p['auction'] is None
    assert cart(client,customer,p['id'],'3').status_code==200
    quote=client.get(API+'/market/cart',headers=customer).json()
    body={'address_id':a['id'],'quote_hash':quote['quote_hash'],'fulfillment':{p['id']:'delivery'}}
    r=client.post(API+'/market/orders',headers={**customer,'Idempotency-Key':'same'},json=body);assert r.status_code==200,r.text
    order=r.json();assert Decimal(order['total_bdt'])==Decimal('185')
    assert order['payment_status']=='demo_unpaid'
    replay=client.post(API+'/market/orders',headers={**customer,'Idempotency-Key':'same'},json=body)
    assert replay.json()['id']==order['id']
    assert client.get(API+'/market/products/'+p['id']).json()['stock_quantity']=='97.000'
    assert client.get(API+'/market/orders/'+order['id'],headers=other).status_code==404
    so=order['seller_orders'][0]
    assert client.patch(API+'/market/seller-orders/'+so['id'],headers=customer,json={'status':'delivered'}).status_code==403
    for state in ['confirmed','preparing','out_for_delivery','delivered']:
        r=client.patch(API+'/market/seller-orders/'+so['id'],headers=farmer,json={'status':state});assert r.status_code==200,r.text

def test_moq_optional_precision_units_and_fulfillment(client,actors):
    f,_,c,_,_,_=actors;p=product(client,f,minimum_order_quantity='5',nationwide_delivery=False,delivery_districts=['Gazipur'])
    assert cart(client,c,p['id'],'3').status_code==422
    assert cart(client,c,p['id'],'5.5').status_code==422
    assert cart(client,c,p['id'],'5').status_code==200
    a=address(client,c,'Dhaka')
    assert checkout(client,c,a,p['id']).status_code==422
    assert checkout(client,c,a,p['id'],key='pickup',method='pickup').status_code==200
    assert client.post(API+'/market/products',headers=c,json={}).status_code in [403,422]
    bad=client.patch(API+'/market/products/'+p['id'],headers=f,json={'expected_version':p['version'],'price_bdt':'1.999'})
    assert bad.status_code==422

def test_nearby_prioritizes_without_hiding_far_and_public_privacy(client,actors):
    f,_,c,_,_,_=actors;near=product(client,f,name='Nearby potato')
    f2,_=account(client,'farmer','farmer2');far=product(client,f2,name='Far potato')
    client.patch(API+'/market/profile',headers=f2,json={'district':'Sylhet','latitude':'24.89','longitude':'91.87'})
    # New product snapshots the seller's current coarse location.
    far=product(client,f2,name='Far away potato')
    from app.db import Session
    from app.market_models import Product
    with Session() as db:
        row=db.get(Product,far['id']);row.latitude=Decimal('24.89');row.longitude=Decimal('91.87');db.commit()
    rows=client.get(API+'/market/products?lat=24&lon=90.42&q=potato').json()['items']
    assert rows[0]['nearby'] is True and any(x['id']==far['id'] and not x['nearby'] for x in rows)
    assert all('latitude' not in x and 'longitude' not in x and 'phone' not in x for x in rows)
    assert client.get(API+'/market/products?q=potato').status_code==200

def auction(client,f,p,**overrides):
    current=datetime.now(timezone.utc)
    data={'product_id':p['id'],'lot_quantity':'20','starting_bid_bdt':'700','minimum_increment_bdt':'50','starts_at':(current-timedelta(seconds=1)).isoformat(),'ends_at':(current+timedelta(hours=1)).isoformat(),**overrides}
    r=client.post(API+'/market/auctions',headers=f,json=data);assert r.status_code==200,r.text
    return r.json()

def bid(client,c,aid,amount,key):return client.post(API+f'/market/auctions/{aid}/bids',headers={**c,'Idempotency-Key':key},json={'amount_bdt':amount,'confirm':True})

def test_auction_opt_in_reserved_stock_increment_and_deadline(client,actors):
    f,_,c,_,other,_=actors;p=product(client,f);a=auction(client,f,p)
    assert client.get(API+'/market/products/'+p['id']).json()['stock_quantity']=='80.000'
    assert bid(client,f,a['id'],'750','self').status_code==403
    assert bid(client,c,a['id'],'750','bid1').status_code==200
    assert bid(client,c,a['id'],'750','bid1').status_code==200
    assert bid(client,other,a['id'],'775','small').status_code==422
    assert bid(client,other,a['id'],'850','bid2').status_code==200
    assert client.post(API+f"/market/auctions/{a['id']}/cancel",headers=f,json={'reason':'changed mind'}).status_code==409
    from app.db import Session
    from app.market_models import Auction
    with Session() as db:
        row=db.get(Auction,a['id']);row.ends_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat();db.commit()
    assert bid(client,c,a['id'],'900','late').status_code==409
    ended=client.get(API+f"/market/auctions/{a['id']}",headers=other).json()
    assert ended['state']=='awarded' and ended['winner_is_you']
    addr=address(client,other)
    r=client.post(API+f"/market/auctions/{a['id']}/confirm",headers={**other,'Idempotency-Key':'winner'},json={'address_id':addr['id'],'fulfillment':'pickup'})
    assert r.status_code==200,r.text
    assert Decimal(r.json()['total_bdt'])==Decimal('850')
    assert r.json()['payment_status']=='demo_unpaid'

def test_simultaneous_orders_cannot_oversell(client,actors):
    f,_,c,_,other,_=actors;p=product(client,f,stock_quantity='5');a=address(client,c);b=address(client,other)
    cart(client,c,p['id'],'4');cart(client,other,p['id'],'4')
    quotes=[client.get(API+'/market/cart',headers=h).json()['quote_hash'] for h in [c,other]]
    def buy(args):
        h,addr,key,quote=args
        return client.post(API+'/market/orders',headers={**h,'Idempotency-Key':key},json={'address_id':addr['id'],'quote_hash':quote,'fulfillment':{p['id']:'pickup'}}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(buy,[(c,a,'one',quotes[0]),(other,b,'two',quotes[1])]))
    assert statuses.count(200)==1 and all(x in [200,409,422] for x in statuses)
    assert Decimal(client.get(API+'/market/products/'+p['id']).json()['stock_quantity'])==1

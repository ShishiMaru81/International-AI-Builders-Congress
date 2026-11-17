"""Marketplace transactions and domain rules shared by HTTP and lifecycle worker."""
from __future__ import annotations
import hashlib,json,math
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import delete,func,or_,select,text
from .db import Session,User,Record,now
from .market_models import Address,Auction,Audit,Bid,CartItem,Favorite,Idempotency,Notification,Order,OrderItem,PaymentRecord,Policy,Product,ProductImage,Profile,Report,Review,SellerOrder

NOTICE='Prototype marketplace. No online payment is processed. Cash/fulfillment records are user reports, not independent verification.'
DEFAULT_POLICY={'marketplace_enabled':True,'require_verified_farmer':False,'max_bids_per_minute':20,'winner_confirmation_hours':24,'order_acceptance_hours':48}
Q=Decimal('0.001');M=Decimal('0.01')
def clock():return datetime.now(timezone.utc)
def stamp(value):return value.astimezone(timezone.utc).isoformat()
def money(value):return Decimal(value).quantize(M,rounding=ROUND_HALF_UP)
def m(value):return format(money(value),'.2f')
def q(value):return format(Decimal(value),'.3f')
def fail(status,message):raise HTTPException(status,message)

@contextmanager
def transaction():
    """Cross-worker serialization. PostgreSQL can later replace this with row locks."""
    with Session() as db:
        try:
            if db.bind.dialect.name=='sqlite':
                db.execute(text('PRAGMA busy_timeout=15000'))
                db.execute(text('BEGIN IMMEDIATE'))
            else:
                db.begin();db.execute(text('SELECT pg_advisory_xact_lock(781423601)'))
            yield db
            db.commit()
        except Exception:
            db.rollback();raise

def actor(db,user,roles=None):
    fresh=db.get(User,user.id)
    if not fresh or not fresh.is_active:fail(401,'Session is no longer active')
    if roles and fresh.role not in roles:fail(403,'This operation is not allowed for your role')
    return fresh
def owned(db,model,id,user,field):
    row=db.get(model,id)
    if not row or getattr(row,field)!=user.id:fail(404,'Record not found')
    return row
def policy(db):
    row=db.get(Policy,'settings');return {**DEFAULT_POLICY,**(row.value if row else {})}
def enabled(db):
    if not policy(db)['marketplace_enabled']:fail(503,'Marketplace purchases are temporarily paused by the administrator')
def audit(db,user,event,kind,id,**details):
    db.add(Audit(actor_id=user.id if user else None,event=event,entity_type=kind,entity_id=id,details=details))
def notify(db,uid,title,kind,id,message=''):
    db.add(Notification(user_id=uid,title=title,message=message,entity_type=kind,entity_id=id))
def profile(db,user):
    row=db.get(Profile,user.id)
    if not row:row=Profile(user_id=user.id,public_name=user.name);db.add(row);db.flush()
    return row
def profile_view(row,user=None):
    data={'user_id':row.user_id,'public_name':row.public_name,'bio':row.bio,'district':row.district,'area':row.area,'verification_status':row.verification_status,'updated_at':row.updated_at}
    if user:data.update(phone=row.phone,latitude=str(row.latitude) if row.latitude is not None else None,longitude=str(row.longitude) if row.longitude is not None else None)
    return data
def address_view(row):
    return {k:getattr(row,k) for k in ['id','name','phone','line1','district','area','country','created_at']}|{'latitude':str(row.latitude) if row.latitude is not None else None,'longitude':str(row.longitude) if row.longitude is not None else None}
def distance_km(lat1,lon1,lat2,lon2):
    a,b,c,d=map(math.radians,map(float,[lat1,lon1,lat2,lon2]));x=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 6371.0088*2*math.asin(math.sqrt(min(1,max(0,x))))
def listing_eligible(db,p):
    seller=db.get(User,p.farmer_id)
    verified=not policy(db)['require_verified_farmer'] or bool(db.get(Profile,p.farmer_id) and db.get(Profile,p.farmer_id).verification_status=='verified')
    return bool(verified and p.status=='published' and p.moderation_status=='visible' and seller and seller.is_active and (not p.available_from or p.available_from<=clock().date().isoformat()))
def can_view(db,p,user=None):
    return listing_eligible(db,p) or bool(user and (user.id==p.farmer_id or user.role=='admin'))
def check_quantity(p,quantity,*,stock=True,moq=True):
    quantity=Decimal(quantity)
    if quantity<=0 or quantity%p.quantity_step:fail(422,f'Quantity must be a positive multiple of {q(p.quantity_step)} {p.unit}')
    if p.unit!='kg' and quantity!=quantity.to_integral_value():fail(422,'This listing requires whole units')
    if moq and p.minimum_order_quantity is not None and quantity<p.minimum_order_quantity:fail(422,f'Minimum order is {q(p.minimum_order_quantity)} {p.unit}')
    if moq and p.maximum_order_quantity is not None and quantity>p.maximum_order_quantity:fail(422,'Quantity exceeds this listing maximum order')
    if stock and quantity>p.stock_quantity:fail(409,'Insufficient fixed-price stock. Review your cart.')
def rate(db,user,event,limit=20):
    since=stamp(clock()-timedelta(minutes=1))
    count=db.scalar(select(func.count()).select_from(Audit).where(Audit.actor_id==user.id,Audit.event==event,Audit.created_at>=since))
    if count>=limit:fail(429,'Too many requests. Wait a minute and retry.')
def idempotent(db,user,operation,key,body,run):
    if not key or not 1<=len(key)<=100 or any(ord(c)<33 or ord(c)>126 for c in key):fail(422,'Supply a valid Idempotency-Key header (1–100 printable characters)')
    digest=hashlib.sha256(json.dumps(body,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
    row=db.get(Idempotency,(user.id,operation,key))
    if row:
        if row.fingerprint!=digest:fail(409,'Idempotency key was already used with different request data')
        return row.response
    result=run();db.flush();db.add(Idempotency(user_id=user.id,operation=operation,key=key,fingerprint=digest,response=result));return result

def product_view(db,p,user=None,lat=None,lon=None,include_auction=True):
    seller=db.get(User,p.farmer_id);pr=db.get(Profile,p.farmer_id)
    images=list(db.scalars(select(ProductImage).where(ProductImage.product_id==p.id).order_by(ProductImage.created_at)))
    distance=distance_km(lat,lon,p.latitude,p.longitude) if lat is not None and lon is not None and p.latitude is not None and p.longitude is not None else None
    data={k:getattr(p,k) for k in ['id','farmer_id','farm_id','name','description','category','unit','district','area','pickup_enabled','delivery_enabled','nationwide_delivery','delivery_districts','harvest_date','available_from','moderation_status','version','created_at','updated_at']}
    data.update(seller_name=pr.public_name if pr else seller.name if seller else 'Archived farmer',seller_verification=pr.verification_status if pr else 'unverified',price_bdt=m(p.price_bdt),currency='BDT',quantity_step=q(p.quantity_step),stock_quantity=q(p.stock_quantity),auction_reserved=q(p.auction_reserved),minimum_order_quantity=q(p.minimum_order_quantity) if p.minimum_order_quantity is not None else None,maximum_order_quantity=q(p.maximum_order_quantity) if p.maximum_order_quantity is not None else None,delivery_fee_bdt=m(p.delivery_fee_bdt),status='out_of_stock' if p.status=='published' and p.stock_quantity==0 else p.status,images=[{'id':i.id,'url':f'/api/v1/market/products/{p.id}/images/{i.id}'} for i in images],distance_km=round(distance,1) if distance is not None else None,nearby=distance<=20 if distance is not None else False,distance_notice='Approximate geographic distance to a coarse farm location; not road distance or delivery eligibility.',available=listing_eligible(db,p) and p.stock_quantity>0)
    if user and (user.id==p.farmer_id or user.role=='admin'):data['pickup_instructions']=p.pickup_instructions
    if include_auction:
        a=db.scalar(select(Auction).where(Auction.product_id==p.id,or_(Auction.state.in_(['draft','scheduled','live']), (Auction.state=='awarded') & Auction.reserved.is_(True))).order_by(Auction.created_at.desc()))
        data['auction']=auction_view(db,a,user,include_product=False) if a and (a.state!='draft' or user and user.id==p.farmer_id) else None
    return data

def auction_view(db,a,user=None,include_product=True):
    p=db.get(Product,a.product_id);bids=list(db.scalars(select(Bid).where(Bid.auction_id==a.id).order_by(Bid.amount_bdt.desc(),Bid.created_at)))
    order=db.scalar(select(Order).where(Order.auction_id==a.id))
    data={k:getattr(a,k) for k in ['id','product_id','farmer_id','starts_at','ends_at','confirmation_deadline','state','created_at']}
    data.update(lot_quantity=q(a.lot_quantity),unit=p.unit,starting_bid_bdt=m(a.starting_bid_bdt),minimum_increment_bdt=m(a.minimum_increment_bdt),highest_bid_bdt=m(a.highest_bid_bdt) if a.highest_bid_bdt is not None else None,winner_is_you=bool(user and a.winner_id==user.id),confirmed_order_id=order.id if order and user and (user.id in [a.winner_id,a.farmer_id] or user.role=='admin') else None,reserve_met=a.highest_bid_bdt>=a.reserve_price_bdt if a.reserve_price_bdt and a.highest_bid_bdt is not None else a.reserve_price_bdt is None,server_time=stamp(clock()),notice=NOTICE,bids=[{'id':b.id,'amount_bdt':m(b.amount_bdt),'created_at':b.created_at,'bidder_alias':'Bidder '+hashlib.sha256((a.id+b.customer_id).encode()).hexdigest()[:6],'is_yours':bool(user and b.customer_id==user.id),'eligible':bool(db.get(User,b.customer_id).is_active)} for b in bids[:100]])
    if include_product:data['product']=product_view(db,p,user,include_auction=False)
    if user and (user.id==a.farmer_id or user.role=='admin'):data['reserve_price_bdt']=m(a.reserve_price_bdt) if a.reserve_price_bdt is not None else None
    return data

def release_auction(db,a):
    if a.reserved:
        p=db.get(Product,a.product_id);p.stock_quantity+=a.lot_quantity;p.auction_reserved-=a.lot_quantity;p.version+=1;p.updated_at=stamp(clock());a.reserved=False
def cancel_seller_order(db,so,user,reason):
    if so.status=='cancelled':return
    if so.status not in ['pending','confirmed','preparing','ready_for_pickup']:fail(409,'This fulfillment stage requires a dispute or return review, not automatic stock release')
    for item in db.scalars(select(OrderItem).where(OrderItem.seller_order_id==so.id)):
        p=db.get(Product,item.product_id);p.stock_quantity+=item.quantity;p.version+=1;p.updated_at=stamp(clock())
    so.status='cancelled';so.expires_at=None;so.updated_at=stamp(clock())
    order=db.get(Order,so.order_id)
    if order.auction_id:db.get(Auction,order.auction_id).state='unfulfilled'
    notify(db,order.customer_id,'Order cancelled','order',order.id,reason);notify(db,so.farmer_id,'Seller order cancelled','order',order.id,reason)
    audit(db,user,'order.cancelled','seller_order',so.id,reason=reason)
def tick(db):
    current=stamp(clock());settings=policy(db)
    for a in db.scalars(select(Auction).where(Auction.state.in_(['scheduled','live','awarded']))):
        if a.reserved and not listing_eligible(db,db.get(Product,a.product_id)):
            a.state='cancelled';release_auction(db,a);audit(db,None,'auction.listing_unavailable','auction',a.id)
            for bidder in set(db.scalars(select(Bid.customer_id).where(Bid.auction_id==a.id))):notify(db,bidder,'Auction listing unavailable','auction',a.id)
            continue
        if a.state in ['scheduled','live']:
            best_live=db.scalar(select(Bid).join(User,User.id==Bid.customer_id).where(Bid.auction_id==a.id,User.is_active.is_(True)).order_by(Bid.amount_bdt.desc(),Bid.created_at))
            a.highest_bid_bdt=best_live.amount_bdt if best_live else None
        if a.state=='awarded' and a.reserved and a.winner_id and not db.get(User,a.winner_id).is_active:
            a.state='unfulfilled';release_auction(db,a);audit(db,None,'auction.winner_ineligible','auction',a.id)
            continue
        if a.state=='scheduled' and a.starts_at<=current<a.ends_at:a.state='live'
        if a.state in ['scheduled','live'] and a.ends_at<=current:
            p=db.get(Product,a.product_id)
            best=db.scalar(select(Bid).join(User,User.id==Bid.customer_id).where(Bid.auction_id==a.id,User.is_active.is_(True)).order_by(Bid.amount_bdt.desc(),Bid.created_at))
            if not listing_eligible(db,p):a.state='cancelled';release_auction(db,a)
            elif best and (a.reserve_price_bdt is None or best.amount_bdt>=a.reserve_price_bdt):
                a.state='awarded';a.winner_id=best.customer_id;a.highest_bid_bdt=best.amount_bdt;a.confirmation_deadline=stamp(datetime.fromisoformat(a.ends_at)+timedelta(hours=settings['winner_confirmation_hours']))
                notify(db,a.winner_id,'You won an auction lot','auction',a.id,'Confirm an unpaid order before '+a.confirmation_deadline)
                notify(db,a.farmer_id,'Auction lot awarded','auction',a.id)
            else:a.state='ended';release_auction(db,a)
            audit(db,None,'auction.closed','auction',a.id,state=a.state)
        if a.state=='awarded' and a.reserved and a.confirmation_deadline<=current:
            a.state='unfulfilled';release_auction(db,a);audit(db,None,'auction.winner_timeout','auction',a.id)
            notify(db,a.farmer_id,'Auction confirmation expired','auction',a.id)
    for so in db.scalars(select(SellerOrder).where(SellerOrder.status.in_(['pending','ready_for_pickup']),SellerOrder.expires_at.is_not(None),SellerOrder.expires_at<=current)):
        cancel_seller_order(db,so,None,'Acceptance/collection deadline expired; inventory released')
    db.flush()

def cart_view(db,user):
    rows=list(db.scalars(select(CartItem).where(CartItem.customer_id==user.id).order_by(CartItem.id)))
    items=[];terms=[];subtotal=Decimal(0)
    for row in rows:
        p=db.get(Product,row.product_id);line=money(p.price_bdt*row.quantity);subtotal+=line
        items.append({'id':row.id,'product_id':p.id,'quantity':q(row.quantity),'product':product_view(db,p,user),'total_bdt':m(line)})
        terms.append([p.id,str(row.quantity),p.version,str(p.price_bdt),p.status,p.moderation_status,str(p.delivery_fee_bdt)])
    digest=hashlib.sha256(json.dumps(terms,separators=(',',':')).encode()).hexdigest()
    return {'items':items,'quote_hash':digest,'subtotal_bdt':m(subtotal),'currency':'BDT','notice':NOTICE,'delivery_fee_notice':'Delivery is charged once per seller/farm group at the maximum configured item delivery fee. Pickup is free.'}

def validate_fulfillment(p,address,method):
    if method=='pickup':
        if not p.pickup_enabled:fail(422,'Pickup is unavailable for '+p.name)
    elif method=='delivery':
        if not p.delivery_enabled or not (p.nationwide_delivery or address.district.casefold() in [x.casefold() for x in p.delivery_districts]):fail(422,'Delivery is not supported to this district for '+p.name)
    else:fail(422,'Choose pickup or delivery for every product')
def order_view(db,order,user):
    all_sellers=list(db.scalars(select(SellerOrder).where(SellerOrder.order_id==order.id)))
    if user.id!=order.customer_id and user.role!='admin' and not any(s.farmer_id==user.id for s in all_sellers):fail(404,'Order not found')
    sellers=all_sellers if user.id==order.customer_id or user.role=='admin' else [s for s in all_sellers if s.farmer_id==user.id]
    data=[]
    for so in sellers:
        items=list(db.scalars(select(OrderItem).where(OrderItem.seller_order_id==so.id)))
        data.append({k:getattr(so,k) for k in ['id','farmer_id','farm_id','fulfillment','status','payment_status','destination','expires_at','updated_at']}|{'subtotal_bdt':m(so.subtotal_bdt),'delivery_fee_bdt':m(so.delivery_fee_bdt),'total_bdt':m(so.total_bdt),'items':[{'product_id':i.product_id,'name':i.name,'unit':i.unit,'quantity':q(i.quantity),'unit_price_bdt':m(i.unit_price_bdt),'line_total_bdt':m(i.line_total_bdt)} for i in items]})
    states={s.status for s in sellers};payment={s.payment_status for s in sellers}
    status=next(iter(states)) if len(states)==1 else 'partially_fulfilled'
    return {'id':order.id,'customer_id':order.customer_id,'auction_id':order.auction_id,'created_at':order.created_at,'status':status,'payment_status':'cash_recorded' if payment=={'cash_recorded'} else 'demo_unpaid','total_bdt':m(sum((s.total_bdt for s in sellers),Decimal(0))),'currency':'BDT','seller_orders':data,'notice':NOTICE}

def create_order(db,user,address,lines,fulfillment,auction=None):
    """lines=(Product, quantity, line_total) snapshots; all checks precede mutations."""
    groups={}
    for p,quantity,total in lines:
        if not listing_eligible(db,p):fail(409,'A listing is unavailable. Review your cart.')
        if p.farmer_id==user.id:fail(403,'A farmer cannot purchase their own product')
        method=fulfillment.get(p.id);validate_fulfillment(p,address,method)
        if not auction:check_quantity(p,quantity)
        groups.setdefault((p.farmer_id,p.farm_id,method),[]).append((p,quantity,total))
    estimate=sum((sum((line for _,_,line in items),Decimal(0))+(max(p.delivery_fee_bdt for p,_,_ in items) if key[2]=='delivery' else Decimal(0)) for key,items in groups.items()),Decimal(0))
    if estimate>Decimal('999999999.99'):fail(422,'Order exceeds the prototype maximum value of BDT999999999.99')
    order=Order(customer_id=user.id,auction_id=auction.id if auction else None,total_bdt=Decimal(0));db.add(order);db.flush()
    for (farmer,farm,method),items in groups.items():
        subtotal=sum((line for _,_,line in items),Decimal(0));fee=max((p.delivery_fee_bdt for p,_,_ in items),default=Decimal(0)) if method=='delivery' else Decimal(0)
        destination=address_view(address) if method=='delivery' else {'district':items[0][0].district,'area':items[0][0].area,'pickup_instructions':items[0][0].pickup_instructions,'contact_name':address.name,'phone':address.phone,'notice':'Contact the farmer to agree pickup; exact farm coordinates are not public.'}
        so=SellerOrder(order_id=order.id,farmer_id=farmer,farm_id=farm,fulfillment=method,subtotal_bdt=subtotal,delivery_fee_bdt=fee,total_bdt=subtotal+fee,destination=destination,expires_at=stamp(clock()+timedelta(hours=policy(db)['order_acceptance_hours'])))
        db.add(so);db.flush();order.total_bdt+=so.total_bdt
        for p,quantity,line in items:
            db.add(OrderItem(seller_order_id=so.id,product_id=p.id,name=p.name,unit=p.unit,quantity=quantity,unit_price_bdt=money(line/quantity),line_total_bdt=line))
            if auction:p.auction_reserved-=quantity;auction.reserved=False
            else:p.stock_quantity-=quantity
            p.version+=1;p.updated_at=stamp(clock())
        db.add(PaymentRecord(seller_order_id=so.id,actor_id=user.id,status='demo_unpaid',amount_bdt=so.total_bdt))
        notify(db,farmer,'New order to review','order',order.id,'No online payment has been collected.')
    notify(db,user.id,'Order placed','order',order.id,'Seller confirmation is pending. '+NOTICE);audit(db,user,'order.created','order',order.id,total_bdt=m(order.total_bdt));db.flush();return order_view(db,order,user)

def paginate(items,offset=0,limit=20):
    start=max(0,offset);size=max(1,min(100,limit));return {'items':items[start:start+size],'total':len(items),'offset':start,'limit':size,'has_more':start+size<len(items)}

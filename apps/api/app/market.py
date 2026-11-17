"""Integrated fixed-price marketplace with explicitly optional auction lots."""
import io,os,warnings
from decimal import Decimal
from datetime import timedelta,timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4
from fastapi import APIRouter,Depends,File,Header,HTTPException,Query,UploadFile
from fastapi.responses import Response
from PIL import Image,ImageOps,UnidentifiedImageError
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from sqlalchemy import delete,func,or_,select
from .db import Record,Token,User
from .identity import optional_user,require_user,user_view
from .market_models import *
from .market_schemas import *
from . import market_service as s

router=APIRouter(prefix='/api/v1',tags=['KrishiMarket marketplace'])
Who=Annotated[User,Depends(require_user)];Maybe=Annotated[User|None,Depends(optional_user)]
Idem=Annotated[str|None,Header(alias='Idempotency-Key')]
IMAGE_ROOT=Path(os.getenv('IMAGE_STORAGE_PATH','storage'))/'marketplace'
IMAGE_ROOT.mkdir(parents=True,exist_ok=True)

def get_product(db,id,user=None):
    p=db.get(Product,id)
    if not p or not s.can_view(db,p,user):s.fail(404,'Product not found')
    return p
def owner_product(db,id,user):
    s.actor(db,user,['farmer']);return s.owned(db,Product,id,user,'farmer_id')
def get_auction(db,id,user=None):
    a=db.get(Auction,id)
    if not a:s.fail(404,'Auction not found')
    p=db.get(Product,a.product_id)
    if not s.can_view(db,p,user) or (a.state=='draft' and not(user and (user.id==a.farmer_id or user.role=='admin'))):s.fail(404,'Auction not found')
    return a
def validate_farm(db,id,user):
    farm=db.get(Record,id)
    if not farm or farm.kind!='farm' or farm.owner_id!=user.id:s.fail(404,'Farm not found')
    return farm

@router.get('/market/profile')
def my_profile(user:Who):
    with s.transaction() as db:return s.profile_view(s.profile(db,s.actor(db,user)),user)
@router.patch('/market/profile')
def edit_profile(body:ProfilePatch,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user);p=s.profile(db,u)
        for k,v in body.model_dump(exclude_unset=True).items():setattr(p,k,v.quantize(Decimal('.01')) if k in ['latitude','longitude'] and v is not None else v)
        p.updated_at=s.stamp(s.clock());s.audit(db,u,'profile.updated','profile',u.id);db.flush();return s.profile_view(p,u)
@router.get('/market/farmers/{id}')
def farmer_profile(id:str):
    with s.transaction() as db:
        user=db.get(User,id)
        if not user or user.role!='farmer' or not user.is_active:s.fail(404,'Farmer not found')
        return s.profile_view(s.profile(db,user))

@router.get('/market/addresses')
def addresses(user:Who):
    with s.transaction() as db:
        s.actor(db,user,['customer']);return [s.address_view(a) for a in db.scalars(select(Address).where(Address.user_id==user.id))]
@router.post('/market/addresses')
def add_address(body:AddressCreate,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['customer'])
        if db.scalar(select(func.count()).select_from(Address).where(Address.user_id==user.id))>=20:s.fail(422,'Maximum20 saved addresses')
        a=Address(user_id=user.id,**body.model_dump());db.add(a);db.flush();s.audit(db,u,'address.created','address',a.id);return s.address_view(a)
@router.delete('/market/addresses/{id}')
def delete_address(id:str,user:Who):
    with s.transaction() as db:
        s.actor(db,user,['customer']);a=s.owned(db,Address,id,user,'user_id');db.delete(a);return {'ok':True}

@router.get('/market/nearby')
@router.get('/market/products')
def products(user:Maybe,q:str=Query(default='',max_length=150),category:str|None=None,unit:str|None=None,
             district:str|None=None,district_filter:str|None=None,lat:float|None=Query(default=None,ge=20.4,le=26.7),lon:float|None=Query(default=None,ge=88,le=92.8),
             sort:str=Query(default='nearby',pattern='^(nearby|nearest|price|price_desc|newest)$'),available:bool=True,offset:int=Query(default=0,ge=0),limit:int=Query(default=20,ge=1,le=100)):
    if (lat is None)!=(lon is None):s.fail(422,'Provide both location coordinates, or leave both unset')
    with s.transaction() as db:
        s.tick(db);query=select(Product).join(User,User.id==Product.farmer_id).where(Product.status.in_(['published','out_of_stock']),Product.moderation_status=='visible',User.is_active.is_(True))
        if q.strip():query=query.where(or_(Product.name.ilike('%'+q.strip()+'%'),Product.description.ilike('%'+q.strip()+'%')))
        if category:query=query.where(Product.category==category)
        if unit:query=query.where(Product.unit==unit)
        if district_filter:query=query.where(func.lower(Product.district)==district_filter.lower())
        if available:query=query.where(Product.stock_quantity>0)
        rows=[p for p in db.scalars(query) if not p.available_from or p.available_from<=s.clock().date().isoformat()]
        items=[]
        for p in rows:
            if not s.listing_eligible(db,p):continue
            item=s.product_view(db,p,user,lat,lon)
            d=s.distance_km(lat,lon,p.latitude,p.longitude) if lat is not None and lon is not None and p.latitude is not None and p.longitude is not None else None
            item.update(distance_km=round(d,1) if d is not None else None,nearby=d is not None and d<=20)
            items.append(item)
        if sort in ['price','price_desc']:items.sort(key=lambda p:Decimal(p['price_bdt']),reverse=sort=='price_desc')
        elif sort=='newest':items.sort(key=lambda p:p['created_at'],reverse=True)
        else:items.sort(key=lambda p:(not p['nearby'] if sort=='nearby' else False,p['distance_km'] is None,p['distance_km'] if p['distance_km'] is not None else float('inf'),p['name'].casefold()))
        return s.paginate(items,offset,limit)|{'location':{'district':district,'lat':lat,'lon':lon,'radius_km':20} if lat is not None or district else None,'sort':sort,'notice':'Approximate geographic distance to a coarse farm location; not road distance. Nationwide results remain available.' if lat is not None else 'Choose an optional location for nearby-first distance ranking. Showing nationwide listings.'}

@router.post('/market/products')
def create_product(body:ProductCreate,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['farmer']);s.enabled(db);s.rate(db,u,'product.created');farm=validate_farm(db,body.farm_id,u);p=s.profile(db,u)
        if body.status=='published' and s.policy(db)['require_verified_farmer'] and p.verification_status!='verified':s.fail(403,'Farmer verification is required before publishing')
        data=body.model_dump();data['harvest_date']=body.harvest_date.isoformat() if body.harvest_date else None;data['available_from']=body.available_from.isoformat() if body.available_from else None
        lat=p.latitude;lon=p.longitude
        if lat is None and farm.payload.get('location_consent') and farm.payload.get('latitude') is not None:
            lat=Decimal(str(farm.payload['latitude'])).quantize(Decimal('.01'));lon=Decimal(str(farm.payload['longitude'])).quantize(Decimal('.01'))
        row=Product(farmer_id=u.id,district=p.district or farm.payload['district'],area=p.area or farm.payload.get('location_name',''),latitude=lat,longitude=lon,**data)
        db.add(row);db.flush();s.audit(db,u,'product.created','product',row.id);return s.product_view(db,row,u)

@router.get('/market/products/{id}')
def product_detail(id:str,user:Maybe):
    with s.transaction() as db:s.tick(db);return s.product_view(db,get_product(db,id,user),user)
@router.patch('/market/products/{id}')
def edit_product(id:str,body:ProductPatch,user:Who):
    with s.transaction() as db:
        p=owner_product(db,id,user);updates=body.model_dump(exclude_unset=True);expected=updates.pop('expected_version')
        if expected!=p.version:s.fail(409,'Listing changed. Reload it before editing stock or terms.')
        if updates.get('status',p.status)!='published':
            active=db.scalar(select(Auction).where(Auction.product_id==id,Auction.state.in_(['scheduled','live','awarded']),Auction.reserved.is_(True)))
            if active and db.scalar(select(Bid.id).where(Bid.auction_id==active.id).limit(1)):s.fail(409,'An auction with bids requires administrator review before hiding or archiving this listing')
        committed=db.scalar(select(func.count()).select_from(OrderItem).where(OrderItem.product_id==id)) or db.scalar(select(func.count()).select_from(Auction).where(Auction.product_id==id))
        if committed and any(k in updates and updates[k]!=getattr(p,k) for k in ['farm_id','unit','quantity_step']):s.fail(409,'Unit, quantity step and farm are locked after an order/auction. Archive and create a new listing.')
        merged={k:getattr(p,k) for k in ProductCreate.model_fields};merged.update(updates)
        try:validated=ProductCreate.model_validate(merged)
        except ValidationError as exc:s.fail(422,str(exc))
        validate_farm(db,validated.farm_id,user)
        if validated.status=='published' and s.policy(db)['require_verified_farmer'] and s.profile(db,user).verification_status!='verified':s.fail(403,'Verified farmer required')
        for k in updates:
            value=getattr(validated,k);setattr(p,k,value.isoformat() if k in ['harvest_date','available_from'] and value is not None else value)
        p.version+=1;p.updated_at=s.stamp(s.clock());s.tick(db);s.audit(db,user,'product.updated','product',p.id);db.flush();return s.product_view(db,p,user)

@router.post('/market/products/{id}/images')
def add_image(id:str,user:Who,image:Annotated[UploadFile,File()]):
    filename=uuid4().hex+'.jpg';path=IMAGE_ROOT/filename
    try:
        with s.transaction() as db:
            p=owner_product(db,id,user);s.rate(db,user,'product.image_uploaded',30)
            if db.scalar(select(func.count()).select_from(ProductImage).where(ProductImage.product_id==id))>=6:s.fail(422,'Maximum6 photos per listing')
            if Path(image.filename or '').suffix.lower() not in ['.jpg','.jpeg','.png','.webp']:s.fail(415,'Use JPG, PNG or WebP')
            data=image.file.read(8*1024*1024+1)
            if len(data)>8*1024*1024:s.fail(413,'Maximum image size is8MB')
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error',Image.DecompressionBombWarning)
                    source=Image.open(io.BytesIO(data))
                    if source.format not in ['JPEG','PNG','WEBP'] or getattr(source,'n_frames',1)!=1 or source.width*source.height>20_000_000:raise ValueError()
                    source.verify();source=ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGBA')
                    rgb=Image.new('RGB',source.size,'white');rgb.paste(source,mask=source.getchannel('A'));rgb.thumbnail((1600,1600));rgb.save(path,'JPEG',quality=88)
            except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombWarning,Image.DecompressionBombError):s.fail(415,'Invalid image, animation or excessive dimensions')
            row=ProductImage(product_id=id,filename=filename);db.add(row);db.flush();s.audit(db,user,'product.image_uploaded','product',id);return {'id':row.id,'url':f'/api/v1/market/products/{id}/images/{row.id}'}
    except Exception:path.unlink(missing_ok=True);raise
@router.get('/market/products/{id}/images/{image_id}')
def image(id:str,image_id:str,user:Maybe):
    with s.transaction() as db:
        row=db.get(ProductImage,image_id);p=db.get(Product,id)
        history=False
        if user and p:
            history=bool(db.scalar(select(OrderItem.id).join(SellerOrder,SellerOrder.id==OrderItem.seller_order_id).join(Order,Order.id==SellerOrder.order_id).where(OrderItem.product_id==id,Order.customer_id==user.id).limit(1)))
        if not row or row.product_id!=id or not p or not(s.can_view(db,p,user) or history):s.fail(404,'Image not found')
        path=IMAGE_ROOT/Path(row.filename).name
        if not path.is_file():s.fail(410,'Photo is no longer available')
        return Response(path.read_bytes(),media_type='image/jpeg')
@router.delete('/market/products/{id}/images/{image_id}')
def remove_image(id:str,image_id:str,user:Who):
    with s.transaction() as db:
        owner_product(db,id,user);row=db.get(ProductImage,image_id)
        if not row or row.product_id!=id:s.fail(404,'Image not found')
        filename=row.filename;db.delete(row);s.audit(db,user,'product.image_deleted','product',id)
    (IMAGE_ROOT/Path(filename).name).unlink(missing_ok=True);return {'ok':True}

@router.get('/market/cart')
def cart(user:Who):
    with s.transaction() as db:s.actor(db,user,['customer']);s.tick(db);return s.cart_view(db,user)
@router.post('/market/cart/items')
def add_cart(body:CartCommand,user:Who):
    with s.transaction() as db:
        s.actor(db,user,['customer']);s.enabled(db);s.tick(db);p=get_product(db,body.product_id,user)
        if not s.listing_eligible(db,p):s.fail(409,'Listing unavailable')
        s.check_quantity(p,body.quantity)
        row=db.scalar(select(CartItem).where(CartItem.customer_id==user.id,CartItem.product_id==p.id))
        if row:row.quantity=body.quantity
        else:
            if db.scalar(select(func.count()).select_from(CartItem).where(CartItem.customer_id==user.id))>=50:s.fail(422,'Cart limit is50 items')
            db.add(CartItem(customer_id=user.id,product_id=p.id,quantity=body.quantity))
        db.flush();return s.cart_view(db,user)
@router.patch('/market/cart/items/{id}')
def edit_cart(id:str,body:QuantityPatch,user:Who):
    with s.transaction() as db:
        s.actor(db,user,['customer']);row=s.owned(db,CartItem,id,user,'customer_id');p=get_product(db,row.product_id,user);s.check_quantity(p,body.quantity);row.quantity=body.quantity;db.flush();return s.cart_view(db,user)
@router.delete('/market/cart/items/{id}')
def remove_cart(id:str,user:Who):
    with s.transaction() as db:s.actor(db,user,['customer']);db.delete(s.owned(db,CartItem,id,user,'customer_id'));return {'ok':True}

@router.post('/market/orders')
def checkout(body:Checkout,user:Who,idempotency_key:Idem=None):
    with s.transaction() as db:
        u=s.actor(db,user,['customer']);s.enabled(db);s.tick(db)
        def run():
            s.rate(db,u,'order.created',10);cart=s.cart_view(db,u)
            if body.quote_hash!=cart['quote_hash']:s.fail(409,'Cart price, stock or terms changed. Review the updated quote before checkout.')
            if not cart['items']:s.fail(422,'Your cart is empty')
            if set(body.fulfillment)!=set(i['product_id'] for i in cart['items']):s.fail(422,'Choose fulfillment for every cart product')
            a=s.owned(db,Address,body.address_id,u,'user_id');lines=[]
            for item in cart['items']:
                p=db.get(Product,item['product_id']);quantity=Decimal(item['quantity']);lines.append((p,quantity,s.money(p.price_bdt*quantity)))
            result=s.create_order(db,u,a,lines,body.fulfillment);db.execute(delete(CartItem).where(CartItem.customer_id==u.id));return result
        return s.idempotent(db,u,'checkout',idempotency_key,body.model_dump(mode='json'),run)
@router.get('/market/orders')
def orders(user:Who,offset:int=0,limit:int=20):
    with s.transaction() as db:
        s.tick(db);u=s.actor(db,user);query=select(Order).order_by(Order.created_at.desc())
        if u.role=='customer':query=query.where(Order.customer_id==u.id)
        elif u.role=='farmer':query=query.where(Order.id.in_(select(SellerOrder.order_id).where(SellerOrder.farmer_id==u.id)))
        return s.paginate([s.order_view(db,o,u) for o in db.scalars(query)],offset,limit)
@router.get('/market/orders/{id}')
def order_detail(id:str,user:Who):
    with s.transaction() as db:
        s.tick(db);o=db.get(Order,id)
        if not o:s.fail(404,'Order not found')
        return s.order_view(db,o,user)
@router.post('/market/orders/{id}/cancel')
def cancel_order(id:str,body:Reason,user:Who):
    with s.transaction() as db:
        s.actor(db,user,['customer']);s.tick(db);o=s.owned(db,Order,id,user,'customer_id');rows=list(db.scalars(select(SellerOrder).where(SellerOrder.order_id==id)))
        if any(row.status not in ['pending','cancelled'] for row in rows):s.fail(409,'Seller already accepted part of this order. Open a dispute for later cancellation.')
        for row in rows:s.cancel_seller_order(db,row,user,body.reason)
        db.flush();return s.order_view(db,o,user)
@router.patch('/market/seller-orders/{id}')
def fulfill(id:str,body:SellerUpdate,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['farmer','admin']);s.tick(db);row=db.get(SellerOrder,id)
        if not row or u.role!='admin' and row.farmer_id!=u.id:s.fail(404,'Seller order not found')
        if body.status=='cancelled':
            if not body.reason.strip():s.fail(422,'Supply a cancellation reason')
            s.cancel_seller_order(db,row,u,body.reason)
        else:
            transitions={'pending':'confirmed','confirmed':'preparing','preparing':'ready_for_pickup' if row.fulfillment=='pickup' else 'out_for_delivery','ready_for_pickup':'delivered','out_for_delivery':'delivered'}
            if transitions.get(row.status)!=body.status:s.fail(409,'Invalid fulfillment status transition')
            if body.cash_received and body.status!='delivered':s.fail(422,'Record cash only with delivered fulfillment')
            row.status=body.status;row.expires_at=s.stamp(s.clock()+timedelta(days=7)) if row.status=='ready_for_pickup' else None;row.updated_at=s.stamp(s.clock())
            if body.cash_received:
                row.payment_status='cash_recorded';db.add(PaymentRecord(seller_order_id=id,actor_id=u.id,status='cash_recorded',amount_bdt=row.total_bdt))
            o=db.get(Order,row.order_id);s.notify(db,o.customer_id,'Order '+body.status.replace('_',' '),'order',o.id);s.audit(db,u,'order.status_changed','seller_order',id,status=row.status,cash_reported=body.cash_received)
        db.flush();return s.order_view(db,db.get(Order,row.order_id),u)

def reserve(db,a,p):
    s.check_quantity(p,a.lot_quantity,moq=False)
    minimum=p.minimum_order_quantity or p.quantity_step
    if p.stock_quantity-a.lot_quantity<minimum:s.fail(422,'Keep enough fixed-price stock for at least one ordinary order; the auction cannot consume all stock')
    p.stock_quantity-=a.lot_quantity;p.auction_reserved+=a.lot_quantity;p.version+=1;a.reserved=True
@router.post('/market/auctions')
def create_auction(body:AuctionCreate,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['farmer']);s.enabled(db);s.tick(db);p=owner_product(db,body.product_id,u)
        if not s.listing_eligible(db,p):s.fail(422,'Publish an eligible fixed-price listing before adding an auction')
        if body.ends_at<=s.clock() or body.ends_at<=body.starts_at or body.ends_at-body.starts_at>timedelta(days=30):s.fail(422,'Auction must end in the future, after its start, within30days')
        if db.scalar(select(Auction.id).where(Auction.product_id==p.id,or_(Auction.state.in_(['draft','scheduled','live']), (Auction.state=='awarded') & Auction.reserved.is_(True)))):s.fail(409,'This product already has an active/draft auction')
        a=Auction(product_id=p.id,farmer_id=u.id,lot_quantity=body.lot_quantity,starting_bid_bdt=body.starting_bid_bdt,minimum_increment_bdt=body.minimum_increment_bdt,reserve_price_bdt=body.reserve_price_bdt,starts_at=s.stamp(body.starts_at),ends_at=s.stamp(body.ends_at),state='draft' if body.draft else 'scheduled' if body.starts_at>s.clock() else 'live')
        if not body.draft:reserve(db,a,p)
        db.add(a);db.flush();s.audit(db,u,'auction.created','auction',a.id);return s.auction_view(db,a,u)
@router.post('/market/auctions/{id}/publish')
def publish_auction(id:str,user:Who):
    with s.transaction() as db:
        s.actor(db,user,['farmer']);a=s.owned(db,Auction,id,user,'farmer_id');p=db.get(Product,a.product_id)
        if a.state!='draft' or a.ends_at<=s.stamp(s.clock()) or not s.listing_eligible(db,p):s.fail(409,'Draft auction cannot be activated')
        reserve(db,a,p);a.state='scheduled' if a.starts_at>s.stamp(s.clock()) else 'live';db.flush();s.audit(db,user,'auction.published','auction',id);return s.auction_view(db,a,user)
@router.patch('/market/auctions/{id}')
def edit_auction(id:str,body:AuctionCreate,user:Who):
    with s.transaction() as db:
        s.actor(db,user,['farmer']);a=s.owned(db,Auction,id,user,'farmer_id')
        if a.state!='draft' or body.product_id!=a.product_id:s.fail(409,'Only draft auction terms can be edited; its product cannot change')
        if body.ends_at<=s.clock() or body.ends_at<=body.starts_at:s.fail(422,'Invalid auction times')
        for k in ['lot_quantity','starting_bid_bdt','minimum_increment_bdt','reserve_price_bdt']:setattr(a,k,getattr(body,k))
        a.starts_at=s.stamp(body.starts_at);a.ends_at=s.stamp(body.ends_at);s.audit(db,user,'auction.edited','auction',id);return s.auction_view(db,a,user)
@router.get('/market/auctions')
def auctions(user:Maybe,offset:int=0,limit:int=20):
    with s.transaction() as db:
        s.tick(db);rows=[a for a in db.scalars(select(Auction).order_by(Auction.created_at.desc())) if a.state!='draft' and s.can_view(db,db.get(Product,a.product_id),user)]
        return s.paginate([s.auction_view(db,a,user) for a in rows],offset,limit)
@router.get('/market/auctions/{id}')
def auction_detail(id:str,user:Maybe):
    with s.transaction() as db:s.tick(db);return s.auction_view(db,get_auction(db,id,user),user)
@router.post('/market/auctions/{id}/settle')
def settle_auction(id:str,user:Who):
    with s.transaction() as db:s.actor(db,user);s.tick(db);return s.auction_view(db,get_auction(db,id,user),user)
@router.post('/market/auctions/{id}/cancel')
def cancel_auction(id:str,body:Reason,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['farmer','admin']);s.tick(db);a=db.get(Auction,id)
        if not a or u.role!='admin' and a.farmer_id!=u.id:s.fail(404,'Auction not found')
        if not a.reserved and a.state!='draft' or a.state not in ['draft','scheduled','live','awarded']:s.fail(409,'Auction can no longer be cancelled')
        if u.role!='admin' and db.scalar(select(Bid.id).where(Bid.auction_id==id).limit(1)):s.fail(409,'An auction with bids requires administrator review')
        a.state='cancelled';s.release_auction(db,a);s.audit(db,u,'auction.cancelled','auction',id,reason=body.reason)
        for bidder in set(db.scalars(select(Bid.customer_id).where(Bid.auction_id==id))):s.notify(db,bidder,'Auction cancelled','auction',id,body.reason)
        db.flush();return s.auction_view(db,a,u)
class BidCommand(Command):
    amount_bdt:PositiveMoney
    confirm:bool
@router.post('/market/auctions/{id}/bids')
def bid(id:str,body:BidCommand,user:Who,idempotency_key:Idem=None):
    with s.transaction() as db:
        u=s.actor(db,user,['customer']);s.enabled(db);s.tick(db)
        def run():
            a=get_auction(db,id,u)
            if not body.confirm:s.fail(422,'Explicitly confirm your bid')
            if a.farmer_id==u.id:s.fail(403,'Self-bidding is forbidden')
            if a.state!='live' or not a.reserved or not a.starts_at<=s.stamp(s.clock())<a.ends_at:s.fail(409,'Auction is not accepting bids')
            p=db.get(Product,a.product_id)
            if not s.listing_eligible(db,p):s.fail(409,'Listing unavailable')
            minimum=a.highest_bid_bdt+a.minimum_increment_bdt if a.highest_bid_bdt is not None else a.starting_bid_bdt
            if body.amount_bdt<minimum:s.fail(422,'Bid must be at least BDT'+s.m(minimum))
            s.rate(db,u,'auction.bid',s.policy(db)['max_bids_per_minute'])
            previous=db.scalar(select(Bid).join(User,User.id==Bid.customer_id).where(Bid.auction_id==id,User.is_active.is_(True)).order_by(Bid.amount_bdt.desc()).limit(1))
            if previous and previous.customer_id==u.id:s.fail(409,'You already hold the highest bid')
            row=Bid(auction_id=id,customer_id=u.id,amount_bdt=body.amount_bdt);db.add(row);a.highest_bid_bdt=body.amount_bdt
            if previous:s.notify(db,previous.customer_id,'You were outbid','auction',id)
            s.audit(db,u,'auction.bid','auction',id,amount_bdt=s.m(body.amount_bdt));db.flush();return s.auction_view(db,a,u)
        return s.idempotent(db,u,'bid:'+id,idempotency_key,body.model_dump(mode='json'),run)
class WinnerCommand(Command):
    address_id:str
    fulfillment:Literal['pickup','delivery']
@router.post('/market/auctions/{id}/confirm')
def confirm_lot(id:str,body:WinnerCommand,user:Who,idempotency_key:Idem=None):
    with s.transaction() as db:
        u=s.actor(db,user,['customer']);s.enabled(db);s.tick(db)
        def run():
            a=get_auction(db,id,u)
            if a.state!='awarded' or not a.reserved or a.winner_id!=u.id or a.confirmation_deadline<=s.stamp(s.clock()):s.fail(409,'Only the eligible winner can confirm before the deadline')
            address=s.owned(db,Address,body.address_id,u,'user_id');p=db.get(Product,a.product_id)
            return s.create_order(db,u,address,[(p,a.lot_quantity,a.highest_bid_bdt)],{p.id:body.fulfillment},auction=a)
        return s.idempotent(db,u,'winner:'+id,idempotency_key,body.model_dump(mode='json'),run)

@router.get('/market/favorites')
def favorites(user:Who):
    with s.transaction() as db:
        s.actor(db,user,['customer']);rows=db.scalars(select(Product).join(Favorite,Favorite.product_id==Product.id).where(Favorite.customer_id==user.id))
        return [s.product_view(db,p,user) for p in rows if s.can_view(db,p,user)]
@router.post('/market/favorites/{id}')
def favorite(id:str,user:Who):
    with s.transaction() as db:
        s.actor(db,user,['customer']);get_product(db,id,user)
        if not db.get(Favorite,(user.id,id)):db.add(Favorite(customer_id=user.id,product_id=id))
        return {'ok':True}
@router.delete('/market/favorites/{id}')
def unfavorite(id:str,user:Who):
    with s.transaction() as db:
        s.actor(db,user,['customer']);row=db.get(Favorite,(user.id,id))
        if row:db.delete(row)
        return {'ok':True}
@router.get('/market/notifications')
def market_notifications(user:Who):
    with s.transaction() as db:
        s.actor(db,user);return [{k:getattr(n,k) for k in ['id','title','message','entity_type','entity_id','read','created_at']} for n in db.scalars(select(Notification).where(Notification.user_id==user.id).order_by(Notification.created_at.desc()).limit(100))]
class ReadNotification(Command):read:bool=True
@router.patch('/market/notifications/{id}')
def read_market_notification(id:str,body:ReadNotification,user:Who):
    with s.transaction() as db:
        s.actor(db,user);row=s.owned(db,Notification,id,user,'user_id');row.read=body.read;return {'ok':True}
@router.post('/market/reports')
def report_market(body:ReportCommand,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user);s.rate(db,u,'report.created',5)
        if body.product_id:get_product(db,body.product_id,u)
        else:
            order=db.get(Order,body.order_id)
            if not order:s.fail(404,'Order not found')
            s.order_view(db,order,u)
        report=Report(reporter_id=u.id,**body.model_dump());db.add(report);db.flush();s.audit(db,u,'report.created','report',report.id)
        for admin in db.scalars(select(User).where(User.role=='admin',User.is_active.is_(True))):s.notify(db,admin.id,'Marketplace report submitted','report',report.id)
        return {'id':report.id,'status':report.status,'notice':'Recorded for an administrator; no external agency has been contacted.'}
@router.post('/market/reviews')
def add_review(body:ReviewCommand,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['customer']);so=db.get(SellerOrder,body.seller_order_id);o=db.get(Order,so.order_id) if so else None
        if not so or not o or o.customer_id!=u.id:s.fail(404,'Order not found')
        if so.status!='delivered' or not db.scalar(select(OrderItem.id).where(OrderItem.seller_order_id==so.id,OrderItem.product_id==body.product_id)):s.fail(422,'Review only an item from your delivered order')
        if db.scalar(select(Review.id).where(Review.customer_id==u.id,Review.product_id==body.product_id,Review.seller_order_id==so.id)):s.fail(409,'This delivered item already has your review')
        row=Review(customer_id=u.id,**body.model_dump());db.add(row);db.flush();s.audit(db,u,'review.created','review',row.id);return {'id':row.id,'rating':row.rating,'comment':row.comment}
@router.get('/market/products/{id}/reviews')
def reviews(id:str,user:Maybe,offset:int=0,limit:int=20):
    with s.transaction() as db:
        get_product(db,id,user);rows=db.scalars(select(Review).where(Review.product_id==id).order_by(Review.created_at.desc()))
        return s.paginate([{'id':r.id,'rating':r.rating,'comment':r.comment,'created_at':r.created_at,'reviewer':'Verified purchase (user-reported fulfillment)'} for r in rows],offset,limit)

def seller_orders(db,u):
    query=select(Order).where(Order.id.in_(select(SellerOrder.order_id).where(SellerOrder.farmer_id==u.id))).order_by(Order.created_at.desc())
    return [s.order_view(db,o,u) for o in db.scalars(query)]
@router.get('/market/farmer/dashboard')
def farmer_dashboard(user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['farmer']);s.tick(db);ps=list(db.scalars(select(Product).where(Product.farmer_id==u.id).order_by(Product.created_at.desc())))
        os=seller_orders(db,u);au=list(db.scalars(select(Auction).where(Auction.farmer_id==u.id).order_by(Auction.created_at.desc())))
        sales=list(db.scalars(select(SellerOrder).where(SellerOrder.farmer_id==u.id)))
        return {'profile':s.profile_view(s.profile(db,u),u),'products':[s.product_view(db,p,u) for p in ps],'orders':os,'auctions':[s.auction_view(db,a,u) for a in au],
            'notifications':market_notification_views(db,u),'sales':{'booked_bdt':s.m(sum((o.total_bdt for o in sales if o.status!='cancelled'),Decimal(0))),'delivered_bdt':s.m(sum((o.total_bdt for o in sales if o.status=='delivered'),Decimal(0)))},'counts':{'products':len(ps),'orders':len(os),'auctions':len(au)}}
def market_notification_views(db,u):
    return [{k:getattr(n,k) for k in ['id','title','message','entity_type','entity_id','read','created_at']} for n in db.scalars(select(Notification).where(Notification.user_id==u.id).order_by(Notification.created_at.desc()).limit(100))]
@router.get('/market/customer/dashboard')
def customer_dashboard(user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['customer']);s.tick(db);os=list(db.scalars(select(Order).where(Order.customer_id==u.id).order_by(Order.created_at.desc())))
        bs=list(db.scalars(select(Bid).where(Bid.customer_id==u.id).order_by(Bid.created_at.desc())));wins=list(db.scalars(select(Auction).where(Auction.winner_id==u.id,Auction.state=='awarded',Auction.reserved.is_(True))))
        fs=list(db.scalars(select(Product).join(Favorite,Favorite.product_id==Product.id).where(Favorite.customer_id==u.id)))
        return {'profile':s.profile_view(s.profile(db,u),u),'orders':[s.order_view(db,o,u) for o in os],
            'bids':[{'id':b.id,'auction_id':b.auction_id,'amount_bdt':s.m(b.amount_bdt),'created_at':b.created_at,'auction':s.auction_view(db,db.get(Auction,b.auction_id),u)} for b in bs[:100]],
            'winning_auctions':[s.auction_view(db,a,u) for a in wins],'favorites':[s.product_view(db,p,u) for p in fs if s.can_view(db,p,u)],'notifications':market_notification_views(db,u),'counts':{'orders':len(os),'bids':len(bs),'favorites':len(fs)}}

class UserModeration(Command):
    is_active:bool
    reason:str=Field(min_length=3,max_length=1000)
class FarmerVerification(Command):
    verification_status:Literal['unverified','pending','verified','rejected']
    reason:str=Field(min_length=3,max_length=1000)
class ProductModeration(Command):
    moderation_status:Literal['visible','hidden']
    reason:str=Field(min_length=3,max_length=1000)
class ResolveReport(Command):
    status:Literal['resolved','dismissed']
    admin_note:str=Field(min_length=3,max_length=1000)
@router.patch('/admin/market/users/{id}')
def moderate_user(id:str,body:UserModeration,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['admin']);target=db.get(User,id)
        if not target:s.fail(404,'User not found')
        if not body.is_active and target.role=='admin' and db.scalar(select(func.count()).select_from(User).where(User.role=='admin',User.is_active.is_(True)))<=1:s.fail(409,'Cannot suspend the last active administrator')
        target.is_active=body.is_active
        if not target.is_active:db.execute(delete(Token).where(Token.user_id==id))
        s.tick(db);s.audit(db,u,'user.moderated','user',id,is_active=body.is_active,reason=body.reason);return user_view(target)
@router.patch('/admin/market/farmers/{id}')
def verify_farmer(id:str,body:FarmerVerification,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['admin']);target=db.get(User,id)
        if not target or target.role!='farmer':s.fail(404,'Farmer not found')
        row=s.profile(db,target);row.verification_status=body.verification_status;s.audit(db,u,'farmer.verification_changed','user',id,status=body.verification_status,reason=body.reason);s.notify(db,id,'Farmer verification updated','profile',id,body.reason);return s.profile_view(row)
@router.patch('/admin/market/products/{id}')
def moderate_product(id:str,body:ProductModeration,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['admin']);p=db.get(Product,id)
        if not p:s.fail(404,'Product not found')
        p.moderation_status=body.moderation_status;p.version+=1;s.tick(db);s.audit(db,u,'product.moderated','product',id,status=body.moderation_status,reason=body.reason);s.notify(db,p.farmer_id,'Listing moderation updated','product',id,body.reason);return s.product_view(db,p,u)
@router.patch('/admin/market/reports/{id}')
def resolve_report(id:str,body:ResolveReport,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['admin']);r=db.get(Report,id)
        if not r:s.fail(404,'Report not found')
        r.status=body.status;r.admin_note=body.admin_note;s.audit(db,u,'report.resolved','report',id,status=body.status);s.notify(db,r.reporter_id,'Report reviewed','report',id,body.admin_note);return {'id':id,'status':r.status,'admin_note':r.admin_note}
@router.get('/admin/market/policy')
def get_policy(user:Who):
    with s.transaction() as db:s.actor(db,user,['admin']);return s.policy(db)
@router.patch('/admin/market/policy')
def edit_policy(body:PolicyPatch,user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['admin']);changes=body.model_dump(exclude_unset=True);value={**s.policy(db),**changes};row=db.get(Policy,'settings')
        if row:row.value=value
        else:db.add(Policy(key='settings',value=value))
        s.audit(db,u,'policy.updated','policy','settings',fields=list(changes));return value
@router.get('/admin/market/dashboard')
def admin_dashboard(user:Who):
    with s.transaction() as db:
        u=s.actor(db,user,['admin']);s.tick(db);users=list(db.scalars(select(User).order_by(User.name)));products=list(db.scalars(select(Product).order_by(Product.created_at.desc())));os=list(db.scalars(select(Order).order_by(Order.created_at.desc())));so=list(db.scalars(select(SellerOrder)))
        return {'users':[{**user_view(x),'verification_status':db.get(Profile,x.id).verification_status if db.get(Profile,x.id) else 'unverified'} for x in users],
            'products':[s.product_view(db,p,u) for p in products[:100]],'orders':[s.order_view(db,o,u) for o in os[:100]],
            'auctions':[s.auction_view(db,a,u) for a in db.scalars(select(Auction).order_by(Auction.created_at.desc()).limit(100))],
            'reports':[{k:getattr(r,k) for k in ['id','product_id','order_id','reason','status','admin_note','created_at']} for r in db.scalars(select(Report).order_by(Report.created_at.desc()).limit(100))],
            'audit':[{k:getattr(a,k) for k in ['id','actor_id','event','entity_type','entity_id','details','created_at']} for a in db.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(100))],
            'analytics':{'user_count':len(users),'product_count':len(products),'order_count':len(os),'booked_bdt':s.m(sum((x.total_bdt for x in so if x.status!='cancelled'),Decimal(0))),'delivered_bdt':s.m(sum((x.total_bdt for x in so if x.status=='delivered'),Decimal(0)))},'policy':s.policy(db)}

@router.get('/admin/market/{collection}')
def admin_collection(collection:Literal['users','products','orders','auctions','reports','audit'],user:Who,offset:int=Query(default=0,ge=0),limit:int=Query(default=20,ge=1,le=100)):
    with s.transaction() as db:
        u=s.actor(db,user,['admin']);s.tick(db)
        model={'users':User,'products':Product,'orders':Order,'auctions':Auction,'reports':Report,'audit':Audit}[collection]
        query=select(model).order_by(model.name if model is User else model.created_at.desc())
        count=db.scalar(select(func.count()).select_from(model));rows=list(db.scalars(query.offset(offset).limit(limit)))
        def serialize(row):
            if model is User:return {**user_view(row),'verification_status':db.get(Profile,row.id).verification_status if db.get(Profile,row.id) else 'unverified'}
            if model is Product:return s.product_view(db,row,u)
            if model is Order:return s.order_view(db,row,u)
            if model is Auction:return s.auction_view(db,row,u)
            fields=['id','product_id','order_id','reason','status','admin_note','created_at'] if model is Report else ['id','actor_id','event','entity_type','entity_id','details','created_at']
            return {k:getattr(row,k) for k in fields}
        return {'items':[serialize(row) for row in rows],'total':count,'offset':offset,'limit':limit,'has_more':offset+limit<count}

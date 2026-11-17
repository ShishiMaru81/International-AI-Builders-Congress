"""Owner exports and account erasure without destroying commerce audit history."""
from pathlib import Path
from sqlalchemy import delete,func,or_,select
from .db import Reading,Record,Token,User
from .market_models import Address,Auction,Audit,Bid,CartItem,Favorite,Idempotency,Notification,Order,Product,ProductImage,Profile,Report,SellerOrder
from . import market_service as s

def owner_export(user):
    with s.transaction() as db:
        own=db.get(User,user.id);p=db.get(Profile,user.id)
        os=db.scalars(select(Order).where(or_(Order.customer_id==user.id,Order.id.in_(select(SellerOrder.order_id).where(SellerOrder.farmer_id==user.id)))))
        return {'profile':s.profile_view(p,own) if p else None,'addresses':[s.address_view(a) for a in db.scalars(select(Address).where(Address.user_id==user.id))],
            'products':[s.product_view(db,p,own) for p in db.scalars(select(Product).where(Product.farmer_id==user.id))],
            'orders':[s.order_view(db,o,own) for o in os],
            'bids':[{'id':b.id,'auction_id':b.auction_id,'amount_bdt':s.m(b.amount_bdt),'created_at':b.created_at} for b in db.scalars(select(Bid).where(Bid.customer_id==user.id))],
            'notice':'Image binaries are separate authorized downloads. Bid/order audit history is retained with opaque IDs after account erasure.'}

def erase_account(user,storage:Path):
    files=[]
    with s.transaction() as db:
        u=s.actor(db,user);s.tick(db)
        if u.role=='admin' and db.scalar(select(func.count()).select_from(User).where(User.role=='admin',User.is_active.is_(True)))<=1:s.fail(409,'Cannot delete the last active administrator')
        open_orders=db.scalar(select(SellerOrder.id).join(Order,Order.id==SellerOrder.order_id).where(or_(SellerOrder.farmer_id==u.id,Order.customer_id==u.id),SellerOrder.status.not_in(['delivered','cancelled'])).limit(1))
        commitments=db.scalar(select(Auction.id).where(Auction.state.in_(['scheduled','live','awarded']),Auction.reserved.is_(True),or_(Auction.farmer_id==u.id,Auction.winner_id==u.id,Auction.id.in_(select(Bid.auction_id).where(Bid.customer_id==u.id)))).limit(1))
        if open_orders or commitments:s.fail(409,'Resolve open orders and auction commitments before deleting this account. No data has been deleted.')
        for case in db.scalars(select(Record).where(Record.owner_id==u.id,Record.kind=='case')):
            filename=case.payload.get('image_file')
            if filename:files.append(storage/Path(filename).name)
        for p in db.scalars(select(Product).where(Product.farmer_id==u.id)):
            p.status='archived';p.description='';p.pickup_instructions='';p.latitude=None;p.longitude=None;p.version+=1
            for image in db.scalars(select(ProductImage).where(ProductImage.product_id==p.id)):
                files.append(storage/'marketplace'/Path(image.filename).name);db.delete(image)
        for so in db.scalars(select(SellerOrder).join(Order,Order.id==SellerOrder.order_id).where(Order.customer_id==u.id)):
            so.destination={'notice':'Customer contact/address removed following account deletion.'}
        for a in db.scalars(select(Auction).where(Auction.farmer_id==u.id,Auction.state=='draft')):a.state='cancelled'
        for cls,col in [(Address,Address.user_id),(CartItem,CartItem.customer_id),(Favorite,Favorite.customer_id),(Notification,Notification.user_id),(Idempotency,Idempotency.user_id)]:db.execute(delete(cls).where(col==u.id))
        p=db.get(Profile,u.id)
        if p:db.delete(p)
        for report in db.scalars(select(Report).where(Report.reporter_id==u.id)):report.reason='Reporter account deleted'
        devices=select(Record.id).where(Record.owner_id==u.id,Record.kind=='device')
        db.execute(delete(Reading).where(Reading.device_id.in_(devices)))
        # Detach farm references before removing original workspace records.
        farms=select(Record.id).where(Record.owner_id==u.id)
        for p in db.scalars(select(Product).where(Product.farm_id.in_(farms))):p.farm_id=None
        for so in db.scalars(select(SellerOrder).where(SellerOrder.farm_id.in_(farms))):so.farm_id=None
        db.execute(delete(Record).where(Record.owner_id==u.id));db.execute(delete(Token).where(Token.user_id==u.id))
        u.name='Deleted account';u.email=None;u.password_hash=None;u.preferences={};u.is_active=False
        s.audit(db,None,'account.erased','user',u.id)
    for path in files:path.unlink(missing_ok=True)
    return {'ok':True,'notice':'Profile/contact data removed. Closed order and immutable bid/audit history retain an anonymous identifier.'}

"""Relational marketplace state. Money/quantity use NUMERIC, never floats."""
from decimal import Decimal
from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base,now,uid

class Profile(Base):
    __tablename__='market_profiles'
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    public_name:Mapped[str]=mapped_column(String(100),default='')
    bio:Mapped[str]=mapped_column(String(1000),default='')
    district:Mapped[str]=mapped_column(String(80),default='')
    area:Mapped[str]=mapped_column(String(160),default='')
    latitude:Mapped[Decimal|None]=mapped_column(Numeric(8,2),nullable=True)
    longitude:Mapped[Decimal|None]=mapped_column(Numeric(8,2),nullable=True)
    phone:Mapped[str]=mapped_column(String(30),default='')
    verification_status:Mapped[str]=mapped_column(String(20),default='unverified')
    updated_at:Mapped[str]=mapped_column(String,default=now)

class Product(Base):
    __tablename__='market_products'
    __table_args__=(CheckConstraint('stock_quantity >= 0'),CheckConstraint('auction_reserved >= 0'),CheckConstraint('price_bdt > 0'),Index('ix_market_products_discovery','status','category','district'))
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    farmer_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    farm_id:Mapped[str|None]=mapped_column(ForeignKey('records.id',ondelete='SET NULL'),nullable=True,index=True)
    name:Mapped[str]=mapped_column(String(120))
    description:Mapped[str]=mapped_column(String(3000),default='')
    category:Mapped[str]=mapped_column(String(30))
    price_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))
    unit:Mapped[str]=mapped_column(String(15))
    quantity_step:Mapped[Decimal]=mapped_column(Numeric(18,3))
    stock_quantity:Mapped[Decimal]=mapped_column(Numeric(18,3))
    auction_reserved:Mapped[Decimal]=mapped_column(Numeric(18,3),default=Decimal(0))
    minimum_order_quantity:Mapped[Decimal|None]=mapped_column(Numeric(18,3),nullable=True)
    maximum_order_quantity:Mapped[Decimal|None]=mapped_column(Numeric(18,3),nullable=True)
    district:Mapped[str]=mapped_column(String(80))
    area:Mapped[str]=mapped_column(String(160),default='')
    latitude:Mapped[Decimal|None]=mapped_column(Numeric(8,2),nullable=True)
    longitude:Mapped[Decimal|None]=mapped_column(Numeric(8,2),nullable=True)
    pickup_enabled:Mapped[bool]=mapped_column(Boolean,default=True)
    delivery_enabled:Mapped[bool]=mapped_column(Boolean,default=False)
    nationwide_delivery:Mapped[bool]=mapped_column(Boolean,default=False)
    delivery_districts:Mapped[list]=mapped_column(JSON,default=list)
    delivery_fee_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2),default=Decimal(0))
    pickup_instructions:Mapped[str]=mapped_column(String(600),default='')
    harvest_date:Mapped[str|None]=mapped_column(String(10),nullable=True)
    available_from:Mapped[str|None]=mapped_column(String(10),nullable=True)
    status:Mapped[str]=mapped_column(String(20),default='draft',index=True)
    moderation_status:Mapped[str]=mapped_column(String(20),default='visible')
    version:Mapped[int]=mapped_column(Integer,default=1)
    created_at:Mapped[str]=mapped_column(String,default=now)
    updated_at:Mapped[str]=mapped_column(String,default=now)

class ProductImage(Base):
    __tablename__='market_product_images'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    product_id:Mapped[str]=mapped_column(ForeignKey('market_products.id'),index=True)
    filename:Mapped[str]=mapped_column(String,unique=True)
    created_at:Mapped[str]=mapped_column(String,default=now)

class Address(Base):
    __tablename__='market_addresses'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    name:Mapped[str]=mapped_column(String(100))
    phone:Mapped[str]=mapped_column(String(30))
    line1:Mapped[str]=mapped_column(String(400))
    district:Mapped[str]=mapped_column(String(80))
    area:Mapped[str]=mapped_column(String(160),default='')
    country:Mapped[str]=mapped_column(String(30),default='Bangladesh')
    latitude:Mapped[Decimal|None]=mapped_column(Numeric(9,5),nullable=True)
    longitude:Mapped[Decimal|None]=mapped_column(Numeric(9,5),nullable=True)
    created_at:Mapped[str]=mapped_column(String,default=now)

class CartItem(Base):
    __tablename__='market_cart_items'
    __table_args__=(UniqueConstraint('customer_id','product_id'),CheckConstraint('quantity > 0'))
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    customer_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    product_id:Mapped[str]=mapped_column(ForeignKey('market_products.id'))
    quantity:Mapped[Decimal]=mapped_column(Numeric(18,3))

class Auction(Base):
    __tablename__='market_auctions'
    __table_args__=(CheckConstraint('lot_quantity > 0'),CheckConstraint('minimum_increment_bdt > 0'),Index('ix_market_auctions_time','state','ends_at'))
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    product_id:Mapped[str]=mapped_column(ForeignKey('market_products.id'),index=True)
    farmer_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    lot_quantity:Mapped[Decimal]=mapped_column(Numeric(18,3))
    starting_bid_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))
    minimum_increment_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))
    reserve_price_bdt:Mapped[Decimal|None]=mapped_column(Numeric(18,2),nullable=True)
    highest_bid_bdt:Mapped[Decimal|None]=mapped_column(Numeric(18,2),nullable=True)
    winner_id:Mapped[str|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    starts_at:Mapped[str]=mapped_column(String)
    ends_at:Mapped[str]=mapped_column(String)
    confirmation_deadline:Mapped[str|None]=mapped_column(String,nullable=True)
    state:Mapped[str]=mapped_column(String(20))
    reserved:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[str]=mapped_column(String,default=now)

class Bid(Base):
    __tablename__='market_bids'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    auction_id:Mapped[str]=mapped_column(ForeignKey('market_auctions.id'),index=True)
    customer_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    amount_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))
    created_at:Mapped[str]=mapped_column(String,default=now,index=True)

class Order(Base):
    __tablename__='market_orders'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    customer_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    auction_id:Mapped[str|None]=mapped_column(ForeignKey('market_auctions.id'),nullable=True,unique=True)
    total_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))
    created_at:Mapped[str]=mapped_column(String,default=now)

class SellerOrder(Base):
    __tablename__='market_seller_orders'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    order_id:Mapped[str]=mapped_column(ForeignKey('market_orders.id'),index=True)
    farmer_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    farm_id:Mapped[str|None]=mapped_column(ForeignKey('records.id',ondelete='SET NULL'),nullable=True)
    fulfillment:Mapped[str]=mapped_column(String(15))
    status:Mapped[str]=mapped_column(String(25),default='pending')
    payment_status:Mapped[str]=mapped_column(String(25),default='demo_unpaid')
    subtotal_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))
    delivery_fee_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))
    total_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))
    destination:Mapped[dict]=mapped_column(JSON)
    expires_at:Mapped[str|None]=mapped_column(String,nullable=True,index=True)
    updated_at:Mapped[str]=mapped_column(String,default=now)

class OrderItem(Base):
    __tablename__='market_order_items'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    seller_order_id:Mapped[str]=mapped_column(ForeignKey('market_seller_orders.id'),index=True)
    product_id:Mapped[str]=mapped_column(ForeignKey('market_products.id'),index=True)
    name:Mapped[str]=mapped_column(String(120))
    unit:Mapped[str]=mapped_column(String(15))
    quantity:Mapped[Decimal]=mapped_column(Numeric(18,3))
    unit_price_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))
    line_total_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))

class PaymentRecord(Base):
    __tablename__='market_payments'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    seller_order_id:Mapped[str]=mapped_column(ForeignKey('market_seller_orders.id'),index=True)
    actor_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    status:Mapped[str]=mapped_column(String(25))
    amount_bdt:Mapped[Decimal]=mapped_column(Numeric(18,2))
    created_at:Mapped[str]=mapped_column(String,default=now)

class Notification(Base):
    __tablename__='market_notifications'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    title:Mapped[str]=mapped_column(String(140))
    message:Mapped[str]=mapped_column(String(700),default='')
    entity_type:Mapped[str]=mapped_column(String(30))
    entity_id:Mapped[str]=mapped_column(String)
    read:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[str]=mapped_column(String,default=now)

class Audit(Base):
    __tablename__='market_audit_logs'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    actor_id:Mapped[str|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    event:Mapped[str]=mapped_column(String(80),index=True)
    entity_type:Mapped[str]=mapped_column(String(30))
    entity_id:Mapped[str]=mapped_column(String)
    details:Mapped[dict]=mapped_column(JSON,default=dict)
    created_at:Mapped[str]=mapped_column(String,default=now,index=True)

class Favorite(Base):
    __tablename__='market_favorites'
    customer_id:Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    product_id:Mapped[str]=mapped_column(ForeignKey('market_products.id'),primary_key=True)

class Report(Base):
    __tablename__='market_reports'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    reporter_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    product_id:Mapped[str|None]=mapped_column(ForeignKey('market_products.id'),nullable=True)
    order_id:Mapped[str|None]=mapped_column(ForeignKey('market_orders.id'),nullable=True)
    reason:Mapped[str]=mapped_column(String(1000))
    status:Mapped[str]=mapped_column(String(20),default='open')
    admin_note:Mapped[str]=mapped_column(String(1000),default='')
    created_at:Mapped[str]=mapped_column(String,default=now)

class Review(Base):
    __tablename__='market_reviews'
    __table_args__=(UniqueConstraint('customer_id','product_id','seller_order_id'),CheckConstraint('rating >= 1 AND rating <= 5'))
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    customer_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    product_id:Mapped[str]=mapped_column(ForeignKey('market_products.id'),index=True)
    seller_order_id:Mapped[str]=mapped_column(ForeignKey('market_seller_orders.id'))
    rating:Mapped[int]=mapped_column(Integer)
    comment:Mapped[str]=mapped_column(String(1000),default='')
    created_at:Mapped[str]=mapped_column(String,default=now)

class Idempotency(Base):
    __tablename__='market_idempotency'
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    operation:Mapped[str]=mapped_column(String(100),primary_key=True)
    key:Mapped[str]=mapped_column(String(100),primary_key=True)
    fingerprint:Mapped[str]=mapped_column(String(64))
    response:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[str]=mapped_column(String,default=now)

class Policy(Base):
    __tablename__='market_policies'
    key:Mapped[str]=mapped_column(String,primary_key=True)
    value:Mapped[dict]=mapped_column(JSON)

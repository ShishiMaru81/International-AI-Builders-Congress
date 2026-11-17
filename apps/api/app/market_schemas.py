"""Validated marketplace commands. Decimal serialization is string-safe."""
from datetime import date
from decimal import Decimal
from typing import Annotated,Literal
from pydantic import AwareDatetime,BaseModel,ConfigDict,Field,model_validator

Money=Annotated[Decimal,Field(ge=0,le=Decimal('999999999'),max_digits=18,decimal_places=2)]
PositiveMoney=Annotated[Decimal,Field(gt=0,le=Decimal('999999999'),max_digits=18,decimal_places=2)]
Quantity=Annotated[Decimal,Field(gt=0,le=Decimal('999999999'),max_digits=18,decimal_places=3)]
Stock=Annotated[Decimal,Field(ge=0,le=Decimal('999999999'),max_digits=18,decimal_places=3)]
Unit=Literal['kg','g','piece','bundle','crate']
Category=Literal['vegetables','fruits','rice_grains','pulses','other']
Status=Literal['draft','published','paused','out_of_stock','archived']

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False,str_strip_whitespace=True)

class Location(Command):
    district:str=Field(min_length=1,max_length=80)
    area:str=Field(default='',max_length=160)
    latitude:Decimal|None=Field(default=None,ge=Decimal('20.4'),le=Decimal('26.7'))
    longitude:Decimal|None=Field(default=None,ge=Decimal('88'),le=Decimal('92.8'))
    @model_validator(mode='after')
    def coordinate_pair(self):
        if (self.latitude is None)!=(self.longitude is None):raise ValueError('Provide both coordinates or neither')
        return self

class ProfilePatch(Command):
    public_name:str|None=Field(default=None,min_length=1,max_length=100)
    bio:str|None=Field(default=None,max_length=1000)
    district:str|None=Field(default=None,min_length=1,max_length=80)
    area:str|None=Field(default=None,max_length=160)
    latitude:Decimal|None=Field(default=None,ge=Decimal('20.4'),le=Decimal('26.7'))
    longitude:Decimal|None=Field(default=None,ge=Decimal('88'),le=Decimal('92.8'))
    phone:str|None=Field(default=None,max_length=30)
    @model_validator(mode='before')
    @classmethod
    def required_nonnull(cls,data):
        if isinstance(data,dict) and any(k in data and data[k] is None for k in ['public_name','bio','district','area','phone']):raise ValueError('Profile text fields cannot be null')
        if isinstance(data,dict) and (('latitude' in data)!=('longitude' in data)):raise ValueError('Update or clear both coordinates together')
        if isinstance(data,dict) and (data.get('latitude') is None)!=(data.get('longitude') is None):raise ValueError('Provide both coordinates or neither')
        return data

class ProductCreate(Command):
    farm_id:str
    name:str=Field(min_length=1,max_length=120)
    category:Category
    description:str=Field(default='',max_length=3000)
    price_bdt:PositiveMoney
    unit:Unit
    quantity_step:Quantity=Decimal('1')
    stock_quantity:Stock
    minimum_order_quantity:Quantity|None=None
    maximum_order_quantity:Quantity|None=None
    pickup_enabled:bool=True
    delivery_enabled:bool=False
    nationwide_delivery:bool=False
    delivery_districts:list[Annotated[str,Field(min_length=1,max_length=80)]]=Field(default_factory=list,max_length=64)
    delivery_fee_bdt:Money=Decimal('0')
    pickup_instructions:str=Field(default='',max_length=600)
    harvest_date:date|None=None
    available_from:date|None=None
    status:Status='draft'
    @model_validator(mode='after')
    def coherent(self):
        if self.unit!='kg' and self.quantity_step!=self.quantity_step.to_integral_value():raise ValueError('This unit requires whole quantity increments')
        if not self.pickup_enabled and not self.delivery_enabled:raise ValueError('Enable pickup or delivery')
        if self.delivery_enabled and not self.nationwide_delivery and not self.delivery_districts:raise ValueError('Choose delivery districts or nationwide delivery')
        if self.minimum_order_quantity and self.maximum_order_quantity and self.maximum_order_quantity<self.minimum_order_quantity:raise ValueError('Maximum quantity is below MOQ')
        return self

class ProductPatch(Command):
    expected_version:int=Field(ge=1)
    # Merge then validate with ProductCreate, so explicit null and cross-field failures cannot poison state.
    name:str|None=None
    farm_id:str|None=None
    category:Category|None=None
    description:str|None=None
    price_bdt:PositiveMoney|None=None
    unit:Unit|None=None
    quantity_step:Quantity|None=None
    stock_quantity:Stock|None=None
    minimum_order_quantity:Quantity|None=None
    maximum_order_quantity:Quantity|None=None
    pickup_enabled:bool|None=None
    delivery_enabled:bool|None=None
    nationwide_delivery:bool|None=None
    delivery_districts:list[str]|None=None
    delivery_fee_bdt:Money|None=None
    pickup_instructions:str|None=None
    harvest_date:date|None=None
    available_from:date|None=None
    status:Status|None=None

class AddressCreate(Location):
    name:str=Field(min_length=1,max_length=100)
    phone:str=Field(min_length=5,max_length=30)
    line1:str=Field(min_length=1,max_length=400)
    country:Literal['Bangladesh']='Bangladesh'

class CartCommand(Command):
    product_id:str
    quantity:Quantity
class QuantityPatch(Command):
    quantity:Quantity
class Checkout(Command):
    address_id:str
    quote_hash:str=Field(min_length=1,max_length=64)
    fulfillment:dict[str,Literal['pickup','delivery']]
class Reason(Command):
    reason:str=Field(min_length=3,max_length=1000)
class SellerUpdate(Command):
    status:Literal['confirmed','preparing','ready_for_pickup','out_for_delivery','delivered','cancelled']
    reason:str=Field(default='',max_length=1000)
    cash_received:bool=False
class AuctionCreate(Command):
    product_id:str
    lot_quantity:Quantity
    starting_bid_bdt:PositiveMoney
    minimum_increment_bdt:PositiveMoney
    starts_at:AwareDatetime
    ends_at:AwareDatetime
    reserve_price_bdt:PositiveMoney|None=None
    draft:bool=False
    @model_validator(mode='after')
    def valid_times(self):
        if self.ends_at<=self.starts_at:raise ValueError('End must follow start')
        if (self.ends_at-self.starts_at).total_seconds()>30*86400:raise ValueError('Maximum auction duration is30 days')
        return self
class BidCommand(Command):
    amount_bdt:PositiveMoney
    confirm:Literal[True]
class AwardConfirmation(Command):
    address_id:str
    fulfillment:Literal['pickup','delivery']
class ReportCommand(Command):
    product_id:str|None=None
    order_id:str|None=None
    reason:str=Field(min_length=5,max_length=1000)
    @model_validator(mode='after')
    def target(self):
        if bool(self.product_id)==bool(self.order_id):raise ValueError('Report exactly one product or order')
        return self
class ReviewCommand(Command):
    product_id:str
    seller_order_id:str
    rating:int=Field(ge=1,le=5)
    comment:str=Field(default='',max_length=1000)
class AdminUser(Command):
    is_active:bool
    reason:str=Field(min_length=3,max_length=1000)
class Verification(Command):
    status:Literal['unverified','pending','verified','rejected']
    reason:str=Field(min_length=3,max_length=1000)
class Moderation(Command):
    hidden:bool
    reason:str=Field(min_length=3,max_length=1000)
class ReportResolution(Command):
    status:Literal['open','resolved','dismissed']
    admin_note:str=Field(min_length=3,max_length=1000)
class PolicyPatch(Command):
    marketplace_enabled:bool|None=None
    require_verified_farmer:bool|None=None
    max_bids_per_minute:int|None=Field(default=None,ge=1,le=60)
    winner_confirmation_hours:int|None=Field(default=None,ge=1,le=72)
    order_acceptance_hours:int|None=Field(default=None,ge=1,le=168)
    @model_validator(mode='before')
    @classmethod
    def no_nulls(cls,data):
        if isinstance(data,dict) and any(v is None for v in data.values()):raise ValueError('Policy values cannot be null')
        return data

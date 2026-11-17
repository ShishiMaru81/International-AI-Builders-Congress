"""Add marketplace tables without resetting existing workspace data."""
from alembic import op
from app.db import Base
from app import market_models
revision='0004'
down_revision='0003'
def upgrade():
    Base.metadata.create_all(op.get_bind(),tables=[t for t in Base.metadata.sorted_tables if t.name.startswith('market_')],checkfirst=True)
def downgrade():
    Base.metadata.drop_all(op.get_bind(),tables=[t for t in reversed(Base.metadata.sorted_tables) if t.name.startswith('market_')],checkfirst=True)

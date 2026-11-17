"""Initial owner-scoped, versioned domain records and sensor events."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
def upgrade():
    tables=set(sa.inspect(op.get_bind()).get_table_names())
    if 'users' not in tables:
        op.create_table('users',sa.Column('id',sa.String(),primary_key=True),sa.Column('name',sa.String(),nullable=False),sa.Column('preferences',sa.JSON(),nullable=False))
    if 'sessions' not in tables:
        op.create_table('sessions',sa.Column('id',sa.String(),primary_key=True),sa.Column('user_id',sa.String(),sa.ForeignKey('users.id'),nullable=False),sa.Column('expires',sa.String(),nullable=False))
    if 'records' not in tables:
        op.create_table('records',sa.Column('id',sa.String(),primary_key=True),sa.Column('owner_id',sa.String(),sa.ForeignKey('users.id'),nullable=False),sa.Column('kind',sa.String(),nullable=False),sa.Column('plot_id',sa.String()),sa.Column('created_at',sa.String(),nullable=False),sa.Column('payload',sa.JSON(),nullable=False))
    indexes={i['name'] for i in sa.inspect(op.get_bind()).get_indexes('records')}
    for col in ['owner_id','kind','plot_id']:
        if 'ix_records_'+col not in indexes:op.create_index('ix_records_'+col,'records',[col])
    if 'sensor_readings' not in tables:
        op.create_table('sensor_readings',sa.Column('id',sa.String(),primary_key=True),sa.Column('device_id',sa.String(),sa.ForeignKey('records.id'),nullable=False),sa.Column('event_id',sa.String(),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),sa.UniqueConstraint('device_id','event_id'))
def downgrade():
    for name in ['sensor_readings','records','sessions','users']:op.drop_table(name)

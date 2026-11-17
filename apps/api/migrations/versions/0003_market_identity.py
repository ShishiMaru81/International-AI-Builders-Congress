"""Add marketplace login fields; existing demo identities remain active farmers."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {c['name'] for c in inspector.get_columns('users')}
    for column in [
        sa.Column('email', sa.String(254), nullable=True),
        sa.Column('password_hash', sa.String(), nullable=True),
        sa.Column('role', sa.String(20), nullable=False, server_default='farmer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    ]:
        if column.name not in columns:
            op.add_column('users', column)
    unique_sets = [set(c['column_names']) for c in inspector.get_unique_constraints('users')]
    if {'email'} not in unique_sets and not any(i.get('unique') and i['column_names'] == ['email'] for i in inspector.get_indexes('users')):
        op.create_index('uq_users_email', 'users', ['email'], unique=True)


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    with op.batch_alter_table('users') as batch:
        for index in inspector.get_indexes('users'):
            if index['column_names'] == ['email'] and index.get('unique'):
                batch.drop_index(index['name'])
        for constraint in inspector.get_unique_constraints('users'):
            if constraint['column_names'] == ['email'] and constraint.get('name'):
                batch.drop_constraint(constraint['name'], type_='unique')
        for name in ['is_active', 'role', 'password_hash', 'email']:
            batch.drop_column(name)

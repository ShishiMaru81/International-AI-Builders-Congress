"""Add relational farm_id, source_record_id, updated_at and reading chronology columns."""
import json
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'


def upgrade():
    # Startup compatibility upgrades can precede Alembic. Inspect before adding
    # so stamping/upgrading that existing database never duplicates its columns.
    inspector = sa.inspect(op.get_bind())
    for table, names, indexed in [
        ('records', ['farm_id', 'source_record_id', 'updated_at'], ['farm_id', 'source_record_id']),
        ('sensor_readings', ['event_timestamp', 'source_type', 'created_at'], ['event_timestamp']),
    ]:
        columns = {column['name'] for column in inspector.get_columns(table)}
        indexes = {index['name'] for index in inspector.get_indexes(table)}
        for name in names:
            if name not in columns:
                op.add_column(table, sa.Column(name, sa.String(), nullable=True))
        for name in indexed:
            index_name = f'ix_{table}_{name}'
            if index_name not in indexes:
                op.create_index(index_name, table, [name])

    # Backfill existing rows without losing user data
    conn = op.get_bind()
    rows = conn.execute(sa.text('SELECT id, kind, created_at, payload FROM records')).fetchall()
    for row_id, kind, created_at, raw_payload in rows:
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else (raw_payload or {})
        farm_id = payload.get('farm_id') if isinstance(payload, dict) else None
        source_id = None
        if isinstance(payload, dict):
            source_id = payload.get('source_record_id') or payload.get('case_id') or payload.get('action_id') or payload.get('record_id')
        conn.execute(
            sa.text(
                'UPDATE records SET farm_id = COALESCE(farm_id, :farm_id), source_record_id = COALESCE(source_record_id, :source_id), '
                'updated_at = COALESCE(updated_at, :created_at) WHERE id = :id'
            ),
            {'farm_id': farm_id, 'source_id': source_id, 'created_at': created_at, 'id': row_id},
        )

    reading_rows = conn.execute(sa.text('SELECT id, payload FROM sensor_readings')).fetchall()
    for r_id, raw_payload in reading_rows:
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else (raw_payload or {})
        ts = payload.get('timestamp') if isinstance(payload, dict) else None
        stype = payload.get('source_type') if isinstance(payload, dict) else None
        conn.execute(
            sa.text(
                'UPDATE sensor_readings SET event_timestamp = COALESCE(event_timestamp, :ts), source_type = COALESCE(source_type, :stype), '
                'created_at = COALESCE(created_at, :ts) WHERE id = :id'
            ),
            {'ts': ts, 'stype': stype, 'id': r_id},
        )


def downgrade():
    with op.batch_alter_table('sensor_readings') as batch_op:
        batch_op.drop_index('ix_sensor_readings_event_timestamp')
        batch_op.drop_column('created_at')
        batch_op.drop_column('source_type')
        batch_op.drop_column('event_timestamp')

    with op.batch_alter_table('records') as batch_op:
        batch_op.drop_index('ix_records_source_record_id')
        batch_op.drop_index('ix_records_farm_id')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('source_record_id')
        batch_op.drop_column('farm_id')

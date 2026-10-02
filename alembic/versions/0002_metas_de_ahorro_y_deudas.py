"""Metas de ahorro (con sus aportes) y deudas (con sus pagos).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('deudas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Enum('ME_DEBEN', 'DEBO', name='tipodeuda'), nullable=False),
    sa.Column('persona', sa.String(length=100), nullable=False),
    sa.Column('descripcion', sa.String(length=255), nullable=True),
    sa.Column('monto_total', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('fecha_vencimiento', sa.Date(), nullable=True),
    sa.Column('creada_en', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('fecha_vencimiento IS NULL OR fecha_vencimiento >= fecha', name='ck_deuda_vencimiento_valido'),
    sa.CheckConstraint('monto_total > 0', name='ck_deuda_monto_positivo'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('deudas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_deudas_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('metas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=80), nullable=False),
    sa.Column('monto_objetivo', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('fecha_objetivo', sa.Date(), nullable=True),
    sa.Column('icono', sa.String(length=40), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('archivada', sa.Boolean(), nullable=False),
    sa.Column('creada_en', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('monto_objetivo > 0', name='ck_meta_objetivo_positivo'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('metas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_metas_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('aportes_meta',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('meta_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Enum('APORTE', 'RETIRO', name='tipoaporte'), nullable=False),
    sa.Column('monto', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('nota', sa.String(length=255), nullable=True),
    sa.CheckConstraint('monto > 0', name='ck_aporte_monto_positivo'),
    sa.ForeignKeyConstraint(['meta_id'], ['metas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('aportes_meta', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_aportes_meta_meta_id'), ['meta_id'], unique=False)

    op.create_table('pagos_deuda',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('deuda_id', sa.Integer(), nullable=False),
    sa.Column('monto', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('nota', sa.String(length=255), nullable=True),
    sa.CheckConstraint('monto > 0', name='ck_pago_monto_positivo'),
    sa.ForeignKeyConstraint(['deuda_id'], ['deudas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('pagos_deuda', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pagos_deuda_deuda_id'), ['deuda_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('pagos_deuda', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pagos_deuda_deuda_id'))

    op.drop_table('pagos_deuda')
    with op.batch_alter_table('aportes_meta', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_aportes_meta_meta_id'))

    op.drop_table('aportes_meta')
    with op.batch_alter_table('metas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_metas_usuario_id'))

    op.drop_table('metas')
    with op.batch_alter_table('deudas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deudas_usuario_id'))

    op.drop_table('deudas')

    # PostgreSQL crea un tipo propio por cada Enum y no lo borra al eliminar las tablas
    if op.get_bind().dialect.name == "postgresql":
        for tipo in ("tipoaporte", "tipodeuda"):
            op.execute(f"DROP TYPE IF EXISTS {tipo}")

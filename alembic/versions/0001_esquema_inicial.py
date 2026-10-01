"""Esquema inicial: usuarios, cuentas, categorías, transacciones, presupuestos, recurrentes y notificaciones.

Revision ID: 0001
Revises:
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('moneda_por_defecto', sa.String(length=3), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usuarios_email'), ['email'], unique=True)

    op.create_table('categorias',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('nombre', sa.String(length=60), nullable=False),
    sa.Column('tipo', sa.Enum('INGRESO', 'GASTO', name='tipocategoria'), nullable=False),
    sa.Column('icono', sa.String(length=40), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('categoria_padre_id', sa.Integer(), nullable=True),
    sa.Column('archivada', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['categoria_padre_id'], ['categorias.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('categorias', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_categorias_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('cuentas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=60), nullable=False),
    sa.Column('tipo', sa.Enum('EFECTIVO', 'BANCARIA', 'BILLETERA_DIGITAL', 'TARJETA_CREDITO', name='tipocuenta'), nullable=False),
    sa.Column('saldo_inicial', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('archivada', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'nombre', name='uq_cuenta_usuario_nombre')
    )
    with op.batch_alter_table('cuentas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cuentas_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('presupuestos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('categoria_id', sa.Integer(), nullable=False),
    sa.Column('monto_limite', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('mes', sa.Integer(), nullable=False),
    sa.Column('anio', sa.Integer(), nullable=False),
    sa.Column('umbral_alerta', sa.Integer(), nullable=False),
    sa.CheckConstraint('mes BETWEEN 1 AND 12', name='ck_presupuesto_mes'),
    sa.CheckConstraint('monto_limite > 0', name='ck_presupuesto_limite_positivo'),
    sa.CheckConstraint('umbral_alerta BETWEEN 1 AND 100', name='ck_presupuesto_umbral'),
    sa.ForeignKeyConstraint(['categoria_id'], ['categorias.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'categoria_id', 'anio', 'mes', name='uq_presupuesto_periodo')
    )
    with op.batch_alter_table('presupuestos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_presupuestos_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('transacciones_recurrentes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('cuenta_id', sa.Integer(), nullable=False),
    sa.Column('categoria_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Enum('INGRESO', 'GASTO', 'TRANSFERENCIA', name='tipotransaccion'), nullable=False),
    sa.Column('monto', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('nota', sa.String(length=255), nullable=True),
    sa.Column('frecuencia', sa.Enum('SEMANAL', 'QUINCENAL', 'MENSUAL', 'ANUAL', name='frecuencia'), nullable=False),
    sa.Column('proxima_fecha', sa.Date(), nullable=False),
    sa.Column('dia_ancla', sa.Integer(), nullable=False),
    sa.Column('fecha_fin', sa.Date(), nullable=True),
    sa.Column('activa', sa.Boolean(), nullable=False),
    sa.CheckConstraint("tipo <> 'TRANSFERENCIA'", name='ck_recurrente_sin_transferencias'),
    sa.CheckConstraint('monto > 0', name='ck_recurrente_monto_positivo'),
    sa.ForeignKeyConstraint(['categoria_id'], ['categorias.id'], ),
    sa.ForeignKeyConstraint(['cuenta_id'], ['cuentas.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('transacciones_recurrentes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_transacciones_recurrentes_proxima_fecha'), ['proxima_fecha'], unique=False)
        batch_op.create_index(batch_op.f('ix_transacciones_recurrentes_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('notificaciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Enum('PRESUPUESTO_UMBRAL', 'PRESUPUESTO_EXCEDIDO', 'RECURRENTE_REGISTRADA', 'INFO', name='tiponotificacion'), nullable=False),
    sa.Column('mensaje', sa.String(length=255), nullable=False),
    sa.Column('presupuesto_id', sa.Integer(), nullable=True),
    sa.Column('leida', sa.Boolean(), nullable=False),
    sa.Column('creada_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['presupuesto_id'], ['presupuestos.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notificaciones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notificaciones_presupuesto_id'), ['presupuesto_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notificaciones_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('transacciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('cuenta_id', sa.Integer(), nullable=False),
    sa.Column('cuenta_destino_id', sa.Integer(), nullable=True),
    sa.Column('categoria_id', sa.Integer(), nullable=True),
    sa.Column('recurrente_id', sa.Integer(), nullable=True),
    sa.Column('tipo', sa.Enum('INGRESO', 'GASTO', 'TRANSFERENCIA', name='tipotransaccion'), nullable=False),
    sa.Column('monto', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('nota', sa.String(length=255), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("(tipo = 'TRANSFERENCIA' AND cuenta_destino_id IS NOT NULL AND cuenta_destino_id <> cuenta_id) OR (tipo <> 'TRANSFERENCIA' AND cuenta_destino_id IS NULL)", name='ck_transaccion_transferencia_valida'),
    sa.CheckConstraint('monto > 0', name='ck_transaccion_monto_positivo'),
    sa.ForeignKeyConstraint(['categoria_id'], ['categorias.id'], ),
    sa.ForeignKeyConstraint(['cuenta_destino_id'], ['cuentas.id'], ),
    sa.ForeignKeyConstraint(['cuenta_id'], ['cuentas.id'], ),
    sa.ForeignKeyConstraint(['recurrente_id'], ['transacciones_recurrentes.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('recurrente_id', 'fecha', name='uq_transaccion_recurrente_fecha')
    )
    with op.batch_alter_table('transacciones', schema=None) as batch_op:
        batch_op.create_index('ix_transaccion_usuario_categoria', ['usuario_id', 'categoria_id'], unique=False)
        batch_op.create_index('ix_transaccion_usuario_fecha', ['usuario_id', 'fecha'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('transacciones', schema=None) as batch_op:
        batch_op.drop_index('ix_transaccion_usuario_fecha')
        batch_op.drop_index('ix_transaccion_usuario_categoria')

    op.drop_table('transacciones')
    with op.batch_alter_table('notificaciones', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notificaciones_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_notificaciones_presupuesto_id'))

    op.drop_table('notificaciones')
    with op.batch_alter_table('transacciones_recurrentes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_transacciones_recurrentes_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_transacciones_recurrentes_proxima_fecha'))

    op.drop_table('transacciones_recurrentes')
    with op.batch_alter_table('presupuestos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_presupuestos_usuario_id'))

    op.drop_table('presupuestos')
    with op.batch_alter_table('cuentas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cuentas_usuario_id'))

    op.drop_table('cuentas')
    with op.batch_alter_table('categorias', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_categorias_usuario_id'))

    op.drop_table('categorias')
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usuarios_email'))

    op.drop_table('usuarios')

    # PostgreSQL crea un tipo propio por cada Enum y no lo borra al eliminar las tablas
    if op.get_bind().dialect.name == "postgresql":
        for tipo in ("tiponotificacion", "frecuencia", "tipotransaccion", "tipocuenta", "tipocategoria"):
            op.execute(f"DROP TYPE IF EXISTS {tipo}")

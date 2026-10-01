from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Categoria, TipoCategoria

G, I = TipoCategoria.GASTO, TipoCategoria.INGRESO

# (nombre, tipo, icono, color)
CATEGORIAS_DEFAULT = [
    ("Comida", G, "🍽️", "#E4572E"),
    ("Mercado", G, "🛒", "#F3A712"),
    ("Transporte", G, "🚌", "#29335C"),
    ("Arriendo", G, "🏠", "#7B2D26"),
    ("Servicios públicos", G, "💡", "#A8C686"),
    ("Salud", G, "💊", "#669BBC"),
    ("Educación", G, "📚", "#5F4B8B"),
    ("Entretenimiento", G, "🎬", "#EE6C4D"),
    ("Ropa", G, "👕", "#B8336A"),
    ("Suscripciones", G, "📱", "#3D5A80"),
    ("Mascotas", G, "🐾", "#8D6B94"),
    ("Otros gastos", G, "📦", "#6B7280"),
    ("Salario", I, "💼", "#2A9D8F"),
    ("Freelance", I, "💻", "#4C9F70"),
    ("Ventas", I, "🏷️", "#8AB17D"),
    ("Regalos", I, "🎁", "#E9C46A"),
    ("Intereses", I, "🏦", "#457B9D"),
    ("Otros ingresos", I, "➕", "#6B7280"),
]


def sembrar_categorias_default(db: Session) -> int:
    """Crea las categorías compartidas (usuario_id nulo) que falten. Es idempotente."""
    existentes = {
        (nombre, tipo)
        for nombre, tipo in db.execute(
            select(Categoria.nombre, Categoria.tipo).where(Categoria.usuario_id.is_(None))
        )
    }
    nuevas = [
        Categoria(usuario_id=None, nombre=n, tipo=t, icono=i, color=c)
        for n, t, i, c in CATEGORIAS_DEFAULT
        if (n, t) not in existentes
    ]
    db.add_all(nuevas)
    db.commit()
    return len(nuevas)

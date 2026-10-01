from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbDep, UsuarioActual
from app.models import Categoria, Presupuesto, TipoCategoria, Transaccion, TransaccionRecurrente
from app.schemas.categoria import CategoriaActualizar, CategoriaCrear, CategoriaLeer

router = APIRouter(prefix="/categorias", tags=["Categorías"])


def _visible(usuario):
    """Predeterminadas (compartidas) + las propias."""
    return or_(Categoria.usuario_id.is_(None), Categoria.usuario_id == usuario.id)


def _propia(db, usuario, categoria_id: int) -> Categoria:
    categoria = db.scalar(select(Categoria).where(Categoria.id == categoria_id, _visible(usuario)))
    if categoria is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada")
    if categoria.predeterminada:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Las categorías predeterminadas no se pueden modificar")
    return categoria


def _validar_nombre_libre(db, usuario, nombre: str, tipo, excluir_id: int | None = None):
    consulta = select(Categoria.id).where(
        _visible(usuario),
        Categoria.tipo == tipo,
        Categoria.archivada.is_(False),
        func.lower(Categoria.nombre) == nombre.lower(),
    )
    if excluir_id is not None:
        consulta = consulta.where(Categoria.id != excluir_id)
    if db.scalar(consulta):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una categoría con ese nombre")


@router.get("", response_model=list[CategoriaLeer])
def listar(
    db: DbDep,
    usuario: UsuarioActual,
    tipo: TipoCategoria | None = None,
    incluir_archivadas: bool = False,
):
    consulta = select(Categoria).where(_visible(usuario)).order_by(Categoria.tipo, Categoria.nombre)
    if tipo is not None:
        consulta = consulta.where(Categoria.tipo == tipo)
    if not incluir_archivadas:
        consulta = consulta.where(Categoria.archivada.is_(False))
    return db.scalars(consulta).all()


@router.post("", response_model=CategoriaLeer, status_code=status.HTTP_201_CREATED)
def crear(datos: CategoriaCrear, db: DbDep, usuario: UsuarioActual):
    _validar_nombre_libre(db, usuario, datos.nombre, datos.tipo)
    if datos.categoria_padre_id is not None:
        padre = db.scalar(
            select(Categoria).where(Categoria.id == datos.categoria_padre_id, _visible(usuario))
        )
        if padre is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "La categoría padre no existe")
        if padre.tipo != datos.tipo:
            raise HTTPException(422, "La subcategoría debe ser del mismo tipo que su padre")
        if padre.categoria_padre_id is not None:
            raise HTTPException(422, "Solo se permite un nivel de subcategorías")
    categoria = Categoria(usuario_id=usuario.id, **datos.model_dump())
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.patch("/{categoria_id}", response_model=CategoriaLeer)
def actualizar(categoria_id: int, datos: CategoriaActualizar, db: DbDep, usuario: UsuarioActual):
    categoria = _propia(db, usuario, categoria_id)
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("nombre", "x") is None or cambios.get("archivada", False) is None:
        raise HTTPException(422, "nombre y archivada no pueden ser nulos")
    if "nombre" in cambios:
        _validar_nombre_libre(db, usuario, cambios["nombre"], categoria.tipo, excluir_id=categoria.id)
    for campo, valor in cambios.items():
        setattr(categoria, campo, valor)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(categoria_id: int, db: DbDep, usuario: UsuarioActual):
    """Solo se borra una categoría sin uso; si ya tiene historial, se archiva."""
    categoria = _propia(db, usuario, categoria_id)
    en_uso = (
        db.scalar(select(Transaccion.id).where(Transaccion.categoria_id == categoria.id).limit(1))
        or db.scalar(select(TransaccionRecurrente.id).where(TransaccionRecurrente.categoria_id == categoria.id).limit(1))
        or db.scalar(select(Presupuesto.id).where(Presupuesto.categoria_id == categoria.id).limit(1))
        or db.scalar(select(Categoria.id).where(Categoria.categoria_padre_id == categoria.id).limit(1))
    )
    if en_uso:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La categoría está en uso; archívala (PATCH archivada=true) en lugar de borrarla",
        )
    try:
        db.delete(categoria)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "La categoría está en uso; archívala en lugar de borrarla")

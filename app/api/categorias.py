from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbDep, UsuarioActual
from app.models import Categoria, CategoriaOculta, Presupuesto, TipoCategoria, Transaccion, TransaccionRecurrente
from app.schemas.categoria import CategoriaActualizar, CategoriaCrear, CategoriaLeer
from app.services.validaciones import categorias_ocultas

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
    ocultas = categorias_ocultas(db, usuario)
    if ocultas:  # una predeterminada que quitaste no te impide crear la tuya con el mismo nombre
        consulta = consulta.where(Categoria.id.not_in(ocultas))
    if db.scalar(consulta):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una categoría con ese nombre")


@router.get("", response_model=list[CategoriaLeer])
def listar(
    db: DbDep,
    usuario: UsuarioActual,
    tipo: TipoCategoria | None = None,
    incluir_archivadas: bool = False,
):
    """Con `incluir_archivadas` también salen las predeterminadas que quitaste (marcadas como archivadas)."""
    consulta = select(Categoria).where(_visible(usuario)).order_by(Categoria.tipo, Categoria.nombre)
    if tipo is not None:
        consulta = consulta.where(Categoria.tipo == tipo)
    if not incluir_archivadas:
        consulta = consulta.where(Categoria.archivada.is_(False))
    ocultas = categorias_ocultas(db, usuario)
    resultado = []
    for categoria in db.scalars(consulta):
        oculta = categoria.id in ocultas
        if oculta and not incluir_archivadas:
            continue
        leida = CategoriaLeer.model_validate(categoria)
        if oculta:
            leida.archivada = True
        resultado.append(leida)
    return resultado


@router.post("", response_model=CategoriaLeer, status_code=status.HTTP_201_CREATED)
def crear(datos: CategoriaCrear, db: DbDep, usuario: UsuarioActual):
    _validar_nombre_libre(db, usuario, datos.nombre, datos.tipo)
    if datos.categoria_padre_id is not None:
        padre = db.scalar(
            select(Categoria).where(Categoria.id == datos.categoria_padre_id, _visible(usuario))
        )
        if padre is None or padre.id in categorias_ocultas(db, usuario):
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
    """Solo se borra una categoría propia sin uso; si ya tiene historial, se archiva.

    En una predeterminada, "eliminar" la quita de TU lista (los demás usuarios la siguen viendo
    y tus movimientos anteriores se conservan). Se recupera con /categorias/restaurar-predeterminadas.
    """
    visible = db.scalar(select(Categoria).where(Categoria.id == categoria_id, _visible(usuario)))
    if visible is not None and visible.predeterminada:
        if visible.id not in categorias_ocultas(db, usuario):
            db.add(CategoriaOculta(usuario_id=usuario.id, categoria_id=visible.id))
            db.commit()
        return
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


@router.post("/restaurar-predeterminadas")
def restaurar_predeterminadas(db: DbDep, usuario: UsuarioActual):
    """Devuelve a tu lista las predeterminadas que quitaste.

    Si ya creaste una categoría propia con el mismo nombre y tipo, esa predeterminada se deja
    quitada para no tener dos iguales.
    """
    quitadas = db.scalars(
        select(Categoria)
        .join(CategoriaOculta, CategoriaOculta.categoria_id == Categoria.id)
        .where(CategoriaOculta.usuario_id == usuario.id)
    ).all()
    restauradas = 0
    for categoria in quitadas:
        repetida = db.scalar(
            select(Categoria.id).where(
                Categoria.usuario_id == usuario.id,
                Categoria.tipo == categoria.tipo,
                Categoria.archivada.is_(False),
                func.lower(Categoria.nombre) == categoria.nombre.lower(),
            )
        )
        if repetida:
            continue
        db.execute(
            delete(CategoriaOculta).where(
                CategoriaOculta.usuario_id == usuario.id, CategoriaOculta.categoria_id == categoria.id
            )
        )
        restauradas += 1
    db.commit()
    return {"restauradas": restauradas}

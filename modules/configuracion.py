"""M9 Configuración de la clínica - HiperOxygen.

Permite que recepción cargue y mantenga los datos reales de la clínica sin
tocar el código:

- Cámaras hiperbáricas: nombre y lugares por sesión (capacidad). La suma de
  las cámaras activas es el cupo de cada horario.
- Especialistas: alta, edición, activar/desactivar y su acceso al sistema.
- Servicios: nombre, duración, precio, descripción y si se dan en cámara.

Nada se borra: lo que ya no se usa se desactiva, para conservar el historial
de citas.
"""

import re
from datetime import date

from modules.auth_roles import ROL_ESPECIALISTA, generar_hash, verificar_permiso
from modules.data_access import ESTATUS_CANCELADA, ErrorBaseDatos, ErrorIntegridad
from modules.patients import validar_credenciales
from modules.validation_messages import construir_mensaje_faltantes, esta_vacio

CAPACIDAD_MAXIMA = 20
DURACION_MINIMA, DURACION_MAXIMA = 5, 480

MENSAJE_CAPACIDAD_INVALIDA = (
    f"Error: Los lugares por sesión deben ser un número entre 1 y {CAPACIDAD_MAXIMA}."
)
MENSAJE_DURACION_INVALIDA = (
    f"Error: La duración debe ser un número de minutos entre {DURACION_MINIMA} y {DURACION_MAXIMA}."
)
MENSAJE_PRECIO_INVALIDO = "Error: El precio debe ser un número mayor o igual a 0, o quedar vacío."
MENSAJE_NOMBRE_DUPLICADO = "Error: Ya existe {tipo} con el nombre '{nombre}'."
MENSAJE_NO_EXISTE = "Error: {tipo} seleccionado no existe."
MENSAJE_USUARIO_OCUPADO = "Error: El usuario '{usuario}' ya está en uso. Elija otro."


def _resultado(exito, mensaje="", **datos):
    return {"exito": exito, "mensaje": mensaje, **datos}


def _texto(valor):
    return valor.strip() if isinstance(valor, str) else valor


def _entero(valor):
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def _precio(valor):
    """'' o None → (None, ''); '$1,250.50' → (1250.5, ''); inválido → (None, error)."""
    if esta_vacio(valor):
        return None, ""
    limpio = re.sub(r"[\s$,]|MXN", "", str(valor), flags=re.I)
    try:
        numero = float(limpio)
    except ValueError:
        return None, MENSAJE_PRECIO_INVALIDO
    if numero < 0:
        return None, MENSAJE_PRECIO_INVALIDO
    return round(numero, 2), ""


def _verdadero(valor):
    return valor in (True, 1, "1", "true", "True", "si", "sí", "on")


def _permiso(sesion):
    return verificar_permiso(sesion, "configurar_clinica")


# -- Resumen ------------------------------------------------------------------

def consultar_configuracion(bd, sesion):
    """Cámaras, especialistas (con su usuario) y servicios, activos e inactivos."""
    permiso = _permiso(sesion)
    if not permiso["exito"]:
        return _resultado(False, permiso["mensaje"])
    try:
        return _resultado(
            True,
            camaras=bd.listar_camaras(),
            especialistas=bd.listar_odontologos_con_acceso(),
            servicios=bd.listar_servicios(solo_activos=False),
            cupo=bd.cupo_camaras(),
        )
    except ErrorBaseDatos as error:
        return _resultado(False, error.mensaje)


# -- Cámaras ------------------------------------------------------------------

def guardar_camara(bd, sesion, datos, id_camara=None):
    """Crea una cámara o, con `id_camara`, la actualiza."""
    permiso = _permiso(sesion)
    if not permiso["exito"]:
        return _resultado(False, permiso["mensaje"])
    datos = datos or {}
    faltantes = [c for c in ("nombre", "capacidad") if esta_vacio(datos.get(c))]
    if faltantes:
        return _resultado(False, construir_mensaje_faltantes(faltantes))
    capacidad = _entero(datos["capacidad"])
    if capacidad is None or not 1 <= capacidad <= CAPACIDAD_MAXIMA:
        return _resultado(False, MENSAJE_CAPACIDAD_INVALIDA)
    nombre = _texto(datos["nombre"])
    try:
        if id_camara is None:
            id_camara = bd.insertar_camara(nombre, capacidad)
        elif bd.obtener_camara(_entero(id_camara)) is None:
            return _resultado(False, MENSAJE_NO_EXISTE.format(tipo="La cámara"))
        else:
            bd.actualizar_camara(_entero(id_camara), nombre, capacidad)
    except ErrorIntegridad:
        return _resultado(False, MENSAJE_NOMBRE_DUPLICADO.format(tipo="una cámara", nombre=nombre))
    except ErrorBaseDatos as error:
        return _resultado(False, error.mensaje)
    lugares = "1 lugar" if capacidad == 1 else f"{capacidad} lugares"
    return _resultado(True, f"Cámara guardada: {nombre} ({lugares} por sesión).", id=id_camara)


def cambiar_estado_camara(bd, sesion, id_camara, activa):
    permiso = _permiso(sesion)
    if not permiso["exito"]:
        return _resultado(False, permiso["mensaje"])
    try:
        camara = bd.obtener_camara(_entero(id_camara))
        if camara is None:
            return _resultado(False, MENSAJE_NO_EXISTE.format(tipo="La cámara"))
        bd.cambiar_estado_camara(camara["id_camara"], _verdadero(activa))
        cupo = bd.cupo_camaras()
    except ErrorBaseDatos as error:
        return _resultado(False, error.mensaje)
    estado = "activada" if _verdadero(activa) else "desactivada"
    mensaje = f"Cámara {estado}: {camara['nombre']}. Cupo actual por horario: {cupo}."
    if cupo == 0:
        mensaje = ("Aviso: No queda ninguna cámara activa; no se podrán agendar "
                   "sesiones en cámara hasta activar una.")
    return _resultado(True, mensaje, cupo=cupo)


# -- Especialistas ----------------------------------------------------------------

def guardar_especialista(bd, sesion, datos, id_especialista=None):
    """Crea un especialista o, con `id_especialista`, actualiza sus datos."""
    permiso = _permiso(sesion)
    if not permiso["exito"]:
        return _resultado(False, permiso["mensaje"])
    datos = datos or {}
    faltantes = [c for c in ("nombre", "apellidos") if esta_vacio(datos.get(c))]
    if faltantes:
        return _resultado(False, construir_mensaje_faltantes(faltantes))
    nombre, apellidos = _texto(datos["nombre"]), _texto(datos["apellidos"])
    especialidad = None if esta_vacio(datos.get("especialidad")) else _texto(datos["especialidad"])
    try:
        if id_especialista is None:
            id_especialista = bd.insertar_odontologo(nombre, apellidos, especialidad)
        elif bd.obtener_odontologo(_entero(id_especialista)) is None:
            return _resultado(False, MENSAJE_NO_EXISTE.format(tipo="El especialista"))
        else:
            bd.actualizar_odontologo(_entero(id_especialista), nombre, apellidos, especialidad)
    except ErrorBaseDatos as error:
        return _resultado(False, error.mensaje)
    return _resultado(True, f"Especialista guardado: {nombre} {apellidos}.", id=id_especialista)


def cambiar_estado_especialista(bd, sesion, id_especialista, activo, hoy=None):
    """Activa o desactiva. Al desactivar avisa cuántas citas próximas tiene."""
    permiso = _permiso(sesion)
    if not permiso["exito"]:
        return _resultado(False, permiso["mensaje"])
    try:
        especialista = bd.obtener_odontologo(_entero(id_especialista))
        if especialista is None:
            return _resultado(False, MENSAJE_NO_EXISTE.format(tipo="El especialista"))
        bd.cambiar_estado_odontologo(especialista["id_odontologo"], _verdadero(activo))
        hoy_iso = (hoy or date.today()).isoformat()
        pendientes = [c for c in bd.consultar_citas(id_odontologo=especialista["id_odontologo"])
                      if c["fecha"] >= hoy_iso and c["estatus"] != ESTATUS_CANCELADA]
    except ErrorBaseDatos as error:
        return _resultado(False, error.mensaje)
    nombre = f"{especialista['nombre']} {especialista['apellidos']}"
    if _verdadero(activo):
        return _resultado(True, f"Especialista activado: {nombre}.")
    if pendientes:
        return _resultado(True, f"Aviso: {nombre} quedó inactivo y tiene {len(pendientes)} "
                                "cita(s) próximas. Reasígnelas desde la agenda.",
                          pendientes=len(pendientes))
    return _resultado(True, f"Especialista desactivado: {nombre}.")


def gestionar_acceso_especialista(bd, sesion, id_especialista, usuario, contrasena):
    """Crea el usuario del especialista o, si ya tiene, restablece su contraseña."""
    permiso = _permiso(sesion)
    if not permiso["exito"]:
        return _resultado(False, permiso["mensaje"])
    try:
        especialista = bd.obtener_odontologo(_entero(id_especialista))
        if especialista is None:
            return _resultado(False, MENSAJE_NO_EXISTE.format(tipo="El especialista"))
        nombre = f"{especialista['nombre']} {especialista['apellidos']}"
        existente = bd.obtener_usuario_de_odontologo(especialista["id_odontologo"])
        if existente is not None:
            error = validar_credenciales(existente["nombre_usuario"], contrasena)
            if error:
                return _resultado(False, error)
            bd.actualizar_contrasena(existente["id_usuario"], generar_hash(contrasena))
            return _resultado(True, f"Contraseña restablecida para {nombre} "
                                    f"(usuario '{existente['nombre_usuario']}').")
        error = validar_credenciales(usuario, contrasena)
        if error:
            return _resultado(False, error)
        usuario = usuario.strip()
        if bd.obtener_usuario_por_nombre(usuario) is not None:
            return _resultado(False, MENSAJE_USUARIO_OCUPADO.format(usuario=usuario))
        bd.insertar_usuario(usuario, generar_hash(contrasena), ROL_ESPECIALISTA,
                            id_odontologo=especialista["id_odontologo"])
    except ErrorIntegridad:
        return _resultado(False, MENSAJE_USUARIO_OCUPADO.format(usuario=usuario))
    except ErrorBaseDatos as error:
        return _resultado(False, error.mensaje)
    return _resultado(True, f"Acceso creado para {nombre}: usuario '{usuario}'.")


# -- Servicios ---------------------------------------------------------------------

def guardar_servicio(bd, sesion, datos, id_servicio=None):
    """Crea un servicio o, con `id_servicio`, lo actualiza."""
    permiso = _permiso(sesion)
    if not permiso["exito"]:
        return _resultado(False, permiso["mensaje"])
    datos = datos or {}
    faltantes = [c for c in ("nombre", "duracion") if esta_vacio(datos.get(c))]
    if faltantes:
        return _resultado(False, construir_mensaje_faltantes(faltantes))
    duracion = _entero(datos["duracion"])
    if duracion is None or not DURACION_MINIMA <= duracion <= DURACION_MAXIMA:
        return _resultado(False, MENSAJE_DURACION_INVALIDA)
    precio, error = _precio(datos.get("precio"))
    if error:
        return _resultado(False, error)
    nombre = _texto(datos["nombre"])
    descripcion = None if esta_vacio(datos.get("descripcion")) else _texto(datos["descripcion"])
    camara = _verdadero(datos.get("usa_camara"))
    try:
        if id_servicio is None:
            id_servicio = bd.insertar_servicio(nombre, duracion, descripcion, precio, usa_camara=camara)
        elif bd.obtener_servicio(_entero(id_servicio)) is None:
            return _resultado(False, MENSAJE_NO_EXISTE.format(tipo="El servicio"))
        else:
            bd.actualizar_servicio(_entero(id_servicio), nombre, duracion, descripcion, precio, camara)
    except ErrorIntegridad:
        return _resultado(False, MENSAJE_NOMBRE_DUPLICADO.format(tipo="un servicio", nombre=nombre))
    except ErrorBaseDatos as error:
        return _resultado(False, error.mensaje)
    tipo = "en cámara" if camara else "consulta"
    return _resultado(True, f"Servicio guardado: {nombre} ({duracion} min, {tipo}).", id=id_servicio)


def cambiar_estado_servicio(bd, sesion, id_servicio, activo):
    permiso = _permiso(sesion)
    if not permiso["exito"]:
        return _resultado(False, permiso["mensaje"])
    try:
        servicio = bd.obtener_servicio(_entero(id_servicio))
        if servicio is None:
            return _resultado(False, MENSAJE_NO_EXISTE.format(tipo="El servicio"))
        bd.cambiar_estado_servicio(servicio["id_servicio"], _verdadero(activo))
    except ErrorBaseDatos as error:
        return _resultado(False, error.mensaje)
    if _verdadero(activo):
        return _resultado(True, f"Servicio activado: {servicio['nombre']}.")
    return _resultado(True, f"Servicio desactivado: {servicio['nombre']}. Ya no aparece "
                            "en el catálogo; las citas que ya lo tienen se conservan.")

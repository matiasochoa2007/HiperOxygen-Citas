"""M3 Disponibilidad - HiperOxygen.

Calcula los horarios libres de un especialista y le entrega a M6 el indicador de
horario ocupado.

Requerimientos: RF-07 (HU-12, HU-13) y RF-02 (HU-03).
Criterios: CA-36 a CA-41 y CA-07 a CA-09.

Reglas de HiperOxygen:
- Consultas (servicios sin cámara): un especialista no tiene dos consultas a
  la misma hora de inicio (RF-02).
- Sesiones en cámara hiperbárica: cada horario tiene tantos lugares como la
  suma de la capacidad de las cámaras activas.
Las citas canceladas liberan el horario o el lugar.
"""

from datetime import date, datetime, timedelta

from config import settings
from modules.auth_roles import ROL_RECEPCIONISTA, verificar_permiso
from modules.data_access import ErrorBaseDatos
from modules.validation_messages import esta_vacio

MENSAJE_FECHA_INVALIDA = (
    "Error: La fecha '{fecha}' no es válida. Use el formato AAAA-MM-DD."
)
MENSAJE_FECHA_PASADA = (
    "Error: La fecha '{fecha}' ya pasó. Elija una fecha de hoy en adelante."
)
MENSAJE_HORA_INVALIDA = (
    "Error: La hora '{hora}' no es un horario de atención. "
    "Elija uno de: {horarios}."
)
MENSAJE_ESPECIALISTA_INEXISTENTE = (
    "Error: El especialista seleccionado no existe o no está activo."
)
MENSAJE_SIN_HORARIOS = (
    "Aviso: El especialista no tiene horarios libres el {fecha}. "
    "Pruebe con otra fecha u otro especialista."
)


def _a_minutos(hora):
    horas, minutos = hora.split(":")
    return int(horas) * 60 + int(minutos)


def horarios_del_dia():
    """Horas de inicio de los bloques de atención, en formato HH:MM."""
    inicio = _a_minutos(settings.HORA_APERTURA)
    fin = _a_minutos(settings.HORA_CIERRE)
    paso = settings.DURACION_BLOQUE_MIN
    return [
        f"{minuto // 60:02d}:{minuto % 60:02d}"
        for minuto in range(inicio, fin - paso + 1, paso)
    ]


def validar_fecha(fecha, hoy=None, permitir_pasadas=False):
    """Devuelve "" si la fecha es válida y no está en el pasado; si no, el
    mensaje de error. Para consultas (RF-06) se permiten fechas pasadas."""
    if esta_vacio(fecha):
        return MENSAJE_FECHA_INVALIDA.format(fecha="")
    texto = str(fecha).strip()
    try:
        dia = datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        return MENSAJE_FECHA_INVALIDA.format(fecha=texto)
    if not permitir_pasadas and dia < (hoy or date.today()):
        return MENSAJE_FECHA_PASADA.format(fecha=texto)
    return ""


def validar_hora(hora):
    """Devuelve "" si la hora es un inicio de bloque válido; si no, el error."""
    horarios = horarios_del_dia()
    if str(hora).strip() in horarios:
        return ""
    return MENSAJE_HORA_INVALIDA.format(hora=hora, horarios=", ".join(horarios))


def obtener_especialista_activo(bd, id_odontologo):
    """Devuelve el especialista si existe y está activo; si no, None."""
    try:
        id_odontologo = int(id_odontologo)
    except (TypeError, ValueError):
        return None
    odontologo = bd.obtener_odontologo(id_odontologo)
    if odontologo is None or not odontologo["activo"]:
        return None
    return odontologo


MENSAJE_SIN_CAMARAS = (
    "Aviso: No hay cámaras activas. Recepción debe dar de alta o activar una "
    "cámara en Configuración."
)
MENSAJE_SERVICIO_NO_DISPONIBLE = (
    "Error: El servicio seleccionado no existe o ya no está disponible."
)


def obtener_servicio_activo(bd, id_servicio):
    """Devuelve el servicio si existe y está activo; si no, None."""
    try:
        id_servicio = int(str(id_servicio).strip())
    except (TypeError, ValueError):
        return None
    servicio = bd.obtener_servicio(id_servicio)
    if servicio is None or not servicio["activo"]:
        return None
    return servicio


def horario_ocupado(bd, id_odontologo, fecha, hora, excluir_id_cita=None,
                    en_camara=False):
    """Indicador para M6 (CA-47).

    - Consulta: True si el especialista ya tiene otra consulta a esa hora (RF-02).
    - Sesión en cámara: True si ya no quedan lugares en las cámaras activas a
      esa hora (cupo = suma de capacidades).
    Puede lanzar ErrorBaseDatos.
    """
    fecha, hora = str(fecha).strip(), str(hora).strip()
    if en_camara:
        ocupados = bd.sesiones_en_camara(fecha, excluir_id_cita).get(hora, 0)
        return ocupados >= bd.cupo_camaras()
    return hora in bd.horas_ocupadas(int(id_odontologo), fecha, excluir_id_cita)


def consultar_disponibilidad(bd, sesion, id_odontologo, fecha, hoy=None,
                             excluir_id_cita=None, id_servicio=None):
    """Horarios libres de un especialista en una fecha (HU-12, HU-13).

    Si se indica un servicio que usa la cámara hiperbárica, la disponibilidad
    se calcula por cupo de cámara y se informa cuántos lugares quedan en cada
    horario ("lugares"). Sin servicio, o si es una consulta, se usa la regla
    del especialista.

    `excluir_id_cita` sirve al modificar una cita: su propio horario se
    muestra como libre para poder conservarlo.

    Devuelve {"exito", "mensaje", "libres", "ocupados", "especialista",
    "en_camara", "cupo", "lugares"}. La recepcionista también recibe los
    horarios ocupados; el paciente solo ve los libres.
    """
    resultado = {"exito": False, "mensaje": "", "libres": [], "ocupados": [],
                 "especialista": None, "en_camara": False, "cupo": None, "lugares": {}}

    permiso = verificar_permiso(sesion, "consultar_disponibilidad")
    if not permiso["exito"]:
        resultado["mensaje"] = permiso["mensaje"]
        return resultado

    error_fecha = validar_fecha(fecha, hoy)
    if error_fecha:
        resultado["mensaje"] = error_fecha
        return resultado

    try:
        especialista = obtener_especialista_activo(bd, id_odontologo)
        if especialista is None:
            resultado["mensaje"] = MENSAJE_ESPECIALISTA_INEXISTENTE
            return resultado
        en_camara = False
        if id_servicio not in (None, ""):
            servicio = obtener_servicio_activo(bd, id_servicio)
            if servicio is None:
                resultado["mensaje"] = MENSAJE_SERVICIO_NO_DISPONIBLE
                return resultado
            en_camara = bool(servicio["usa_camara"])
        if en_camara:
            cupo = bd.cupo_camaras()
            sesiones = bd.sesiones_en_camara(str(fecha).strip(), excluir_id_cita)
            ocupadas = {h for h, n in sesiones.items() if n >= cupo}
            resultado.update(en_camara=True, cupo=cupo)
            resultado["lugares"] = {h: max(cupo - sesiones.get(h, 0), 0)
                                    for h in horarios_del_dia()}
        else:
            ocupadas = set(bd.horas_ocupadas(especialista["id_odontologo"],
                                             str(fecha).strip(), excluir_id_cita))
    except ErrorBaseDatos as error:
        resultado["mensaje"] = error.mensaje
        return resultado

    todas = horarios_del_dia()
    if str(fecha).strip() == (hoy or date.today()).isoformat():
        ahora = datetime.now().strftime("%H:%M")
        todas = [h for h in todas if h > ahora]

    resultado["exito"] = True
    resultado["especialista"] = especialista
    resultado["libres"] = [h for h in todas if h not in ocupadas]
    if sesion.get("rol") == ROL_RECEPCIONISTA:
        resultado["ocupados"] = sorted(ocupadas)
    if resultado["en_camara"] and resultado["cupo"] == 0:
        resultado["libres"] = []
        resultado["mensaje"] = MENSAJE_SIN_CAMARAS
    elif not resultado["libres"]:
        resultado["mensaje"] = MENSAJE_SIN_HORARIOS.format(fecha=str(fecha).strip())
    return resultado


def fecha_de_manana():
    """Ayuda para la consola: fecha de mañana en formato AAAA-MM-DD."""
    return (date.today() + timedelta(days=1)).isoformat()

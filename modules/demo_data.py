"""Datos de demostración para probar el sistema de extremo a extremo.

Solo se cargan cuando la base no tiene usuarios. Las contraseñas son de
prueba para el entorno local; no son credenciales reales.
"""

from modules.auth_roles import registrar_usuario

ODONTOLOGOS_DEMO = (  # especialistas de demostración (nombres ficticios)
    ("Laura", "Peña Núñez", "Medicina hiperbárica"),
    ("Jorge", "Ruiz Campos", "Medicina del deporte"),
)

SERVICIOS_DEMO = (
    # (nombre, minutos, descripción, precio, ¿usa la cámara?)
    # Precios en None: se muestran como "A consultar" hasta que la clínica los defina.
    ("Valoración médica inicial", 30, "Historia clínica y plan de sesiones personalizado", None, False),
    ("Sesión de oxigenoterapia hiperbárica", 60, "Oxígeno al 100 % en cámara presurizada, de 50 a 60 minutos", None, True),
    ("Sesión de recuperación deportiva", 60, "Oxigenoterapia enfocada en lesiones y recuperación muscular", None, True),
    ("Revisión de avance", 30, "Seguimiento médico de la evolución del tratamiento", None, False),
)

# (nombre, lugares por sesión). Ajustable en Configuración.
CAMARAS_DEMO = (
    ("Cámara hiperbárica", 1),
)

PACIENTES_DEMO = (
    ("Ana", "Pérez Soto", "4431112233", "ana.perez@correo.com"),
    ("Luis", "Gómez Vega", "4434445566", None),
)

# (usuario, contraseña de prueba, rol, índice del paciente u especialista)
USUARIOS_DEMO = (
    ("recepcion01", "Recepcion#2026", "recepcionista", None),
    ("paciente01", "Paciente#2026", "paciente", 0),
    ("paciente02", "Paciente#2026", "paciente", 1),
    ("especialista01", "Especialista#2026", "especialista", 0),
    ("especialista02", "Especialista#2026", "especialista", 1),
)


def sembrar_datos_demo(bd):
    """Carga los datos de demostración si la base no tiene usuarios.

    Devuelve True si cargó los datos y False si ya existían.
    """
    if bd.contar_usuarios() > 0:
        return False

    ids_odontologo = [bd.insertar_odontologo(*o) for o in ODONTOLOGOS_DEMO]
    for nombre, duracion, descripcion, precio, camara in SERVICIOS_DEMO:
        bd.insertar_servicio(nombre, duracion, descripcion, precio, usa_camara=camara)
    for nombre, capacidad in CAMARAS_DEMO:
        bd.insertar_camara(nombre, capacidad)
    ids_paciente = [
        bd.insertar_paciente(nombre, apellidos, telefono, correo)
        for nombre, apellidos, telefono, correo in PACIENTES_DEMO
    ]

    for usuario, clave, rol, indice in USUARIOS_DEMO:
        registrar_usuario(
            bd, usuario, clave, rol,
            id_paciente=ids_paciente[indice] if rol == "paciente" else None,
            id_odontologo=ids_odontologo[indice] if rol == "especialista" else None,
        )
    return True

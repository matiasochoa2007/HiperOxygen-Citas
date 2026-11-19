"""Pruebas de M9 Configuración de la clínica (HiperOxygen).

Ejecutar desde la raíz del repositorio:
    py -m unittest tests.test_configuracion -v
"""

import unittest
from datetime import date

from modules.appointments import registrar_cita
from modules.auth_roles import iniciar_sesion
from modules.configuracion import (
    MENSAJE_CAPACIDAD_INVALIDA,
    MENSAJE_DURACION_INVALIDA,
    MENSAJE_PRECIO_INVALIDO,
    cambiar_estado_camara,
    cambiar_estado_especialista,
    cambiar_estado_servicio,
    consultar_configuracion,
    gestionar_acceso_especialista,
    guardar_camara,
    guardar_especialista,
    guardar_servicio,
)
from tests.utilidades import BaseTemporal

R = {"rol": "recepcionista"}
HOY = date(2030, 3, 1)


class EscenarioConfig(unittest.TestCase):
    def setUp(self):
        self.temp = BaseTemporal()
        self.bd = self.temp.bd

    def tearDown(self):
        self.temp.limpiar()


class PruebasCamaras(EscenarioConfig):
    def test_alta_edicion_y_cupo(self):
        r = guardar_camara(self.bd, R, {"nombre": "Cámara 1", "capacidad": "2"})
        self.assertTrue(r["exito"], r["mensaje"])
        self.assertIn("2 lugares", r["mensaje"])
        guardar_camara(self.bd, R, {"nombre": "Cámara 1 (multiplaza)", "capacidad": 4}, r["id"])
        self.assertEqual(self.bd.cupo_camaras(), 4)

    def test_validaciones(self):
        self.assertIn("'nombre'", guardar_camara(self.bd, R, {"capacidad": 1})["mensaje"])
        for mala in (0, 21, "dos"):
            self.assertEqual(guardar_camara(self.bd, R, {"nombre": "C", "capacidad": mala})["mensaje"],
                             MENSAJE_CAPACIDAD_INVALIDA)
        guardar_camara(self.bd, R, {"nombre": "C", "capacidad": 1})
        self.assertIn("Ya existe", guardar_camara(self.bd, R, {"nombre": "C", "capacidad": 1})["mensaje"])

    def test_desactivar_la_ultima_camara_avisa(self):
        id_camara = guardar_camara(self.bd, R, {"nombre": "C", "capacidad": 1})["id"]
        r = cambiar_estado_camara(self.bd, R, id_camara, False)
        self.assertTrue(r["mensaje"].startswith("Aviso"))
        self.assertEqual(cambiar_estado_camara(self.bd, R, id_camara, True)["cupo"], 1)


class PruebasEspecialistas(EscenarioConfig):
    def test_alta_acceso_e_inicio_de_sesion(self):
        id_e = guardar_especialista(self.bd, R, {"nombre": "Marta", "apellidos": "Gil",
                                                 "especialidad": "Medicina hiperbárica"})["id"]
        r = gestionar_acceso_especialista(self.bd, R, id_e, "marta.gil", "Oxigeno2030")
        self.assertTrue(r["exito"], r["mensaje"])
        sesion = iniciar_sesion(self.bd, "marta.gil", "Oxigeno2030")["sesion"]
        self.assertEqual((sesion["rol"], sesion["id_odontologo"]), ("especialista", id_e))

    def test_restablecer_contrasena_conserva_usuario(self):
        id_e = guardar_especialista(self.bd, R, {"nombre": "Marta", "apellidos": "Gil"})["id"]
        gestionar_acceso_especialista(self.bd, R, id_e, "marta.gil", "Oxigeno2030")
        r = gestionar_acceso_especialista(self.bd, R, id_e, "", "Nueva2030x")
        self.assertIn("restablecida", r["mensaje"])
        self.assertTrue(iniciar_sesion(self.bd, "marta.gil", "Nueva2030x")["exito"])

    def test_editar_y_validar(self):
        id_e = guardar_especialista(self.bd, R, {"nombre": "Marta", "apellidos": "Gil"})["id"]
        guardar_especialista(self.bd, R, {"nombre": "Marta", "apellidos": "Gil Luna"}, id_e)
        self.assertEqual(self.bd.obtener_odontologo(id_e)["apellidos"], "Gil Luna")
        self.assertIn("'apellidos'", guardar_especialista(self.bd, R, {"nombre": "X"})["mensaje"])

    def test_desactivar_avisa_citas_pendientes(self):
        id_e = guardar_especialista(self.bd, R, {"nombre": "Marta", "apellidos": "Gil"})["id"]
        id_s = guardar_servicio(self.bd, R, {"nombre": "Valoración", "duracion": 30})["id"]
        id_p = self.bd.insertar_paciente("Ana", "Pérez", "4431112233")
        registrar_cita(self.bd, R, {"paciente": id_p, "especialista": id_e, "servicio": id_s,
                                    "fecha": "2030-03-05", "hora": "10:00"}, hoy=HOY)
        r = cambiar_estado_especialista(self.bd, R, id_e, False, hoy=HOY)
        self.assertEqual(r["pendientes"], 1)
        self.assertEqual(self.bd.listar_odontologos(), [])


class PruebasServicios(EscenarioConfig):
    def test_alta_con_precio_y_camara(self):
        r = guardar_servicio(self.bd, R, {"nombre": "Sesión OHB", "duracion": "60",
                                          "precio": "$1,250.50", "usa_camara": True})
        self.assertTrue(r["exito"], r["mensaje"])
        servicio = self.bd.obtener_servicio(r["id"])
        self.assertEqual((servicio["precio"], servicio["usa_camara"]), (1250.5, 1))
        self.assertIn("en cámara", r["mensaje"])

    def test_precio_vacio_queda_a_consultar(self):
        r = guardar_servicio(self.bd, R, {"nombre": "Valoración", "duracion": 30, "precio": ""})
        self.assertIsNone(self.bd.obtener_servicio(r["id"])["precio"])

    def test_validaciones(self):
        self.assertEqual(guardar_servicio(self.bd, R, {"nombre": "X", "duracion": 1})["mensaje"],
                         MENSAJE_DURACION_INVALIDA)
        self.assertEqual(guardar_servicio(self.bd, R, {"nombre": "X", "duracion": 30, "precio": "-5"})["mensaje"],
                         MENSAJE_PRECIO_INVALIDO)
        guardar_servicio(self.bd, R, {"nombre": "X", "duracion": 30})
        self.assertIn("Ya existe", guardar_servicio(self.bd, R, {"nombre": "X", "duracion": 30})["mensaje"])

    def test_desactivar_y_reactivar(self):
        id_s = guardar_servicio(self.bd, R, {"nombre": "X", "duracion": 30})["id"]
        cambiar_estado_servicio(self.bd, R, id_s, False)
        self.assertEqual(self.bd.listar_servicios(), [])
        cambiar_estado_servicio(self.bd, R, id_s, True)
        self.assertEqual(len(self.bd.listar_servicios()), 1)


class PruebasPermisos(EscenarioConfig):
    def test_solo_recepcion_configura(self):
        for rol in ("paciente", "especialista"):
            sesion = {"rol": rol}
            self.assertFalse(consultar_configuracion(self.bd, sesion)["exito"])
            self.assertIn("no tiene permiso", guardar_camara(self.bd, sesion, {"nombre": "C", "capacidad": 1})["mensaje"])

    def test_resumen_de_configuracion(self):
        guardar_camara(self.bd, R, {"nombre": "C", "capacidad": 3})
        guardar_servicio(self.bd, R, {"nombre": "X", "duracion": 30})
        r = consultar_configuracion(self.bd, R)
        self.assertEqual((r["cupo"], len(r["camaras"]), len(r["servicios"])), (3, 1, 1))


if __name__ == "__main__":
    unittest.main()

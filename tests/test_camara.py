"""Pruebas de la regla de cupo por cámara hiperbárica (HiperOxygen).

- Las sesiones en cámara se limitan por la capacidad total de las cámaras
  activas, sin importar el especialista.
- Las consultas (sin cámara) conservan la regla de un especialista por horario.

Ejecutar desde la raíz del repositorio:
    py -m unittest tests.test_camara -v
"""

import sqlite3
import unittest
from datetime import date

from modules.appointments import cancelar_cita, modificar_cita, registrar_cita
from modules.availability import MENSAJE_SIN_CAMARAS, consultar_disponibilidad
from modules.data_access import BaseDatos, ErrorCupoLleno
from modules.service_catalog import consultar_catalogo
from modules.validation_messages import MENSAJE_HORARIO_OCUPADO
from tests.utilidades import BaseTemporal

FECHA = "2030-03-04"
HOY = date(2030, 3, 1)
RECEPCION = {"rol": "recepcionista"}


class EscenarioCamara(unittest.TestCase):
    def setUp(self):
        self.temp = BaseTemporal()
        bd = self.bd = self.temp.bd
        self.pacientes = [bd.insertar_paciente(f"P{i}", "Prueba", f"44300000{i:02d}") for i in range(4)]
        self.e1 = bd.insertar_odontologo("Laura", "Peña", "Medicina hiperbárica")
        self.e2 = bd.insertar_odontologo("Jorge", "Ruiz", "Medicina del deporte")
        self.sesion = bd.insertar_servicio("Sesión OHB", 60, usa_camara=True)
        self.consulta = bd.insertar_servicio("Valoración", 30)
        self.camara = bd.insertar_camara("Cámara 1", 2)

    def tearDown(self):
        self.temp.limpiar()

    def agendar(self, paciente, hora="10:00", especialista=None, servicio=None):
        return registrar_cita(self.bd, RECEPCION, {
            "paciente": self.pacientes[paciente], "especialista": especialista or self.e1,
            "servicio": servicio or self.sesion, "fecha": FECHA, "hora": hora}, hoy=HOY)


class PruebasCupo(EscenarioCamara):
    def test_varios_pacientes_con_el_mismo_especialista_hasta_el_cupo(self):
        self.assertTrue(self.agendar(0)["exito"])
        self.assertTrue(self.agendar(1)["exito"])
        tercero = self.agendar(2)
        self.assertFalse(tercero["exito"])
        self.assertEqual(tercero["mensaje"], MENSAJE_HORARIO_OCUPADO)

    def test_el_cupo_es_de_la_camara_no_del_especialista(self):
        self.assertTrue(self.agendar(0, especialista=self.e1)["exito"])
        self.assertTrue(self.agendar(1, especialista=self.e2)["exito"])
        self.assertFalse(self.agendar(2, especialista=self.e2)["exito"])

    def test_cancelar_libera_un_lugar(self):
        primera = self.agendar(0)["id_cita"]
        self.agendar(1)
        cancelar_cita(self.bd, RECEPCION, primera)
        self.assertTrue(self.agendar(2)["exito"])

    def test_disponibilidad_informa_lugares(self):
        self.agendar(0)
        r = consultar_disponibilidad(self.bd, RECEPCION, self.e2, FECHA, hoy=HOY, id_servicio=self.sesion)
        self.assertTrue(r["en_camara"])
        self.assertEqual((r["cupo"], r["lugares"]["10:00"], r["lugares"]["11:00"]), (2, 1, 2))
        self.agendar(1)
        r = consultar_disponibilidad(self.bd, RECEPCION, self.e2, FECHA, hoy=HOY, id_servicio=self.sesion)
        self.assertNotIn("10:00", r["libres"])
        self.assertEqual(r["ocupados"], ["10:00"])

    def test_cupo_suma_solo_camaras_activas(self):
        self.bd.insertar_camara("Cámara 2", 3)
        self.assertEqual(self.bd.cupo_camaras(), 5)
        self.bd.cambiar_estado_camara(self.camara, False)
        self.assertEqual(self.bd.cupo_camaras(), 3)

    def test_sin_camaras_activas_no_hay_sesiones(self):
        self.bd.cambiar_estado_camara(self.camara, False)
        r = consultar_disponibilidad(self.bd, RECEPCION, self.e1, FECHA, hoy=HOY, id_servicio=self.sesion)
        self.assertEqual((r["libres"], r["mensaje"]), ([], MENSAJE_SIN_CAMARAS))
        self.assertFalse(self.agendar(0)["exito"])

    def test_la_base_impide_rebasar_el_cupo_aunque_se_salte_la_validacion(self):
        for i in range(2):
            self.bd.insertar_cita(FECHA, "12:00", self.pacientes[i], self.e1, self.sesion,
                                  en_camara=True, cupo=2)
        with self.assertRaises(ErrorCupoLleno):
            self.bd.insertar_cita(FECHA, "12:00", self.pacientes[2], self.e1, self.sesion,
                                  en_camara=True, cupo=2)


class PruebasConsultas(EscenarioCamara):
    def test_consultas_siguen_siendo_una_por_especialista(self):
        self.assertTrue(self.agendar(0, servicio=self.consulta)["exito"])
        self.assertFalse(self.agendar(1, servicio=self.consulta)["exito"])
        self.assertTrue(self.agendar(1, servicio=self.consulta, especialista=self.e2)["exito"])

    def test_consulta_y_sesion_en_camara_no_se_estorban(self):
        self.agendar(0, servicio=self.consulta)
        self.assertTrue(self.agendar(1)["exito"])
        self.assertTrue(self.agendar(2)["exito"])
        self.assertEqual(self.bd.sesiones_en_camara(FECHA), {"10:00": 2})


class PruebasModificar(EscenarioCamara):
    def test_mover_a_horario_lleno_se_rechaza_y_a_libre_se_permite(self):
        self.agendar(0, "10:00"); self.agendar(1, "10:00")
        otra = self.agendar(2, "11:00")["id_cita"]
        r = modificar_cita(self.bd, RECEPCION, otra, {"hora": "10:00"}, hoy=HOY)
        self.assertEqual(r["mensaje"], MENSAJE_HORARIO_OCUPADO)
        self.assertTrue(modificar_cita(self.bd, RECEPCION, otra, {"hora": "12:00"}, hoy=HOY)["exito"])

    def test_cambiar_consulta_a_sesion_respeta_el_cupo(self):
        self.agendar(0); self.agendar(1)
        consulta = self.agendar(2, servicio=self.consulta, especialista=self.e2)["id_cita"]
        r = modificar_cita(self.bd, RECEPCION, consulta, {"servicio": self.sesion}, hoy=HOY)
        self.assertFalse(r["exito"])
        r = modificar_cita(self.bd, RECEPCION, consulta, {"servicio": self.sesion, "hora": "13:00"}, hoy=HOY)
        self.assertTrue(r["exito"], r["mensaje"])
        self.assertEqual(self.bd.obtener_cita(consulta)["en_camara"], 1)


class PruebasServiciosInactivos(EscenarioCamara):
    def test_servicio_inactivo_no_se_agenda_ni_aparece_en_catalogo(self):
        self.bd.cambiar_estado_servicio(self.consulta, False)
        self.assertIn("no existe", self.agendar(0, servicio=self.consulta)["mensaje"])
        nombres = [s["nombre"] for s in consultar_catalogo(self.bd, RECEPCION)["servicios"]]
        self.assertEqual(nombres, ["Sesión OHB"])

    def test_cita_existente_conserva_servicio_que_se_desactivo(self):
        cita = self.agendar(0)["id_cita"]
        self.bd.cambiar_estado_servicio(self.sesion, False)
        r = modificar_cita(self.bd, RECEPCION, cita, {"hora": "15:00"}, hoy=HOY)
        self.assertTrue(r["exito"], r["mensaje"])


class PruebasMigracion(unittest.TestCase):
    def test_base_anterior_se_actualiza_sin_perder_datos(self):
        temp = BaseTemporal()
        temp.bd.cerrar()
        con = sqlite3.connect(temp.ruta)
        con.executescript("""
            DROP INDEX IF EXISTS ux_consulta_especialista_horario;
            DROP INDEX IF EXISTS ix_cita_camara_horario;
            DROP TABLE cita; DROP TABLE servicio; DROP TABLE camara;
            CREATE TABLE servicio (id_servicio INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE,
                descripcion TEXT, duracion_min INTEGER NOT NULL, precio REAL);
            CREATE TABLE cita (id_cita INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, hora TEXT NOT NULL,
                motivo TEXT, estatus TEXT NOT NULL DEFAULT 'Programada', id_paciente INTEGER NOT NULL,
                id_odontologo INTEGER NOT NULL, id_servicio INTEGER NOT NULL);
            CREATE UNIQUE INDEX ux_cita_odontologo_horario ON cita (id_odontologo, fecha, hora)
                WHERE estatus <> 'Cancelada';
            INSERT INTO servicio (nombre, duracion_min) VALUES ('Antiguo', 30);
        """)
        con.commit(); con.close()
        try:
            bd = BaseDatos(temp.ruta)
            bd.inicializar()
            servicio = bd.listar_servicios()[0]
            self.assertEqual((servicio["nombre"], servicio["activo"], servicio["usa_camara"]), ("Antiguo", 1, 0))
            indices = {f["name"] for f in bd._consultar("SELECT name FROM sqlite_master WHERE type = 'index'")}
            self.assertNotIn("ux_cita_odontologo_horario", indices)
            self.assertIn("ux_consulta_especialista_horario", indices)
            self.assertIn("camara", bd.tablas())
            bd.cerrar()
        finally:
            temp.limpiar()


if __name__ == "__main__":
    unittest.main()

# HiperOxygen · Sistema de citas

Aplicación de escritorio para Windows para agendar sesiones de **oxigenoterapia hiperbárica**:
los pacientes crean su cuenta y agendan en cinco pasos, recepción administra pacientes, accesos y la
agenda completa, y cada especialista ve su jornada. Los datos se guardan en SQLite, en la propia
computadora de la clínica.

Es una adaptación del sistema de citas desarrollado para Orthoimagen Dental: **misma lógica y mismas
reglas** (sin citas empalmadas por especialista, cancelar conserva el historial, eliminar solo desde
recepción), con la marca, colores y estilo de [hiperoxygen.com](https://www.hiperoxygen.com/).

## Qué cambia respecto a Orthoimagen Dental

| Aspecto | HiperOxygen |
|---------|-------------|
| Marca | Nombre, ícono de molécula de oxígeno y textos de oxigenoterapia hiperbárica |
| Colores | Azul profundo `#07496f`, azul `#18719a`, aqua `#1e8bb1`, acento verde `#25b577` |
| Estilo | Botones en píldora, degradado azul → aqua, títulos muy gruesos en azul profundo, sombras azuladas |
| Tipografía | Inter (la del sitio) si está instalada; si no, Segoe UI de Windows |
| Terminología | "Especialista" en lugar de "dentista" |
| Servicios de ejemplo | Valoración médica inicial, sesión de oxigenoterapia hiperbárica, sesión de recuperación deportiva y revisión de avance; precios "A consultar" |

Los especialistas, pacientes y precios de ejemplo son **ficticios**: antes de usarla en la clínica
hay que cargar sus datos reales.

## Cómo ejecutar

**Ejecutable:** doble clic en `HiperOxygen.exe` (Windows 10/11). La base se crea en la carpeta `data`,
junto al `.exe`. La primera vez, Windows SmartScreen puede advertir que no está firmado: *Más
información → Ejecutar de todas formas*.

**Desde el código** (Python 3.10 o superior):

```powershell
py -m pip install -r requirements.txt
```

```powershell
py app_escritorio.py
```

**Consola:** `py main.py` · **Navegador (desarrollo):** `py -m interfaz.servidor_dev` → http://127.0.0.1:8765

Variables de entorno: `HIPEROXYGEN_BD` cambia la ruta de la base; `HIPEROXYGEN_DEMO=0` oculta los
botones de usuarios de demostración.

### Usuarios de demostración (solo entorno local)

| Usuario | Contraseña | Rol |
|---------|-----------|-----|
| `recepcion01` | `Recepcion#2026` | recepcionista |
| `paciente01` | `Paciente#2026` | paciente (Ana Pérez Soto) |
| `especialista01` | `Especialista#2026` | especialista (Laura Peña Núñez) |

## Pruebas y ejecutable

```powershell
py -m unittest discover -v
```

Resultado actual: **177 pruebas, 0 fallidas**.

```powershell
powershell -ExecutionPolicy Bypass -File construir_exe.ps1
```

Genera `dist\HiperOxygen.exe`.

## Estructura

```
app_escritorio.py        Ventana nativa (pywebview + WebView2)
interfaz/web/            Interfaz con el estilo de HiperOxygen (estilos.css, app.js, logo.svg)
interfaz/api.py          Puente interfaz ↔ módulos
main.py                  Versión de consola
modules/                 Lógica: citas, disponibilidad, agenda, pacientes, acceso a datos, mensajes
tests/                   177 pruebas automáticas
assets/hiperoxygen.ico   Ícono de la aplicación
```

Nota técnica: internamente la tabla de especialistas conserva el nombre `odontologo` heredado del
proyecto original; no es visible para el usuario.

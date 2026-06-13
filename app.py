from flask import Flask, render_template, request, jsonify, session
import sqlite3
from datetime import datetime, time
import math
import pytz
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "kukulcan_asistencia_2026")

DB_NAME = "asistencias.db"
ZONA_CANCUN = pytz.timezone("America/Cancun")

# Coordenadas aproximadas de sucursal. Ajustamos después si se requiere.
CENTER_LAT = 21.131
CENTER_LON = -86.891
MAX_DISTANCE_KM = 1.0

TARIFA_HORA_EXTRA = 50.00

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def hora_cancun():
    ahora_utc = datetime.now(pytz.utc)
    ahora_cancun = ahora_utc.astimezone(ZONA_CANCUN)
    return ahora_cancun.strftime("%Y-%m-%d"), ahora_cancun.strftime("%H:%M:%S")


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS colaboradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            pin TEXT NOT NULL,
            puesto TEXT DEFAULT '',
            activo INTEGER DEFAULT 1,
            fecha_alta TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            lat REAL,
            lon REAL
        )
    """)

    # Por si existe una base vieja, agrega columnas faltantes sin borrar datos.
    columnas = conn.execute("PRAGMA table_info(colaboradores)").fetchall()
    columnas = [c["name"] for c in columnas]

    if "pin" not in columnas:
        conn.execute("ALTER TABLE colaboradores ADD COLUMN pin TEXT DEFAULT '0000'")
    if "puesto" not in columnas:
        conn.execute("ALTER TABLE colaboradores ADD COLUMN puesto TEXT DEFAULT ''")
    if "activo" not in columnas:
        conn.execute("ALTER TABLE colaboradores ADD COLUMN activo INTEGER DEFAULT 1")
    if "fecha_alta" not in columnas:
        conn.execute("ALTER TABLE colaboradores ADD COLUMN fecha_alta TEXT DEFAULT ''")

    fecha, _ = hora_cancun()

    colaboradores_base = [
        ("Emilio Rojas", "1234", "Administrativo"),
        ("Eric Gutiérrez", "2345", "Operativo"),
        ("Rutilo Pérez", "3456", "Operativo"),
        ("Ángel Pérez", "4567", "Operativo")
    ]

    for nombre, pin, puesto in colaboradores_base:
        existe = conn.execute(
            "SELECT id FROM colaboradores WHERE nombre = ?",
            (nombre,)
        ).fetchone()

        if not existe:
            conn.execute("""
                INSERT INTO colaboradores (nombre, pin, puesto, activo, fecha_alta)
                VALUES (?, ?, ?, 1, ?)
            """, (nombre, pin, puesto, fecha))

    conn.commit()
    conn.close()


def obtener_data():
    return request.get_json(silent=True) or request.form or {}


def convertir_hora(hora_texto):
    try:
        return datetime.strptime(hora_texto, "%H:%M:%S").time()
    except Exception:
        return datetime.strptime(hora_texto, "%H:%M").time()


def segundos_a_horas(segundos):
    return round(segundos / 3600, 2)


def segundos_a_texto(segundos):
    segundos = int(segundos)
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    return f"{horas}h {minutos}m"


def obtener_horario_autorizado(fecha_obj):
    dia = fecha_obj.weekday()

    if dia in [0, 1, 2, 3, 4]:
        return time(8, 0, 0), time(17, 0, 0), "Lunes a viernes"
    if dia == 5:
        return time(8, 0, 0), time(12, 0, 0), "Sábado"

    return None, None, "Domingo / descanso"


def calcular_extra_por_dia(fecha_texto, entrada_texto, salida_texto):
    if not entrada_texto or not salida_texto:
        return {
            "segundos_extra": 0,
            "horas_extra": 0,
            "extra_texto": "0h 0m",
            "importe": 0,
            "detalle": "Pendiente: falta entrada o salida"
        }

    fecha_obj = datetime.strptime(fecha_texto, "%Y-%m-%d").date()
    entrada = convertir_hora(entrada_texto)
    salida = convertir_hora(salida_texto)

    dt_entrada = datetime.combine(fecha_obj, entrada)
    dt_salida = datetime.combine(fecha_obj, salida)

    if dt_salida <= dt_entrada:
        return {
            "segundos_extra": 0,
            "horas_extra": 0,
            "extra_texto": "0h 0m",
            "importe": 0,
            "detalle": "Revisar: salida menor o igual a entrada"
        }

    inicio, fin, _ = obtener_horario_autorizado(fecha_obj)
    segundos_extra = 0
    detalle = []

    if fecha_obj.weekday() == 6:
        segundos_extra = int((dt_salida - dt_entrada).total_seconds())
        detalle.append("Domingo descanso: todo el tiempo trabajado cuenta como extra")
    else:
        dt_inicio = datetime.combine(fecha_obj, inicio)
        dt_fin = datetime.combine(fecha_obj, fin)

        if dt_entrada < dt_inicio:
            extra_antes = int((dt_inicio - dt_entrada).total_seconds())
            segundos_extra += extra_antes
            detalle.append(f"Antes de horario: {segundos_a_texto(extra_antes)}")

        if dt_salida > dt_fin:
            extra_despues = int((dt_salida - dt_fin).total_seconds())
            segundos_extra += extra_despues
            detalle.append(f"Después de horario: {segundos_a_texto(extra_despues)}")

    horas_extra = segundos_a_horas(segundos_extra)
    importe = round(horas_extra * TARIFA_HORA_EXTRA, 2)

    if not detalle:
        detalle.append("Sin horas extra")

    return {
        "segundos_extra": segundos_extra,
        "horas_extra": horas_extra,
        "extra_texto": segundos_a_texto(segundos_extra),
        "importe": importe,
        "detalle": " | ".join(detalle)
    }


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def validar_admin():
    return bool(session.get("admin"))


def obtener_colaboradores_activos():
    conn = get_db()
    colaboradores = conn.execute("""
        SELECT nombre
        FROM colaboradores
        WHERE activo = 1
        ORDER BY nombre ASC
    """).fetchall()
    conn.close()
    return [c["nombre"] for c in colaboradores]


@app.route("/")
def index():
    return render_template("index.html", colaboradores=obtener_colaboradores_activos())


@app.route("/admin")
def admin_page():
    return render_template("admin.html", admin_iniciado=validar_admin())


@app.route("/login", methods=["POST"])
@app.route("/login_colaborador", methods=["POST"])
def login_colaborador():
    data = obtener_data()
    nombre = data.get("nombre", "").strip()
    pin = data.get("pin", "").strip()

    conn = get_db()
    colaborador = conn.execute("""
        SELECT *
        FROM colaboradores
        WHERE nombre = ? AND pin = ? AND activo = 1
    """, (nombre, pin)).fetchone()
    conn.close()

    if colaborador:
        session["usuario"] = nombre
        session["colaborador_id"] = colaborador["id"]
        return jsonify({
            "success": True,
            "exito": True,
            "mensaje": "Inicio de sesión correcto",
            "nombre": nombre
        })

    return jsonify({
        "success": False,
        "exito": False,
        "mensaje": "Usuario o PIN incorrecto, o colaborador inactivo"
    })


@app.route("/logout")
def logout():
    session.pop("usuario", None)
    session.pop("colaborador_id", None)
    return jsonify({"success": True, "exito": True, "mensaje": "Sesión cerrada correctamente"})


@app.route("/registrar", methods=["POST"])
def registrar():
    if "usuario" not in session:
        return jsonify({
            "success": False,
            "exito": False,
            "mensaje": "Sesión no iniciada. Vuelve a ingresar."
        })

    data = obtener_data()
    tipo = data.get("tipo", "").strip().lower()
    auto = bool(data.get("auto", False))

    if tipo not in ["entrada", "salida"]:
        return jsonify({"success": False, "exito": False, "mensaje": "Tipo de registro inválido"})

    try:
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
    except Exception:
        return jsonify({"success": False, "exito": False, "mensaje": "No se pudo obtener ubicación válida"})

    distancia = haversine(lat, lon, CENTER_LAT, CENTER_LON)

    if False and distancia > MAX_DISTANCE_KM:
        return jsonify({
            "success": False,
            "exito": False,
            "mensaje": "Estás fuera del área permitida para registrar asistencia"
        })

    nombre = session["usuario"]
    fecha, hora = hora_cancun()

    conn = get_db()

    registros_hoy = conn.execute("""
        SELECT *
        FROM registros
        WHERE nombre = ? AND fecha = ?
        ORDER BY hora ASC
    """, (nombre, fecha)).fetchall()

    ultimo = registros_hoy[-1] if registros_hoy else None

    if auto and tipo == "entrada" and registros_hoy:
        conn.close()
        return jsonify({
            "success": True,
            "exito": True,
            "mensaje": "Ya existe un marcaje de hoy. No se duplicó la entrada automática."
        })

    if ultimo and ultimo["tipo"] == tipo:
        conn.close()
        return jsonify({
            "success": False,
            "exito": False,
            "mensaje": f"La última marca ya fue {tipo}. No se duplicó el registro."
        })

    conn.execute("""
        INSERT INTO registros (nombre, tipo, fecha, hora, lat, lon)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nombre, tipo, fecha, hora, lat, lon))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "exito": True,
        "mensaje": f"{tipo.capitalize()} registrada correctamente a las {hora}",
        "nombre": nombre,
        "tipo": tipo,
        "fecha": fecha,
        "hora": hora
    })


@app.route("/admin/login", methods=["POST"])
@app.route("/admin_login", methods=["POST"])
def admin_login():
    data = obtener_data()

    usuario = (
        data.get("usuario")
        or data.get("adminUsuario")
        or data.get("admin_user")
        or ""
    ).strip()

    password = (
        data.get("password")
        or data.get("adminPassword")
        or data.get("admin_password")
        or ""
    ).strip()

    if usuario == ADMIN_USER and password == ADMIN_PASS:
        session["admin"] = True
        return jsonify({"success": True, "exito": True, "mensaje": "Administrador autorizado"})

    return jsonify({"success": False, "exito": False, "mensaje": "Datos de administrador incorrectos"})


@app.route("/admin/logout")
@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    return jsonify({"success": True, "exito": True, "mensaje": "Administrador cerrado correctamente"})


@app.route("/admin/colaboradores")
@app.route("/admin_colaboradores")
def admin_colaboradores():
    if not validar_admin():
        return jsonify({"success": False, "exito": False, "mensaje": "No autorizado"})

    conn = get_db()
    colaboradores = conn.execute("""
        SELECT *
        FROM colaboradores
        ORDER BY activo DESC, nombre ASC
    """).fetchall()
    conn.close()

    resultado = []
    for c in colaboradores:
        resultado.append({
            "id": c["id"],
            "nombre": c["nombre"],
            "pin": c["pin"],
            "puesto": c["puesto"],
            "activo": c["activo"],
            "fecha_alta": c["fecha_alta"]
        })

    return jsonify({"success": True, "exito": True, "colaboradores": resultado})


@app.route("/admin/colaboradores/agregar", methods=["POST"])
@app.route("/admin_colaboradores_agregar", methods=["POST"])
def agregar_colaborador():
    if not validar_admin():
        return jsonify({"success": False, "exito": False, "mensaje": "No autorizado"})

    data = obtener_data()
    nombre = data.get("nombre", "").strip()
    pin = data.get("pin", "").strip()
    puesto = data.get("puesto", "").strip()

    if not nombre or not pin:
        return jsonify({"success": False, "exito": False, "mensaje": "Nombre y PIN son obligatorios"})

    fecha, _ = hora_cancun()

    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO colaboradores (nombre, pin, puesto, activo, fecha_alta)
            VALUES (?, ?, ?, 1, ?)
        """, (nombre, pin, puesto, fecha))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "exito": True, "mensaje": "Colaborador agregado correctamente"})

    except sqlite3.IntegrityError:
        return jsonify({"success": False, "exito": False, "mensaje": "Ese colaborador ya existe"})


@app.route("/admin/colaboradores/toggle/<int:colaborador_id>", methods=["POST"])
@app.route("/admin_colaboradores_toggle/<int:colaborador_id>", methods=["POST"])
def toggle_colaborador(colaborador_id):
    if not validar_admin():
        return jsonify({"success": False, "exito": False, "mensaje": "No autorizado"})

    conn = get_db()
    colaborador = conn.execute("SELECT * FROM colaboradores WHERE id = ?", (colaborador_id,)).fetchone()

    if not colaborador:
        conn.close()
        return jsonify({"success": False, "exito": False, "mensaje": "Colaborador no encontrado"})

    nuevo_estado = 0 if colaborador["activo"] == 1 else 1

    conn.execute("UPDATE colaboradores SET activo = ? WHERE id = ?", (nuevo_estado, colaborador_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "exito": True, "mensaje": "Estado actualizado correctamente"})


@app.route("/admin/colaboradores/pin/<int:colaborador_id>", methods=["POST"])
@app.route("/admin_colaboradores_pin/<int:colaborador_id>", methods=["POST"])
def cambiar_pin(colaborador_id):
    if not validar_admin():
        return jsonify({"success": False, "exito": False, "mensaje": "No autorizado"})

    data = obtener_data()
    nuevo_pin = data.get("pin", "").strip()

    if not nuevo_pin:
        return jsonify({"success": False, "exito": False, "mensaje": "El PIN no puede ir vacío"})

    conn = get_db()
    conn.execute("UPDATE colaboradores SET pin = ? WHERE id = ?", (nuevo_pin, colaborador_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "exito": True, "mensaje": "PIN actualizado correctamente"})


@app.route("/admin/estado-sucursal")
@app.route("/admin_estado_sucursal")
def estado_sucursal():
    if not validar_admin():
        return jsonify({"success": False, "exito": False, "mensaje": "No autorizado"})

    fecha, _ = hora_cancun()

    conn = get_db()
    colaboradores = conn.execute("""
        SELECT *
        FROM colaboradores
        WHERE activo = 1
        ORDER BY nombre ASC
    """).fetchall()

    resultado = []
    for c in colaboradores:
        ultimo = conn.execute("""
            SELECT *
            FROM registros
            WHERE nombre = ? AND fecha = ?
            ORDER BY hora DESC
            LIMIT 1
        """, (c["nombre"], fecha)).fetchone()

        if not ultimo:
            estado = "Sin registro"
            hora = ""
            tipo = ""
        elif ultimo["tipo"] == "entrada":
            estado = "En sucursal"
            hora = ultimo["hora"]
            tipo = "entrada"
        else:
            estado = "Salida registrada"
            hora = ultimo["hora"]
            tipo = "salida"

        resultado.append({
            "nombre": c["nombre"],
            "puesto": c["puesto"],
            "estado": estado,
            "hora": hora,
            "tipo": tipo
        })

    conn.close()
    return jsonify({"success": True, "exito": True, "fecha": fecha, "estado": resultado})


@app.route("/admin/registros")
@app.route("/admin_registros")
def admin_registros():
    if not validar_admin():
        return jsonify({"success": False, "exito": False, "mensaje": "No autorizado"})

    conn = get_db()
    registros = conn.execute("""
        SELECT *
        FROM registros
        ORDER BY fecha DESC, hora DESC
    """).fetchall()
    conn.close()

    resultado = []
    for r in registros:
        resultado.append({
            "id": r["id"],
            "nombre": r["nombre"],
            "tipo": r["tipo"],
            "fecha": r["fecha"],
            "hora": r["hora"],
            "lat": r["lat"],
            "lon": r["lon"]
        })

    return jsonify({"success": True, "exito": True, "registros": resultado})


@app.route("/admin/horas-extra")
@app.route("/admin_horas_extra")
def admin_horas_extra():
    if not validar_admin():
        return jsonify({"success": False, "exito": False, "mensaje": "No autorizado"})

    conn = get_db()
    registros = conn.execute("""
        SELECT nombre, tipo, fecha, hora
        FROM registros
        ORDER BY fecha ASC, nombre ASC, hora ASC
    """).fetchall()
    conn.close()

    agrupado = {}

    for r in registros:
        clave = (r["nombre"], r["fecha"])

        if clave not in agrupado:
            agrupado[clave] = {"nombre": r["nombre"], "fecha": r["fecha"], "marcajes": []}

        agrupado[clave]["marcajes"].append({"tipo": r["tipo"], "hora": r["hora"]})

    resumen = []
    total_segundos_extra = 0
    total_importe = 0

    for _, datos in agrupado.items():
        marcajes = sorted(datos["marcajes"], key=lambda x: x["hora"])

        if len(marcajes) == 0:
            entrada = ""
            salida = ""
            detalle_marcajes = "Sin marcajes"
        elif len(marcajes) == 1:
            entrada = marcajes[0]["hora"]
            salida = ""
            detalle_marcajes = "Pendiente: solo existe un marcaje en el día"
        else:
            entrada = marcajes[0]["hora"]
            salida = marcajes[-1]["hora"]

            if len(marcajes) > 2:
                detalle_marcajes = (
                    f"Primer marcaje tomado como entrada y último como salida. "
                    f"Marcajes intermedios ignorados: {len(marcajes) - 2}"
                )
            else:
                detalle_marcajes = "Primer marcaje tomado como entrada y último como salida"

        calculo = calcular_extra_por_dia(datos["fecha"], entrada, salida)

        total_segundos_extra += calculo["segundos_extra"]
        total_importe += calculo["importe"]

        fecha_obj = datetime.strptime(datos["fecha"], "%Y-%m-%d").date()
        _, _, tipo_dia = obtener_horario_autorizado(fecha_obj)

        resumen.append({
            "nombre": datos["nombre"],
            "fecha": datos["fecha"],
            "tipo_dia": tipo_dia,
            "entrada": entrada or "Sin entrada",
            "salida": salida or "Sin salida",
            "total_marcajes": len(marcajes),
            "horas_extra": calculo["horas_extra"],
            "extra_texto": calculo["extra_texto"],
            "importe": calculo["importe"],
            "detalle": calculo["detalle"] + " | " + detalle_marcajes
        })

    resumen.sort(key=lambda x: (x["fecha"], x["nombre"]), reverse=True)

    return jsonify({
        "success": True,
        "exito": True,
        "tarifa": TARIFA_HORA_EXTRA,
        "total_horas_extra": segundos_a_horas(total_segundos_extra),
        "total_extra_texto": segundos_a_texto(total_segundos_extra),
        "total_importe": round(total_importe, 2),
        "resumen": resumen
    })


@app.route("/admin/eliminar/<int:registro_id>", methods=["DELETE"])
@app.route("/admin_eliminar/<int:registro_id>", methods=["DELETE"])
def eliminar_registro(registro_id):
    if not validar_admin():
        return jsonify({"success": False, "exito": False, "mensaje": "No autorizado"})

    conn = get_db()
    conn.execute("DELETE FROM registros WHERE id = ?", (registro_id,))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "exito": True, "mensaje": "Registro eliminado correctamente"})


init_db()

if __name__ == "__main__":
    app.run(debug=True)

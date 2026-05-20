from flask import Flask, render_template, request, jsonify, session, Response
import sqlite3
from datetime import datetime
import math
import csv
import io

app = Flask(__name__)
app.secret_key = "kukulcan2025"

CENTER_LAT = 21.045218
CENTER_LON = -86.850981
MAX_DISTANCE_KM = 1.0

ADMIN_USER = "admin"
ADMIN_PASSWORD = "1234"
JORNADA_HORAS = 8


def get_db():
    conn = sqlite3.connect("asistencias.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS colaboradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            pin TEXT,
            puesto TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            tipo TEXT,
            fecha TEXT,
            hora TEXT,
            lat REAL,
            lon REAL
        )
    """)

    base = [
        ("Emilio Rojas", "1234", "Supervisor"),
        ("Eric Gutiérrez", "2345", "Operador"),
        ("Rutilo Pérez", "3456", "Auxiliar"),
        ("Ángel Pérez", "4567", "Montacarguista")
    ]

    for nombre, pin, puesto in base:
        conn.execute("""
            INSERT OR IGNORE INTO colaboradores (nombre, pin, puesto)
            VALUES (?, ?, ?)
        """, (nombre, pin, puesto))

    conn.commit()
    conn.close()


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


def obtener_colaboradores():
    conn = get_db()
    colaboradores = conn.execute("""
        SELECT * FROM colaboradores ORDER BY nombre ASC
    """).fetchall()
    conn.close()
    return colaboradores


def generar_resumen():
    conn = get_db()

    registros = conn.execute("""
        SELECT r.*, c.puesto
        FROM registros r
        LEFT JOIN colaboradores c ON r.nombre = c.nombre
        ORDER BY r.fecha DESC, r.hora ASC
    """).fetchall()

    conn.close()

    agrupados = {}

    for r in registros:
        clave = f"{r['nombre']}_{r['fecha']}"

        if clave not in agrupados:
            agrupados[clave] = {
                "nombre": r["nombre"],
                "puesto": r["puesto"] or "-",
                "fecha": r["fecha"],
                "entrada": "",
                "salida": "",
                "entrada_id": "",
                "salida_id": ""
            }

        if r["tipo"] == "entrada":
            agrupados[clave]["entrada"] = r["hora"]
            agrupados[clave]["entrada_id"] = r["id"]

        if r["tipo"] == "salida":
            agrupados[clave]["salida"] = r["hora"]
            agrupados[clave]["salida_id"] = r["id"]

    resumen = []

    for item in agrupados.values():
        entrada = item["entrada"]
        salida = item["salida"]

        horas_trabajadas = "-"
        horas_extra = "-"

        if entrada and salida:
            h1 = datetime.strptime(entrada, "%H:%M")
            h2 = datetime.strptime(salida, "%H:%M")

            diferencia = h2 - h1
            horas = diferencia.seconds / 3600

            horas_trabajadas = round(horas, 2)
            horas_extra = round(max(0, horas - JORNADA_HORAS), 2)

        resumen.append({
            "nombre": item["nombre"],
            "puesto": item["puesto"],
            "fecha": item["fecha"],
            "entrada": entrada,
            "salida": salida,
            "entrada_id": item["entrada_id"],
            "salida_id": item["salida_id"],
            "horas_trabajadas": horas_trabajadas,
            "horas_extra": horas_extra
        })

    return resumen


init_db()


@app.route("/")
def index():
    colaboradores = obtener_colaboradores()
    return render_template("index.html", colaboradores=colaboradores)


@app.route("/empleados")
def empleados():
    colaboradores = obtener_colaboradores()
    return jsonify([dict(c) for c in colaboradores])


@app.route("/login", methods=["POST"])
def login():
    nombre = request.form.get("nombre")
    pin = request.form.get("pin")

    conn = get_db()

    colaborador = conn.execute("""
        SELECT * FROM colaboradores WHERE nombre = ? AND pin = ?
    """, (nombre, pin)).fetchone()

    conn.close()

    if colaborador:
        session["nombre"] = nombre
        return jsonify({"success": True})

    return jsonify({
        "success": False,
        "message": "Nombre o PIN incorrecto"
    })


@app.route("/registrar", methods=["POST"])
def registrar():
    if "nombre" not in session:
        return jsonify({
            "success": False,
            "message": "No has iniciado sesión"
        })

    nombre = session["nombre"]
    tipo = request.form.get("tipo")
    lat = request.form.get("lat")
    lon = request.form.get("lon")

    if tipo not in ["entrada", "salida"]:
        return jsonify({
            "success": False,
            "message": "Tipo inválido"
        })

    try:
        lat = float(lat)
        lon = float(lon)
    except:
        return jsonify({
            "success": False,
            "message": "No se pudo obtener ubicación válida"
        })

    distancia = haversine(lat, lon, CENTER_LAT, CENTER_LON)

    if distancia > MAX_DISTANCE_KM:
        return jsonify({
            "success": False,
            "message": f"Fuera del rango permitido. Estás a {distancia:.2f} km."
        })

    ahora = datetime.now()
    fecha = ahora.strftime("%Y-%m-%d")
    hora = ahora.strftime("%H:%M")

    conn = get_db()

    existente = conn.execute("""
        SELECT * FROM registros
        WHERE nombre = ? AND tipo = ? AND fecha = ?
    """, (nombre, tipo, fecha)).fetchone()

    if existente:
        conn.close()
        return jsonify({
            "success": False,
            "message": f"Ya tienes registrada tu {tipo} de hoy"
        })

    conn.execute("""
        INSERT INTO registros (nombre, tipo, fecha, hora, lat, lon)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nombre, tipo, fecha, hora, lat, lon))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"{tipo.capitalize()} registrada correctamente a las {hora}"
    })


@app.route("/admin_login", methods=["POST"])
def admin_login():
    usuario = request.form.get("usuario")
    password = request.form.get("password")

    if usuario == ADMIN_USER and password == ADMIN_PASSWORD:
        session["admin"] = True
        return jsonify({"success": True})

    return jsonify({
        "success": False,
        "message": "Usuario o contraseña incorrectos"
    })


@app.route("/admin")
def admin():
    if not session.get("admin"):
        return "Acceso denegado. Primero inicia sesión como administrador."

    resumen = generar_resumen()
    colaboradores = obtener_colaboradores()

    return render_template(
        "admin.html",
        resumen=resumen,
        colaboradores=colaboradores
    )


@app.route("/agregar_colaborador", methods=["POST"])
def agregar_colaborador():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Acceso denegado"})

    nombre = request.form.get("nombre")
    pin = request.form.get("pin")
    puesto = request.form.get("puesto")

    if not nombre or not pin or not puesto:
        return jsonify({
            "success": False,
            "message": "Nombre, PIN y puesto son obligatorios"
        })

    if len(pin) != 4:
        return jsonify({
            "success": False,
            "message": "El PIN debe tener 4 dígitos"
        })

    conn = get_db()

    try:
        conn.execute("""
            INSERT INTO colaboradores (nombre, pin, puesto)
            VALUES (?, ?, ?)
        """, (nombre, pin, puesto))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Ese colaborador ya existe"
        })

    conn.close()

    return jsonify({
        "success": True,
        "message": "Colaborador agregado correctamente"
    })


@app.route("/editar_colaborador", methods=["POST"])
def editar_colaborador():
    if not session.get("admin"):
        return jsonify({
            "success": False,
            "message": "Acceso denegado"
        })

    colaborador_id = request.form.get("id")
    nombre = request.form.get("nombre")
    pin = request.form.get("pin")
    puesto = request.form.get("puesto")

    if not colaborador_id:
        return jsonify({
            "success": False,
            "message": "ID inválido"
        })

    conn = get_db()

    conn.execute("""
        UPDATE colaboradores
        SET nombre = ?, pin = ?, puesto = ?
        WHERE id = ?
    """, (nombre, pin, puesto, colaborador_id))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Colaborador actualizado correctamente"
    })


@app.route("/editar_registro", methods=["POST"])
def editar_registro():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Acceso denegado"})

    registro_id = request.form.get("id")
    nueva_hora = request.form.get("hora")

    if not registro_id or not nueva_hora:
        return jsonify({
            "success": False,
            "message": "Datos incompletos"
        })

    conn = get_db()

    conn.execute("""
        UPDATE registros
        SET hora = ?
        WHERE id = ?
    """, (nueva_hora, registro_id))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Registro actualizado correctamente"
    })


@app.route("/descargar_reporte")
def descargar_reporte():
    if not session.get("admin"):
        return "Acceso denegado"

    resumen = generar_resumen()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Colaborador",
        "Puesto",
        "Fecha",
        "Entrada",
        "Salida",
        "Horas trabajadas",
        "Horas extra"
    ])

    for r in resumen:
        writer.writerow([
            r["nombre"],
            r["puesto"],
            r["fecha"],
            r["entrada"],
            r["salida"],
            r["horas_trabajadas"],
            r["horas_extra"]
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )

    response.headers["Content-Disposition"] = "attachment; filename=reporte_asistencias.csv"

    return response


@app.route("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/logout_admin")
def logout_admin():
    session.pop("admin", None)
    return """
    <h2>Sesión de administrador cerrada</h2>
    <a href="/">Volver al inicio</a>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
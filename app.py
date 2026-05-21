from flask import Flask, render_template, request, jsonify, session
import sqlite3
from datetime import datetime
import math
import pytz

app = Flask(__name__)
app.secret_key = "kukulcan2025"

# Zona horaria correcta para Cancún
ZONA_MEXICO = pytz.timezone("America/Cancun")

# Ubicación permitida
CENTER_LAT = 21.131
CENTER_LON = -86.891
MAX_DISTANCE_KM = 1.0

colaboradores = {
    "Emilio Rojas": "1234",
    "Eric Gutiérrez": "2345",
    "Rutilo Pérez": "3456",
    "Ángel Pérez": "4567"
}

def get_db():
    conn = sqlite3.connect("asistencias.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
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
    conn.commit()
    conn.close()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

@app.route("/")
def index():
    return render_template("index.html", colaboradores=colaboradores.keys())

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    nombre = data.get("nombre")
    pin = data.get("pin")

    if nombre in colaboradores and colaboradores[nombre] == pin:
        session["usuario"] = nombre
        return jsonify({"success": True, "nombre": nombre})

    return jsonify({"success": False, "mensaje": "Usuario o PIN incorrecto"})

@app.route("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/registrar", methods=["POST"])
def registrar():
    if "usuario" not in session:
        return jsonify({"success": False, "mensaje": "Sesión no iniciada"})

    data = request.json

    tipo = data.get("tipo")
    lat = float(data.get("lat"))
    lon = float(data.get("lon"))
    nombre = session["usuario"]

    distancia = haversine(lat, lon, CENTER_LAT, CENTER_LON)

    if distancia > MAX_DISTANCE_KM:
        return jsonify({
            "success": False,
            "mensaje": "No estás dentro del área permitida para registrar asistencia"
        })

    ahora = datetime.now(ZONA_MEXICO)
    fecha = ahora.strftime("%Y-%m-%d")
    hora = ahora.strftime("%H:%M")

    conn = get_db()
    conn.execute("""
        INSERT INTO registros (nombre, tipo, fecha, hora, lat, lon)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nombre, tipo, fecha, hora, lat, lon))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "mensaje": f"{tipo.capitalize()} registrada correctamente a las {hora}"
    })

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json
    usuario = data.get("usuario")
    password = data.get("password")

    if usuario == "admin" and password == "admin123":
        session["admin"] = True
        return jsonify({"success": True})

    return jsonify({"success": False, "mensaje": "Datos de administrador incorrectos"})

@app.route("/admin/registros")
def admin_registros():
    if not session.get("admin"):
        return jsonify({"success": False, "mensaje": "No autorizado"})

    conn = get_db()
    registros = conn.execute("""
        SELECT * FROM registros
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

    return jsonify({"success": True, "registros": resultado})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
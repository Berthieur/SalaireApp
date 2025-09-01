import logging
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
import sqlite3
import os
import time
from datetime import datetime, timedelta
from database import init_db, get_db

# Configuration des logs
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = '3fb5222037e2be9d7d09019e1b46e268ec470fa2974a3981'  # Nouvelle clé unique
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Autoriser toutes les origines pour les tests

# --- Initialisation ---
init_db()

# --- Filtres Jinja2 pour le template ---
def timestamp_to_datetime_full(timestamp):
    try:
        # Ajuster pour EAT (UTC+3)
        dt = datetime.fromtimestamp(timestamp / 1000, tz=datetime.utcnow().astimezone().tzinfo)
        dt_eat = dt + timedelta(hours=3)  # Forcer EAT
        return dt_eat.strftime('%d/%m/%Y %H:%M:%S')
    except (TypeError, ValueError):
        return '-'
app.jinja_env.filters['timestamp_to_datetime_full'] = timestamp_to_datetime_full

# Middleware pour vérifier la session
@app.before_request
def check_session():
    if request.path.startswith('/api/') and request.method in ['POST', 'GET'] and not session.get('logged_in'):
        logger.error(f"Session check failed for {request.path}, session={session}, logged_in={session.get('logged_in')}")
        return jsonify({"error": "Non autorisé"}), 403
    logger.debug(f"Session check passed for {request.path}, session={session}, logged_in={session.get('logged_in')}")

# --- Routes API ---

# 1. 🔐 Login (mise à jour pour session)
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    logger.debug(f"Login attempt: {data}")
    if data.get('username') == 'admin' and data.get('password') == '1234':
        session['logged_in'] = True
        session['role'] = 'admin'
        session['userId'] = 'ADMIN001'
        logger.info("Login successful, session updated")
        return jsonify({"status": "success", "message": "Connexion réussie"})
    logger.warning("Login failed")
    return jsonify({"error": "Identifiants invalides"}), 401

# 2. 🔓 Déconnexion
@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    session.pop('role', None)
    session.pop('userId', None)
    logger.info("Logout successful")
    return jsonify({"status": "success", "message": "Déconnexion réussie"})

# 3. 👥 Enregistrement employé
@app.route('/api/employees', methods=['POST'])
def register_employee():
    emp = request.get_json()
    required = ['id', 'nom', 'prenom', 'type']
    for field in required:
        if field not in emp:
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO employees 
            (id, nom, prenom, date_naissance, lieu_naissance, telephone, email, profession,
             type, taux_horaire, frais_ecolage, qr_code, is_active, created_at, is_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', [
            emp['id'],
            emp['nom'],
            emp['prenom'],
            emp.get('dateNaissance'),
            emp.get('lieuNaissance'),
            emp.get('telephone'),
            emp.get('email'),
            emp.get('profession'),
            emp['type'],
            emp.get('tauxHoraire'),
            emp.get('fraisEcolage'),
            emp.get('qrCode'),
            emp.get('isActive', True),
            emp.get('createdAt', int(time.time() * 1000))
        ])
        conn.commit()
        logger.info(f"Employee registered: {emp['id']}")
        return jsonify({"status": "success", "message": "Employé enregistré"}), 201
    except Exception as e:
        logger.error(f"Error registering employee: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 4. 📋 Liste de tous les employés
@app.route('/api/employees', methods=['GET'])
def get_all_employees():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM employees ORDER BY nom, prenom")
        employees = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"Retrieved {len(employees)} employees")
        return jsonify(employees)
    except Exception as e:
        logger.error(f"Error retrieving employees: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 5. 👷 Employés actifs
@app.route('/api/employees/active', methods=['GET'])
def get_active_employees():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM employees WHERE is_active = 1 ORDER BY nom")
        employees = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"Retrieved {len(employees)} active employees")
        return jsonify(employees)
    except Exception as e:
        logger.error(f"Error retrieving active employees: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 6. 📍 Position (dernier pointage)
@app.route('/api/employees/<employeeId>/position', methods=['GET'])
def get_employee_position(employeeId):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT employee_id, employee_name, type, timestamp, date
            FROM pointages
            WHERE employee_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', [employeeId])
        row = cursor.fetchone()
        if row:
            logger.debug(f"Retrieved position for employee {employeeId}")
            return jsonify(dict(row))
        logger.warning(f"No position found for employee {employeeId}")
        return jsonify({"error": "Aucun pointage trouvé"}), 404
    except Exception as e:
        logger.error(f"Error retrieving position for {employeeId}: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 7. 💰 Enregistrer un salaire
@app.route('/api/salary', methods=['POST'])
def save_salary_record():
    record = request.get_json()
    required = ['employeeId', 'employeeName', 'type', 'amount', 'period', 'date']
    for field in required:
        if field not in record:
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO salaries 
            (id, employee_id, employee_name, type, amount, hours_worked, period, date, is_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', [
            record.get('id', str(int(record['date']))),
            record['employeeId'],
            record['employeeName'],
            record['type'],
            record['amount'],
            record.get('hoursWorked'),
            record['period'],
            record['date']
        ])
        conn.commit()
        logger.info(f"Salary recorded: {record['id']}")
        return jsonify({"status": "success", "id": cursor.lastrowid}), 201
    except Exception as e:
        logger.error(f"Error recording salary: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 8. 📅 Historique des salaires
@app.route('/api/salary/history', methods=['GET'])
def get_salary_history():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM salaries ORDER BY date DESC")
        salaries = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"Retrieved {len(salaries)} salary records")
        return jsonify(salaries)
    except Exception as e:
        logger.error(f"Error retrieving salary history: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 9. 📊 Statistiques par zone (exemple fictif)
@app.route('/api/statistics/zones/<employeeId>', methods=['GET'])
def get_zone_statistics(employeeId):
    try:
        stats = [{"zone_name": "Zone A", "duration_seconds": 2700}, {"zone_name": "Zone B", "duration_seconds": 1800}]
        logger.debug(f"Retrieved zone statistics for {employeeId}")
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error retrieving zone statistics for {employeeId}: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 10. 🚶 Historique des mouvements (pointages)
@app.route('/api/movements/<employeeId>', methods=['GET'])
def get_movement_history(employeeId):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT employee_id, employee_name, type, timestamp, date
            FROM pointages
            WHERE employee_id = ?
            ORDER BY timestamp DESC
        ''', [employeeId])
        movements = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"Retrieved {len(movements)} movements for {employeeId}")
        return jsonify(movements)
    except Exception as e:
        logger.error(f"Error retrieving movements for {employeeId}: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 11. ⚠️ Alerte zone interdite
@app.route('/api/alerts/forbidden-zone', methods=['POST'])
def report_forbidden_zone():
    alert = request.get_json()
    required = ['employeeId', 'employeeName', 'zoneName', 'timestamp']
    for field in required:
        if field not in alert:
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO alerts (employeeId, employeeName, zone_name, timestamp)
            VALUES (?, ?, ?, ?)
        ''', [
            alert['employeeId'],
            alert['employeeName'],
            alert['zoneName'],
            alert['timestamp']
        ])
        conn.commit()
        logger.info(f"Forbidden zone alert recorded for {alert['employeeId']}")
        return jsonify({"status": "alerte_enregistrée"}), 201
    except Exception as e:
        logger.error(f"Error recording forbidden zone alert: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 12. 📡 État ESP32
@app.route('/api/esp32/status', methods=['GET'])
def get_esp32_status():
    try:
        status = {
            "is_online": True,
            "last_seen": int(time.time() * 1000),
            "firmware_version": "1.2.0",
            "uptime_seconds": 3672
        }
        logger.debug("ESP32 status retrieved")
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error retrieving ESP32 status: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 13. 🔊 Activer le buzzer
@app.route('/api/esp32/buzzer', methods=['POST'])
def activate_buzzer():
    data = request.get_json()
    duration = data.get('durationMs', 1000)
    try:
        response = {
            "status": "buzzer_activé",
            "durationMs": duration,
            "timestamp": int(time.time() * 1000)
        }
        logger.info(f"Buzzer activated for {duration}ms")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error activating buzzer: {str(e)}")
        return jsonify({"error": str(e)}), 500

# --- Nouvelles routes utiles ---

# 🔄 Synchronisation : Récupérer les données non synchronisées
@app.route('/api/sync/pointages', methods=['GET'])
def get_unsynced_pointages():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM pointages WHERE is_synced = 0")
        pointages = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"Retrieved {len(pointages)} unsynced pointages")
        return jsonify(pointages)
    except Exception as e:
        logger.error(f"Error retrieving unsynced pointages: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 🔄 Envoyer des pointages depuis Android
@app.route('/api/pointages', methods=['POST'])
def add_pointage():
    p = request.get_json()
    required = ['id', 'employeeId', 'employeeName', 'type', 'timestamp', 'date']
    for field in required:
        if field not in p:
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO pointages 
            (id, employee_id, employee_name, type, timestamp, date, is_synced)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', [
            p['id'],
            p['employeeId'],
            p['employeeName'],
            p['type'],
            p['timestamp'],
            p['date']
        ])
        conn.commit()
        logger.info(f"Pointage recorded: {p['id']}")
        return jsonify({"status": "pointage_enregistré"}), 201
    except Exception as e:
        logger.error(f"Error recording pointage: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 📥 Télécharger tous les pointages (pour mise à jour locale)
@app.route('/api/pointages', methods=['GET'])
def get_all_pointages():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM pointages ORDER BY timestamp DESC")
        pointages = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"Retrieved {len(pointages)} pointages")
        return jsonify(pointages)
    except Exception as e:
        logger.error(f"Error retrieving all pointages: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 💸 Liste des employés avec leurs paiements
@app.route('/api/employee_payments', methods=['GET'])
def get_employee_payments():
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.nom, e.prenom, e.type, s.employee_name, s.type AS payment_type, 
                   s.amount, s.period, s.date
            FROM employees e
            LEFT JOIN salaries s ON e.id = s.employee_id
            WHERE e.is_active = 1
            ORDER BY s.date DESC
        ''')
        payments = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"Retrieved {len(payments)} employee payments")
        return jsonify(payments)
    except Exception as e:
        logger.error(f"Error retrieving employee payments: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 📊 Tableau de bord HTML (sécurisé)
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if not session.get('logged_in'):
        logger.warning("Unauthorized access to dashboard, redirecting to login")
        return redirect(url_for('login'))
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COALESCE(e.nom, SUBSTR(s.employee_name, 1, INSTR(s.employee_name, ' ') - 1)) AS nom,
                COALESCE(e.prenom, SUBSTR(s.employee_name, INSTR(s.employee_name, ' ') + 1)) AS prenom,
                COALESCE(e.type, s.type) AS type,
                s.employee_name,
                s.type AS payment_type,
                s.amount,
                s.period,
                s.date
            FROM salaries s
            LEFT JOIN employees e ON e.id = s.employee_id
            ORDER BY s.date DESC
        ''')
        payments = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"Number of payments retrieved: {len(payments)}")
        for payment in payments:
            logger.debug(f"Payment data: nom={payment['nom']}, prenom={payment['prenom']}, type={payment['type']}, payment_type={payment['payment_type']}, date={payment['date']}, period={payment['period']}")
        return render_template('dashboard.html', payments=payments)
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 📝 Page de login
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        logger.debug(f"Login attempt: username={username}, password={password}")
        if username == 'admin' and password == '1234':
            session['logged_in'] = True
            session['role'] = 'admin'
            session['userId'] = 'ADMIN001'
            logger.info("Login successful, session updated")
            return redirect(url_for('dashboard'))
        logger.warning("Login failed")
        return render_template('login.html', error="Identifiants invalides")
    return render_template('login.html')

# --- Démarrage ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)  # Activer debug pour logs

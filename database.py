import sqlite3
import os

# Chemin de la base de données
DB_PATH = os.getenv('DATABASE_PATH', 'tracking.db')

def init_db():
    """Crée les tables si elles n'existent pas"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Table employees
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id TEXT PRIMARY KEY,
                nom TEXT NOT NULL,
                prenom TEXT NOT NULL,
                date_naissance TEXT,
                lieu_naissance TEXT,
                telephone TEXT,
                email TEXT,
                profession TEXT,
                type TEXT NOT NULL,
                taux_horaire REAL,
                frais_ecolage REAL,
                qr_code TEXT,
                is_active INTEGER DEFAULT 1,
                created_at INTEGER,
                is_synced INTEGER DEFAULT 0
            )
        ''')

        # Table pointages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pointages (
                id TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                employee_name TEXT NOT NULL,
                type TEXT NOT NULL,  -- ARRIVEE ou DEPART
                timestamp INTEGER NOT NULL,
                date TEXT NOT NULL,
                is_synced INTEGER DEFAULT 0,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
        ''')

        # Table salaries
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS salaries (
                id TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                employee_name TEXT NOT NULL,
                type TEXT NOT NULL,  -- salaire ou ecolage
                amount REAL NOT NULL,
                hours_worked REAL,
                period TEXT NOT NULL,
                date INTEGER NOT NULL,
                is_synced INTEGER DEFAULT 0,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
        ''')

        conn.commit()

def get_db():
    """Retourne une connexion à la base"""
    return sqlite3.connect(DB_PATH)
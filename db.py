# db.py
import mysql.connector
from mysql.connector import Error
from flask import g, current_app

def get_db_connection():
    """
    يعيد اتصال MySQL أو None إذا فشل.
    يخزن الاتصال في g حتى لا نفتح اتصال جديد في نفس الطلب.
    """
    if hasattr(g, 'db_conn') and g.db_conn:
        return g.db_conn
    try:
        g.db_conn = mysql.connector.connect(
            host=current_app.config.get('MYSQL_HOST', 'localhost'),
            user=current_app.config.get('MYSQL_USER', 'root'),
            password=current_app.config.get('MYSQL_PASSWORD', ''),
            database=current_app.config.get('MYSQL_DB', 'forn'),
            charset='utf8mb4',
            auth_plugin=current_app.config.get('MYSQL_AUTH_PLUGIN', None)  # استخدمه لو احتجت
        )
        return g.db_conn
    except Error as e:
        current_app.logger.error(f"DB connection error: {e}")
        return None

def close_db_connection(e=None):
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        try:
            db_conn.close()
        except Exception:
            pass

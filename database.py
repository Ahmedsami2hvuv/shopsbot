

import os
import psycopg2
from psycopg2 import sql

# الحصول على URL الاتصال بقاعدة البيانات من متغيرات البيئة (PostgreSQL)
# هذا المتغير يتم انشاؤه تلقائيا عند اضافة خدمة PostgreSQL بـ Railway
DATABASE_URL = os.getenv('DATABASE_URL')

def connect_db():
    """يربط بقاعدة بيانات PostgreSQL."""
    if not DATABASE_URL:
        # إذا لم يتم تعريف الـ URL، ارفع خطأ لأن البوت ما راح يشتغل
        raise Exception("DATABASE_URL environment variable is not set. Please add a PostgreSQL service in Railway.")
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def setup_db():
    """إنشاء الجداول عند تشغيل البوت لأول مرة."""
    conn = None
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        # جدول المحلات (Shops)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Shops (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL
            )
        """)
        
        # جدول المجهزين (Agents)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Agents (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,  -- آيدي التليجرام
                name TEXT NOT NULL,
                secret_code TEXT NOT NULL UNIQUE
            )
        """)
        
        # جدول ربط المحلات والمجهزين (AgentShops)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS AgentShops (
                agent_id INTEGER REFERENCES Agents(id),
                shop_id INTEGER REFERENCES Shops(id),
                PRIMARY KEY (agent_id, shop_id)
            )
        """)
        
        conn.commit()
    except Exception as e:
        print(f"Error during database setup: {e}")
    finally:
        if conn:
            conn.close()

# دالة مساعدة لإجراء الاستعلامات (PostgreSQL يحتاج طريقة مختلفة لجلب الصفوف كـ Dict)
def execute_query(query, params=None, fetch_all=False, fetch_one=False):
    conn = None
    result = None
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch_all:
            # جلب أسماء الأعمدة يدوياً
            col_names = [desc[0] for desc in cursor.description]
            # جلب كل الصفوف وتحويلها إلى قائمة من القواميس
            result = [dict(zip(col_names, row)) for row in cursor.fetchall()]
        elif fetch_one:
            col_names = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            if row:
                result = dict(zip(col_names, row))
        else:
            conn.commit()
    except psycopg2.IntegrityError:
        if conn: conn.rollback()
        raise
    except Exception as e:
        if conn: conn.rollback()
        raise
    finally:
        if conn: conn.close()
    return result


# تعديل دوال إضافة محل وجلب محلات
def add_shop(name: str, url: str) -> bool:
    """يضيف محل جديد ويرجع True اذا نجحت العملية."""
    try:
        execute_query("INSERT INTO Shops (name, url) VALUES (%s, %s)", (name, url))
        return True
    except psycopg2.IntegrityError:
        return False
    except Exception:
        return False

def get_all_shops():
    """يجلب قائمة بكل المحلات المخزنة."""
    return execute_query("SELECT id, name, url FROM Shops ORDER BY name", fetch_all=True)

# تعديل دالة إضافة مجهز
def add_agent(name: str, secret_code: str) -> bool:
    """يضيف مجهز جديد ويرجع True اذا نجحت العملية."""
    try:
        execute_query(
            "INSERT INTO Agents (name, secret_code) VALUES (%s, %s)", 
            (name, secret_code)
        )
        return True
    except psycopg2.IntegrityError:
        return False
    except Exception:
        return False

# تعديل دالة جلب المجهزين
def get_all_agents():
    """يجلب قائمة بكل المجهزين المخزنين (الاسم والآيدي)."""
    return execute_query("SELECT id, name FROM Agents ORDER BY name", fetch_all=True)

def get_agent_name_by_id(agent_id: int) -> str | None:
    """يجلب اسم المجهز بواسطة الـ ID الداخلي."""
    agent = execute_query("SELECT name FROM Agents WHERE id = %s", (agent_id,), fetch_one=True)
    return agent['name'] if agent else None

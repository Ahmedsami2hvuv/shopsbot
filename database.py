# database.py
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
        # يستخدم لربط المجهز بالمحلات التي يمكنه التعامل معها
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS AgentShops (
                agent_id INTEGER REFERENCES Agents(id) ON DELETE CASCADE,
                shop_id INTEGER REFERENCES Shops(id) ON DELETE CASCADE,
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
        raise # رفع الخطأ للـ main.py لمعالجته
    except Exception as e:
        if conn: conn.rollback()
        # هنا قد تحتاج تسجيل الخطأ بدلاً من طباعته
        print(f"Database error: {e}") 
        raise # رفع الخطأ لمعالجته
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

# ------------------------------------------------------------------------------------------------
# الدالة الجديدة: حذف المحل
# ------------------------------------------------------------------------------------------------
def delete_shop(shop_id: int) -> bool:
    """يحذف محل من جدول Shops بواسطة الـ ID."""
    try:
        # PostgreSQL سيحذف أيضاً المدخلات المرتبطة في AgentShops بسبب ON DELETE CASCADE
        execute_query("DELETE FROM Shops WHERE id = %s", (shop_id,))
        return True
    except Exception:
        return False
# ------------------------------------------------------------------------------------------------

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
    try:
        agent = execute_query("SELECT name FROM Agents WHERE id = %s", (agent_id,), fetch_one=True)
        return agent['name'] if agent else None
    except Exception as e:
        print(f"Error fetching agent name: {e}")
        return None

# ------------------------------------------------------------------------------------------------
# الدوال الجديدة المطلوبة لربط المحلات والمجهزين (لحالة MANAGE_AGENT و AGENT_LOGIN)
# ------------------------------------------------------------------------------------------------

def get_assigned_shop_ids(agent_id: int) -> list[int]:
    """
    تسترجع قائمة بـ ID المحلات المرتبطة حالياً بالمجهز.
    """
    try:
        results = execute_query(
            "SELECT shop_id FROM AgentShops WHERE agent_id = %s", 
            (agent_id,), 
            fetch_all=True
        )
        # تحويل قائمة القواميس إلى قائمة من الـ ID (int)
        return [row['shop_id'] for row in results] if results else []
    except Exception:
        return [] 

def toggle_agent_shop_assignment(agent_id: int, shop_id: int, is_assigned: bool) -> bool:
    """
    تقوم بربط أو إلغاء ربط محل معين بمجهز معين في قاعدة البيانات.
    """
    try:
        if is_assigned:
            # الربط: INSERT
            execute_query(
                "INSERT INTO AgentShops (agent_id, shop_id) VALUES (%s, %s)",
                (agent_id, shop_id)
            )
        else:
            # إلغاء الربط: DELETE
            execute_query(
                "DELETE FROM AgentShops WHERE agent_id = %s AND shop_id = %s",
                (agent_id, shop_id)
            )
        return True
    except psycopg2.IntegrityError:
        # إذا حاولنا الإضافة وموجود بالفعل (لا مشكلة)
        return True
    except Exception:
        return False

# دالة التحقق من رمز المجهز (لجزء تسجيل الدخول)
def check_agent_code(agent_code: str):
    """
    تتحقق من وجود رمز الدخول السري للمجهز في قاعدة البيانات وترجع معلوماته.
    """
    try:
        agent = execute_query(
            "SELECT id, telegram_id, name FROM Agents WHERE secret_code = %s", 
            (agent_code,), 
            fetch_one=True
        )
        return agent # ترجع قاموس أو None
    except Exception:
        return None

# ------------------------------------------------------------------------------------------------
# الدالة الجديدة: تحديث تفاصيل المجهز
# ------------------------------------------------------------------------------------------------
def update_agent_details(agent_id, new_name, new_code):
    """تحديث اسم ورمز الدخول لمجهز محدد بواسطة ID."""
    
    # استعلام للتحقق من أن الرمز الجديد غير مستخدم من قبل مجهز آخر
    check_query = """
        SELECT id FROM Agents WHERE secret_code = %s AND id != %s
    """
    # استعلام لتحديث الاسم والرمز
    update_query = """
        UPDATE Agents 
        SET name = %s, secret_code = %s 
        WHERE id = %s
    """
    try:
        # 1. التحقق من الرمز
        existing_agent = execute_query(check_query, (new_code, agent_id), fetch_one=True)
        if existing_agent:
            return "CODE_EXISTS" # رمز الدخول مستخدم بالفعل
            
        # 2. تنفيذ التحديث
        execute_query(update_query, (new_name, new_code, agent_id))
        return True
    except Exception as e:
        print(f"Database error in update_agent_details: {e}")
        return False

# database.py
import os
import logging
import psycopg2
from psycopg2 import sql
import psycopg2.extras # 👈🏼 تم إضافة الاستدعاء هذا لكي يعمل RealDictCursor

# تفعيل نظام الـ Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# الحصول على URL الاتصال بقاعدة البيانات من متغيرات البيئة (PostgreSQL)
DATABASE_URL = os.getenv('DATABASE_URL')

def connect_db():
    """يربط بقاعدة بيانات PostgreSQL."""
    if not DATABASE_URL:
        # إذا لم يتم تعريف الـ URL، ارفع خطأ لأن البوت ما راح يشتغل
        raise Exception("DATABASE_URL environment variable is not set. Please add a PostgreSQL service in Railway.")
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# ------------------------------------------------------------------------------------------------
# الدالة الأساسية لتنفيذ الاستعلامات (execute_query)
# ------------------------------------------------------------------------------------------------
def execute_query(query: str, params: tuple = None, fetch_one: bool = False, fetch_all: bool = False):
    """
    تنفذ استعلام SQL، وتفتح وتغلق الاتصال بالقاعدة.
    ترجع قائمة من القواميس (عند fetch_all) أو قاموس واحد (عند fetch_one) أو True/False.
    """
    conn = None
    try:
        conn = connect_db()
        # RealDictCursor يحول النتائج إلى قواميس (مفيدة جداً)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) 
        cursor.execute(query, params)
        conn.commit()
        
        if fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        else:
            return True # تم التنفيذ بنجاح
            
    except Exception as e:
        # logger.error(f"DB Error executing query: {e}")
        return False
        
    finally:
        if conn:
            conn.close()

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
                telegram_id BIGINT UNIQUE,
                name TEXT NOT NULL,
                secret_code TEXT NOT NULL UNIQUE
            )
        """)
        
        # جدول ربط المحلات والمجهزين (AgentShops)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS AgentShops (
                agent_id INTEGER REFERENCES Agents(id) ON DELETE CASCADE,
                shop_id INTEGER REFERENCES Shops(id) ON DELETE CASCADE,
                PRIMARY KEY (agent_id, shop_id)
            )
        """)
        conn.commit()
        
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
    finally:
        if conn:
            conn.close()

# ------------------------------------------------------------------------------------------------
# دوال المحلات (Shops)
# ------------------------------------------------------------------------------------------------

def add_shop(name: str, url: str):
    """إضافة محل جديد إلى قاعدة البيانات."""
    query = "INSERT INTO Shops (name, url) VALUES (%s, %s)"
    return execute_query(query, (name, url))

def get_all_shops():
    """جلب جميع المحلات."""
    query = "SELECT id, name, url FROM Shops ORDER BY name"
    return execute_query(query, fetch_all=True)

def update_shop_details(shop_id, new_name, new_url):
    """تحديث اسم ورابط محل محدد."""
    query = "UPDATE Shops SET name = %s, url = %s WHERE id = %s"
    return execute_query(query, (new_name, new_url, shop_id))

def delete_shop(shop_id):
    """حذف محل محدد بواسطة ID وحذف كل ارتباطاته بالمجهزين. 👈🏼 تم الإضافة"""
    try:
        # 1. حذف ارتباطات المجهزين أولاً (AgentShops)
        delete_assignments_query = "DELETE FROM AgentShops WHERE shop_id = %s"
        execute_query(delete_assignments_query, (shop_id,))
        
        # 2. حذف المحل نفسه (Shops)
        delete_shop_query = "DELETE FROM Shops WHERE id = %s"
        execute_query(delete_shop_query, (shop_id,))
        
        return True
    except Exception as e:
        logger.error(f"Error deleting shop {shop_id}: {e}")
        return False

# ------------------------------------------------------------------------------------------------
# دوال المجهزين (Agents)
# ------------------------------------------------------------------------------------------------

def add_agent(name: str, secret_code: str):
    """إضافة مجهز جديد."""
    query = "INSERT INTO Agents (name, secret_code) VALUES (%s, %s)"
    return execute_query(query, (name, secret_code))

def get_all_agents():
    """جلب جميع المجهزين."""
    query = "SELECT id, name FROM Agents ORDER BY name"
    return execute_query(query, fetch_all=True)

def get_agent_name_by_id(agent_id: int):
    """جلب اسم مجهز بواسطة ID."""
    query = "SELECT name FROM Agents WHERE id = %s"
    result = execute_query(query, (agent_id,), fetch_one=True)
    return result['name'] if result else None

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
        logger.error(f"Error updating agent details: {e}")
        return False

def delete_agent(agent_id):
    """حذف مجهز محدد بواسطة ID وحذف كل ارتباطاته بالمحلات. 👈🏼 تم الإضافة"""
    try:
        # 1. حذف ارتباطات المحلات أولاً (AgentShops)
        delete_assignments_query = "DELETE FROM AgentShops WHERE agent_id = %s"
        execute_query(delete_assignments_query, (agent_id,))
        
        # 2. حذف المجهز نفسه (Agents)
        delete_agent_query = "DELETE FROM Agents WHERE id = %s"
        execute_query(delete_agent_query, (agent_id,))
        
        return True
    except Exception as e:
        logger.error(f"Error deleting agent {agent_id}: {e}")
        return False

# ------------------------------------------------------------------------------------------------
# دوال الربط (Assignment)
# ------------------------------------------------------------------------------------------------

def get_assigned_shop_ids(agent_id: int):
    """جلب قائمة بـ ID المحلات المخصصة لمجهز معين."""
    query = "SELECT shop_id FROM AgentShops WHERE agent_id = %s"
    results = execute_query(query, (agent_id,), fetch_all=True)
    # تحويل قائمة القواميس إلى قائمة من الأرقام الصحيحة
    return [row['shop_id'] for row in results] if results else []

def toggle_agent_shop_assignment(agent_id: int, shop_id: int, assign: bool):
    """ربط أو إلغاء ربط محل بمجهز محدد."""
    if assign:
        query = "INSERT INTO AgentShops (agent_id, shop_id) VALUES (%s, %s) ON CONFLICT DO NOTHING"
    else:
        query = "DELETE FROM AgentShops WHERE agent_id = %s AND shop_id = %s"
        
    return execute_query(query, (agent_id, shop_id))

# ------------------------------------------------------------------------------------------------
# دوال تسجيل الدخول والبحث
# ------------------------------------------------------------------------------------------------

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

def get_agent_shops_by_search(agent_id: int, search_term: str):
    """
    تجلب المحلات المخصصة لمجهز معين والتي يتطابق اسمها جزئياً مع نص البحث.
    """
    try:
        query = """
            SELECT T1.id, T1.name, T1.url 
            FROM Shops AS T1
            JOIN AgentShops AS T2 ON T1.id = T2.shop_id
            WHERE T2.agent_id = %s AND T1.name ILIKE %s
            ORDER BY T1.name
        """
        search_pattern = f"%{search_term}%" 
        
        results = execute_query(query, (agent_id, search_pattern), fetch_all=True)
        
        return results if results else []
    except Exception as e:
        logger.error(f"DB Error in get_agent_shops_by_search: {e}")
        return []

def get_shops_by_search(search_term: str):
    """
    تجلب المحلات التي يتطابق اسمها جزئياً مع نص البحث للمدير.
    """
    try:
        query = """
            SELECT id, name, url 
            FROM Shops 
            WHERE name ILIKE %s
            ORDER BY name
        """
        search_pattern = f"%{search_term}%" 
        
        results = execute_query(query, (search_pattern,), fetch_all=True)
        
        return results if results else []
    except Exception as e:
        logger.error(f"DB Error in get_shops_by_search: {e}")
        return []

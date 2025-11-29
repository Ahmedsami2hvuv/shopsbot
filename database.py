# database.py
import os
import psycopg2
from psycopg2 import sql
import psycopg2.extras # 👈🏼 تم إضافة الاستدعاء هذا لكي يعمل RealDictCursor

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

# ------------------------------------------------------------------------------------------------
# الدالة الأساسية لتنفيذ الاستعلامات (execute_query) 👈🏼 تم الإضافة
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
        
        return True # للعمليات التي لا تتطلب إرجاع (INSERT/UPDATE/DELETE)
    
    except Exception as e:
        print(f"Database Query Error: {e} | Query: {query}")
        # في حالة الخطأ، نرجع None للـ SELECT و False لغيرها
        return None if (fetch_one or fetch_all) else False
    
    finally:
        if conn:
            conn.close()

# ------------------------------------------------------------------------------------------------
# دوال الإعداد والإنشاء
# ------------------------------------------------------------------------------------------------
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
                agent_id INTEGER REFERENCES Agents(id) ON DELETE CASCADE,
                shop_id INTEGER REFERENCES Shops(id) ON DELETE CASCADE,
                PRIMARY KEY (agent_id, shop_id)
            )
        """)
        
        conn.commit()
    except Exception as e:
        print(f"Database setup error: {e}")
    finally:
        if conn:
            conn.close()

# ------------------------------------------------------------------------------------------------
# دوال إضافة العناصر
# ------------------------------------------------------------------------------------------------
def add_shop(name: str, url: str) -> bool:
    """إضافة محل جديد إلى جدول Shops."""
    query = "INSERT INTO Shops (name, url) VALUES (%s, %s)"
    return execute_query(query, (name, url))

def add_agent(telegram_id: int, name: str, secret_code: str) -> bool:
    """إضافة مجهز جديد إلى جدول Agents."""
    query = "INSERT INTO Agents (telegram_id, name, secret_code) VALUES (%s, %s, %s)"
    # الـ telegram_id يمكن أن يكون None إذا لم يسجل الدخول بعد
    return execute_query(query, (telegram_id, name, secret_code))

# ------------------------------------------------------------------------------------------------
# دوال استرجاع البيانات
# ------------------------------------------------------------------------------------------------
def get_all_shops() -> list:
    """استرجاع قائمة بجميع المحلات."""
    query = "SELECT id, name, url FROM Shops ORDER BY name"
    return execute_query(query, fetch_all=True)

def get_all_agents() -> list:
    """استرجاع قائمة بجميع المجهزين."""
    query = "SELECT id, name, secret_code FROM Agents ORDER BY name"
    return execute_query(query, fetch_all=True)

def get_agent_name_by_id(agent_id: int) -> str | None:
    """استرجاع اسم المجهز بواسطة ID."""
    query = "SELECT name FROM Agents WHERE id = %s"
    result = execute_query(query, (agent_id,), fetch_one=True)
    return result['name'] if result else None

def get_assigned_shop_ids(agent_id: int) -> list[int]:
    """استرجاع IDs المحلات المرتبطة بمجهز معين."""
    results = execute_query(
        "SELECT shop_id FROM AgentShops WHERE agent_id = %s", 
        (agent_id,), 
        fetch_all=True
    )
    # تحويل قائمة القواميس إلى قائمة من الـ ID (int)
    return [row['shop_id'] for row in results] if results else []

def check_agent_code(agent_code: str) -> dict | None:
    """تتحقق من وجود رمز الدخول السري للمجهز في قاعدة البيانات وترجع معلوماته."""
    agent = execute_query(
        "SELECT id, telegram_id, name FROM Agents WHERE secret_code = %s", 
        (agent_code,), 
        fetch_one=True
    )
    return agent # ترجع قاموس أو None

# ------------------------------------------------------------------------------------------------
# دوال التحديث والربط (التي سببت مشاكل الـ Import)
# ------------------------------------------------------------------------------------------------
def toggle_agent_shop_assignment(agent_id: int, shop_id: int, is_assigned: bool) -> bool:
    """تقوم بربط أو إلغاء ربط محل معين بمجهز معين في قاعدة البيانات."""
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
    except Exception:
        return False
        
# ------------------------------------------------------------------------------------------------
# الدالة الجديدة: تحديث تفاصيل المحل 👈🏼 تم الإضافة
# ------------------------------------------------------------------------------------------------
def update_shop_details(shop_id: int, new_name: str, new_url: str) -> bool:
    """تحديث اسم ورابط محل محدد بواسطة ID."""
    try:
        # التحقق من أن الاسم الجديد غير مستخدم من قبل محل آخر (باستثناء المحل الحالي)
        check_query = "SELECT id FROM Shops WHERE name = %s AND id != %s"
        existing_shop = execute_query(check_query, (new_name, shop_id), fetch_one=True)
        if existing_shop:
            return False # الاسم مستخدم بالفعل
            
        update_query = "UPDATE Shops SET name = %s, url = %s WHERE id = %s"
        return execute_query(update_query, (new_name, new_url, shop_id))
    except Exception:
        return False

# ------------------------------------------------------------------------------------------------
# الدالة الجديدة: حذف المحل 👈🏼 تم الإضافة
# ------------------------------------------------------------------------------------------------
def delete_shop(shop_id: int) -> bool:
    """حذف محل بواسطة ID وحذف جميع ارتباطاته بالمجهزين."""
    try:
        # 1. حذف الارتباطات من جدول AgentShops أولاً
        execute_query("DELETE FROM AgentShops WHERE shop_id = %s", (shop_id,))
        
        # 2. حذف المحل نفسه من جدول Shops
        execute_query("DELETE FROM Shops WHERE id = %s", (shop_id,))
        
        return True
    except Exception:
        return False

# ------------------------------------------------------------------------------------------------
# الدالة الجديدة: حذف المجهز 👈🏼 تم الإضافة
# ------------------------------------------------------------------------------------------------
def delete_agent(agent_id: int) -> bool:
    """حذف مجهز بواسطة ID وحذف جميع ارتباطاته بالمحلات."""
    try:
        # 1. حذف الارتباطات من جدول AgentShops أولاً
        execute_query("DELETE FROM AgentShops WHERE agent_id = %s", (agent_id,))
        
        # 2. حذف المجهز نفسه من جدول Agents
        execute_query("DELETE FROM Agents WHERE id = %s", (agent_id,))
        
        return True
    except Exception:
        return False

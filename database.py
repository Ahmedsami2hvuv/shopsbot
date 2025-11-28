# database.py
import sqlite3

# اسم قاعدة البيانات
DB_NAME = 'delivery_system.db'

def connect_db():
    """يربط بقاعدة البيانات ويرجع كائن الاتصال والمؤشر."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # حتى نرجع البيانات كـقاموس (Dict)
    return conn

def setup_db():
    """إنشاء الجداول عند تشغيل البوت لأول مرة."""
    conn = connect_db()
    cursor = conn.cursor()
    
    # جدول المحلات (Shops)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Shops (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL
        )
    """)
    
    # جدول المجهزين (Agents)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Agents (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,  -- آيدي التليجرام للمجهز (نخليه فارغ لحد ما يسجل دخول)
            name TEXT NOT NULL,
            secret_code TEXT NOT NULL UNIQUE
        )
    """)
    
    # جدول ربط المحلات والمجهزين (AgentShops)
    # هذا الجدول يحدد يا مجهز يگدر يرفع طلبية لـ يا محل
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS AgentShops (
            agent_id INTEGER,
            shop_id INTEGER,
            FOREIGN KEY (agent_id) REFERENCES Agents(id),
            FOREIGN KEY (shop_id) REFERENCES Shops(id),
            PRIMARY KEY (agent_id, shop_id)
        )
    """)
    
    conn.commit()
    conn.close()

# دالة لإضافة محل جديد
def add_shop(name: str, url: str) -> bool:
    """يضيف محل جديد ويرجع True اذا نجحت العملية."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Shops (name, url) VALUES (?, ?)", (name, url))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # ممكن يصير ايرور إذا اسم المحل موجود مسبقاً
        return False
    finally:
        conn.close()

# ******* هنا نحتاج دوال اضافية بس راح نبدي بالأساسيات حالياً *******
# (لجلب المحلات، إضافة مجهز، ربط مجهز بمحل...)

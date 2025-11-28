here# main.py
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from database import setup_db, add_shop # استدعاء الدوال الجديدة

# تعريف حالات المحادثة
(
    MAIN_MENU,          # القائمة الرئيسية للمستخدم العادي والـ Admin
    ADMIN_MENU,         # قائمة خيارات الـ Admin
    ADD_SHOP_STATE,     # حالة اضافة محل
    ADD_AGENT_STATE,    # حالة اضافة مجهز
    AGENT_LOGIN,        # حالة تسجيل دخول المجهز
    AGENT_MENU,         # قائمة المجهز (عرض المحلات المخصصة إله)
    MANAGE_AGENT,       # إدارة مجهز موجود (تعديل/إضافة محلات)
    SELECT_SHOPS        # اختيار المحلات لربطها بالمجهز
) = range(8)

# تعريف الـ Admin IDs (الناس اللي عدها صلاحية الإدارة)
# ملاحظة: لازم تحدد الأيدي مالتك هنا!
ADMIN_IDS = [123456789] # ***** حط آيدي التليجرام مالتك هنا! *****

# تفعيل نظام الـ Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# الدوال الأساسية (Start Command)
# ----------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يبدأ المحادثة ويعرض القائمة الرئيسية حسب نوع المستخدم."""
    
    user_id = update.effective_user.id
    
    # اذا كان المستخدم هو Admin (إدارة)
    if user_id in ADMIN_IDS:
        keyboard = [
            [InlineKeyboardButton("عرض المحلات", callback_data="show_shops_admin")],
            [InlineKeyboardButton("إضافة محل 🏬", callback_data="add_shop")],
            [InlineKeyboardButton("إدارة المجهزين 🧑‍💻", callback_data="manage_agents")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "👋🏼 أهلاً بك يا مدير! إختار شنو تريد تسوي:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU # نحوله لحالة قائمة المدير
        
    # اذا كان مستخدم عادي (مجهز)
    else:
        # راح نفرض انه المستخدم لازم يسجل دخول (Agent Login)
        keyboard = [
            [InlineKeyboardButton("دخول المجهز 🔑", callback_data="agent_login")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "أهلاً بك. لرفع الطلبيات، إضغط على 'دخول المجهز'.",
            reply_markup=reply_markup
        )
        return AGENT_LOGIN # نحوله لحالة تسجيل دخول المجهز

# ----------------------------------------------------------------------
# دوال قائمة المدير (Admin Menu)
# ----------------------------------------------------------------------

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعالج الأزرار اللي تنضغط بقائمة المدير."""
    query = update.callback_query
    await query.answer()
    
    # امسح الرسالة القديمة ونعرض الرسالة الجديدة
    await query.edit_message_text(text="جاري تحميل الخيار...") 

    data = query.data

    if data == "add_shop":
        await query.edit_message_text(
            "📝 **لإضافة محل جديد:**\n"
            "إرسل إسم المحل بالسطر الأول، والرابط (URL) اللي يفتح نافذة الويب بالسطر الثاني.\n"
            "مثال: \n"
            "مطعم النخيل\n"
            "https://your.app/order/shop/1"
        )
        return ADD_SHOP_STATE # تحويل لحالة إضافة محل

    elif data == "manage_agents":
        # ****** نحتاج نسوي دالة تجيب المجهزين من DB ونعرضهم كأزرار ******
        await query.edit_message_text("🧑‍💻 إدارة المجهزين... (هذا الخيار قريباً)")
        return ADMIN_MENU # يبقى بنفس الحالة حالياً
    
    # اذا ماكو خيار، نرجع للقائمة الرئيسية
    else:
        await start_command(update, context) # نرجع لقائمة الـ start
        return ADMIN_MENU


# ----------------------------------------------------------------------
# دوال إضافة محل (Add Shop State)
# ----------------------------------------------------------------------

async def receive_shop_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المحل ويحفظها بقاعدة البيانات."""
    
    try:
        # فصل الإسم والرابط (نفترض أنهن على سطرين)
        text = update.message.text.strip()
        parts = text.split('\n', 1) # يقسم النص على سطرين كحد أقصى
        
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ صيغة الإدخال خطأ. لازم تكون:\n"
                "إسم المحل\n"
                "رابط المحل (URL)"
            )
            return ADD_SHOP_STATE # نرجع لنفس الحالة

        shop_name = parts[0].strip()
        shop_url = parts[1].strip()

        # إستدعاء دالة الحفظ من database.py
        if add_shop(shop_name, shop_url):
            keyboard = [[InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="start")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ تم إضافة المحل **{shop_name}** بنجاح!",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"❌ المحل **{shop_name}** موجود مسبقاً أو حدث خطأ بالحفظ."
            )
        
    except Exception as e:
        logger.error(f"Error adding shop: {e}")
        await update.message.reply_text("❌ حدث خطأ غير متوقع أثناء إضافة المحل.")

    # نرجع لقائمة المدير
    return ADMIN_MENU


# ----------------------------------------------------------------------
# الدالة الرئيسية للتشغيل
# ----------------------------------------------------------------------

def main() -> None:
    """بدء تشغيل البوت."""
    
    # 1. تهيئة قاعدة البيانات قبل كلشي
    setup_db() 
    
    # 2. جلب التوكن
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("🚫 التوكن مال البوت (BOT_TOKEN) ما متوفر بمتغيرات البيئة.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # إنشاء الـ Conversation Handler لإدارة الحالات
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(admin_menu_handler, pattern="^(add_shop|manage_agents)$"),
                # هنا ممكن نضيف خيارات ثانية مثل عرض المحلات
                CallbackQueryHandler(start_command, pattern="^start$") # العودة للقائمة
            ],
            
            ADD_SHOP_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_shop_data)
            ],
            
            # ****** هنا نضيف حالات AGENT_LOGIN, AGENT_MENU, وغيرهن لاحقاً ******
            AGENT_LOGIN: [
                CallbackQueryHandler(admin_menu_handler) # مؤقتاً
            ],
        },
        
        fallbacks=[CommandHandler("start", start_command)], # اذا صارت مشكلة نرجع لـ /start
    )

    application.add_handler(conv_handler)

    logger.info("🤖 البوت جاي يشتغل (Long Polling)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

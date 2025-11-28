# main.py
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
# استدعاء كل الدوال من database.py

from database import setup_db, add_shop, get_all_shops, add_agent, get_all_agents

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
ADMIN_IDS = [7032076289] # آيدي التليجرام مالتك

# تفعيل نظام الـ Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# تعيين الـ Logger للـ python-telegram-bot
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# الدوال المساعدة (Helper Functions)
# ----------------------------------------------------------------------

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تظهر قائمة خيارات المدير، وتُستخدم للرجوع من أي قائمة فرعية."""
    keyboard = [
        [InlineKeyboardButton("عرض المحلات 📊", callback_data="show_shops_admin")],
        [InlineKeyboardButton("إضافة محل 🏬", callback_data="add_shop")],
        [InlineKeyboardButton("إدارة المجهزين 🧑‍💻", callback_data="manage_agents")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "👋🏼 أهلاً بك يا مدير! إختار شنو تريد تسوي:"
    
    # لمعالجة الضغط على زر (CallbackQuery)
    if update.callback_query:
        await update.callback_query.answer()
        # نعدل الرسالة الموجودة بدلاً من إرسال رسالة جديدة
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    # لمعالجة أمر /start جديد
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)
        
    return ADMIN_MENU

# ----------------------------------------------------------------------
# الدوال الأساسية (Start Command)
# ----------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يبدأ المحادثة ويعرض القائمة الرئيسية حسب نوع المستخدم."""
    
    user_id = update.effective_user.id
    
    # اذا كان المستخدم هو Admin (إدارة)
    if user_id in ADMIN_IDS:
        # توجه مباشرة للدالة الجديدة اللي تعرض قائمة المدير (وتعالج الكولباك)
        return await show_admin_menu(update, context) 
        
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


async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعالج الأزرار اللي تنضغط بقائمة المدير."""
    query = update.callback_query
    
    data = query.data
    
    if data == "admin_menu": 
        return await show_admin_menu(update, context)

    if data == "show_shops_admin":
        return await show_shops_admin_handler(update, context)

    if data == "add_shop":
        await query.answer()
        await query.edit_message_text(
            "📝 **لإضافة محل جديد:**\n"
            "إرسل إسم المحل بالسطر الأول، والرابط (URL) اللي يفتح نافذة الويب بالسطر الثاني.\n"
            "مثال: \n"
            "مطعم النخيل\n"
            "https://your.app/order/shop/1",
            parse_mode="Markdown"
        )
        return ADD_SHOP_STATE

    if data == "manage_agents":
        return await manage_agents_menu(update, context) # توجيه لقائمة إدارة المجهزين
    
    return ADMIN_MENU

# ----------------------------------------------------------------------
# دوال عرض المحلات (Show Shops State)
# ----------------------------------------------------------------------

async def show_shops_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يجلب المحلات ويعرضها على شكل ازرار WebApp للأدمن."""
    query = update.callback_query
    await query.answer()

    shops = get_all_shops() # جلب المحلات
    
    keyboard = []
    
    if shops:
        # هنا نرتب الأزرار: كل 2 أو 3 زر بسطر واحد
        current_row = []
        for i, shop in enumerate(shops):
            # إنشاء الزر كـ WebAppInfo (حتى يفتح نافذة المتصفح)
            button = InlineKeyboardButton(
                text=shop['name'], 
                web_app=WebAppInfo(url=shop['url'])
            )
            current_row.append(button)
            
            # إذا صار عندنا 3 أزرار بالسطر، أو وصلنا لآخر محل:
            if len(current_row) == 3 or i == len(shops) - 1:
                keyboard.append(current_row) # نضيف السطر للوحة المفاتيح
                current_row = [] # نبدي سطر جديد

        # إضافة زر العودة للقائمة الرئيسية بآخر شي
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")])
        
        text = "📊 **إختر المحل لرفع الطلبية:**"
    
    else:
        text = "❌ لا توجد محلات مُضافة حالياً."
        keyboard.append([InlineKeyboardButton("🏬 إضافة محل جديد", callback_data="add_shop")])
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text, 
        reply_markup=reply_markup,
        parse_mode="Markdown" 
    )
    
    return ADMIN_MENU


# ----------------------------------------------------------------------
# دوال إضافة محل (Add Shop State)
# ----------------------------------------------------------------------

async def receive_shop_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المحل ويحفظها بقاعدة البيانات."""
    
    try:
        # فصل الإسم والرابط (نفترض أنه على سطرين)
        text = update.message.text.strip()
        parts = text.split('\n', 1) 
        
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ صيغة الإدخال خطأ. لازم تكون:\n"
                "إسم المحل\n"
                "رابط المحل (URL)"
            )
            return ADD_SHOP_STATE # نرجع لنفس الحالة

        shop_name = parts[0].strip()
        shop_url = parts[1].strip()

        # إستدعاء دالة الحفظ
        if add_shop(shop_name, shop_url):
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ تم إضافة المحل **{shop_name}** بنجاح!",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ المحل **{shop_name}** موجود مسبقاً أو حدث خطأ بالحفظ.",
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error adding shop: {e}")
        await update.message.reply_text("❌ حدث خطأ غير متوقع أثناء إضافة المحل.")

    # نرجع لقائمة المدير
    return ADMIN_MENU

# ----------------------------------------------------------------------
# دوال إدارة المجهزين (Agent Management)
# ----------------------------------------------------------------------


async def manage_agents_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة خيارات إدارة المجهزين."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("إضافة مجهز جديد ➕", callback_data="add_new_agent")], 
        [InlineKeyboardButton("عرض وتعديل المجهزين 📄", callback_data="list_agents")], # شلنا (قريباً)
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🧑‍💻 **قائمة إدارة المجهزين:**\n\nإختار الإجراء المطلوب:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return MANAGE_AGENT # تحويل لحالة إدارة المجهز


async def list_agents_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة بالمجهزين الحاليين كأزرار للتعديل."""
    query = update.callback_query
    await query.answer()

    agents = get_all_agents() # جلب المجهزين
    
    keyboard = []
    text = "📄 **قائمة المجهزين الحاليين:**\n\n"

    if agents:
        # ترتيب الأزرار: سطر واحد لكل مجهز
        for agent in agents:
            # الـ callback_data راح يكون "select_agent_" متبوع بـ ID المجهز الداخلي
            callback_data = f"select_agent_{agent['id']}" 
            keyboard.append([InlineKeyboardButton(agent['name'], callback_data=callback_data)])
        
        text += "إختر المجهز اللي تريد تعدل عليه أو تربطه بمحلات:"

    else:
        text = "❌ لا يوجد مجهزين مُضافين حالياً."
        keyboard.append([InlineKeyboardButton("➕ إضافة مجهز جديد", callback_data="add_new_agent")])

    # زر العودة لإدارة المجهزين
    keyboard.append([InlineKeyboardButton("🔙 العودة لإدارة المجهزين", callback_data="manage_agents")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text, 
        reply_markup=reply_markup,
        parse_mode="Markdown" 
    )
    
    return MANAGE_AGENT


async def add_new_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تطلب بيانات المجهز الجديد."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔑 **لإضافة مجهز جديد:**\n"
        "إرسل إسم المجهز بالسطر الأول، ورمز الدخول السري (كلمة سر خاصة بيه) بالسطر الثاني.\n"
        "مثال: \n"
        "علي الزيدي\n"
        "AZ1234",
        parse_mode="Markdown"
    )
    return ADD_AGENT_STATE # تحويل لحالة إدخال بيانات المجهز


async def receive_agent_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المجهز ويحفظها بقاعدة البيانات."""
    
    try:
        # فصل الإسم والرمز السري (نفترض أنهن على سطرين)
        text = update.message.text.strip()
        parts = text.split('\n', 1) 
        
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ صيغة الإدخال خطأ. لازم تكون:\n"
                "إسم المجهز\n"
                "رمز الدخول السري"
            )
            return ADD_AGENT_STATE # نرجع لنفس الحالة

        agent_name = parts[0].strip()
        agent_code = parts[1].strip()

        # إستدعاء دالة الحفظ
        if add_agent(agent_name, agent_code):
            keyboard = [[InlineKeyboardButton("🔙 العودة لإدارة المجهزين", callback_data="manage_agents")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ تم إضافة المجهز **{agent_name}** بنجاح، ورمز دخوله هو: **{agent_code}**",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ الرمز السري موجود مسبقاً أو حدث خطأ بالحفظ. جرب رمز سري مختلف.",
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error adding agent: {e}")
        await update.message.reply_text("❌ حدث خطأ غير متوقع أثناء إضافة المجهز.")

    # نرجع لقائمة إدارة المجهزين
    return MANAGE_AGENT


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
                # عدلنا الـ pattern حتى يشمل كل الـ callbacks الجديدة
                CallbackQueryHandler(admin_menu_handler, pattern="^(add_shop|manage_agents|show_shops_admin|admin_menu)$"),
            ],
            
            ADD_SHOP_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_shop_data)
            ],
            
            # حالة إدارة المجهزين
            MANAGE_AGENT: [
                CallbackQueryHandler(admin_menu_handler, pattern="^admin_menu$"), 
                CallbackQueryHandler(add_new_agent_menu, pattern="^add_new_agent$"), 
                CallbackQueryHandler(admin_menu_handler, pattern="^manage_agents$"), # العودة لإدارة المجهزين
                CallbackQueryHandler(list_agents_menu, pattern="^list_agents$"), # *التعريف الجديد*
            ],
            
            # حالة إضافة بيانات المجهز
            ADD_AGENT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_agent_data)
            ],
            
            # حالات المجهز (تسجيل الدخول)
            AGENT_LOGIN: [
                # مؤقت
            ],
        },
        
        fallbacks=[CommandHandler("start", start_command)],
    )

    application.add_handler(conv_handler)

    logger.info("🤖 البوت جاي يشتغل (Long Polling)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

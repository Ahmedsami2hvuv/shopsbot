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
# استدعاء كل الدوال اللازمة من database.py 
from database import (
    setup_db, 
    add_shop, 
    get_all_shops, 
    add_agent, 
    get_all_agents, 
    get_agent_name_by_id,
    # نفترض وجود هذه الدوال الجديدة الآن لمعالجة الربط التفاعلي
    get_assigned_shop_ids, # لمعرفة المحلات المرتبطة حالياً
    toggle_agent_shop_assignment # لربط/إلغاء ربط المحل
) 

# تعريف حالات المحادثة
(
    MAIN_MENU,          
    ADMIN_MENU,         
    ADD_SHOP_STATE,     
    ADD_AGENT_STATE,    
    AGENT_LOGIN,        
    AGENT_MENU,         
    MANAGE_AGENT,       
    SELECT_SHOPS        
) = range(8)

# تعريف الـ Admin IDs (الناس اللي عدها صلاحية الإدارة)
ADMIN_IDS = [7032076289] # آيدي التليجرام مالتك

# تفعيل نظام الـ Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
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
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)
        
    return ADMIN_MENU

# ----------------------------------------------------------------------
# الدوال الأساسية
# ----------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يبدأ المحادثة ويعرض القائمة الرئيسية حسب نوع المستخدم."""
    
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        return await show_admin_menu(update, context) 
    else:
        # هنا نعرض الزر الذي يقود لحالة AGENT_LOGIN
        keyboard = [
            [InlineKeyboardButton("دخول المجهز 🔑", callback_data="agent_login_prompt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "أهلاً بك. لرفع الطلبيات، إضغط على 'دخول المجهز'.",
            reply_markup=reply_markup
        )
        return AGENT_LOGIN

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
        keyboard = [
            [InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="admin_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📝 **لإضافة محل جديد:**\n"
            "إرسل إسم المحل بالسطر الأول، والرابط (URL) اللي يفتح نافذة الويب بالسطر الثاني.\n"
            "مثال: \n"
            "مطعم النخيل\n"
            "https://your.app/order/shop/1",
            parse_mode="Markdown",
            reply_markup=reply_markup 
        )
        return ADD_SHOP_STATE

    if data == "manage_agents":
        return await manage_agents_menu(update, context)
    
    return ADMIN_MENU

# ----------------------------------------------------------------------
# دوال عرض المحلات (Show Shops State)
# ----------------------------------------------------------------------

async def show_shops_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يجلب المحلات ويعرضها على شكل ازرار WebApp للأدمن (تم حل مشكلة عدم عمل هذه الميزة)."""
    
    # نحدد مصدر التحديث (زر أو أمر)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message_to_edit = query.edit_message_text
    else:
        # إذا كان الاستدعاء من مكان آخر غير زر، نعامله كرسالة جديدة (نادر الحدوث هنا)
        return ADMIN_MENU

    shops = get_all_shops()
    
    keyboard = []
    
    if shops:
        current_row = []
        for i, shop in enumerate(shops):
            button = InlineKeyboardButton(
                text=shop['name'], 
                web_app=WebAppInfo(url=shop['url'])
            )
            current_row.append(button)
            
            if len(current_row) == 3 or i == len(shops) - 1:
                keyboard.append(current_row)
                current_row = []

        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")])
        text = "📊 **إختر المحل لرفع الطلبية:**"
    
    else:
        text = "❌ لا توجد محلات مُضافة حالياً."
        keyboard.append([InlineKeyboardButton("🏬 إضافة محل جديد", callback_data="add_shop")])
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await message_to_edit(
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
        text = update.message.text.strip()
        parts = text.split('\n', 1) 
        
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ صيغة الإدخال خطأ. لازم تكون:\n"
                "إسم المحل\n"
                "رابط المحل (URL)"
            )
            return ADD_SHOP_STATE

        shop_name = parts[0].strip()
        shop_url = parts[1].strip()

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
        [InlineKeyboardButton("عرض وتعديل المجهزين 📄", callback_data="list_agents")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🧑‍💻 **قائمة إدارة المجهزين:**\n\nإختار الإجراء المطلوب:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return MANAGE_AGENT


async def list_agents_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة بالمجهزين الحاليين كأزرار للتعديل."""
    query = update.callback_query
    await query.answer()

    agents = get_all_agents()
    
    keyboard = []
    text = "📄 **قائمة المجهزين الحاليين:**\n\n"

    if agents:
        for agent in agents:
            callback_data = f"select_agent_{agent['id']}" 
            keyboard.append([InlineKeyboardButton(agent['name'], callback_data=callback_data)])
        
        text += "إختر المجهز اللي تريد تعدل عليه أو تربطه بمحلات:"

    else:
        text = "❌ لا يوجد مجهزين مُضافين حالياً."
        keyboard.append([InlineKeyboardButton("➕ إضافة مجهز جديد", callback_data="add_new_agent")])

    keyboard.append([InlineKeyboardButton("🔙 العودة لإدارة المجهزين", callback_data="manage_agents")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text, 
        reply_markup=reply_markup,
        parse_mode="Markdown" 
    )
    
    return MANAGE_AGENT


async def select_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض خيارات التعديل لمجهز محدد."""
    query = update.callback_query
    await query.answer()

    if query.data and query.data.startswith("select_agent_"):
        agent_id = int(query.data.split('_')[-1])
        context.user_data['selected_agent_id'] = agent_id 
        # عند الدخول لقائمة التعديل، نقوم بتحميل المحلات المرتبطة من قاعدة البيانات
        # ونخزنها مؤقتاً لعملية التعديل
        try:
            assigned_ids = get_assigned_shop_ids(agent_id)
            context.user_data['temp_assigned_shops'] = set(assigned_ids)
        except Exception:
            context.user_data['temp_assigned_shops'] = set() # في حال لم تكن الدالة متوفرة بعد

    agent_id = context.user_data.get('selected_agent_id')

    if not agent_id:
        await query.edit_message_text("❌ حدث خطأ، لم يتم تحديد المجهز.")
        return await manage_agents_menu(update, context)
        
    agent_name = get_agent_name_by_id(agent_id) 
    if not agent_name:
        agent_name = f"المجهز رقم {agent_id}"

    keyboard = [
        [InlineKeyboardButton(f"إضافة محلات إلى {agent_name} 🏪", callback_data=f"assign_shops_{agent_id}")],
        [InlineKeyboardButton(f"تعديل تفاصيل {agent_name} ✏️ (قريباً)", callback_data=f"edit_details_soon")],
        [InlineKeyboardButton("🔙 العودة لقائمة المجهزين", callback_data="list_agents")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"**إختر الإجراء المطلوب للمجهز {agent_name}:**",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return MANAGE_AGENT


async def list_shops_to_assign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة المحلات لربطها بالمجهز وتظهر علامة ✅ (حل المشكلة الجديدة)."""
    query = update.callback_query
    await query.answer()

    agent_id = context.user_data.get('selected_agent_id')
    if not agent_id:
        return await manage_agents_menu(update, context)
        
    shops = get_all_shops()
    agent_name = get_agent_name_by_id(agent_id) or f"المجهز رقم {agent_id}"
    
    # جلب المحلات المحددة حالياً من الـ context
    selected_shops = context.user_data.get('temp_assigned_shops', set())

    keyboard = []
    
    if not shops:
        keyboard.append([InlineKeyboardButton("🔙 العودة لخيارات المجهز", callback_data=f"select_agent_{agent_id}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"❌ لا توجد محلات مُضافة حالياً لربطها بالمجهز {agent_name}.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return MANAGE_AGENT

    for shop in shops:
        is_selected = shop['id'] in selected_shops
        emoji = "✅ " if is_selected else "⬜ "
        callback_data = f"toggle_shop_{shop['id']}"
        keyboard.append([InlineKeyboardButton(f"{emoji}{shop['name']}", callback_data=callback_data)])

    # أزرار الإجراءات
    keyboard.append([InlineKeyboardButton("✅ تأكيد وحفظ الربط", callback_data="confirm_shop_assignment")])
    keyboard.append([InlineKeyboardButton("🔙 إلغاء والعودة لخيارات المجهز", callback_data=f"select_agent_{agent_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🏪 **ربط محلات بالمجهز {agent_name}:**\n\n"
        "إختر المحلات التي سيتم إتاحتها لهذا المجهز. اضغط على 'تأكيد وحفظ الربط' لتطبيق التغييرات.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return SELECT_SHOPS


async def toggle_shop_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعكس حالة اختيار المحل مؤقتاً ويعيد عرض القائمة (لحل المشكلة الجديدة)."""
    query = update.callback_query
    await query.answer()
    
    # جلب ID المحل من الـ callback data
    shop_id = int(query.data.split('_')[-1])
    
    # جلب قائمة المحلات المختارة مؤقتاً
    selected_shops = context.user_data.get('temp_assigned_shops', set())
    
    # عكس حالة الاختيار
    if shop_id in selected_shops:
        selected_shops.remove(shop_id)
    else:
        selected_shops.add(shop_id)
        
    # حفظ التغييرات في الـ context
    context.user_data['temp_assigned_shops'] = selected_shops
    
    # إعادة عرض القائمة المحدثة
    return await list_shops_to_assign(update, context)


async def handle_shop_assignment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """حفظ المحلات المختارة في قاعدة البيانات."""
    query = update.callback_query
    await query.answer()
    
    agent_id = context.user_data.get('selected_agent_id')
    selected_shops = context.user_data.get('temp_assigned_shops', set())
    
    if not agent_id:
        await query.edit_message_text("❌ حدث خطأ، لم يتم تحديد المجهز.")
        return await manage_agents_menu(update, context)

    try:
        # هنا سننفذ عملية الحفظ في قاعدة البيانات
        # نحتاج دالة في database.py تقوم بربط/إلغاء ربط كل المحلات دفعة واحدة
        # مؤقتاً: سننفذ منطق تبسيط، يفترض أنك ستنفذ الدالة toggle_agent_shop_assignment
        
        # 1. جلب المحلات المرتبطة حالياً من القاعدة
        current_assigned_ids = set(get_assigned_shop_ids(agent_id))
        
        # 2. تحديد المحلات التي يجب إضافتها وإزالتها
        to_add = selected_shops - current_assigned_ids
        to_remove = current_assigned_ids - selected_shops
        
        # 3. تطبيق التغييرات
        for shop_id in to_add:
            toggle_agent_shop_assignment(agent_id, shop_id, True)
        for shop_id in to_remove:
            toggle_agent_shop_assignment(agent_id, shop_id, False)

        await query.edit_message_text("✅ تم حفظ ربط المحلات بنجاح!")
        
    except Exception as e:
        logger.error(f"Error saving shop assignment for agent {agent_id}: {e}")
        await query.edit_message_text("❌ حدث خطأ أثناء محاولة حفظ ربط المحلات.")

    # نرجع لقائمة خيارات المجهز بعد الانتهاء
    return await select_agent_menu(update, context)


async def add_new_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تطلب بيانات المجهز الجديد."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="manage_agents")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔑 **لإضافة مجهز جديد:**\n"
        "إرسل إسم المجهز بالسطر الأول، ورمز الدخول السري (كلمة سر خاصة بيه) بالسطر الثاني.\n"
        "مثال: \n"
        "علي الزيدي\n"
        "AZ1234",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return ADD_AGENT_STATE


async def receive_agent_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المجهز ويحفظها بقاعدة البيانات."""
    
    try:
        text = update.message.text.strip()
        parts = text.split('\n', 1) 
        
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ صيغة الإدخال خطأ. لازم تكون:\n"
                "إسم المجهز\n"
                "رمز الدخول السري"
            )
            return ADD_AGENT_STATE

        agent_name = parts[0].strip()
        agent_code = parts[1].strip()

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

    return MANAGE_AGENT

# ----------------------------------------------------------------------
# دوال المجهز (Agent)
# ----------------------------------------------------------------------

async def agent_login_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب من المجهز إدخال رمز الدخول السري (حل مشكلة عدم عمل الزر)."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🔑 **تسجيل دخول المجهز:**\n"
        "الرجاء إرسال رمز الدخول السري الخاص بك:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return AGENT_LOGIN

async def agent_login_receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل رمز الدخول السري ويتحقق منه (هيكل)."""
    # هنا يجب إضافة منطق التحقق من الرمز في database.py
    # if check_agent_code(update.message.text):
    #     return AGENT_MENU
    # else:
    #     await update.message.reply_text("❌ رمز الدخول غير صحيح.")
    #     return AGENT_LOGIN

    await update.message.reply_text("مرحباً بك كمجهز! (منطق التحقق قيد التنفيذ)")
    return AGENT_MENU # مؤقتاً نرجع لقائمة المجهز

# ----------------------------------------------------------------------
# الدالة الرئيسية للتشغيل
# ----------------------------------------------------------------------

def main() -> None:
    """بدء تشغيل البوت."""
    
    setup_db() 
    
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("🚫 التوكن مال البوت (BOT_TOKEN) ما متوفر بمتغيرات البيئة.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(admin_menu_handler, pattern="^(add_shop|manage_agents|show_shops_admin|admin_menu)$"),
            ],
            
            ADD_SHOP_STATE: [
                CallbackQueryHandler(admin_menu_handler, pattern="^admin_menu$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_shop_data),
            ],
            
            MANAGE_AGENT: [
                CallbackQueryHandler(admin_menu_handler, pattern="^admin_menu$"), 
                CallbackQueryHandler(manage_agents_menu, pattern="^manage_agents$"), # للعودة من القوائم الفرعية
                CallbackQueryHandler(add_new_agent_menu, pattern="^add_new_agent$"), 
                CallbackQueryHandler(list_agents_menu, pattern="^list_agents$"), 
                
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"),
                CallbackQueryHandler(list_shops_to_assign, pattern="^assign_shops_\d+$"),
            ],
            
            ADD_AGENT_STATE: [
                CallbackQueryHandler(manage_agents_menu, pattern="^manage_agents$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_agent_data)
            ],

            SELECT_SHOPS: [
                CallbackQueryHandler(handle_shop_assignment, pattern="^confirm_shop_assignment$"),
                # زر اختيار/إلغاء اختيار المحل
                CallbackQueryHandler(toggle_shop_selection, pattern="^toggle_shop_\d+$"), 
                # العودة لخيارات المجهز
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"),
            ],
            
            AGENT_LOGIN: [
                # New: Handler for the initial login prompt button
                CallbackQueryHandler(agent_login_prompt, pattern="^agent_login_prompt$"),
                # New: Handler for receiving the code
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_login_receive_code),
                # New: Handler for Cancel button in login prompt
                CommandHandler("start", start_command),
                CallbackQueryHandler(start_command, pattern="^start$"),
            ],

            AGENT_MENU: [
                # قائمة المجهز
            ]
        },
        
        fallbacks=[CommandHandler("start", start_command)],
    )

    application.add_handler(conv_handler)

    logger.info("🤖 البوت جاي يشتغل (Long Polling)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

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
from database import (
    setup_db, 
    add_shop, 
    get_all_shops, 
    update_shop_details, 
    delete_shop,         
    add_agent, 
    get_all_agents, 
    get_agent_name_by_id,
    get_assigned_shop_ids, 
    toggle_agent_shop_assignment,
    check_agent_code,
    update_agent_details, 
    delete_agent,         
    get_agent_shops_by_search, 
    get_shops_by_search        
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
    SELECT_SHOPS,
    EDIT_AGENT_DETAILS,
    DELETE_SHOP_STATE, 
    EDIT_SHOP_STATE,    
    DELETE_AGENT_STATE,
    SHOW_SHOPS_ADMIN 
) = range(13) 

# تعريف الـ Admin IDs (الناس اللي عدها صلاحية الإدارة)
ADMIN_IDS = [7032076289] # آيدي التليجرام مالتك

# تفعيل نظام الـ Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# الدوال الأساسية والتحقق من الصلاحيات
# ----------------------------------------------------------------------

def is_admin(user_id: int) -> bool:
    """التحقق ما إذا كان المستخدم يملك صلاحيات الإدارة."""
    return user_id in ADMIN_IDS

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة البداية للمستخدم."""
    if not update.message:
        # إذا كانت الدالة تم استدعاؤها من CallbackQuery (مثل تسجيل الخروج)، نستخدم update.callback_query.message
        message = update.callback_query.message
        # إزالة البيانات المخزنة من المحادثة السابقة
        context.user_data.clear()
        
    elif update.message:
        message = update.message
        # إزالة البيانات المخزنة من المحادثة السابقة
        context.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("مدير 👑", callback_data="admin_login")],
        [InlineKeyboardButton("مجهز 🧑‍💻", callback_data="agent_login_prompt")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        "👋🏼 أهلاً بك! إختار نوع حسابك:", 
        reply_markup=reply_markup
    )
    return MAIN_MENU

# ----------------------------------------------------------------------
# دوال إدارة المدير (ADMIN)
# ----------------------------------------------------------------------

async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يتحقق من هوية المدير ويعرض القائمة الرئيسية للإدارة."""
    user_id = update.effective_user.id
    await update.callback_query.answer()
    
    if is_admin(user_id):
        return await show_admin_menu(update, context)
    else:
        await update.callback_query.edit_message_text("❌ آسف، لا تملك صلاحية المدير.")
        return MAIN_MENU

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تظهر قائمة خيارات المدير، وتُستخدم للرجوع من أي قائمة فرعية."""
    
    keyboard = [
        [InlineKeyboardButton("عرض المحلات 📊", callback_data="show_shops_list")], 
        [InlineKeyboardButton("إضافة محل 🏬", callback_data="add_shop"), 
         InlineKeyboardButton("حذف محل 🗑️", callback_data="delete_shop")], 
        [InlineKeyboardButton("تعديل محل ✏️", callback_data="edit_shops")], 
        [InlineKeyboardButton("إدارة المجهزين 🧑‍💻", callback_data="manage_agents")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "👋🏼 أهلاً بك يا مدير! إختار شنو تريد تسوي:"
    
    if update.callback_query:
        await update.callback_query.answer()
        try:
             await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
        except Exception:
             await update.callback_query.message.reply_text(text=text, reply_markup=reply_markup)

    elif update.message:
        await update.message.reply_text(text=text, reply_markup=reply_markup)
        
    return ADMIN_MENU

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج عام لأزرار قائمة المدير الرئيسية."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "add_shop":
        await query.edit_message_text(
            "📝 أرسل اسم المحل ورابطه في سطرين منفصلين:\n"
            "الاسم\n"
            "الرابط (URL)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="admin_menu")]])
        )
        return ADD_SHOP_STATE
    
    elif data == "manage_agents":
        return await manage_agents_menu(update, context)

    # Note: shop list handlers are handled in SHOW_SHOPS_ADMIN state now.
    
    return ADMIN_MENU


# ----------------------------------------------------------------------
# دوال إدارة المحلات (Shops Management)
# ----------------------------------------------------------------------

async def receive_shop_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المحل الجديد ويحفظها."""
    text = update.message.text.strip()
    parts = text.split('\n', 1) 
    
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ صيغة الإدخال خطأ. لازم تكون:\n"
            "الاسم\n"
            "الرابط (URL)"
        )
        return ADD_SHOP_STATE

    shop_name = parts[0].strip()
    shop_url = parts[1].strip()

    if add_shop(shop_name, shop_url):
        await update.message.reply_text(f"✅ تم إضافة محل: {shop_name}")
    else:
        await update.message.reply_text("❌ فشل إضافة المحل. قد يكون الاسم مستخدماً بالفعل أو حدث خطأ في قاعدة البيانات.")

    # نعود إلى القائمة الرئيسية للمدير
    return await show_admin_menu(update, context)

# --- عرض وبحث المحلات (SHOW_SHOPS_ADMIN State) ---

async def show_and_search_shops(update: Update, context: ContextTypes.DEFAULT_TYPE, search_term: str = None) -> int:
    """تعرض قائمة المحلات وتسمح بالبحث، مع أزرار الإدارة."""
    
    if search_term:
        shops = get_shops_by_search(search_term) # بحث جزئي
    else:
        shops = get_all_shops() # عرض الكل
    
    keyboard = []
    
    if shops:
        if search_term:
            text = f"✅ **نتائج البحث عن '{search_term}'**:"
        else:
            text = "📊 **جميع المحلات:**\n يمكنك كتابة اسم المحل للبحث السريع."
            
        for shop in shops:
            shop_url = shop['url']
            if not shop_url.lower().startswith(('http://', 'https://')):
                 shop_url = "https://" + shop_url 
            
            # زر رابط المحل
            url_button = InlineKeyboardButton(text=f"🔗 {shop['name']}", url=shop_url)
            
            # أزرار الإدارة
            edit_button = InlineKeyboardButton("✏️ تعديل", callback_data=f"edit_shop_select_{shop['id']}")
            delete_button = InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_shop_confirm_{shop['id']}")
            
            keyboard.append([url_button])
            keyboard.append([edit_button, delete_button]) # صف جديد فيه زري التعديل والحذف
            keyboard.append([InlineKeyboardButton("---", callback_data="ignore")]) # فاصل
    
    else:
        if search_term:
            text = f"❌ لا توجد محلات مطابقة لـ '{search_term}'."
        else:
            text = "❌ لا توجد محلات مُضافة حالياً."
            keyboard.append([InlineKeyboardButton("🏬 إضافة محل جديد", callback_data="add_shop")])

    keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # التعامل مع تحديث الرسالة أو إرسال رسالة جديدة
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=text, 
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    elif update.message:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # نعود إلى حالة عرض المحلات للسماح بالبحث أو النقر على الأزرار
    return SHOW_SHOPS_ADMIN

async def admin_shop_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل نص البحث من المدير (في حالة SHOW_SHOPS_ADMIN) ويعرض النتائج."""
    search_term = update.message.text.strip()
    
    # نستخدم الدالة الأساسية لتنفيذ البحث وعرض النتائج
    return await show_and_search_shops(update, context, search_term)

# --- حذف المحلات (DELETE_SHOP_STATE) ---

async def confirm_shop_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض رسالة تأكيد لحذف المحل."""
    query = update.callback_query
    await query.answer()
    
    # استخلاص ID المحل من CallbackData (delete_shop_confirm_ID)
    try:
        shop_id = int(query.data.split('_')[-1])
    except ValueError:
        return await show_admin_menu(update, context)

    if update.callback_query and update.callback_query.data.startswith('delete_shop_confirm_'):
        # هنا يتم التنفيذ الفعلي للحذف (عندما يأتي من زر "حذف" في قائمة البحث)
        if delete_shop(shop_id):
            await query.edit_message_text(
                f"✅ تم حذف المحل بنجاح!", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة لقائمة المحلات", callback_data="show_shops_list")]])
            )
        else:
            await query.edit_message_text(
                "❌ حدث خطأ أثناء حذف المحل.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة لقائمة المحلات", callback_data="show_shops_list")]])
            )
        # نعود إلى قائمة البحث والعرض بعد الحذف
        return SHOW_SHOPS_ADMIN
    
    return SHOW_SHOPS_ADMIN

# --- تعديل المحلات (EDIT_SHOP_STATE) ---

async def prompt_edit_shop_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب من المدير إدخال تفاصيل التعديل للمحل المحدد."""
    query = update.callback_query
    await query.answer()
    
    # استخلاص ID المحل من CallbackData (edit_shop_select_ID)
    try:
        shop_id = int(query.data.split('_')[-1])
    except ValueError:
        return await show_admin_menu(update, context)
    
    # تخزين ID المحل في بيانات المستخدم
    context.user_data['selected_shop_id'] = shop_id
    
    keyboard = [[InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="show_shops_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"📝 لإجراء التعديل على المحل رقم {shop_id}:\n"
        "أرسل **الاسم الجديد** و **الرابط الجديد** في سطرين منفصلين:\n"
        "الاسم الجديد\n"
        "الرابط الجديد (URL)",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return EDIT_SHOP_STATE

async def receive_updated_shop_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المحل المحدثة ويحفظها."""
    text = update.message.text.strip()
    parts = text.split('\n', 1) 
    shop_id = context.user_data.get('selected_shop_id')

    if not shop_id:
        await update.message.reply_text("❌ حدث خطأ، لم يتم تحديد المحل المطلوب تعديله.")
        return await show_and_search_shops(update, context) 

    if len(parts) != 2:
        await update.message.reply_text(
            "❌ صيغة الإدخال خطأ. الرجاء إرسال الاسم الجديد والرابط الجديد في سطرين منفصلين."
        )
        return EDIT_SHOP_STATE

    new_name = parts[0].strip()
    new_url = parts[1].strip()

    if update_shop_details(shop_id, new_name, new_url):
        await update.message.reply_text(f"✅ تم تحديث تفاصيل المحل رقم {shop_id} بنجاح!")
    else:
        await update.message.reply_text("❌ فشل تحديث التفاصيل. قد يكون الاسم مستخدماً أو حدث خطأ.")

    # نعود إلى قائمة عرض المحلات
    return await show_and_search_shops(update, context) 


# ----------------------------------------------------------------------
# دوال إدارة المجهزين (Agents Management)
# ----------------------------------------------------------------------

async def manage_agents_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة خيارات إدارة المجهزين."""
    keyboard = [
        [InlineKeyboardButton("إضافة مجهز ➕", callback_data="add_new_agent")],
        [InlineKeyboardButton("عرض المجهزين 📄", callback_data="list_agents")],
        [InlineKeyboardButton("حذف مجهز 🗑️", callback_data="delete_agent")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "إختر عملية لإدارة المجهزين:"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=reply_markup)
        
    return MANAGE_AGENT

# --- إضافة مجهز ---

async def add_new_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب تفاصيل المجهز الجديد."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="manage_agents")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📝 أرسل اسم المجهز والرمز السري الخاص به في سطرين منفصلين:\n"
        "الاسم\n"
        "الرمز السري",
        reply_markup=reply_markup
    )
    return ADD_AGENT_STATE

async def receive_agent_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المجهز الجديد ويحفظها."""
    text = update.message.text.strip()
    parts = text.split('\n', 1) 
    
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ صيغة الإدخال خطأ. الرجاء إرسال الاسم والرمز السري في سطرين منفصلين."
        )
        return ADD_AGENT_STATE

    agent_name = parts[0].strip()
    secret_code = parts[1].strip()

    if add_agent(agent_name, secret_code):
        await update.message.reply_text(f"✅ تم إضافة مجهز: {agent_name} بالرمز: {secret_code}")
    else:
        await update.message.reply_text("❌ فشل إضافة المجهز. قد يكون الرمز السري مستخدماً بالفعل.")

    # نعود إلى قائمة إدارة المجهزين
    return await manage_agents_menu(update, context)

# --- عرض واختيار مجهز ---

async def list_agents_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة المجهزين لغرض الاختيار."""
    query = update.callback_query
    await query.answer()
    
    agents = get_all_agents()
    keyboard = []
    
    if agents:
        for agent in agents:
            # زر اختيار المجهز
            keyboard.append([InlineKeyboardButton(agent['name'], callback_data=f"select_agent_{agent['id']}")])
        
        text = "إختر مجهزاً للقيام بعملية:"
    else:
        text = "لا يوجد مجهزون مُضافون حالياً."
        
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="manage_agents")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup)
    
    return MANAGE_AGENT # نبقى في MANAGE_AGENT لمعالجة الـ CallbackQuery التالي

async def select_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض خيارات (ربط/تعديل/حذف) للمجهز المحدد."""
    query = update.callback_query
    await query.answer()
    
    # استخلاص ID المجهز
    try:
        agent_id = int(query.data.split('_')[-1])
    except ValueError:
        return await manage_agents_menu(update, context)
        
    context.user_data['selected_agent_id'] = agent_id # تخزين ID المجهز

    agent_name = get_agent_name_by_id(agent_id)
    
    keyboard = [
        [InlineKeyboardButton("ربط/إلغاء ربط محلات 🔗", callback_data=f"assign_shops_{agent_id}")],
        [InlineKeyboardButton("تعديل تفاصيل المجهز ✏️", callback_data=f"edit_details_{agent_id}")],
        [InlineKeyboardButton("حذف المجهز 🗑️", callback_data=f"delete_agent_confirm_{agent_id}")],
        [InlineKeyboardButton("🔙 العودة لقائمة المجهزين", callback_data="list_agents")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"خيارات المجهز: **{agent_name}**",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return MANAGE_AGENT # نبقى في MANAGE_AGENT لمعالجة الخيارات

# --- تعديل تفاصيل المجهز (EDIT_AGENT_DETAILS State) ---

async def edit_agent_details_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب إدخال تفاصيل المجهز الجديدة."""
    query = update.callback_query
    await query.answer()
    
    # استخلاص ID المجهز
    try:
        agent_id = int(query.data.split('_')[-1])
    except ValueError:
        return await manage_agents_menu(update, context)

    context.user_data['selected_agent_id'] = agent_id # تخزين ID المجهز

    keyboard = [[InlineKeyboardButton("🔙 إلغاء والعودة", callback_data=f"select_agent_{agent_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📝 أرسل **الاسم الجديد** و **رمز الدخول السري الجديد** في سطرين منفصلين:\n"
        "الإسم الجديد\n"
        "رمز الدخول السري الجديد",
        reply_markup=reply_markup
    )
    return EDIT_AGENT_DETAILS

async def receive_new_agent_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل تفاصيل المجهز الجديدة ويحفظها، ويعيد الحالة إلى خيارات المجهز."""
    
    text = update.message.text.strip()
    parts = text.split('\n', 1) 
    agent_id = context.user_data.get('selected_agent_id')

    if not agent_id:
        await update.message.reply_text("❌ حدث خطأ، لم يتم تحديد المجهز المطلوب تعديله.")
        return await manage_agents_menu(update, context) 

    if len(parts) != 2:
        keyboard = [[InlineKeyboardButton("🔙 العودة لخيارات المجهز", callback_data=f"select_agent_{agent_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ صيغة الإدخال خطأ. لازم تكون:\n"
            "الإسم الجديد للمجهز\n"
            "رمز الدخول السري الجديد",
            reply_markup=reply_markup
        )
        return EDIT_AGENT_DETAILS # نبقى في نفس الحالة لنطلب الإعادة

    new_name = parts[0].strip()
    new_code = parts[1].strip()

    result = update_agent_details(agent_id, new_name, new_code)
    
    if result is True:
        await update.message.reply_text(
            f"✅ تم تحديث بيانات المجهز بنجاح!\n"
            f"الإسم الجديد: **{new_name}**\n"
            f"الرمز الجديد: **{new_code}**",
            parse_mode="Markdown"
        )
    elif result == "CODE_EXISTS":
        keyboard = [
            [InlineKeyboardButton("↩️ إعادة إدخال التفاصيل", callback_data=f"edit_details_{agent_id}")],
            [InlineKeyboardButton("🔙 العودة لخيارات المجهز", callback_data=f"select_agent_{agent_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ فشل التحديث: رمز الدخول السري **مستخدم بالفعل** من قبل مجهز آخر. الرجاء إدخال رمز آخر.",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return MANAGE_AGENT

    else:
        await update.message.reply_text(
            "❌ حدث خطأ غير متوقع أثناء تحديث بيانات المجهز."
        )

    await select_agent_menu(update, context)
    return MANAGE_AGENT 

# --- حذف المجهز (DELETE_AGENT_STATE) ---

async def list_agents_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة المجهزين لغرض الحذف."""
    query = update.callback_query
    await query.answer()
    
    agents = get_all_agents()
    keyboard = []
    
    if agents:
        for agent in agents:
            # زر تأكيد الحذف
            keyboard.append([InlineKeyboardButton(agent['name'], callback_data=f"delete_agent_confirm_{agent['id']}")])
        
        text = "إختر مجهزاً للحذف (تأكيد مباشر بعد النقر):"
    else:
        text = "لا يوجد مجهزون مُضافون حالياً للحذف."
        
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="manage_agents")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup)
    
    return DELETE_AGENT_STATE # نذهب إلى حالة الحذف

async def confirm_agent_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ينفذ حذف المجهز بعد تأكيد من القائمة."""
    query = update.callback_query
    await query.answer()
    
    # استخلاص ID المجهز من CallbackData (delete_agent_confirm_ID)
    try:
        agent_id = int(query.data.split('_')[-1])
    except ValueError:
        return await manage_agents_menu(update, context)

    # تنفيذ الحذف الفعلي
    if delete_agent(agent_id):
        await query.edit_message_text(
            f"✅ تم حذف المجهز بنجاح!", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة لقائمة الإدارة", callback_data="manage_agents")]])
        )
    else:
        await query.edit_message_text(
            "❌ حدث خطأ أثناء حذف المجهز.", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة لقائمة الإدارة", callback_data="manage_agents")]])
        )
        
    return MANAGE_AGENT # نعود إلى قائمة إدارة المجهزين


# ----------------------------------------------------------------------
# دوال ربط المحلات (Assignment)
# ----------------------------------------------------------------------

async def list_shops_to_assign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة المحلات لربطها/إلغاء ربطها بالمجهز المحدد."""
    query = update.callback_query
    await query.answer()
    
    # استخلاص ID المجهز
    try:
        agent_id = int(query.data.split('_')[-1])
    except ValueError:
        return await manage_agents_menu(update, context)

    context.user_data['selected_agent_id'] = agent_id # تخزين ID المجهز
    
    all_shops = get_all_shops()
    assigned_shop_ids = get_assigned_shop_ids(agent_id)
    agent_name = get_agent_name_by_id(agent_id)
    
    keyboard = []
    if all_shops:
        for shop in all_shops:
            is_assigned = shop['id'] in assigned_shop_ids
            emoji = "✅" if is_assigned else "❌"
            # القيمة تفرق بين اختيار المحل و تأكيد الحفظ
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {shop['name']}", 
                callback_data=f"toggle_shop_{shop['id']}"
            )])
            
        # زر تأكيد الحفظ والرجوع
        keyboard.append([InlineKeyboardButton("حفظ والعودة 💾", callback_data="confirm_shop_assignment")])
    
    keyboard.append([InlineKeyboardButton("🔙 العودة لخيارات المجهز", callback_data=f"select_agent_{agent_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"ربط/إلغاء ربط المحلات للمجهز: **{agent_name}**\n"
        "اضغط على اسم المحل لتبديل حالة التخصيص.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return SELECT_SHOPS

async def toggle_shop_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تبديل حالة الربط للمحل المحدد."""
    query = update.callback_query
    await query.answer()
    
    agent_id = context.user_data.get('selected_agent_id')
    
    # استخلاص ID المحل من CallbackData (toggle_shop_ID)
    try:
        shop_id = int(query.data.split('_')[-1])
    except ValueError:
        return SELECT_SHOPS

    # جلب حالة الربط الحالية
    assigned_shops = get_assigned_shop_ids(agent_id)
    is_assigned = shop_id in assigned_shops
    
    # تبديل حالة الربط في قاعدة البيانات
    toggle_agent_shop_assignment(agent_id, shop_id, not is_assigned)
    
    # إعادة عرض القائمة لتحديث الأزرار
    await list_shops_to_assign(update, context) 
    
    return SELECT_SHOPS

async def handle_shop_assignment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """التعامل مع زر تأكيد الحفظ والعودة بعد تغيير الربط."""
    query = update.callback_query
    await query.answer("تم حفظ التغييرات")

    agent_id = context.user_data.get('selected_agent_id')

    # عرض قائمة خيارات المجهز مرة أخرى
    await select_agent_menu(update, context) 
    return MANAGE_AGENT

# ----------------------------------------------------------------------
# دوال المجهز (Agent)
# ----------------------------------------------------------------------

async def agent_login_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب من المجهز إدخال الرمز السري."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📝 يرجى إدخال رمز الدخول السري الخاص بك:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="start")]])
    )
    return AGENT_LOGIN

async def agent_login_receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل رمز الدخول السري ويتحقق منه."""
    secret_code = update.message.text.strip()
    agent_data = check_agent_code(secret_code)
    
    if agent_data:
        # تسجيل دخول ناجح
        agent_id = agent_data['id']
        agent_name = agent_data['name']
        telegram_id = update.effective_user.id
        
        # تخزين بيانات المجهز في context
        context.user_data['agent_id'] = agent_id
        context.user_data['agent_name'] = agent_name
        
        # عرض قائمة المجهز
        return await show_agent_menu(update, context)
        
    else:
        await update.message.reply_text("❌ رمز الدخول غير صحيح. حاول مرة أخرى:")
        return AGENT_LOGIN

async def show_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة خيارات المجهز (بعد تسجيل الدخول)."""
    
    agent_name = context.user_data.get('agent_name', 'مجهز')
    
    keyboard = [
        [InlineKeyboardButton("عرض محلاتي 🔗", callback_data="show_agent_shops")],
        [InlineKeyboardButton("تسجيل خروج 🚪", callback_data="start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"👋🏼 أهلاً بك يا مجهز ({agent_name})!\n"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=reply_markup)
        
    return AGENT_MENU

async def show_agent_shops_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, search_term: str = None) -> int:
    """يعرض قائمة المحلات المخصصة للمجهز مع إمكانية البحث."""
    query = update.callback_query
    
    agent_id = context.user_data.get('agent_id')
    agent_name = context.user_data.get('agent_name', 'المجهز')
    
    if search_term:
        shops = get_agent_shops_by_search(agent_id, search_term)
    else:
        # جلب جميع المحلات المخصصة للمجهز
        assigned_shop_ids = get_assigned_shop_ids(agent_id)
        # بما أن get_all_shops ترجع كل المحلات، يجب تصفيتها
        all_shops = get_all_shops()
        shops = [shop for shop in all_shops if shop['id'] in assigned_shop_ids]

    keyboard = []
    
    if shops:
        if search_term:
            text = f"✅ **نتائج البحث عن '{search_term}'** للمجهز {agent_name}:"
        else:
            text = f"🔗 **محلات {agent_name} المخصصة:**\n يمكنك كتابة اسم المحل للبحث السريع."
            
        for shop in shops:
            shop_url = shop['url']
            if not shop_url.lower().startswith(('http://', 'https://')):
                 shop_url = "https://" + shop_url 
                 
            keyboard.append([InlineKeyboardButton(f"🔗 {shop['name']}", url=shop_url)])
            
    else:
        if search_term:
            text = f"❌ لا توجد محلات مطابقة لـ '{search_term}' مخصصة لك."
        else:
            text = f"❌ لم يتم تخصيص أي محلات لك يا {agent_name} بعد."

    keyboard.append([InlineKeyboardButton("🔙 العودة لقائمة المجهز", callback_data="agent_menu_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.answer()
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
        
    return AGENT_MENU

async def agent_shop_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل نص البحث من المجهز (في حالة AGENT_MENU) ويعرض النتائج."""
    search_term = update.message.text.strip()
    
    # نستخدم الدالة الأساسية لتنفيذ البحث وعرض النتائج
    return await show_agent_shops_handler(update, context, search_term)


# ----------------------------------------------------------------------
# دالة main وتشغيل البوت
# ----------------------------------------------------------------------

def main() -> None:
    """بدء تشغيل البوت."""
    
    # 🚨 هذه الدالة تبدأ اتصال قاعدة البيانات وتنشئ الجداول.
    setup_db() 
    
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("🚫 التوكن مال البوت (BOT_TOKEN) ما متوفر بمتغيرات البيئة.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # -------------------------------------------------------------------
    # إعداد ConversationHandler
    # -------------------------------------------------------------------

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        
        states={
            MAIN_MENU: [
                 CallbackQueryHandler(admin_login, pattern="^admin_login$"),
                 CallbackQueryHandler(agent_login_prompt, pattern="^agent_login_prompt$"),
            ],
            
            ADMIN_MENU: [
                # عرض المحلات/البحث
                CallbackQueryHandler(show_and_search_shops, pattern="^show_shops_list$"), 
                # إضافة محل وإدارة المجهزين
                CallbackQueryHandler(admin_menu_handler, pattern="^(add_shop|manage_agents|admin_menu)$"),
            ],
            
            SHOW_SHOPS_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_shop_search_handler),
                
                # أزرار الإدارة التي تظهر في نتائج البحث
                CallbackQueryHandler(prompt_edit_shop_details, pattern="^edit_shop_select_\d+$"),
                CallbackQueryHandler(confirm_shop_deletion, pattern="^delete_shop_confirm_\d+$"),
                
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"), 
            ],
            
            ADD_SHOP_STATE: [
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_shop_data),
            ],
            
            MANAGE_AGENT: [
                # القائمة الرئيسية لإدارة المجهزين
                CallbackQueryHandler(manage_agents_menu, pattern="^manage_agents$"), 
                # إضافة مجهز جديد
                CallbackQueryHandler(add_new_agent_menu, pattern="^add_new_agent$"), 
                # عرض المجهزين للاختيار
                CallbackQueryHandler(list_agents_menu, pattern="^list_agents$"), 
                # قائمة المجهزين للحذف (تذهب إلى DELETE_AGENT_STATE)
                CallbackQueryHandler(list_agents_to_delete, pattern="^delete_agent$"),
                # تعديل تفاصيل المجهز
                CallbackQueryHandler(edit_agent_details_menu, pattern="^edit_details_\d+$"),
                # خيارات المجهز (ربط/تعديل/حذف)
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"),
                # قائمة المحلات لربطها
                CallbackQueryHandler(list_shops_to_assign, pattern="^assign_shops_\d+$"),
            ],
            
            ADD_AGENT_STATE: [
                CallbackQueryHandler(manage_agents_menu, pattern="^manage_agents$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_agent_data)
            ],

            SELECT_SHOPS: [
                CallbackQueryHandler(handle_shop_assignment, pattern="^confirm_shop_assignment$"),
                CallbackQueryHandler(toggle_shop_selection, pattern="^toggle_shop_\d+$"), 
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"),
            ],

            EDIT_AGENT_DETAILS: [
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"), 
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_agent_details), 
            ],
            
            DELETE_SHOP_STATE: [
                # تنفيذ الحذف يتم من داخل SHOW_SHOPS_ADMIN 
                CallbackQueryHandler(show_and_search_shops, pattern="^show_shops_list$"), 
            ],
            
            DELETE_AGENT_STATE: [
                CallbackQueryHandler(manage_agents_menu, pattern="^manage_agents$"), 
                CallbackQueryHandler(confirm_agent_deletion, pattern="^delete_agent_confirm_\d+$"),
            ],

            EDIT_SHOP_STATE: [
                CallbackQueryHandler(show_and_search_shops, pattern="^show_shops_list$"), 
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"), 
                CallbackQueryHandler(prompt_edit_shop_details, pattern="^edit_shop_select_\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_updated_shop_data),
            ],
            
            AGENT_LOGIN: [
                CallbackQueryHandler(agent_login_prompt, pattern="^agent_login_prompt$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_login_receive_code),
                CallbackQueryHandler(start_command, pattern="^start$"),
                CommandHandler("start", start_command), 
            ],

            AGENT_MENU: [
                 CallbackQueryHandler(show_agent_shops_handler, pattern="^show_agent_shops$"),
                 MessageHandler(filters.TEXT & ~filters.COMMAND, agent_shop_search_handler),
                 CallbackQueryHandler(show_agent_menu, pattern="^agent_menu_back$"), 
                 CallbackQueryHandler(start_command, pattern="^start$"), 
                 CommandHandler("start", start_command), 
            ]
        },
        
        fallbacks=[CommandHandler("start", start_command)],
    )

    application.add_handler(conv_handler)
    
    # -------------------------------------------------------------------
    # 🚀 الكود المصحح لتشغيل Webhook (باستخدام APP_PUBLIC_URL الذي تم إضافته)
    # -------------------------------------------------------------------
    
    PORT = int(os.environ.get('PORT', '8080')) 
    
    # نعتمد على المتغير الذي قمت بتعريفه يدوياً
    RAILWAY_URL = os.getenv('APP_PUBLIC_URL') 
    
    if RAILWAY_URL:
        # تشغيل الـ Webhook
        url_path = BOT_TOKEN
        webhook_url = f"https://{RAILWAY_URL}/{url_path}"
        
        application.run_webhook(
            listen="0.0.0.0", 
            port=PORT,
            url_path=url_path,
            webhook_url=webhook_url
        )
        logger.info(f"🤖 تم تشغيل البوت بوضعية Webhook قسرية على العنوان: {RAILWAY_URL}")
        
    else:
        logger.error("🚫 فشل العثور على APP_PUBLIC_URL. Webhook لم يضبط.")
        
    # -------------------------------------------------------------------

if __name__ == "__main__":
    main()

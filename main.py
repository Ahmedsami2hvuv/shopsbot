# main.py
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    """يعرض قائمة البداية للمستخدم ويتعرف على المدير."""
    
    # 1. تحديد المصدر والرسالة
    if update.callback_query:
        # 🚨 التعديل هنا: عند الرجوع بالـ callback، لا نستخدم update.callback_query.message
        # لتجنب خطأ تعديل رسالة محذوفة أو قديمة، بل نستخدم effective_message
        message = update.callback_query.message
    elif update.message:
        message = update.message
    else:
        # إذا لم يكن هناك رسالة أو استدعاء، نرجع للقائمة الرئيسية
        return MAIN_MENU 
        
    user_id = update.effective_user.id
        
    # إزالة البيانات المخزنة من المحادثة السابقة
    context.user_data.clear()
        
    # 2. التحقق من هوية المدير
    if is_admin(user_id):
        # ✅ الحل: إذا كان المدير، يتم نقله مباشرة إلى قائمة الإدارة
        # نستخدم is_command=True لضمان إرسال رسالة جديدة بدلاً من تعديلها
        return await show_admin_menu(update, context, is_command=True) 
    
    # 3. إذا لم يكن المدير، يتم عرض قائمة الدخول العادية
    keyboard = [
        [InlineKeyboardButton("إدخال رقمك السري 🔑", callback_data="agent_login_prompt")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        "👋🏼 أهلاً بك! إختار:",
        reply_markup=reply_markup
    )
    return MAIN_MENU

async def admin_login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يتحقق من هوية المدير ويعرض القائمة الرئيسية للإدارة عند استخدام الأمر /admin."""
    user_id = update.effective_user.id
    if is_admin(user_id):
        # نستخدم update.message لأن الأمر جاء من رسالة
        return await show_admin_menu(update, context, is_command=True)
    else:
        if update.message:
            await update.message.reply_text("❌ آسف، لا تملك صلاحية المدير.")
        return MAIN_MENU

# ----------------------------------------------------------------------
# دوال إدارة المدير (ADMIN)
# ----------------------------------------------------------------------

async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يتحقق من هوية المدير ويعرض القائمة الرئيسية للإدارة (في حال تم استدعاؤه بـ callback)."""
    user_id = update.effective_user.id
    await update.callback_query.answer()
    
    if is_admin(user_id):
        return await show_admin_menu(update, context)
    else:
        await update.callback_query.edit_message_text("❌ آسف، لا تملك صلاحية المدير.")
        return MAIN_MENU

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_command: bool = False) -> int:
    """تظهر قائمة خيارات المدير، وتُستخدم للرجوع من أي قائمة فرعية."""
    
    keyboard = [
        [InlineKeyboardButton("عرض المحلات 📊", callback_data="show_shops_list"), 
         InlineKeyboardButton("إضافة محل 🏬", callback_data="add_shop")], 
        [InlineKeyboardButton("تعديل محل ✏️", callback_data="edit_shops"), 
         InlineKeyboardButton("حذف محل 🗑️", callback_data="delete_shop")], # تم إبقاء الزر ليدخل على قائمة العرض
        [InlineKeyboardButton("إدارة المجهزين 🧑‍💻", callback_data="manage_agents")],
        [InlineKeyboardButton("تسجيل الخروج 🚪", callback_data="start")] # لإرجاع المستخدم للقائمة الرئيسية
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "👋🏼 أهلاً بك يا مدير! إختار شنو تريد تسوي:"
    
    if update.callback_query:
        await update.callback_query.answer()
        try:
             await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
        except Exception:
             await update.callback_query.message.reply_text(text=text, reply_markup=reply_markup)
             
    elif update.message or is_command:
        # يستخدم عند استدعاء الدالة من الأمر /admin
        await update.effective_message.reply_text(text=text, reply_markup=reply_markup)
        
    return ADMIN_MENU

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج عام لأزرار قائمة المدير الرئيسية، ويُستخدم أيضاً كمعالج لـ 'admin_menu' للرجوع."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # FIX: حل مشكلة الرجوع من القوائم الفرعية
    if data == "admin_menu":
        return await show_admin_menu(update, context)
        
    elif data == "add_shop":
        await query.edit_message_text(
            "📝 أرسل اسم المحل ورابطه في سطرين منفصلين:\n"
            "الاسم\n"
            "الرابط (URL)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="admin_menu")]])
        )
        return ADD_SHOP_STATE
    
    elif data == "manage_agents":
        return await manage_agents_menu(update, context)

    # FIX: عرض المحلات، حذف محل، وتعديل محل كلها تذهب إلى قائمة عرض المحلات
    elif data in ["show_shops_list", "delete_shop", "edit_shops"]:
        return await show_and_search_shops(update, context)
        
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
    return await show_admin_menu(update, context, is_command=True) # is_command=True لتجنب خطأ الـ callback

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

    # FIX: زر العودة من قائمة عرض المحلات
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
    """ينفذ حذف المحل فعلياً (بدون خطوة تأكيد ثانية)."""
    query = update.callback_query
    await query.answer()
    
    # استخلاص ID المحل من CallbackData (delete_shop_confirm_ID)
    try:
        shop_id = int(query.data.split('_')[-1])
    except ValueError:
        return await show_admin_menu(update, context)

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
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("إضافة مجهز ➕", callback_data="add_new_agent")],
        [InlineKeyboardButton("عرض المجهزين 📄", callback_data="list_agents")],
        [InlineKeyboardButton("حذف مجهز 🗑️", callback_data="delete_agent_prompt")],
        [InlineKeyboardButton("تعديل مجهز ✏️", callback_data="edit_agent_prompt")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")] # FIX: زر العودة
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🧑‍💻 قائمة إدارة المجهزين. إختار الإجراء:"
    
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return MANAGE_AGENT

async def manage_agents_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج عام لأزرار قائمة إدارة المجهزين."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "add_new_agent":
        await query.edit_message_text(
            "📝 أرسل اسم المجهز والرمز السري في سطرين منفصلين:\n"
            "الاسم\n"
            "الرمز السري (Code)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="manage_agents")]])
        )
        return ADD_AGENT_STATE
        
    elif data == "list_agents":
        return await list_all_agents(update, context)
        
    elif data == "delete_agent_prompt" or data == "edit_agent_prompt":
        # عرض قائمة المجهزين لاختيار من سيتم حذفه أو تعديله
        context.user_data['action_type'] = data.split('_')[0] # 'delete' or 'edit'
        return await list_agents_for_selection(update, context)
        
    # FIX: حل مشكلة الرجوع
    elif data == "manage_agents":
        return await manage_agents_menu(update, context)
        
    return MANAGE_AGENT

async def receive_agent_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المجهز الجديد ويحفظها."""
    text = update.message.text.strip()
    parts = text.split('\n', 1) 
    
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ صيغة الإدخال خطأ. لازم تكون:\n"
            "الاسم\n"
            "الرمز السري (Code)"
        )
        return ADD_AGENT_STATE

    agent_name = parts[0].strip()
    secret_code = parts[1].strip()

    if add_agent(agent_name, secret_code):
        await update.message.reply_text(f"✅ تم إضافة مجهز: {agent_name}")
    else:
        await update.message.reply_text("❌ فشل إضافة المجهز. الرمز السري قد يكون مستخدماً أو حدث خطأ في قاعدة البيانات.")

    # نعود إلى قائمة إدارة المجهزين
    return await manage_agents_menu(update, context)


# ----------------------------------------------------------------------
# دوال عرض واختيار المجهزين (Used for List, Edit, Delete, Assign)
# ----------------------------------------------------------------------

async def list_all_agents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة بجميع المجهزين."""
    query = update.callback_query
    await query.answer()
    
    agents = get_all_agents()
    
    if agents:
        text = "📄 **قائمة المجهزين:**"
        keyboard = [
            [InlineKeyboardButton(f"👤 {agent['name']}", callback_data=f"select_agent_{agent['id']}")]
            for agent in agents
        ]
    else:
        text = "❌ لا يوجد مجهزون مُضافون حالياً."
        keyboard = [[InlineKeyboardButton("➕ إضافة مجهز جديد", callback_data="add_new_agent")]]

    keyboard.append([InlineKeyboardButton("🔙 العودة لقائمة الإدارة", callback_data="manage_agents")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    return MANAGE_AGENT

async def list_agents_for_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة المجهزين لاختيار مجهز معين (للتعديل، الحذف، أو الربط)."""
    query = update.callback_query
    await query.answer()
    
    agents = get_all_agents()
    action_type = context.user_data.get('action_type', 'select')
    
    if agents:
        text = "إختار المجهز الذي تريد "
        if action_type == 'delete':
             text += "**حذفه**:"
        elif action_type == 'edit':
             text += "**تعديل تفاصيله**:"
        elif action_type == 'assign':
             text += "**تخصيص المحلات له**:"
        else:
             text += "**اختياره**:"

        keyboard = [
            [InlineKeyboardButton(f"👤 {agent['name']}", callback_data=f"select_agent_{agent['id']}")]
            for agent in agents
        ]
    else:
        text = "❌ لا يوجد مجهزون مُضافون حالياً."
        keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="manage_agents")]]

    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="manage_agents")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    return MANAGE_AGENT

async def select_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة الإجراءات لمجهز محدد (للتعديل أو الربط أو الحذف)."""
    query = update.callback_query
    await query.answer()
    
    # استخلاص ID المجهز
    try:
        agent_id = int(query.data.split('_')[-1])
        context.user_data['selected_agent_id'] = agent_id
    except ValueError:
        return await manage_agents_menu(update, context)

    agent_name = get_agent_name_by_id(agent_id)
    action_type = context.user_data.get('action_type', 'select')
    
    if action_type == 'delete':
        text = f"هل أنت متأكد من حذف المجهز **{agent_name}**؟"
        keyboard = [
            [InlineKeyboardButton("✅ تأكيد الحذف", callback_data=f"delete_agent_confirm_{agent_id}")],
            [InlineKeyboardButton("❌ إلغاء والعودة", callback_data="delete_agent_prompt")] # العودة لقائمة الاختيار
        ]
        
    elif action_type == 'edit':
        text = f"إختار الإجراء المطلوب للمجهز **{agent_name}**:"
        keyboard = [
            [InlineKeyboardButton("✏️ تعديل تفاصيل الدخول", callback_data=f"edit_details_{agent_id}")],
            [InlineKeyboardButton("🔗 تخصيص المحلات", callback_data=f"assign_shops_{agent_id}")],
            [InlineKeyboardButton("🔙 العودة", callback_data="edit_agent_prompt")]
        ]
        
    else: # Default (Assign only)
        text = f"إختار الإجراء المطلوب للمجهز **{agent_name}**:"
        keyboard = [
            [InlineKeyboardButton("🔗 تخصيص المحلات", callback_data=f"assign_shops_{agent_id}")],
            [InlineKeyboardButton("🔙 العودة", callback_data="manage_agents")]
        ]
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    return MANAGE_AGENT

# --- حذف مجهز (DELETE_AGENT_STATE) ---

async def confirm_agent_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ينفذ حذف المجهز فعلياً."""
    query = update.callback_query
    await query.answer()
    
    try:
        agent_id = int(query.data.split('_')[-1])
    except ValueError:
        return await manage_agents_menu(update, context)

    agent_name = get_agent_name_by_id(agent_id)
    
    if delete_agent(agent_id):
        await query.edit_message_text(f"✅ تم حذف المجهز **{agent_name}** بنجاح!")
    else:
        await query.edit_message_text("❌ حدث خطأ أثناء حذف المجهز.")

    # نعود لقائمة اختيار المجهزين للحذف
    context.user_data['action_type'] = 'delete'
    return await list_agents_for_selection(update, context)


# --- تعديل تفاصيل المجهز (EDIT_AGENT_DETAILS) ---

async def edit_agent_details_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب من المدير إدخال تفاصيل التعديل للمجهز المحدد."""
    query = update.callback_query
    await query.answer()
    
    try:
        agent_id = int(query.data.split('_')[-1])
        context.user_data['selected_agent_id'] = agent_id
    except ValueError:
        return await manage_agents_menu(update, context)

    keyboard = [[InlineKeyboardButton("🔙 إلغاء والعودة", callback_data=f"select_agent_{agent_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📝 لإجراء التعديل على المجهز رقم {agent_id}:\n"
        "أرسل **الاسم الجديد** و **الرمز السري الجديد** في سطرين منفصلين:\n"
        "الاسم الجديد\n"
        "الرمز السري الجديد (Code)",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return EDIT_AGENT_DETAILS

async def receive_updated_agent_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المجهز المحدثة ويحفظها."""
    text = update.message.text.strip()
    parts = text.split('\n', 1) 
    agent_id = context.user_data.get('selected_agent_id')
    
    if not agent_id:
        await update.message.reply_text("❌ حدث خطأ، لم يتم تحديد المجهز المطلوب تعديله.")
        return await manage_agents_menu(update, context)

    if len(parts) != 2:
        await update.message.reply_text(
            "❌ صيغة الإدخال خطأ. الرجاء إرسال الاسم الجديد والرمز الجديد في سطرين منفصلين."
        )
        return EDIT_AGENT_DETAILS
        
    new_name = parts[0].strip()
    new_code = parts[1].strip()

    result = update_agent_details(agent_id, new_name, new_code)
    
    if result is True:
        await update.message.reply_text(f"✅ تم تحديث تفاصيل المجهز رقم {agent_id} بنجاح!")
    elif result == "CODE_EXISTS":
        await update.message.reply_text("❌ فشل التحديث. الرمز السري الجديد مستخدم بالفعل لمجهز آخر.")
        return EDIT_AGENT_DETAILS
    else:
        await update.message.reply_text("❌ فشل تحديث التفاصيل. حدث خطأ في قاعدة البيانات.")

    # نعود لقائمة اختيار المجهز
    context.user_data['action_type'] = 'edit'
    return await list_agents_for_selection(update, context)

# ----------------------------------------------------------------------
# دوال تخصيص المحلات للمجهزين (Assignment)
# ----------------------------------------------------------------------

async def list_shops_to_assign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة المحلات لإضافة أو إزالة الربط من مجهز محدد."""
    query = update.callback_query
    await query.answer()
    
    # يتم استخلاص ID المجهز إما من query.data أو من context.user_data
    if query.data.startswith('assign_shops_'):
        try:
            agent_id = int(query.data.split('_')[-1])
            context.user_data['selected_agent_id'] = agent_id
        except ValueError:
            return await manage_agents_menu(update, context)
    else:
        agent_id = context.user_data.get('selected_agent_id')
        if not agent_id:
            return await manage_agents_menu(update, context)
            
    agent_name = get_agent_name_by_id(agent_id)
    all_shops = get_all_shops()
    assigned_shops = get_assigned_shop_ids(agent_id)
    
    text = f"🔗 **تخصيص المحلات للمجهز {agent_name}:**\n"
    text += "إضغط على المحل للربط (✅) أو إلغاء الربط (❌)."
    
    keyboard = []
    if all_shops:
        for shop in all_shops:
            is_assigned = shop['id'] in assigned_shops
            status = "✅" if is_assigned else "❌"
            
            # زر الربط/إلغاء الربط
            button = InlineKeyboardButton(
                text=f"{status} {shop['name']}", 
                callback_data=f"toggle_shop_{shop['id']}" # نستخدم ID المحل فقط
            )
            keyboard.append([button])
    else:
        text = "❌ لا توجد محلات مُضافة لتخصيصها."

    # زر العودة يعود إلى قائمة الإجراءات للمجهز المحدد
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data=f"select_agent_{agent_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    return SELECT_SHOPS

# FIX: تم تصحيح هذه الدالة لحل مشكلة أزرار الصح والخطأ
async def toggle_shop_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ربط أو إلغاء ربط محل بمجهز عند النقر على علامة صح/خطأ."""
    query = update.callback_query
    await query.answer()
    
    # 1. استخلاص ID المحل والمجهز
    try:
        # CallbackData: 'toggle_shop_SHOPID'
        shop_id = int(query.data.split('_')[-1])
        agent_id = context.user_data.get('selected_agent_id')
        
        if not agent_id:
             await query.edit_message_text("❌ حدث خطأ: لم يتم تحديد المجهز المطلوب.")
             return await manage_agents_menu(update, context)
             
    except Exception as e:
        logger.error(f"Error extracting IDs in toggle_shop_selection: {e}")
        return await manage_agents_menu(update, context)

    # 2. تحديد حالة الربط الحالية
    assigned_shops = get_assigned_shop_ids(agent_id)
    is_assigned = shop_id in assigned_shops
    
    # 3. تبديل حالة الربط (Toggle)
    # نستخدم `not is_assigned` لقلب الحالة (إذا كان مربوطاً، ألغي الربط، وإذا لم يكن، اربط)
    if toggle_agent_shop_assignment(agent_id, shop_id, not is_assigned):
        # 4. إعادة عرض القائمة لتحديث الأزرار
        # يجب استدعاء list_shops_to_assign الذي يعيد عرض القائمة
        return await list_shops_to_assign(update, context)
    else:
        await query.answer("❌ فشل تحديث الربط في قاعدة البيانات.")
        return SELECT_SHOPS # البقاء في نفس الحالة


# ----------------------------------------------------------------------
# دوال المجهز (Agent)
# ----------------------------------------------------------------------

async def agent_login_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب من المجهز إدخال الرمز السري."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔑 **أدخل رقمك السري الآن**:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="start")]])
    )
    return AGENT_LOGIN

async def agent_login_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل الرمز السري ويتحقق منه."""
    secret_code = update.message.text.strip()
    agent = check_agent_code(secret_code)
    
    if agent:
        # تسجيل الدخول الناجح
        context.user_data['is_agent'] = True
        context.user_data['agent_id'] = agent['id']
        context.user_data['agent_name'] = agent['name']
        
        # ربط الـ Telegram ID بآيدي المجهز في قاعدة البيانات
        # (يجب إضافة دالة في database.py لتحديث telegram_id) - نفترض أن هذه خطوة لاحقة
        
        await update.message.reply_text(f"👋🏼 أهلاً بك يا مجهز {agent['name']}!")
        return await show_agent_menu(update, context, is_login=True)
    else:
        await update.message.reply_text("❌ رمز سري خاطئ. حاول مرة أخرى.")
        return AGENT_LOGIN

async def show_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_login: bool = False) -> int:
    """يعرض قائمة المجهز."""
    
    agent_name = context.user_data.get('agent_name', 'مجهز')
    
    keyboard = [
        [InlineKeyboardButton("عرض المحلات المخصصة 📊", callback_data="show_agent_shops")],
        [InlineKeyboardButton("تسجيل الخروج 🚪", callback_data="start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"👋🏼 أهلاً بك يا {agent_name}!"
    
    if update.callback_query and not is_login:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    elif update.message or is_login:
        await update.effective_message.reply_text(text=text, reply_markup=reply_markup)
        
    return AGENT_MENU

async def agent_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج عام لأزرار قائمة المجهز."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "show_agent_shops":
        return await show_agent_shops(update, context)
        
    return AGENT_MENU

async def show_agent_shops(update: Update, context: ContextTypes.DEFAULT_TYPE, search_term: str = None) -> int:
    """تعرض المحلات المخصصة للمجهز وتسمح بالبحث."""
    
    agent_id = context.user_data.get('agent_id')
    
    if search_term:
        shops = get_agent_shops_by_search(agent_id, search_term)
    else:
        shops = get_agent_shops_by_search(agent_id, "") # جلب الكل
    
    keyboard = []
    
    if shops:
        if search_term:
            text = f"✅ **نتائج البحث عن '{search_term}'**:"
        else:
            text = "📊 **محلاتك المخصصة:**\n يمكنك كتابة اسم المحل للبحث السريع."
            
        for shop in shops:
            shop_url = shop['url']
            if not shop_url.lower().startswith(('http://', 'https://')):
                 shop_url = "https://" + shop_url 
            
            # زر رابط المحل
            url_button = InlineKeyboardButton(text=f"🔗 {shop['name']}", url=shop_url)
            keyboard.append([url_button])
            keyboard.append([InlineKeyboardButton("---", callback_data="ignore")]) # فاصل
    
    else:
        if search_term:
            text = f"❌ لا توجد محلات مطابقة لـ '{search_term}'."
        else:
            text = "❌ لم يتم تخصيص أي محلات لك حالياً."

    # زر العودة للقائمة
    keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="agent_menu_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

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
    
    return AGENT_MENU

async def agent_shop_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل نص البحث من المجهز ويعرض النتائج."""
    search_term = update.message.text.strip()
    return await show_agent_shops(update, context, search_term)


# ----------------------------------------------------------------------
# الدوال الرئيسية (Main)
# ----------------------------------------------------------------------

def main() -> None:
    """الدالة الرئيسية لتشغيل البوت."""
    
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("🚫 BOT_TOKEN غير معرّف. لا يمكن تشغيل البوت.")
        return

    # إنشاء الجداول عند التشغيل
    setup_db()

    application = Application.builder().token(BOT_TOKEN).build()
    
    # 🚨 FIX: إضافة معالج للأمر /admin 
    application.add_handler(CommandHandler("admin", admin_login_command))
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        
        states={
            MAIN_MENU: [
                # FIX: تم حذف admin_login، وتم استبدال agent_login_prompt
                CallbackQueryHandler(agent_login_prompt, pattern=r"^agent_login_prompt$"),
                CommandHandler("start", start_command),
            ],
            
            AGENT_LOGIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_login_handler),
                CallbackQueryHandler(start_command, pattern=r"^start$"),
                CommandHandler("start", start_command),
            ],

            ADMIN_MENU: [
                # FIX: admin_menu_handler الآن يعالج كل أزرار القائمة والرجوع
                CallbackQueryHandler(admin_menu_handler, pattern=r"^(add_shop|manage_agents|show_shops_list|delete_shop|edit_shops|admin_menu)$"),
                CommandHandler("start", start_command),
            ],
            
            ADD_SHOP_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_shop_data),
                CallbackQueryHandler(admin_menu_handler, pattern=r"^admin_menu$"),
                CommandHandler("start", start_command),
            ],
            
            SHOW_SHOPS_ADMIN: [
                CallbackQueryHandler(confirm_shop_deletion, pattern=r"^delete_shop_confirm_\d+$"),
                CallbackQueryHandler(prompt_edit_shop_details, pattern=r"^edit_shop_select_\d+$"),
                CallbackQueryHandler(admin_menu_handler, pattern=r"^(show_shops_list|admin_menu)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_shop_search_handler),
                CommandHandler("start", start_command),
            ],
            
            EDIT_SHOP_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_updated_shop_data),
                CallbackQueryHandler(admin_menu_handler, pattern=r"^show_shops_list$"),
                CommandHandler("start", start_command),
            ],
            
            MANAGE_AGENT: [
                CallbackQueryHandler(manage_agents_handler, pattern=r"^(add_new_agent|list_agents|delete_agent_prompt|edit_agent_prompt|manage_agents)$"),
                CallbackQueryHandler(list_agents_for_selection, pattern=r"^(list_agents|delete_agent_prompt|edit_agent_prompt)$"),
                CallbackQueryHandler(select_agent_menu, pattern=r"^select_agent_\d+$"),
                CallbackQueryHandler(edit_agent_details_menu, pattern=r"^edit_details_\d+$"),
                CallbackQueryHandler(list_shops_to_assign, pattern=r"^assign_shops_\d+$"),
                CallbackQueryHandler(confirm_agent_deletion, pattern=r"^delete_agent_confirm_\d+$"),
                CallbackQueryHandler(admin_menu_handler, pattern=r"^admin_menu$"),
                CommandHandler("start", start_command),
            ],
            
            ADD_AGENT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_agent_data),
                CallbackQueryHandler(manage_agents_handler, pattern=r"^manage_agents$"),
                CommandHandler("start", start_command),
            ],
            
            EDIT_AGENT_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_updated_agent_data),
                CallbackQueryHandler(select_agent_menu, pattern=r"^select_agent_\d+$"),
                CommandHandler("start", start_command),
            ],
            
            SELECT_SHOPS: [
                # FIX: معالج تبديل حالة الربط
                CallbackQueryHandler(toggle_shop_selection, pattern=r"^toggle_shop_\d+$"), 
                CallbackQueryHandler(list_shops_to_assign, pattern=r"^assign_shops_\d+$"),
                CallbackQueryHandler(select_agent_menu, pattern=r"^select_agent_\d+$"),
                CommandHandler("start", start_command),
            ],
            
            AGENT_MENU: [
                CallbackQueryHandler(agent_menu_handler, pattern=r"^show_agent_shops$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_shop_search_handler),
                CallbackQueryHandler(show_agent_menu, pattern=r"^agent_menu_back$"), 
                CallbackQueryHandler(start_command, pattern=r"^start$"), 
                CommandHandler("start", start_command), 
            ]
        },
        
        fallbacks=[CommandHandler("start", start_command)],
    )

    application.add_handler(conv_handler)
    
    # -------------------------------------------------------------------
    # 🚀 الكود المصحح لتشغيل Webhook (باستخدام APP_PUBLIC_URL)
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
        logger.error("🚫 فشل العثور على APP_PUBLIC_URL. الرجاء التحقق من متغيرات البيئة.")
        
if __name__ == "__main__":
    main()

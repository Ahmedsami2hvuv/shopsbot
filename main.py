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
        message = update.callback_query.message
    elif update.message:
        message = update.message
    else:
        return MAIN_MENU
        
    user_id = update.effective_user.id
        
    # إزالة البيانات المخزنة من المحادثة السابقة
    context.user_data.clear()
        
    # 2. التحقق من هوية المدير
    if is_admin(user_id):
        # ✅ المدير يدخل مباشرة إلى قائمة الإدارة
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
        return await show_admin_menu(update, context, is_command=True)
    else:
        if update.message:
            await update.message.reply_text("❌ آسف، لا تملك صلاحية المدير.")
        return MAIN_MENU

# ----------------------------------------------------------------------
# دوال إدارة المدير (ADMIN)
# ----------------------------------------------------------------------

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_command: bool = False) -> int:
    """تظهر قائمة خيارات المدير، وتُستخدم للرجوع من أي قائمة فرعية."""
    
    # 🚨 تم تبسيط الأزرار
    keyboard = [
        [InlineKeyboardButton("عرض المحلات (تعديل/حذف) 📊", callback_data="show_shops_list"), 
         InlineKeyboardButton("إضافة محل 🏬", callback_data="add_shop")], 
        [InlineKeyboardButton("إدارة المجهزين 🧑‍💻", callback_data="manage_agents")], 
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "👋🏼 أهلاً بك يا مدير! إختار شنو تريد تسوي:"
    
    if update.callback_query and not is_command:
        await update.callback_query.answer()
        try:
             await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
        except Exception:
             await update.callback_query.message.reply_text(text=text, reply_markup=reply_markup)
             
    elif update.message or is_command:
        await update.effective_message.reply_text(text=text, reply_markup=reply_markup)
        
    return ADMIN_MENU

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج عام لأزرار قائمة المدير الرئيسية، ويُستخدم أيضاً كمعالج لـ 'admin_menu' للرجوع."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # الرجوع للقائمة الرئيسية للمدير (يستخدمه زر "إنهاء والعودة")
    if data == "admin_menu":
        return await show_admin_menu(update, context)
        
    elif data == "add_shop":
        # بدء عملية إضافة محل
        await query.edit_message_text(
            "📝 أرسل اسم المحل ورابطه في سطرين منفصلين:\n"
            "الاسم\n"
            "الرابط (URL)",
            # ✅ زر "إنهاء والعودة" الجديد
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ إنهاء والعودة", callback_data="admin_menu")]])
        )
        return ADD_SHOP_STATE
    
    elif data == "manage_agents":
        # التوجه مباشرة إلى قائمة عرض/إدارة المجهزين المبسّطة
        return await show_and_manage_agents(update, context)

    # عرض المحلات
    elif data == "show_shops_list":
        return await show_and_search_shops(update, context)
        
    return ADMIN_MENU


# ----------------------------------------------------------------------
# دوال إدارة المحلات (Shops Management)
# ----------------------------------------------------------------------

async def receive_shop_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المحل الجديد ويحفظها، ويبقى في نفس الحالة لإضافة المزيد."""
    text = update.message.text.strip()
    parts = text.split('\n', 1) 
    
    # 🚨 زر العودة لإنهاء عملية الإضافة المتعددة
    keyboard = [[InlineKeyboardButton("✅ إنهاء والعودة", callback_data="admin_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ صيغة الإدخال خطأ. لازم تكون:\n"
            "الاسم\n"
            "الرابط (URL)",
            reply_markup=reply_markup
        )
        return ADD_SHOP_STATE

    shop_name = parts[0].strip()
    shop_url = parts[1].strip()

    if add_shop(shop_name, shop_url):
        # 💡 يبقى في نفس الحالة
        await update.message.reply_text(
            f"✅ تم إضافة محل: **{shop_name}** بنجاح.\n"
            "أرسل المحل التالي (الاسم والرابط في سطرين)، أو إضغط إنهاء:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ فشل إضافة المحل. قد يكون الاسم مستخدماً بالفعل أو حدث خطأ في قاعدة البيانات.",
            reply_markup=reply_markup
        )

    # البقاء في نفس الحالة (ADD_SHOP_STATE) لإضافة محل جديد
    return ADD_SHOP_STATE

async def show_and_search_shops(update: Update, context: ContextTypes.DEFAULT_TYPE, search_term: str = None) -> int:
    """تعرض قائمة المحلات وتسمح بالبحث، مع أزرار الإدارة (تعديل وحذف)."""
    
    if search_term:
        shops = get_shops_by_search(search_term) 
    else:
        shops = get_all_shops()
    
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
            
            url_button = InlineKeyboardButton(text=f" {shop['name']}", url=shop_url)
            edit_button = InlineKeyboardButton("✏️", callback_data=f"edit_shop_select_{shop['id']}")
            delete_button = InlineKeyboardButton("🗑️", callback_data=f"delete_shop_confirm_{shop['id']}")
            
            keyboard.append([url_button])
            keyboard.append([edit_button, delete_button]) 
            keyboard.append([InlineKeyboardButton("------", callback_data="ignore")])
    
    else:
        if search_term:
            text = f"❌ لا توجد محلات مطابقة لـ '{search_term}'."
        else:
            text = "❌ لا توجد محلات مُضافة حالياً."
            keyboard.append([InlineKeyboardButton("🏬 إضافة محل جديد", callback_data="add_shop")])

    keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text=text, 
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except:
             await update.callback_query.message.reply_text(
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
    
    return SHOW_SHOPS_ADMIN

async def admin_shop_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل نص البحث من المدير (في حالة SHOW_SHOPS_ADMIN) ويعرض النتائج."""
    search_term = update.message.text.strip()
    return await show_and_search_shops(update, context, search_term)

async def confirm_shop_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ينفذ حذف المحل فعلياً."""
    query = update.callback_query
    await query.answer()
    
    try:
        shop_id = int(query.data.split('_')[-1])
    except ValueError:
        return await show_admin_menu(update, context)

    if delete_shop(shop_id):
        await query.message.reply_text(
            f"✅ تم حذف المحل بنجاح!", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة لقائمة المحلات", callback_data="show_shops_list")]])
        )
    else:
        await query.message.reply_text(
            "❌ حدث خطأ أثناء حذف المحل.", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة لقائمة المحلات", callback_data="show_shops_list")]])
        )
    return SHOW_SHOPS_ADMIN

async def prompt_edit_shop_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب من المدير إدخال تفاصيل التعديل للمحل المحدد."""
    query = update.callback_query
    await query.answer()
    
    try:
        shop_id = int(query.data.split('_')[-1])
    except ValueError:
        return await show_admin_menu(update, context)
    
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

    return await show_and_search_shops(update, context) 


# ----------------------------------------------------------------------
# دوال إدارة المجهزين (Agents Management) - تم تبسيطها بالكامل
# ----------------------------------------------------------------------

async def show_and_manage_agents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة المجهزين مع أزرار الإدارة (تعديل، حذف، تخصيص) بشكل مصغّر."""
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message
        
    agents = get_all_agents()
    
    keyboard = []
    
    # 1. زر إضافة مجهز (الزر العلوي المطلوب)
    keyboard.append([InlineKeyboardButton("➕ إضافة مجهز جديد", callback_data="add_new_agent")])

    if agents:
        text = "📄 **قائمة المجهزين والإدارة السريعة:**"

        for agent in agents:
            agent_id = agent['id']
            agent_name = agent['name']
            
            # 1. زر المجهز كعنوان
            keyboard.append([InlineKeyboardButton(f"🧔🏻‍♂ {agent_name}", callback_data="ignore")])
            
            # 2. أزرار الإدارة المصغّرة (3 أزرار برموز تعبيرية فقط)
            assign_shops_btn = InlineKeyboardButton("➕🏬", callback_data=f"assign_shops_{agent_id}")
            edit_details_btn = InlineKeyboardButton("✏️", callback_data=f"edit_details_{agent_id}")
            delete_btn = InlineKeyboardButton("🗑️", callback_data=f"delete_agent_confirm_{agent_id}") 
            
            keyboard.append([assign_shops_btn, edit_details_btn, delete_btn])
            keyboard.append([InlineKeyboardButton("------", callback_data="ignore_2")]) 
    
    else:
        text = "❌ لا يوجد مجهزون مُضافون حالياً. إضغط على الزر أعلاه للإضافة."

    # زر العودة 
    keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        try:
            await message.edit_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
        except:
             await message.reply_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.message:
         await message.reply_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
         
    return MANAGE_AGENT

async def manage_agents_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج عام لأزرار قائمة إدارة المجهزين (للإضافة والعودة)."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "add_new_agent":
        await query.edit_message_text(
            "📝 أرسل اسم المجهز والرمز السري في سطرين منفصلين:\n"
            "الاسم\n"
            "الرمز السري (Code)",
            # الرجوع يعود إلى قائمة عرض/إدارة المجهزين
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="manage_agents_back")]])
        )
        return ADD_AGENT_STATE
        
    elif data == "manage_agents_back":
         # الرجوع يعيد عرض قائمة إدارة المجهزين المبسّطة
         return await show_and_manage_agents(update, context)
        
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

    # نعود إلى قائمة عرض/إدارة المجهزين
    return await show_and_manage_agents(update, context)

async def confirm_agent_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ينفذ حذف المجهز فعلياً (بعد النقر على زر السلة)."""
    query = update.callback_query
    await query.answer()
    
    try:
        agent_id = int(query.data.split('_')[-1])
    except ValueError:
        return await show_and_manage_agents(update, context)

    agent_name = get_agent_name_by_id(agent_id)
    
    if delete_agent(agent_id):
        await query.message.reply_text(f"✅ تم حذف المجهز **{agent_name}** بنجاح!")
    else:
        await query.message.reply_text("❌ حدث خطأ أثناء حذف المجهز.")

    return await show_and_manage_agents(update, context)


async def edit_agent_details_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب من المدير إدخال تفاصيل التعديل للمجهز المحدد (بعد النقر على زر القلم)."""
    query = update.callback_query
    await query.answer()
    
    try:
        agent_id = int(query.data.split('_')[-1])
        context.user_data['selected_agent_id'] = agent_id
    except ValueError:
        return await show_and_manage_agents(update, context)

    keyboard = [[InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="manage_agents_back")]]
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
        return await show_and_manage_agents(update, context)

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

    return await show_and_manage_agents(update, context)


async def list_shops_to_assign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض قائمة المحلات لإضافة أو إزالة الربط من مجهز محدد (بعد النقر على زر 🔗🏬)."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('assign_shops_'):
        try:
            agent_id = int(query.data.split('_')[-1])
            context.user_data['selected_agent_id'] = agent_id
        except ValueError:
            return await show_and_manage_agents(update, context)
    else:
        agent_id = context.user_data.get('selected_agent_id')
        if not agent_id:
            return await show_and_manage_agents(update, context)
            
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
            
            button = InlineKeyboardButton(
                text=f"{status} {shop['name']}", 
                callback_data=f"toggle_shop_{shop['id']}" 
            )
            keyboard.append([button])
    else:
        text = "❌ لا توجد محلات مُضافة لتخصيصها."

    # زر العودة يعود إلى قائمة إدارة المجهزين المبسّطة
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="manage_agents_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    return SELECT_SHOPS

async def toggle_shop_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ربط أو إلغاء ربط محل بمجهز عند النقر على علامة صح/خطأ."""
    query = update.callback_query
    await query.answer()
    
    try:
        shop_id = int(query.data.split('_')[-1])
        agent_id = context.user_data.get('selected_agent_id')
        
        if not agent_id:
             await query.message.reply_text("❌ حدث خطأ: لم يتم تحديد المجهز المطلوب.")
             return await show_and_manage_agents(update, context)
             
    except Exception as e:
        logger.error(f"Error extracting IDs in toggle_shop_selection: {e}")
        return await show_and_manage_agents(update, context)

    assigned_shops = get_assigned_shop_ids(agent_id)
    is_assigned = shop_id in assigned_shops
    
    if toggle_agent_shop_assignment(agent_id, shop_id, not is_assigned):
        return await list_shops_to_assign(update, context)
    else:
        await query.answer("❌ فشل تحديث الربط في قاعدة البيانات.")
        return SELECT_SHOPS 

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
        context.user_data['is_agent'] = True
        context.user_data['agent_id'] = agent['id']
        context.user_data['agent_name'] = agent['name']
        
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
        shops = get_agent_shops_by_search(agent_id, "") 
    
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
            
            url_button = InlineKeyboardButton(text=f" {shop['name']}", url=shop_url)
            keyboard.append([url_button])
            keyboard.append([InlineKeyboardButton("---", callback_data="ignore")])
    
    else:
        if search_term:
            text = f"❌ لا توجد محلات مطابقة لـ '{search_term}'."
        else:
            text = "❌ لم يتم تخصيص أي محلات لك حالياً."

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

    setup_db()

    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("admin", admin_login_command))
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        
        states={
            MAIN_MENU: [
                CallbackQueryHandler(agent_login_prompt, pattern=r"^agent_login_prompt$"),
                CommandHandler("start", start_command),
            ],
            
            AGENT_LOGIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_login_handler),
                CallbackQueryHandler(start_command, pattern=r"^start$"),
                CommandHandler("start", start_command),
            ],

            ADMIN_MENU: [
                CallbackQueryHandler(admin_menu_handler, pattern=r"^(add_shop|manage_agents|show_shops_list|admin_menu)$"),
                CommandHandler("start", start_command),
            ],
            
            ADD_SHOP_STATE: [
                # يتم البقاء في نفس الحالة
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_shop_data),
                # عند الضغط على زر "إنهاء والعودة" يعود للقائمة الرئيسية
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
                # 🚨 الحالة الأساسية أصبحت show_and_manage_agents
                CallbackQueryHandler(show_and_manage_agents, pattern=r"^manage_agents$"),
                CallbackQueryHandler(manage_agents_handler, pattern=r"^(add_new_agent|manage_agents_back)$"),
                
                # ربط الأزرار المصغّرة مباشرة بالدوال
                CallbackQueryHandler(edit_agent_details_menu, pattern=r"^edit_details_\d+$"), 
                CallbackQueryHandler(list_shops_to_assign, pattern=r"^assign_shops_\d+$"), 
                CallbackQueryHandler(confirm_agent_deletion, pattern=r"^delete_agent_confirm_\d+$"), 
                
                CallbackQueryHandler(admin_menu_handler, pattern=r"^admin_menu$"),
                CommandHandler("start", start_command),
            ],
            
            ADD_AGENT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_agent_data),
                CallbackQueryHandler(manage_agents_handler, pattern=r"^manage_agents_back$"),
                CommandHandler("start", start_command),
            ],
            
            EDIT_AGENT_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_updated_agent_data),
                CallbackQueryHandler(manage_agents_handler, pattern=r"^manage_agents_back$"),
                CommandHandler("start", start_command),
            ],
            
            SELECT_SHOPS: [
                CallbackQueryHandler(toggle_shop_selection, pattern=r"^toggle_shop_\d+$"), 
                CallbackQueryHandler(list_shops_to_assign, pattern=r"^assign_shops_\d+$"),
                CallbackQueryHandler(manage_agents_handler, pattern=r"^manage_agents_back$"),
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
    
    PORT = int(os.environ.get('PORT', '8080')) 
    RAILWAY_URL = os.getenv('APP_PUBLIC_URL') 
    
    if RAILWAY_URL:
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

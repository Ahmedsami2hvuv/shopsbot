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
# 🚨 ملاحظة: يجب التأكد من وجود هذه الدوال في ملف database.py
from database import (
    setup_db, 
    add_shop, 
    get_all_shops, 
    update_shop_details, # 👈🏼 لتعديل تفاصيل المحل
    delete_shop,         # 👈🏼 لحذف المحل
    add_agent, 
    get_all_agents, 
    get_agent_name_by_id,
    get_assigned_shop_ids, 
    toggle_agent_shop_assignment,
    check_agent_code,
    update_agent_details, # 👈🏼 لتعديل تفاصيل المجهز
    delete_agent,         # 👈🏼 لحذف المجهز
    get_agent_shops_by_search, # 👈🏼 البحث للمجهز
    get_shops_by_search        # 👈🏼 البحث للمدير
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
    # 👈🏼 حالة جديدة لعرض والبحث عن المحلات (المدير)
    SHOW_SHOPS_ADMIN 
) = range(13) # 👈🏼 تم التحديث إلى range(13)

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
        # 👈🏼 إعادة زر عرض المحلات
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
             # في حال كان التعديل يحتاج إلى إرسال رسالة جديدة (خطأ Edit)
             await update.callback_query.message.reply_text(text=text, reply_markup=reply_markup)

    elif update.message:
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
        keyboard = [
            [InlineKeyboardButton("دخول المجهز 🔑", callback_data="agent_login_prompt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        effective_message = update.effective_message
        
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                 "أهلاً بك. لرفع الطلبيات، إضغط على 'دخول المجهز'.",
                 reply_markup=reply_markup
            )
        elif effective_message:
             await effective_message.reply_text(
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
    
    if data == "edit_shops":
        return await list_shops_to_edit(update, context)
    
    return ADMIN_MENU

# ----------------------------------------------------------------------
# دوال عرض المحلات (Show Shops State) 
# ----------------------------------------------------------------------

async def show_shops_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يجلب المحلات ويعرضها على شكل ازرار URL للأدمن (لفتح كـ Web View)."""
    
    query = update.callback_query
    
    try:
        await query.answer("⏳ جاري جلب المحلات...") 
    except Exception:
        pass 

    shops = []
    
    try:
        shops = get_all_shops() 
    except Exception as e:
        logger.error(f"Error fetching shops for admin: {e}")
        text = "❌ حدث خطأ في قاعدة البيانات أثناء جلب المحلات."
        await update.effective_message.reply_text(text=text)
        return ADMIN_MENU 

    keyboard = []
    
    if shops:
        text = "📊 إختر المحل لفتح نافذة الطلبات (Web View):" 
        for shop in shops:
            
            shop_url = shop['url']
            
            if not shop_url.lower().startswith(('http://', 'https://')):
                 shop_url = "https://" + shop_url 
            
            button = InlineKeyboardButton(
                text=f"🔗 {shop['name']}", 
                url=shop_url
            )
            keyboard.append([button])
    
    else:
        text = "❌ لا توجد محلات مُضافة حالياً. الرجاء الضغط على الزر أدناه لإضافة أول محل."
        keyboard.append([InlineKeyboardButton("🏬 إضافة محل جديد", callback_data="add_shop")])

    keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            text=text, 
            reply_markup=reply_markup,
        )
    except Exception as e:
         logger.error(f"Failed to reply with WebApp buttons: {e}")
         text_only_fallback = "⚠️ فشل إرسال قائمة المحلات. القائمة المتوفرة:\n" + "\n".join([shop['name'] + " (" + shop['url'] + ")" for shop in shops])
         await update.effective_message.reply_text(text_only_fallback)
    
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
# دوال حذف المحلات (Delete Shop State) 
# ----------------------------------------------------------------------

async def list_shops_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة المحلات كأزرار لحذفها."""
    query = update.callback_query
    await query.answer()
    
    shops = get_all_shops()
    keyboard = []
    
    if shops:
        text = "🗑️ **إختر المحل الذي تريد حذفه نهائياً:**"
        for shop in shops:
            callback_data = f"delete_shop_confirm_{shop['id']}" 
            keyboard.append([InlineKeyboardButton(f"❌ {shop['name']}", callback_data=callback_data)])
    else:
        text = "❌ لا توجد محلات مُضافة حالياً لحذفها."

    keyboard.append([InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="admin_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text, 
        reply_markup=reply_markup,
        parse_mode="Markdown" 
    )
    return DELETE_SHOP_STATE


async def confirm_shop_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يؤكد ويحذف المحل المحدد."""
    query = update.callback_query
    await query.answer()

    try:
        shop_id = int(query.data.split('_')[-1])
        shops = get_all_shops()
        shop_name = next((shop['name'] for shop in shops if shop['id'] == shop_id), f"المحل رقم {shop_id}")
        
    except:
        await query.edit_message_text("❌ حدث خطأ في تحديد المحل.")
        return await show_admin_menu(update, context)

    if delete_shop(shop_id): 
        await query.edit_message_text(f"✅ تم حذف المحل **{shop_name}** بنجاح!")
    else:
        await query.edit_message_text("❌ فشل حذف المحل. تأكد من اتصال قاعدة البيانات.")
    
    return await show_admin_menu(update, context)

# ----------------------------------------------------------------------
# دوال تعديل المحلات (Edit Shop State) 
# ----------------------------------------------------------------------

async def list_shops_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة المحلات كأزرار لتعديل تفاصيلها (الاسم أو الرابط)."""
    query = update.callback_query
    await query.answer()
    
    shops = get_all_shops()
    keyboard = []
    
    if shops:
        text = "✏️ **إختر المحل الذي تريد تعديل تفاصيله:**"
        for shop in shops:
            callback_data = f"edit_shop_select_{shop['id']}" 
            keyboard.append([InlineKeyboardButton(f"✏️ {shop['name']}", callback_data=callback_data)])
    else:
        text = "❌ لا توجد محلات مُضافة حالياً لتعديلها."

    keyboard.append([InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="admin_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text, 
        reply_markup=reply_markup,
        parse_mode="Markdown" 
    )
    return EDIT_SHOP_STATE


async def prompt_edit_shop_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب من المدير إرسال تفاصيل المحل الجديدة."""
    query = update.callback_query
    await query.answer()

    try:
        shop_id = int(query.data.split('_')[-1])
        context.user_data['selected_shop_id'] = shop_id
        
        shops = get_all_shops()
        shop_name = next((shop['name'] for shop in shops if shop['id'] == shop_id), f"المحل رقم {shop_id}")
        
    except:
        await query.edit_message_text("❌ حدث خطأ في تحديد المحل.")
        return await show_admin_menu(update, context)

    keyboard = [
        [InlineKeyboardButton("🔙 إلغاء والعودة للقائمة", callback_data="edit_shops")] 
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📝 **تعديل المحل {shop_name}:**\n"
        "إرسل **الإسم الجديد للمحل** بالسطر الأول، و**الرابط الجديد (URL)** بالسطر الثاني. \n"
        "سيتم حفظ التغييرات عند الإرسال.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return EDIT_SHOP_STATE


async def receive_updated_shop_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل بيانات المحل المحدثة ويحفظها بقاعدة البيانات."""
    
    shop_id = context.user_data.get('selected_shop_id')
    
    if not shop_id:
        await update.message.reply_text("❌ حدث خطأ، لم يتم تحديد المحل المطلوب تعديله.")
        return await show_admin_menu(update, context)

    try:
        text = update.message.text.strip()
        parts = text.split('\n', 1) 
        
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ صيغة الإدخال خطأ. لازم تكون:\n"
                "إسم المحل الجديد\n"
                "رابط المحل الجديد (URL)"
            )
            return EDIT_SHOP_STATE 

        new_shop_name = parts[0].strip()
        new_shop_url = parts[1].strip()

        if update_shop_details(shop_id, new_shop_name, new_shop_url): 
             await update.message.reply_text(
                f"✅ تم تحديث تفاصيل المحل **{new_shop_name}** بنجاح!",
                parse_mode="Markdown"
            )
        else:
             await update.message.reply_text(
                f"❌ فشل تحديث المحل. تأكد من عدم وجود محل آخر بنفس الاسم أو حدث خطأ في قاعدة البيانات."
            )
        
    except Exception as e:
        logger.error(f"Error updating shop: {e}")
        await update.message.reply_text("❌ حدث خطأ غير متوقع أثناء تحديث المحل.")

    return await show_admin_menu(update, context)


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
        [InlineKeyboardButton("حذف مجهز 🗑️", callback_data="delete_agent")], 
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")] # 👈🏼 هنا التصحيح
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🧑‍💻 **قائمة إدارة المجهزين:**\n\nإختار الإجراء المطلوب:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return MANAGE_AGENT # 👈🏼 يجب أن تبقى الحالة MANAGE_AGENT


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
    
    if update.callback_query:
        query = update.callback_query
        
        if query.data and query.data.startswith(("select_agent_", "edit_details_")):
            try:
                agent_id = int(query.data.split('_')[-1])
                context.user_data['selected_agent_id'] = agent_id 
            except ValueError:
                pass
        
        agent_id = context.user_data.get('selected_agent_id')

        if agent_id:
            try:
                assigned_ids = get_assigned_shop_ids(agent_id)
                context.user_data['temp_assigned_shops'] = set(assigned_ids)
            except Exception:
                context.user_data['temp_assigned_shops'] = set() 
        
        await query.answer()
    
    agent_id = context.user_data.get('selected_agent_id')

    if not agent_id:
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ حدث خطأ، لم يتم تحديد المجهز.")
            return await manage_agents_menu(update, context)
        else:
            await update.message.reply_text("❌ حدث خطأ، لم يتم تحديد المجهز.")
            return MANAGE_AGENT

    agent_name = get_agent_name_by_id(agent_id) 
    if not agent_name:
        agent_name = f"المجهز رقم {agent_id}"
    
    edit_details_callback = f"edit_details_{agent_id}" 

    keyboard = [
        [InlineKeyboardButton(f"إضافة محلات إلى {agent_name} 🏪", callback_data=f"assign_shops_{agent_id}")],
        [InlineKeyboardButton(f"تعديل تفاصيل {agent_name} ✏️", callback_data=edit_details_callback)],
        [InlineKeyboardButton("🔙 العودة لقائمة المجهزين", callback_data="list_agents")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"**إختر الإجراء المطلوب للمجهز {agent_name}:**"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    elif update.message:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    return MANAGE_AGENT

async def edit_agent_details_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب من المدير إرسال تفاصيل المجهز الجديدة."""
    query = update.callback_query
    await query.answer()

    agent_id = int(query.data.split('_')[-1])
    context.user_data['selected_agent_id'] = agent_id 
    
    agent_name = get_agent_name_by_id(agent_id) or "هذا المجهز"

    keyboard = [
        [InlineKeyboardButton("🔙 العودة لخيارات المجهز", callback_data=f"select_agent_{agent_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✏️ **تعديل تفاصيل المجهز {agent_name}:**\n"
        "إرسل الإسم الجديد للمجهز بالسطر الأول، ورمز الدخول السري الجديد بالسطر الثاني. \n"
        "سيتم حفظ التغييرات عند الإرسال.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return EDIT_AGENT_DETAILS 

async def receive_new_agent_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل تفاصيل المجهز الجديدة ويحفظها، ويعيد الحالة إلى خيارات المجهز."""
    
    text = update.message.text.strip()
    parts = text.split('\n', 1) 
    agent_id = context.user_data.get('selected_agent_id')

    # ... (تحقق من ID المجهز وصيغة الإدخال كما في الكود السابق)

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

    # 🚀 التصحيح النهائي: نرسل رسالة جديدة تعرض قائمة خيارات المجهز
    # ونعيد الحالة إلى MANAGE_AGENT (الحالة التي تحتوي على الخيارات)
    await select_agent_menu(update, context)
    return MANAGE_AGENT

async def list_shops_to_assign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة المحلات لربطها بالمجهز وتظهر علامة ✅، مرتبة حسب التعيين أولاً."""
    query = update.callback_query
    await query.answer()

    agent_id = context.user_data.get('selected_agent_id')
    if not agent_id:
        return await manage_agents_menu(update, context)
        
    shops = get_all_shops()
    agent_name = get_agent_name_by_id(agent_id) or f"المجهز رقم {agent_id}"
    
    selected_shops = context.user_data.get('temp_assigned_shops', set())

    def sort_shops_key(shop):
        is_assigned_flag = 0 if shop['id'] in selected_shops else 1
        return (is_assigned_flag, shop['name'])
    
    shops.sort(key=sort_shops_key) 

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
        shop_id = shop['id']
        is_selected = shop_id in selected_shops
        emoji = "✅ " if is_selected else "⬜ "
        callback_data = f"toggle_shop_{shop_id}"
        keyboard.append([InlineKeyboardButton(f"{emoji}{shop['name']}", callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton("✅ تأكيد وحفظ الربط", callback_data="confirm_shop_assignment")])
    keyboard.append([InlineKeyboardButton("🔙 إلغاء والعودة لخيارات المجهز", callback_data=f"select_agent_{agent_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🏪 **ربط محلات بالمجهز {agent_name}:**\n\n"
        "إختر المحلات التي سيتم إتاحتها لهذا المجهز. المحلات المربوطة حالياً تظهر أولاً.\n\n"
        "اضغط على 'تأكيد وحفظ الربط' لتطبيق التغييرات.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return SELECT_SHOPS


async def toggle_shop_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعكس حالة اختيار المحل مؤقتاً ويعيد عرض القائمة."""
    query = update.callback_query
    await query.answer()
    
    shop_id = int(query.data.split('_')[-1])
    
    selected_shops = context.user_data.get('temp_assigned_shops', set())
    
    if shop_id in selected_shops:
        selected_shops.remove(shop_id)
    else:
        selected_shops.add(shop_id)
        
    context.user_data['temp_assigned_shops'] = selected_shops
    
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
        current_assigned_ids = set(get_assigned_shop_ids(agent_id))
        
        to_add = selected_shops - current_assigned_ids
        to_remove = current_assigned_ids - selected_shops
        
        for shop_id in to_add:
            toggle_agent_shop_assignment(agent_id, shop_id, True)
        for shop_id in to_remove:
            toggle_agent_shop_assignment(agent_id, shop_id, False)

        await query.edit_message_text("✅ تم حفظ ربط المحلات بنجاح!")
        
    except Exception as e:
        logger.error(f"Error saving shop assignment for agent {agent_id}: {e}")
        await query.edit_message_text("❌ حدث خطأ أثناء محاولة حفظ ربط المحلات.")

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
            keyboard = [
                [InlineKeyboardButton("↩️ إعادة إدخال البيانات", callback_data="add_new_agent")],
                [InlineKeyboardButton("🔙 العودة لإدارة المجهزين", callback_data="manage_agents")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ صيغة الإدخال خطأ. لازم تكون:\n"
                "إسم المجهز\n"
                "رمز الدخول السري",
                 reply_markup=reply_markup
            )
            return MANAGE_AGENT 

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
            return MANAGE_AGENT
        else:
            keyboard = [
                [InlineKeyboardButton("↩️ إعادة إدخال الرمز", callback_data="add_new_agent")],
                [InlineKeyboardButton("🔙 العودة لإدارة المجهزين", callback_data="manage_agents")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"❌ الرمز السري موجود مسبقاً أو حدث خطأ بالحفظ. جرب رمز سري مختلف.",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            return MANAGE_AGENT
        
    except Exception as e:
        logger.error(f"Error adding agent: {e}")
        keyboard = [
            [InlineKeyboardButton("↩️ إعادة إدخال البيانات", callback_data="add_new_agent")],
            [InlineKeyboardButton("🔙 العودة لإدارة المجهزين", callback_data="manage_agents")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ حدث خطأ غير متوقع أثناء إضافة المجهز.",
            reply_markup=reply_markup
        )
        return MANAGE_AGENT

# ----------------------------------------------------------------------
# دوال حذف المجهزين (Delete Agent State) 
# ----------------------------------------------------------------------

async def list_agents_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة المجهزين كأزرار لحذفهم."""
    query = update.callback_query
    await query.answer()
    
    agents = get_all_agents()
    keyboard = []
    
    if agents:
        text = "🗑️ **إختر المجهز الذي تريد حذفه نهائياً:**"
        for agent in agents:
            callback_data = f"delete_agent_confirm_{agent['id']}" 
            keyboard.append([InlineKeyboardButton(f"❌ {agent['name']}", callback_data=callback_data)])
    else:
        text = "❌ لا يوجد مجهزين مُضافين حالياً لحذفهم."

    keyboard.append([InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="manage_agents")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text, 
        reply_markup=reply_markup,
        parse_mode="Markdown" 
    )
    return DELETE_AGENT_STATE


async def confirm_agent_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يؤكد ويحذف المجهز المحدد."""
    query = update.callback_query
    await query.answer()

    try:
        agent_id = int(query.data.split('_')[-1])
        agent_name = get_agent_name_by_id(agent_id) or f"المجهز رقم {agent_id}"
        
    except:
        await query.edit_message_text("❌ حدث خطأ في تحديد المجهز.")
        return await manage_agents_menu(update, context)

    if delete_agent(agent_id): 
        await query.edit_message_text(f"✅ تم حذف المجهز **{agent_name}** بنجاح! جميع ارتباطاته بالمحلات قد حُذفت أيضاً.")
    else:
        await query.edit_message_text("❌ فشل حذف المجهز. تأكد من اتصال قاعدة البيانات.")
    
    return await manage_agents_menu(update, context)

# ----------------------------------------------------------------------
# دوال المجهز (Agent)
# ----------------------------------------------------------------------

async def agent_login_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يطلب من المجهز إدخال رمز الدخول السري."""
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
    """يستقبل رمز الدخول السري ويتحقق منه ويرحب باسم المجهز."""
    
    agent_code = update.message.text.strip()
    
    agent_info = check_agent_code(agent_code)
    
    if agent_info:
        agent_name = agent_info['name']
        agent_id = agent_info['id']
        
        context.user_data['current_agent_id'] = agent_id
        
        await update.message.reply_text(
            f"👋🏼 **أهلاً بك {agent_name}** كمجهز! تم تسجيل دخولك بنجاح.",
            parse_mode="Markdown"
        )
        
        return await show_agent_menu(update, context) 
        
    else:
        await update.message.reply_text(
            "❌ رمز الدخول غير صحيح. الرجاء المحاولة مرة أخرى أو إرسال /start للعودة للقائمة."
        )
        return AGENT_LOGIN

async def agent_shop_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل نص البحث من المجهز ويعرض المحلات المطابقة."""

    search_term = update.message.text.strip()
    agent_id = context.user_data.get('current_agent_id')

    if not agent_id:
        await update.message.reply_text("❌ لم يتم تسجيل دخول المجهز.")
        return AGENT_LOGIN

    agent_shops = get_agent_shops_by_search(agent_id, search_term)

    keyboard = []

    if agent_shops:
        text = f"✅ **نتائج البحث عن '{search_term}'** (إضغط لفتح رابط المحل):"
        for shop in agent_shops:
            shop_url = shop['url']
            # للتأكد من أن الرابط يبدأ بـ https://
            if not shop_url.lower().startswith(('http://', 'https://')):
                 shop_url = "https://" + shop_url 

            button = InlineKeyboardButton(f"🔗 {shop['name']}", url=shop_url)
            keyboard.append([button])
    else:
        text = f"❌ لم يتم العثور على محلات مطابقة لـ '{search_term}' ضمن محلاتك المخصصة."

    keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة", callback_data="agent_menu_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return AGENT_MENU
    

async def show_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة المجهز بعد تسجيل الدخول."""
    
    agent_name = get_agent_name_by_id(context.user_data.get('current_agent_id')) or "عزيزي المجهز"
    
    keyboard = [
        # 👇🏼 الزر الذي يعرض كل المحلات
        [InlineKeyboardButton("🏪 عرض جميع محلاتي", callback_data="show_agent_shops")], 
        [InlineKeyboardButton("🚪 تسجيل خروج", callback_data="start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"**قائمة المجهز {agent_name}:**\n إختر الإجراء المطلوب أو:\n\n"
        "🔍 **للبحث السريع:** قم بإرسال أي جزء من إسم المحل (مثل: خالد). \n"
        "ستظهر لك أزرار المحلات التي تطابق بحثك."
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    return AGENT_MENU

async def show_agent_shops_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض المحلات المخصصة للمجهز (باستخدام URL لفتح كـ Web View)، مرتبة أبجدياً."""
    query = update.callback_query
    await query.answer()
    
    agent_id = context.user_data.get('current_agent_id')
    assigned_shop_ids = get_assigned_shop_ids(agent_id)
    
    shops = get_all_shops()
    agent_shops = [shop for shop in shops if shop['id'] in assigned_shop_ids]

    agent_shops.sort(key=lambda shop: shop['name'])

    keyboard = []
    
    if agent_shops:
        text = "**🏪 المحلات المتاحة لك لرفع الطلبات (Web View):**"
        for shop in agent_shops:
            
            shop_url = shop['url']
            if not shop_url.lower().startswith(('http://', 'https://')):
                 shop_url = "https://" + shop_url 

            button = InlineKeyboardButton(f"🔗 {shop['name']}", url=shop_url)
            keyboard.append([button])
    else:
        text = "❌ لا توجد محلات مربوطة بحسابك حالياً."

    keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة", callback_data="agent_menu_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    return AGENT_MENU

async def admin_shop_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل نص البحث من المدير ويعرض المحلات المطابقة كأزرار Web View."""

    search_term = update.message.text.strip()

    if not search_term:
        await update.message.reply_text("❌ لم يتم إدخال نص للبحث.")
        return ADMIN_MENU

    shops = get_shops_by_search(search_term)

    keyboard = []

    if shops:
        text = f"✅ **نتائج البحث عن '{search_term}'** (إضغط لفتح نافذة الطلبات):"
        for shop in shops:
            shop_url = shop['url']
            # للتأكد من أن الرابط يبدأ بـ https://
            if not shop_url.lower().startswith(('http://', 'https://')):
                 shop_url = "https://" + shop_url 

            button = InlineKeyboardButton(f"🔗 {shop['name']}", url=shop_url)
            keyboard.append([button])
    else:
        text = f"❌ لم يتم العثور على محلات مطابقة لـ '{search_term}'."

    keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة", callback_data="admin_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return ADMIN_MENU

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
            text = "📊 **جميع المحلات:**"
            
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
            text = "❌ لا توجد محلات مُضافة حالياً. إضغط لإضافة محل."
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
    
    # يجب أن نبقى في حالة تسمح باستقبال نص البحث
    return SHOW_SHOPS_ADMIN

async def admin_shop_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل نص البحث من المدير (في حالة SHOW_SHOPS_ADMIN) ويعرض النتائج."""
    search_term = update.message.text.strip()
    
    # نستخدم الدالة الأساسية لتنفيذ البحث وعرض النتائج
    return await show_and_search_shops(update, context, search_term)


# ----------------------------------------------------------------------
# الدالة الرئيسية للتشغيل
# ----------------------------------------------------------------------

def main() -> None:
    """بدء تشغيل البوت. تم التعديل لاستخدام Webhook القسري لبيئة Railway."""
    
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
            # 🚀 1. القائمة الرئيسية للمدير (نقطة الدخول)
            ADMIN_MENU: [
                # 👈🏼 يذهب إلى شاشة البحث/العرض الجديدة التي تحتوي على أزرار التعديل والحذف
                CallbackQueryHandler(show_and_search_shops, pattern="^show_shops_list$"), 
                # معالجات الأزرار الأخرى التي لا تحتاج إلى بحث
                CallbackQueryHandler(admin_menu_handler, pattern="^(add_shop|manage_agents|admin_menu)$"),
            ],
            
            # 🚀 2. الحالة الجديدة للبحث وعرض المحلات (المدير)
            SHOW_SHOPS_ADMIN: [
                # معالج الرسائل النصية للبحث الجزئي
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_shop_search_handler),
                
                # أزرار الإدارة التي تظهر في نتائج البحث
                CallbackQueryHandler(prompt_edit_shop_details, pattern="^edit_shop_select_\d+$"),
                # عند الضغط على حذف يذهب إلى حالة DELETE_SHOP_STATE لتأكيد الحذف
                CallbackQueryHandler(confirm_shop_deletion, pattern="^delete_shop_confirm_\d+$"), 
                
                # زر العودة
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"), 
            ],
            
            # 3. إضافة محل
            ADD_SHOP_STATE: [
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_shop_data),
            ],
            
            # 4. إدارة المجهزين (المدير)
            MANAGE_AGENT: [
                CallbackQueryHandler(manage_agents_menu, pattern="^manage_agents$"), 
                CallbackQueryHandler(add_new_agent_menu, pattern="^add_new_agent$"), 
                CallbackQueryHandler(list_agents_menu, pattern="^list_agents$"), 
                CallbackQueryHandler(list_agents_to_delete, pattern="^delete_agent$"),
                
                CallbackQueryHandler(edit_agent_details_menu, pattern="^edit_details_\d+$"),
                
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"),
                CallbackQueryHandler(list_shops_to_assign, pattern="^assign_shops_\d+$"),
            ],
            
            # 5. إضافة مجهز
            ADD_AGENT_STATE: [
                CallbackQueryHandler(manage_agents_menu, pattern="^manage_agents$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_agent_data)
            ],

            # 6. اختيار المحلات للمجهز
            SELECT_SHOPS: [
                CallbackQueryHandler(handle_shop_assignment, pattern="^confirm_shop_assignment$"),
                CallbackQueryHandler(toggle_shop_selection, pattern="^toggle_shop_\d+$"), 
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"),
            ],

            # 7. تعديل تفاصيل المجهز (زر الرجوع يعمل الآن)
            EDIT_AGENT_DETAILS: [
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"), # 👈🏼 زر الرجوع
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_agent_details), 
            ],
            
            # 8. حالة حذف المحل (نعود منها إلى قائمة المحلات للعرض/البحث)
            DELETE_SHOP_STATE: [
                # 👈🏼 العودة إلى قائمة العرض والبحث
                CallbackQueryHandler(show_and_search_shops, pattern="^show_shops_list$"), 
                # 👈🏼 معالج التأكيد الفعلي (يجب أن يتم تحديثه في main.py)
                CallbackQueryHandler(confirm_shop_deletion, pattern="^delete_shop_confirm_\d+$"),
            ],
            
            # 9. حذف المجهز
            DELETE_AGENT_STATE: [
                CallbackQueryHandler(manage_agents_menu, pattern="^manage_agents$"), 
                CallbackQueryHandler(confirm_agent_deletion, pattern="^delete_agent_confirm_\d+$"),
            ],

            # 10. تعديل تفاصيل المحل (بعد الإدخال نعود إلى قائمة المحلات للعرض/البحث)
            EDIT_SHOP_STATE: [
                # 👈🏼 العودة إلى قائمة العرض والبحث
                CallbackQueryHandler(show_and_search_shops, pattern="^show_shops_list$"), 
                CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"), 
                CallbackQueryHandler(prompt_edit_shop_details, pattern="^edit_shop_select_\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_updated_shop_data),
            ],
            
            # 11. تسجيل دخول المجهز
            AGENT_LOGIN: [
                CallbackQueryHandler(agent_login_prompt, pattern="^agent_login_prompt$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_login_receive_code),
                CallbackQueryHandler(start_command, pattern="^start$"),
                CommandHandler("start", start_command), 
            ],

            # 12. قائمة المجهز (البحث الجزئي للمجهز)
            AGENT_MENU: [
                # 1. معالج الرسائل النصية: يستقبل نص البحث ويجلب المحلات المطابقة
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_shop_search_handler),
                
                # 2. العودة وتسجيل الخروج
                CallbackQueryHandler(show_agent_menu, pattern="^agent_menu_back$"), 
                CallbackQueryHandler(start_command, pattern="^start$"), 
                CommandHandler("start", start_command), 
            ]
        },
        
        fallbacks=[CommandHandler("start", start_command)],
    )

    application.add_handler(conv_handler)
    
    # -------------------------------------------------------------------
    # 🚀 الكود الجديد والفعّال لتشغيل Webhook على Railway
    # -------------------------------------------------------------------
    
    # -------------------------------------------------------------------
    # 🚀 الكود الجديد لتشغيل Webhook على Railway (مصحح)
    # -------------------------------------------------------------------
    
    PORT = int(os.environ.get('PORT', '8080')) 
    
    # 💡 التصحيح: نستخدم os.getenv() للتحقق من وجود العنوان بشكل آمن
    RAILWAY_URL = os.getenv('RAILWAY_STATIC_URL') 
    
    if RAILWAY_URL:
        # تشغيل الـ Webhook
        url_path = BOT_TOKEN # نستخدم التوكن كمسار سري
        webhook_url = f"https://{RAILWAY_URL}/{url_path}"
        
        application.run_webhook(
            listen="0.0.0.0", 
            port=PORT,
            url_path=url_path,
            webhook_url=webhook_url
        )
        logger.info(f"🤖 تم تشغيل البوت بوضعية Webhook قسرية على العنوان: {RAILWAY_URL}")
        
    else:
        # إذا لم يتم العثور على عنوان Railway، نعتبر أن البوت يعمل محلياً أو فشل Webhook
        logger.error("🚫 فشل العثور على RAILWAY_STATIC_URL. الرجاء التحقق من متغيرات البيئة.")
        # هنا يمكنك وضع Polling إذا كنت تتوقع تشغيل البوت محليًا في بعض الأحيان
        # application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    # -------------------------------------------------------------------

if __name__ == "__main__":
    main()

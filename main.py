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
    get_assigned_shop_ids, 
    toggle_agent_shop_assignment,
    check_agent_code,
    update_agent_details # <<< تم إضافة دالة التحديث
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
    EDIT_AGENT_DETAILS 
) = range(9)

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
    
    # التعامل مع update.effective_message سواء كانت رسالة /start أو رد على رسالة سابقة
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
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
    """يجلب المحلات ويعرضها على شكل ازرار WebApp للأدمن (تم التأكيد على WebAppInfo)."""
    
    query = update.callback_query
    await query.answer() 

    shops = get_all_shops()
    
    keyboard = []
    
    if shops:
        text = "📊 **إختر المحل لفتح نافذة الطلبات (Web App):**"
        current_row = []
        for i, shop in enumerate(shops):
            # التأكد من استخدام WebAppInfo لفتح الويب فيو
            button = InlineKeyboardButton(
                text=shop['name'], 
                web_app=WebAppInfo(url=shop['url'])
            )
            current_row.append(button)
            
            # 3 أزرار في الصف كحد أقصى
            if len(current_row) == 3 or i == len(shops) - 1:
                keyboard.append(current_row)
                current_row = []
    
    else:
        text = "❌ لا توجد محلات مُضافة حالياً."
        keyboard.append([InlineKeyboardButton("🏬 إضافة محل جديد", callback_data="add_shop")])

    keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # يجب أن يتم هنا تعديل الرسالة التي ضغط منها الزر (query)
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
    # ملاحظة: هذه الدالة تستقبل إما query أو message (من receive_new_agent_details)
    
    if update.callback_query:
        query = update.callback_query
        await query.answer() # الرد على الضغطة

        # استخدام الـ ID المخزن أو استخراجه
        if query.data and query.data.startswith("select_agent_"):
            agent_id = int(query.data.split('_')[-1])
            context.user_data['selected_agent_id'] = agent_id 
        
            try:
                assigned_ids = get_assigned_shop_ids(agent_id)
                context.user_data['temp_assigned_shops'] = set(assigned_ids)
            except Exception:
                context.user_data['temp_assigned_shops'] = set() 
    
    agent_id = context.user_data.get('selected_agent_id')

    if not agent_id:
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ حدث خطأ، لم يتم تحديد المجهز.")
            return await manage_agents_menu(update, context)
        else:
            await update.message.reply_text("❌ حدث خطأ، لم يتم تحديد المجهز.")
            return MANAGE_AGENT # نعتمد على أن المجهز سيعيد الضغط على زر ما

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
         # يتم الرد هنا عندما تكون العودة من رسالة نصية (مثل بعد تعديل التفاصيل)
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

    # استخراج الـ agent_id من الـ callback_data الجديدة
    agent_id = int(query.data.split('_')[-1])
    context.user_data['selected_agent_id'] = agent_id 
    
    agent_name = get_agent_name_by_id(agent_id) or "هذا المجهز"

    # تم إضافة زر العودة لخيارات المجهز
    keyboard = [
        [InlineKeyboardButton("🔙 العودة لخيارات المجهز", callback_data=f"select_agent_{agent_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✏️ **تعديل تفاصيل المجهز {agent_name}:**\n"
        "إرسل الإسم الجديد للمجهز بالسطر الأول، ورمز الدخول السري الجديد بالسطر الثاني. \n"
        "سيتم حفظ التغييرات عند الإرسال.", # <<< تم إزالة الرسالة المؤقتة
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    # الانتقال إلى حالة استقبال التفاصيل الجديدة
    return EDIT_AGENT_DETAILS 

async def receive_new_agent_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يستقبل تفاصيل المجهز الجديدة ويحفظها."""
    
    text = update.message.text.strip()
    parts = text.split('\n', 1) 
    agent_id = context.user_data.get('selected_agent_id')

    if not agent_id:
        await update.message.reply_text("❌ حدث خطأ، لم يتم تحديد المجهز المطلوب تعديله.")
        # العودة إلى قائمة خيارات المجهز المحدد
        return await select_agent_menu(update, context) 

    if len(parts) != 2:
        await update.message.reply_text(
            "❌ صيغة الإدخال خطأ. لازم تكون:\n"
            "الإسم الجديد للمجهز\n"
            "رمز الدخول السري الجديد"
        )
        return EDIT_AGENT_DETAILS

    new_name = parts[0].strip()
    new_code = parts[1].strip()

    # *** منطق الحفظ الفعلي ***
    result = update_agent_details(agent_id, new_name, new_code)
    
    if result is True:
        await update.message.reply_text(
            f"✅ تم تحديث بيانات المجهز بنجاح!\n"
            f"الإسم الجديد: **{new_name}**\n"
            f"الرمز الجديد: **{new_code}**",
            parse_mode="Markdown"
        )
    elif result == "CODE_EXISTS":
        await update.message.reply_text(
            "❌ فشل التحديث: رمز الدخول السري **مستخدم بالفعل** من قبل مجهز آخر. الرجاء إدخال رمز آخر.",
            parse_mode="Markdown"
        )
        return EDIT_AGENT_DETAILS
    else:
        await update.message.reply_text(
            "❌ حدث خطأ غير متوقع أثناء تحديث بيانات المجهز."
        )

    # العودة إلى قائمة خيارات المجهز المحدد
    return await select_agent_menu(update, context) 


async def list_shops_to_assign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة المحلات لربطها بالمجهز وتظهر علامة ✅."""
    query = update.callback_query
    await query.answer()

    agent_id = context.user_data.get('selected_agent_id')
    if not agent_id:
        return await manage_agents_menu(update, context)
        
    shops = get_all_shops()
    agent_name = get_agent_name_by_id(agent_id) or f"المجهز رقم {agent_id}"
    
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
        shop_id = shop['id']
        is_selected = shop_id in selected_shops
        emoji = "✅ " if is_selected else "⬜ "
        callback_data = f"toggle_shop_{shop_id}"
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
        
        # رسالة الترحيب باسم المجهز
        await update.message.reply_text(
            f"👋🏼 **أهلاً بك {agent_name}** كمجهز! تم تسجيل دخولك بنجاح.",
            parse_mode="Markdown"
        )
        
        return await show_agent_menu(update, context) # التوجيه لقائمة المجهز
        
    else:
        await update.message.reply_text(
            "❌ رمز الدخول غير صحيح. الرجاء المحاولة مرة أخرى أو إرسال /start للعودة للقائمة."
        )
        return AGENT_LOGIN

async def show_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تعرض قائمة المجهز بعد تسجيل الدخول."""
    
    agent_name = get_agent_name_by_id(context.user_data.get('current_agent_id')) or "عزيزي المجهز"
    
    keyboard = [
        [InlineKeyboardButton("🏪 عرض محلاتي", callback_data="show_agent_shops")],
        [InlineKeyboardButton("🚪 تسجيل خروج", callback_data="start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # إذا كان هناك استدعاء من زر (query) نستخدم edit
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            f"**قائمة المجهز {agent_name}:**\n إختر الإجراء المطلوب:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    # إذا كان الاستدعاء من رسالة (login_receive_code) نستخدم reply
    else:
        await update.message.reply_text(
            f"**قائمة المجهز {agent_name}:**\n إختر الإجراء المطلوب:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    return AGENT_MENU

async def show_agent_shops_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض المحلات المخصصة للمجهز (تم التأكيد على WebAppInfo)."""
    query = update.callback_query
    await query.answer()
    
    agent_id = context.user_data.get('current_agent_id')
    assigned_shop_ids = get_assigned_shop_ids(agent_id)
    
    shops = get_all_shops()
    # جلب المحلات المربوطة فقط
    agent_shops = [shop for shop in shops if shop['id'] in assigned_shop_ids]

    keyboard = []
    
    if agent_shops:
        text = "**🏪 المحلات المتاحة لك لرفع الطلبات (Web View):**"
        current_row = []
        for i, shop in enumerate(agent_shops):
            # *** هنا يكمن الحل! استخدام WebAppInfo لفتح الويب فيو ***
            button = InlineKeyboardButton(shop['name'], web_app=WebAppInfo(url=shop['url']))
            current_row.append(button)
            
            if len(current_row) == 2 or i == len(agent_shops) - 1: # نضع زرين في الصف
                keyboard.append(current_row)
                current_row = []
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
                CallbackQueryHandler(show_shops_admin_handler, pattern="^show_shops_admin$"),
                CallbackQueryHandler(admin_menu_handler, pattern="^(add_shop|manage_agents|admin_menu)$"),
            ],
            
            ADD_SHOP_STATE: [
                CallbackQueryHandler(admin_menu_handler, pattern="^admin_menu$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_shop_data),
            ],
            
            MANAGE_AGENT: [
                CallbackQueryHandler(admin_menu_handler, pattern="^admin_menu$"), 
                CallbackQueryHandler(manage_agents_menu, pattern="^manage_agents$"), 
                CallbackQueryHandler(add_new_agent_menu, pattern="^add_new_agent$"), 
                CallbackQueryHandler(list_agents_menu, pattern="^list_agents$"), 
                
                # المعالج الجديد لزر تعديل التفاصيل
                CallbackQueryHandler(edit_agent_details_menu, pattern="^edit_details_\d+$"), 
                
                # المعالجات الرئيسية لصفحة المجهز المحدد
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"),
                CallbackQueryHandler(list_shops_to_assign, pattern="^assign_shops_\d+$"),
            ],
            
            ADD_AGENT_STATE: [
                CallbackQueryHandler(manage_agents_menu, pattern="^manage_agents$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_agent_data)
            ],

            SELECT_SHOPS: [
                CallbackQueryHandler(handle_shop_assignment, pattern="^confirm_shop_assignment$"),
                CallbackQueryHandler(toggle_shop_selection, pattern="^toggle_shop_\d+$"), 
                # العودة من شاشة اختيار المحلات
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"),
            ],

            EDIT_AGENT_DETAILS: [
                # العودة من شاشة تعديل التفاصيل
                CallbackQueryHandler(select_agent_menu, pattern="^select_agent_\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_agent_details), # دالة الحفظ الفعلية
            ],
            
            AGENT_LOGIN: [
                CallbackQueryHandler(agent_login_prompt, pattern="^agent_login_prompt$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_login_receive_code),
                CallbackQueryHandler(start_command, pattern="^start$"),
                CommandHandler("start", start_command), 
            ],

            AGENT_MENU: [
                 CallbackQueryHandler(show_agent_shops_handler, pattern="^show_agent_shops$"), # عرض المحلات (للمجهز)
                 CallbackQueryHandler(show_agent_menu, pattern="^agent_menu_back$"), # للعودة من عرض المحلات
                 CallbackQueryHandler(start_command, pattern="^start$"), # تسجيل خروج
                 CommandHandler("start", start_command), 
            ]
        },
        
        fallbacks=[CommandHandler("start", start_command)],
    )

    application.add_handler(conv_handler)

    logger.info("🤖 البوت جاي يشتغل (Long Polling)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

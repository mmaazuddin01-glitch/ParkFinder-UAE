"""ParkFinder UAE - STREAMLIT app, version 2 (mobile-app look).     PARKFINDER_STREAMLIT_V2

Install:  py -m pip install streamlit
Run:      py -m streamlit run "parkfinder_streamlit_v2.py"      (from Command Prompt)
      or: put run_parkfinder.py next to this file and press F5 on it in IDLE.

Pages: Home, Search, Map, Saved, Profile (bottom bar) + Nearby, About, Parking Timer, Cost Calculator.

HONEST NOTES (tell the judges):
 - LIVE LOCATIONS: parking places are loaded from OpenStreetMap (Overpass API) for Dubai, Sharjah and Ajman and
   refreshed every 30 minutes. They are REAL mapped locations, but nobody publishes live free/occupied spaces for
   them, so availability is a TYPICAL-PATTERN ESTIMATE for the weekday + time (labelled "Usually...", not live), or
   a driver report / average of driver reports when those exist. If the internet/OSM is unreachable
   the app shows the last saved copy, or the 26 DEMO entries below.
 - The 26 DEMO parking entries (only used offline). The places are real, but the spaces, prices and opening
   hours are MADE UP and coordinates are approximate. There are NO live sensors.
 - Community reports come from users, are labelled, and expire after 2 hours.
 - "Recommended" / "Best Match" use a simple visible score (distance, availability, price). Not AI.
 - Accounts are LOCAL to this computer (passwords are salted + hashed). Google sign-in only works if you
   add Streamlit's [auth] settings in .streamlit/secrets.toml; otherwise use email or guest.
 - Streamlit cannot read your phone/browser location, so "location" = type an area.
 - Optional: put a photo called hero.jpg next to this file to use it as the Home banner.
 - Built with help from AI tools.
"""
import base64
import datetime
import hashlib
import hmac
import html
import json
import math
import os
import re
import secrets
import time
import urllib.parse
import urllib.request

import streamlit as st

try:   # optional: real browser location (pip install streamlit-geolocation)
    from streamlit_geolocation import streamlit_geolocation
except Exception:
    streamlit_geolocation = None

st.set_page_config(page_title="ParkFinder UAE", page_icon="🅿️", layout="wide",
                   initial_sidebar_state="collapsed")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "user_data")
REPORT_LIFETIME = 2 * 3600          # community reports expire after 2 hours
HEADERS = {"User-Agent": "ParkFinderUAE-school-project/1.0"}
ss = st.session_state

# ===================================================== LANGUAGE: ENGLISH <-> ARABIC ====
# tr() turns the app's English text into Arabic when ss.lang == "ar". It only swaps exact UI phrases (a dictionary) and
# a few number patterns. Parking names are never machine-translated: Arabic names come from OpenStreetMap's name:ar tag.
AR = {
    # navigation and general
    "Home": "الرئيسية", "Search": "بحث", "Map": "الخريطة", "Saved": "المحفوظة", "Profile": "حسابي", "Salik": "سالك",
    "← Home": "← الرئيسية", "← Back": "← رجوع", "Go": "اذهب", "About": "عن التطبيق", "Nearby": "القريبة", "Explore": "استكشف",
    "Coverage": "التغطية", "Where we cover": "مناطق التغطية", "**Where we cover**": "**مناطق التغطية**",
    "Dubai": "دبي", "Sharjah": "الشارقة", "Ajman": "عجمان", "Whole UAE": "كل الإمارات", "Downtown Dubai": "وسط مدينة دبي",
    "Prototype": "نموذج أولي", "your location": "موقعك",
    # status, types, price
    "Available": "متاح", "Limited": "محدود", "Full": "ممتلئ", "Unknown": "غير معروف", "Almost Full": "شبه ممتلئ",
    "Usually available": "عادةً متاح", "Usually limited": "عادةً محدود", "Usually full": "عادةً ممتلئ", "Usually unknown": "عادةً غير معروف",
    "Garage": "مرآب", "Street": "شارع", "Open lot": "موقف مكشوف", "Free": "مجاني", "Paid": "مدفوع", "Any": "أي", "All": "الكل",
    "Paid (rate not listed)": "مدفوع (السعر غير مذكور)", "Not listed": "غير مذكور", "Opening hours not listed": "ساعات العمل غير مذكورة",
    "Limited (almost full)": "محدود (شبه ممتلئ)", "Free to use": "الاستخدام مجاني", "Fee not listed": "الرسوم غير مذكورة",
    # card labels and buttons
    "Distance": "المسافة", "Walk": "مشياً", "Price": "السعر", "Power": "القدرة", "Points": "نقاط الشحن",
    "Details": "التفاصيل", "Directions": "الاتجاهات", "♥ Saved": "♥ محفوظ", "♡ Save": "♡ حفظ", "Start Parking": "ابدأ الركن",
    "View details": "عرض التفاصيل", "Recommended for you": "موصى به لك", "Best parking": "أفضل موقف", "Open →": "افتح ←", "Try →": "جرّب ←",
    "See all": "عرض الكل", "Show 25 more": "عرض 25 أخرى", "Refresh now": "تحديث الآن", "Send": "إرسال", "Clear chat": "مسح المحادثة",
    "Source: ": "المصدر: ", "Demo data": "بيانات تجريبية", "Typical estimate (not live)": "تقدير معتاد (ليس مباشراً)",
    "Estimate from typical busyness at this day and time, not a live count": "تقدير من الازدحام المعتاد في هذا اليوم والوقت، وليس عدّاً مباشراً",
    "Reported by a driver in the last 2 hours": "أبلغ عنه سائق خلال آخر ساعتين",
    # home
    "PARKFINDER UAE": "باركفايندر الإمارات", "📍 PARKFINDER UAE": "📍 باركفايندر الإمارات",
    "Find parking near your destination": "ابحث عن موقف قرب وجهتك",
    "Street bays and garages across Dubai, Sharjah and Ajman.": "مواقف الشوارع والمرائب في دبي والشارقة وعجمان.",
    "Where do you want to park?": "أين تريد أن تركن؟", "Find Parking": "ابحث عن موقف",
    "Enable location": "تفعيل الموقع", "🎯 Enable location": "🎯 تفعيل الموقع",
    "Show every parking spot near you, including street parking": "اعرض كل المواقف القريبة منك، بما فيها مواقف الشوارع",
    "Smart Recommendation": "أفضل اقتراح", "Let us pick the best parking for you.": "دعنا نختار لك أفضل موقف.",
    "Nearby Parking": "مواقف قريبة", "Nearby parking": "المواقف القريبة",
    "Parking around you, with a free-parking filter and our best pick.": "مواقف حولك مع فلتر المواقف المجانية وأفضل اختيار.",
    "Parking Timer": "مؤقت الوقوف", "Keep track of how long you've been parked.": "تابع مدة وقوف سيارتك.",
    "EV Charging": "شحن السيارات الكهربائية", "Find electric-car charging stations near you.": "ابحث عن محطات شحن السيارات الكهربائية القريبة منك.",
    "Where did I park?": "أين ركنت سيارتي؟", "Save your parking spot and get walking directions back to your car.": "احفظ مكان سيارتك واحصل على اتجاهات المشي للعودة إليها.",
    "Cost Calculator": "حاسبة التكلفة", "Estimate your parking cost before you park.": "قدّر تكلفة الوقوف قبل أن تركن.",
    "Map view": "عرض الخريطة", "Pick a city, then tap a pin for details.": "اختر مدينة ثم اضغط على دبوس لعرض التفاصيل.",
    "Prototype · locations © OpenStreetMap contributors · no live availability sensors · built with help from AI tools":
        "نموذج أولي · المواقع © مساهمو OpenStreetMap · لا توجد حساسات توفّر مباشرة · بُني بمساعدة أدوات الذكاء الاصطناعي",
    "Prototype · demo data, not live availability · built with help from AI tools":
        "نموذج أولي · بيانات تجريبية وليست توفراً مباشراً · بُني بمساعدة أدوات الذكاء الاصطناعي",
    "Light / dark mode": "الوضع الفاتح / الداكن",
    # search, map, nearby
    "Search results": "نتائج البحث", "More filters": "المزيد من الفلاتر", "City": "المدينة", "Availability": "التوفر", "Within": "ضمن",
    "Rule-based pick from distance, availability and price. It is not AI.": "اختيار قائم على قواعد من المسافة والتوفر والسعر. وهو ليس ذكاءً اصطناعياً.",
    "No parking locations found.": "لم يتم العثور على مواقف.",
    "Try searching another area or city, or loosen the filters.": "جرّب البحث عن منطقة أو مدينة أخرى، أو خفّف الفلاتر.",
    "Turn off the free filter or set another area.": "أوقف فلتر المجاني أو اختر منطقة أخرى.",
    "Parking map": "خريطة المواقف", "Or choose one of the 40 closest spots": "أو اختر أحد أقرب 40 موقعاً", "Selected": "المحدد",
    "Tap a pin on the map, or choose a spot above.": "اضغط على دبوس في الخريطة أو اختر موقعاً من الأعلى.",
    "The map isn't available right now, so please use the list below.": "الخريطة غير متاحة الآن، يرجى استخدام القائمة أدناه.",
    "Nearby Parking ": "مواقف قريبة", "Use your location, filter for free parking, and see our best pick for you.": "استخدم موقعك، وفلتر المواقف المجانية، واطّلع على أفضل اختيار لك.",
    "Area": "المنطقة", "e.g. Dubai Marina, Deira, Mall of the Emirates": "مثال: دبي مارينا، ديرة، مول الإمارات", "Set location": "تحديد الموقع",
    "Reset to Downtown Dubai": "إعادة إلى وسط مدينة دبي", "Free parking only": "المواقف المجانية فقط",
    "Tap the button. Your browser will ask for permission, then we measure distances from where you are. Your position stays in this session only.":
        "اضغط على الزر. سيطلب المتصفح إذنك، ثم نقيس المسافات من مكانك. يبقى موقعك في هذه الجلسة فقط.",
    "Waiting for permission... If nothing happens, allow location for this site in your browser, or type an area below.":
        "بانتظار الإذن... إن لم يحدث شيء، اسمح بالموقع لهذا الموقع في المتصفح أو اكتب منطقة أدناه.",
    "Location button not installed (pip install streamlit-geolocation). Type an area below instead.": "زر الموقع غير مثبّت. اكتب منطقة أدناه بدلاً منه.",
    "Please type an area, landmark or city.": "يرجى كتابة منطقة أو معلم أو مدينة.",
    "We couldn't find that place in the UAE. Try another area or landmark.": "لم نجد هذا المكان في الإمارات. جرّب منطقة أو معلماً آخر.",
    "Saved Parking": "المواقف المحفوظة", "Your saved parking locations.": "مواقفك المحفوظة.", "Nothing saved yet": "لا شيء محفوظ بعد",
    "Save parking locations so you can quickly find them again.": "احفظ المواقف لتجدها بسرعة لاحقاً.",
    "Removed from saved parking": "تمت الإزالة من المحفوظات", "Parking spot saved": "تم حفظ مكان السيارة",
    # profile / about
    "Your account": "حسابك", "Review the details linked to your ParkFinder account.": "راجع البيانات المرتبطة بحسابك في ParkFinder.",
    "Guest mode: nothing is linked to an email.": "وضع الضيف: لا شيء مرتبط ببريد إلكتروني.", "Dark mode": "الوضع الداكن",
    "Your theme is remembered while the app is open.": "يُحفظ المظهر طالما التطبيق مفتوح.", "Guest mode": "وضع الضيف",
    "Saved spots stay on this computer. Log out to create an account.": "تبقى المواقف المحفوظة في هذه الجلسة. سجّل الخروج لإنشاء حساب.",
    "Delete account": "حذف الحساب", "I understand this cannot be undone": "أفهم أنه لا يمكن التراجع", "Delete my account": "احذف حسابي", "Log out": "تسجيل الخروج",
    "Your account was deleted.": "تم حذف حسابك.",
    "Parking in the UAE, without the circling": "الوقوف في الإمارات، بلا دوران",
    "Search or tap a pin": "ابحث أو اضغط على دبوس", "Look up an area, a landmark or a city and see what is free right now.": "ابحث عن منطقة أو معلم أو مدينة وشاهد ما هو متاح.",
    "Compare at a glance": "قارن بنظرة واحدة", "Distance, walking time and hourly price sit side by side on every card.": "المسافة ووقت المشي وسعر الساعة معاً على كل بطاقة.",
    "Drive straight there": "اذهب مباشرة", "Open directions in one tap, or save the spot to your favourites for later.": "افتح الاتجاهات بضغطة واحدة أو احفظ الموقع في المفضلة.",
    "Browse parking": "تصفّح المواقف",
    # car, ev
    "Save your spot when you leave the car, then get walking directions back to it later.": "احفظ مكانك عند ترك السيارة، ثم احصل لاحقاً على اتجاهات المشي للعودة إليها.",
    "1. Save my parking spot": "١. احفظ مكان سيارتي", "2. Find my car": "٢. اعثر على سيارتي",
    "Save my parking spot here": "احفظ مكان سيارتي هنا", "Walking directions to my car": "اتجاهات المشي إلى سيارتي", "Clear saved spot": "مسح المكان المحفوظ",
    "No parking spot saved yet.": "لا يوجد مكان محفوظ بعد.", "Waiting for permission... allow location for this site in your browser.": "بانتظار الإذن... اسمح بالموقع لهذا الموقع في المتصفح.",
    "Find electric-car charging stations across Dubai, Sharjah and Ajman.": "ابحث عن محطات شحن السيارات الكهربائية في دبي والشارقة وعجمان.",
    "Plug type": "نوع القابس", "Plug types not listed": "أنواع القوابس غير مذكورة", "Refreshing charging stations...": "جارٍ تحديث محطات الشحن...",
    "Source: OpenStreetMap volunteers. Live free/busy status is not available.": "المصدر: متطوعو OpenStreetMap. حالة الشغل المباشرة غير متوفرة.",
    "Technical detail: ": "تفاصيل تقنية: ", "Opening hours not listed ": "ساعات العمل غير مذكورة",
    "Tip: charging station details are added by volunteers, so plug type and power may be missing. Check the operator's app before you go.":
        "تلميح: يضيف المتطوعون تفاصيل المحطات، لذا قد ينقص نوع القابس أو القدرة. تحقق من تطبيق المشغّل قبل الذهاب.",
    "Refreshing parking locations...": "جارٍ تحديث المواقف...",
    # timer, calculator, details
    "Start the timer yourself when you park. It uses real timestamps, so it stays accurate.": "ابدأ المؤقت بنفسك عند الركن. يعتمد على أوقات حقيقية فيبقى دقيقاً.",
    "**Parking:** ": "**الموقف:** ", "none selected (manual timer)": "لم يُحدد (مؤقت يدوي)", "Rate in AED per hour (optional)": "السعر بالدرهم للساعة (اختياري)",
    "START": "ابدأ", "PAUSE": "إيقاف مؤقت", "RESUME": "استئناف", "STOP": "إنهاء", "RESET": "إعادة ضبط",
    "Parking Session Complete": "انتهت جلسة الوقوف", "Manual timer": "مؤقت يدوي", "**Duration:** ": "**المدة:** ",
    "Add a rate next time to see an estimated cost.": "أضف سعراً في المرة القادمة لعرض التكلفة التقديرية.",
    "Press START when you park.": "اضغط ابدأ عند الركن.", "Parked for ": "مدة الوقوف: ",
    "An estimate only. It does not know the official parking fee.": "تقدير فقط. لا يعرف الرسوم الرسمية للموقف.",
    "Parking rate (AED per hour)": "سعر الموقف (درهم للساعة)", "Duration: hours": "المدة: ساعات", "Duration: minutes": "المدة: دقائق",
    "Free period in minutes (optional)": "فترة مجانية بالدقائق (اختياري)", "Use a maximum daily charge": "استخدم حداً أقصى يومياً",
    "Maximum daily charge (AED)": "الحد الأقصى اليومي (درهم)", "Enter a parking duration to see the estimate.": "أدخل مدة الوقوف لعرض التقدير.",
    "This is an estimate. The official parking fee may be different.": "هذا تقدير. قد تختلف الرسوم الرسمية.",
    "Mon": "الاثنين", "Tue": "الثلاثاء", "Wed": "الأربعاء", "Thu": "الخميس", "Fri": "الجمعة", "Sat": "السبت", "Sun": "الأحد",
    "Parking type": "نوع الموقف", "Walking time": "وقت المشي", "Opening hours": "ساعات العمل", "Spaces": "الأماكن", "Location data": "بيانات الموقع",
    "Demo data (approximate coordinates)": "بيانات تجريبية (إحداثيات تقريبية)", "OpenStreetMap contributors (real mapped location)": "مساهمو OpenStreetMap (موقع حقيقي مرسوم)",
    "Get Directions": "احصل على الاتجاهات", "Remove Saved": "إزالة من المحفوظات", "Save Parking": "احفظ الموقف", "Calculate Cost": "احسب التكلفة",
    "Report current availability": "أبلغ عن التوفر الحالي", "What is it like right now?": "كيف الوضع الآن؟", "Is there a free space right now?": "هل يوجد مكان شاغر الآن؟",
    "Submit report": "إرسال البلاغ", "Thanks! Saved as a community report.": "شكراً! تم حفظه كبلاغ من المجتمع.",
    # login
    "Welcome back": "مرحباً بعودتك", "Log in to your account": "سجّل الدخول إلى حسابك", "Create your account": "أنشئ حسابك", "Sign up to get started": "سجّل للبدء",
    "Reset password": "إعادة تعيين كلمة المرور", "We'll send you a link to reset it": "سنرسل لك رابطاً لإعادة تعيينها", "Email": "البريد الإلكتروني",
    "you@example.com": "you@example.com", "Password": "كلمة المرور", "Log in": "تسجيل الدخول", "Email or password is incorrect.": "البريد أو كلمة المرور غير صحيحة.",
    "Forgot password?": "نسيت كلمة المرور؟", "Name": "الاسم", "Your name": "اسمك", "At least 8 characters": "8 أحرف على الأقل", "Confirm Password": "تأكيد كلمة المرور",
    "Type it again": "اكتبها مرة أخرى", "Create account": "إنشاء حساب", "The two passwords don't match.": "كلمتا المرور غير متطابقتين.",
    "Email address": "البريد الإلكتروني", "Send reset link": "إرسال رابط الاستعادة",
    "Don't have an account? Create one": "ليس لديك حساب؟ أنشئ حساباً", "← Back to log in": "← العودة لتسجيل الدخول", "Continue as guest": "المتابعة كضيف",
    "Please enter a valid email address.": "يرجى إدخال بريد إلكتروني صحيح.", "Your password needs at least 8 characters.": "كلمة المرور تحتاج 8 أحرف على الأقل.",
    "An account with this email already exists. Try logging in.": "يوجد حساب بهذا البريد. جرّب تسجيل الدخول.",
    "Accounts are stored only on this computer (prototype). Passwords are salted and hashed, never saved as typed.":
        "تُحفظ الحسابات على الخادم فقط (نموذج أولي). كلمات المرور مشفّرة ولا تُحفظ كما كُتبت.",
    # Parky
    "💬 Ask Parky": "💬 اسأل باركي", "**Parky, your parking helper**": "**باركي، مساعدك للمواقف**", "A simple keyword bot, not AI.": "بوت بسيط بالكلمات المفتاحية، وليس ذكاءً اصطناعياً.",
    "Ask me something, or tap a question:": "اسألني شيئاً أو اختر سؤالاً:", "Your question": "سؤالك", "e.g. nearest free parking": "مثال: أقرب موقف مجاني",
    "Nearest parking": "أقرب موقف", "EV charging near me": "شحن كهربائي قريب مني", "Free parking near me": "موقف مجاني قريب مني",
    "Cost for 3 hours at AED 5": "تكلفة 3 ساعات بسعر 5 دراهم", "What is Salik?": "ما هو سالك؟",
    # data status
    "Refreshing...": "جارٍ التحديث...",
}
AR_SENTENCES = {
    "Hi! I'm Parky, your parking helper. I'm a simple keyword bot, not AI, and I only use this app's own data. Try: **nearest parking**, **free parking**, **garage**, **street parking**, **cost for 3 hours at AED 5**, **where did I park**, **timer**, **Salik**, or **how accurate is availability**.":
        "أهلاً! أنا باركي، مساعدك للمواقف. أنا بوت بسيط بالكلمات المفتاحية وليس ذكاءً اصطناعياً، وأستخدم بيانات التطبيق فقط. جرّب: **أقرب موقف**، **موقف مجاني**، **مرآب**، **موقف شارع**، **تكلفة 3 ساعات بسعر 5 دراهم**، **أين ركنت**، **المؤقت**، **سالك**، أو **مدى دقة التوفر**.",
    "I couldn't load charging stations right now (OpenStreetMap may be busy). Open **EV Charging** on the home page and tap Refresh.":
        "تعذّر تحميل محطات الشحن الآن (قد يكون OpenStreetMap مشغولاً). افتح **شحن السيارات الكهربائية** من الصفحة الرئيسية واضغط تحديث.",
    "The closest EV charging stations to %s:\n%s\n\nOpen **EV Charging** for plug types, a map and directions. I can't tell if a charger is free right now.":
        "أقرب محطات الشحن الكهربائي إلى %s:\n%s\n\nافتح **شحن السيارات الكهربائية** لأنواع القوابس والخريطة والاتجاهات. لا أستطيع معرفة إن كان الشاحن متاحاً الآن.",
    "At AED %s per hour for %s, the estimated cost is **AED %.2f** (rate x time; the official fee may differ).":
        "بسعر %s درهم للساعة لمدة %s، التكلفة التقديرية **%.2f درهم** (السعر × الوقت؛ قد تختلف الرسوم الرسمية).",
    "Tell me the time and the rate, for example: **cost for 3 hours at AED 5**. You can also use the Cost Calculator on the home page.":
        "أخبرني بالمدة والسعر، مثلاً: **تكلفة 3 ساعات بسعر 5 دراهم**. يمكنك أيضاً استخدام حاسبة التكلفة في الصفحة الرئيسية.",
    "The closest free parking places to %s:\n%s": "أقرب المواقف المجانية إلى %s:\n%s",
    "I couldn't find a parking place marked free in the current list.": "لم أجد موقفاً مصنفاً مجانياً في القائمة الحالية.",
    "Closest %s parking to %s:\n%s": "أقرب موقف (%s) إلى %s:\n%s", "No %s parking in the current list.": "لا يوجد موقف (%s) في القائمة الحالية.",
    "The closest parking places to %s:\n%s\n\nOpen **Nearby** to change the starting point or use your location.":
        "أقرب المواقف إلى %s:\n%s\n\nافتح **القريبة** لتغيير نقطة البداية أو لاستخدام موقعك.",
    "No prices are listed in the data.": "لا توجد أسعار مذكورة في البيانات.", "The cheapest places with a known price:\n%s": "أرخص المواقف ذات السعر المعروف:\n%s",
    "Your car spot is saved. [Walking directions to my car](https://www.google.com/maps/dir/?api=1&destination=%s,%s&travelmode=walking)":
        "تم حفظ مكان سيارتك. [اتجاهات المشي إلى سيارتي](https://www.google.com/maps/dir/?api=1&destination=%s,%s&travelmode=walking)",
    "Open **Where did I park?** on the home page, allow location, then tap *Save my parking spot here*. Later you can get walking directions back.":
        "افتح **أين ركنت سيارتي؟** من الصفحة الرئيسية، واسمح بالموقع، ثم اضغط *احفظ مكان سيارتي هنا*. لاحقاً يمكنك الحصول على اتجاهات المشي للعودة.",
    "Open the **Parking Timer** from the home page. Press START when you park. It uses real timestamps and can estimate the cost if you enter a rate.":
        "افتح **مؤقت الوقوف** من الصفحة الرئيسية. اضغط ابدأ عند الركن. يعتمد على أوقات حقيقية ويقدّر التكلفة إن أدخلت السعر.",
    "Salik is Dubai's road toll system. The **Salik** button at the bottom opens the official site, or the Smart Salik app page on your phone.":
        "سالك هو نظام رسوم الطرق في دبي. يفتح زر **سالك** في الأسفل الموقع الرسمي، أو صفحة تطبيق Smart Salik على هاتفك.",
    "Tap **Directions** on any parking card. It opens Google Maps with that parking place as the destination.":
        "اضغط **الاتجاهات** على أي بطاقة موقف. يفتح خرائط جوجل مع وجهة الموقف.",
    "Availability here is a **typical-busyness estimate** for this weekday and time, not a live count. If at least 3 drivers report the same weekday and hour, the driver average is used instead. Always check on arrival.":
        "التوفر هنا **تقدير للازدحام المعتاد** لهذا اليوم والوقت، وليس عدّاً مباشراً. إذا أبلغ 3 سائقين على الأقل عن نفس اليوم والساعة يُستخدم متوسطهم. تحقق دائماً عند الوصول.",
    "Parking places come from OpenStreetMap and refresh every 30 minutes. If its free server is busy you'll see a yellow note; tap **Refresh now**.":
        "تأتي المواقف من OpenStreetMap وتتحدث كل 30 دقيقة. إذا كان خادمه المجاني مشغولاً ستظهر ملاحظة صفراء؛ اضغط **تحديث الآن**.",
    "On **Nearby** or **Where did I park?**, tap the location button. Your browser asks for permission; your position stays in your session only.":
        "في **القريبة** أو **أين ركنت سيارتي؟** اضغط زر الموقع. سيطلب المتصفح الإذن، ويبقى موقعك في جلستك فقط.",
    "Tap the heart (**Save**) on a parking card. Open the **Saved** tab to see them. Sign in to keep them between visits.":
        "اضغط القلب (**حفظ**) على بطاقة الموقف. افتح تبويب **المحفوظة** لرؤيتها. سجّل الدخول لتبقى بين الزيارات.",
    "ParkFinder UAE is a school project. I'm Parky, a rule-based helper that answers from the app's own data; I'm not an AI model.":
        "ParkFinder UAE مشروع مدرسي. أنا باركي، مساعد قائم على قواعد يجيب من بيانات التطبيق نفسها، ولست نموذج ذكاء اصطناعي.",
    "Sorry, Parky didn't understand that. Try: **nearest parking**, **free parking**, **cost for 3 hours at AED 5**, **where did I park**, or **Salik**.":
        "عذراً، لم يفهم باركي ذلك. جرّب: **أقرب موقف**، **موقف مجاني**، **تكلفة 3 ساعات بسعر 5 دراهم**، **أين ركنت**، أو **سالك**.",
    "- **%s** (%s): %.1f km, %s walk, %s": "- **%s** (%s): %.1f كم، مشياً %s، %s",
    "OpenStreetMap is busy right now, so this is the last saved list from %s.": "OpenStreetMap مشغول الآن، لذا هذه آخر قائمة محفوظة من %s.",
    "OpenStreetMap's free server is busy right now, so no charging stations can be shown yet. Wait a minute and tap Refresh now.":
        "خادم OpenStreetMap المجاني مشغول الآن، لذا لا يمكن عرض محطات الشحن بعد. انتظر دقيقة واضغط تحديث الآن.",
}
# number / sentence patterns whose text changes at run time (checked in order)
AR_RULES = [(re.compile(p), r) for p, r in [
    (r"Distances are measured from (.+?) \(straight-line estimates\)\. Change it on the Nearby page\.", r"تُقاس المسافات من \1 (تقديرات بخط مستقيم). غيّرها من صفحة القريبة."),
    (r"Distances are now measured from (.+?)\.$", r"تُقاس المسافات الآن من \1."),
    (r"Using your device location \(accuracy about (\d+) m\)\.", r"نستخدم موقع جهازك (الدقة نحو \1 م)."),
    (r"Location found \(accuracy about (\d+) m\)\.", r"تم العثور على الموقع (الدقة نحو \1 م)."),
    (r"\*\*(\d+) parking locations? found\*\*", r"**تم العثور على \1 موقف**"),
    (r"Showing the closest (\d+) of (\d+)\.", r"عرض أقرب \1 من \2."),
    (r"Showing the 12 closest\. Use Search to see all (\d+)\.", r"عرض أقرب 12. استخدم البحث لرؤية كل \1."),
    (r"All ([\d,]+) parking places mapped in OpenStreetMap", r"\1 موقفاً مرسوماً في OpenStreetMap"),
    (r"([\d,]+) parking places mapped in OpenStreetMap \(not every real space\)", r"\1 موقفاً مرسوماً في OpenStreetMap (وليس كل الأماكن الفعلية)"),
    (r"All ([\d,]+) mapped parking places across the UAE\. Pick a city to zoom in, then tap a pin for details\.", r"\1 موقفاً مرسوماً في الإمارات. اختر مدينة للتقريب ثم اضغط على دبوس لعرض التفاصيل."),
    (r"([\d,]+) demo parking places\. Pick a city to zoom in, then tap a pin for details\.", r"\1 موقفاً تجريبياً. اختر مدينة للتقريب ثم اضغط على دبوس لعرض التفاصيل."),
    (r"([\d,]+) demo parking places", r"\1 موقفاً تجريبياً"),
    (r"([\d,]+) parking places mapped$", r"\1 موقفاً مرسوماً"),
    (r"Total: ([\d,]+) parking places · ([\d,]+) with a mapped capacity · ([\d,]+) marked free", r"المجموع: \1 موقف · \2 بسعة مرسومة · \3 مجاني"),
    (r"Recommended: (.+)", r"موصى به: \1"),
    (r"Saved: (.+)", r"تم الحفظ: \1"),
    (r"\*\*Saved:\*\* (.+?) \((.+?) ago\)", r"**تم الحفظ:** \1 (قبل \2)"),
    (r"\*\*Distance from you now:\*\* (.+?) \((.+?)\)", r"**المسافة منك الآن:** \1 (\2)"),
    (r"Show more \((\d+) left\)", r"عرض المزيد (بقي \1)"),
    (r"Usually about (\d+)% full now", r"عادةً ممتلئ بنسبة \1% الآن"),
    (r"About (\d+)% full now", r"ممتلئ بنسبة \1% الآن تقريباً"),
    (r"(\d+) / (\d+) spaces", r"\1 / \2 مكان"),
    (r"(\d+) free of (\d+) \(([\d.]+)% occupied\)", r"\1 شاغر من \2 (\3% مشغول)"),
    (r" · mapped capacity (\d+)", r" · السعة المرسومة \1"),
    (r"([\d.]+) km from (.+)", r"\1 كم من \2"),
    (r"An estimate based on AED ([\d.]+)/hour\. The official fee may be different\.", r"تقدير مبني على \1 درهم/ساعة. قد تختلف الرسوم الرسمية."),
    (r"Estimated cost: AED ([\d.]+)", r"التكلفة التقديرية: \1 درهم"),
    (r"\*\*Parking rate:\*\* AED ([\d.]+)/hour", r"**سعر الموقف:** \1 درهم/ساعة"),
    (r"\*\*Free period:\*\* (\d+) minutes", r"**الفترة المجانية:** \1 دقيقة"),
    (r"\*\*Calculation:\*\* (.+)", r"**الحساب:** \1"),
    (r"Daily maximum of AED ([\d.]+) applied\.", r"تم تطبيق الحد الأقصى اليومي \1 درهم."),
    (r"(\d+) charging stations from OpenStreetMap · updated (.+?) \(UAE time\) · refreshes every 30 minutes\.", r"\1 محطة شحن من OpenStreetMap · آخر تحديث \2 (بتوقيت الإمارات) · يتحدث كل 30 دقيقة."),
    (r"(\d+) parking places from OpenStreetMap · updated (.+?) \(UAE time\) · refreshes every 30 minutes · availability is a typical-pattern estimate unless drivers report\.",
     r"\1 موقفاً من OpenStreetMap · آخر تحديث \2 (بتوقيت الإمارات) · يتحدث كل 30 دقيقة · التوفر تقدير للنمط المعتاد ما لم يبلّغ السائقون."),
    (r"Couldn't reach OpenStreetMap, so this is the last saved copy from (.+?)\. \(.*\)", r"تعذّر الوصول إلى OpenStreetMap، لذا هذه آخر نسخة محفوظة من \1."),
    (r"OpenStreetMap is busy right now, so this is the last saved copy from (.+?)\. Tap Refresh now in a minute\.", r"OpenStreetMap مشغول الآن، لذا هذه آخر نسخة محفوظة من \1. اضغط تحديث الآن بعد دقيقة."),
    (r"OpenStreetMap's free server is busy right now, so only the 26 demo places are shown for the moment\. Wait a minute and tap Refresh now\.",
     r"خادم OpenStreetMap المجاني مشغول الآن، لذا تُعرض 26 موقعاً تجريبياً فقط حالياً. انتظر دقيقة واضغط تحديث الآن."),
    (r"Technical detail: (.+)", r"تفاصيل تقنية: \1"),
    (r"No charging station with (.+?) plugs is listed\. Many stations don't list their plug type, so try 'Any'\.", r"لا توجد محطة بقوابس \1 مذكورة. كثير من المحطات لا تذكر نوع القابس، جرّب «أي»."),
    (r"Your location is (\d+) km from the nearest demo parking, so these distances are not useful\. Type a UAE area below instead\.",
     r"موقعك يبعد \1 كم عن أقرب موقف تجريبي، فلا فائدة من هذه المسافات. اكتب منطقة في الإمارات أدناه."),
    (r"A timer is already running\. Stop or reset it first\.", r"المؤقت يعمل بالفعل. أوقفه أو أعد ضبطه أولاً."),
    (r"The rate was not a valid number, so no rate will be used\.", r"السعر ليس رقماً صالحاً، لذا لن يُستخدم سعر."),
    (r"Your spot is stored for you only \(guests: for this visit only; sign in to keep it\)\. Directions open in Google Maps, which uses your phone's location\.",
     r"مكانك محفوظ لك وحدك (للضيوف: لهذه الزيارة فقط؛ سجّل الدخول للاحتفاظ به). تُفتح الاتجاهات في خرائط جوجل التي تستخدم موقع هاتفك."),
    (r"This school prototype can't send emails, so no link was sent\. You can create a new account instead\.", r"هذا نموذج مدرسي لا يرسل بريداً، فلم يُرسل رابط. يمكنك إنشاء حساب جديد."),
    (r"Google sign-in isn't switched on.*", r"تسجيل الدخول عبر جوجل غير مفعّل."),
    (r"(\d[\d,]*(?:\.\d+)?) km\b", r"\1 كم"),
    (r"(\d+)h (\d+)m\b", r"\1 س \2 د"),
    (r"(\d+) min\b", r"\1 دقيقة"),
    (r"AED ([\d.]+)/hr", r"\1 درهم/ساعة"),
    (r"AED ([\d.]+)\b", r"\1 درهم"),
    (r"(\d+) hours? (\d+) minutes?", r"\1 ساعة \2 دقيقة"),
    (r"(\d+) hours?\b", r"\1 ساعة"),
    (r"(\d+) minutes?\b", r"\1 دقيقة"),
    (r"^Garage parking near (.+)$", r"موقف مرآب قرب \1"), (r"^Street parking on (.+)$", r"موقف شارع في \1"),
    (r"^Parking lot near (.+)$", r"موقف سيارات قرب \1"), (r"^Garage parking in (.+)$", r"موقف مرآب في \1"),
    (r"^Street parking in (.+)$", r"موقف شارع في \1"), (r"^Parking lot in (.+)$", r"موقف سيارات في \1"),
    (r"^Parking lot in (.+)$", r"موقف سيارات في \1"), (r"^EV charger in (.+)$", r"شاحن كهربائي في \1"), (r"^(.+) charger$", r"شاحن \1"),
    (r"^(.+) parking$", r"موقف \1"),
    (r"^(.+) · (Dubai|Sharjah|Ajman)$", lambda m: m.group(1) + " · " + AR[m.group(2)]),
]]

AR.update({
    "Pick a city to zoom in, then tap a pin for details.": "اختر مدينة للتقريب ثم اضغط على دبوس لعرض التفاصيل.",
    "Pick a city, then tap a pin for details.": "اختر مدينة ثم اضغط على دبوس لعرض التفاصيل.",
    "Source: Demo data": "المصدر: بيانات تجريبية", "Source: OpenStreetMap": "المصدر: OpenStreetMap", "Source: Community report": "المصدر: بلاغ من المجتمع",
    "Keep track of how long you've been parked.": "تابع مدة وقوف سيارتك.",
    "Street and garage parking across Dubai, Sharjah and Ajman.": "مواقف الشوارع والمرائب في دبي والشارقة وعجمان.",
    "How we choose": "كيف نختار", "Free street bays and paid garages, side by side": "مواقف الشوارع المجانية والمرائب المدفوعة جنباً إلى جنب",
    "Typical busyness this week": "الازدحام المعتاد هذا الأسبوع",
    "Location button not installed (pip install streamlit-geolocation).": "زر الموقع غير مثبّت.",
    "Source: OpenStreetMap volunteers. Live free/busy status is not available.": "المصدر: متطوعو OpenStreetMap. حالة الشغل المباشرة غير متوفرة.",
})
AR_SENTENCES.update({
    "ParkFinder UAE brings street bays and paid garages across Dubai, Sharjah and Ajman into one simple view, so you can see what is available, what it costs and how far you will walk before you set off.":
        "يجمع ParkFinder UAE مواقف الشوارع والمرائب المدفوعة في دبي والشارقة وعجمان في عرض واحد بسيط، لتعرف المتاح وتكلفته ومسافة المشي قبل أن تنطلق.",
    "Every listing shows whether it is free or paid, a street bay or a garage, its opening hours and how many spaces are free. Locations come from OpenStreetMap and refresh every 30 minutes. Live free-space counts are not published for them, so availability shows a typical estimate for the day and time (marked \"Usually...\"), replaced by driver reports when they exist, and the top suggestion is a simple visible score of distance, availability and price.":
        "تعرض كل بطاقة إن كان الموقف مجانياً أو مدفوعاً، شارعاً أو مرآباً، وساعات عمله وعدد الأماكن الشاغرة. تأتي المواقع من OpenStreetMap وتتحدث كل 30 دقيقة. لا تتوفر أعداد مباشرة للأماكن الشاغرة، لذا يعرض التوفر تقديراً معتاداً لليوم والوقت (مكتوب «عادةً...») ويُستبدل ببلاغات السائقين عند وجودها، والاقتراح الأول نتيجة بسيطة ومعلنة من المسافة والتوفر والسعر.",
    "Stand next to your car and tap the location button. Your browser will ask for permission. Then tap Save.":
        "قف بجانب سيارتك واضغط زر الموقع. سيطلب المتصفح الإذن. ثم اضغط حفظ.",
    "How full this kind of place usually is (percent of spaces taken). It is an ESTIMATE from a simple daily pattern, not a live count. When 3+ drivers report for the same weekday and hour, their average is used instead.":
        "مدى امتلاء هذا النوع من المواقف عادةً (نسبة الأماكن المشغولة). هو تقدير من نمط يومي بسيط وليس عدّاً مباشراً. عندما يبلّغ 3 سائقين أو أكثر عن نفس اليوم والساعة يُستخدم متوسطهم.",
    "Community reports come from users like you. They are labelled and expire after 2 hours.":
        "تأتي بلاغات المجتمع من مستخدمين مثلك. وهي معلّمة وتنتهي بعد ساعتين.",
})
AR_RULES += [(re.compile(p), r) for p, r in [
    (r"It is (very close|close|within reach|[\d.]+ km away), (.+?), and (.+)\.$", lambda m: "هو %s، %s، و%s." % (
        {"very close": "قريب جداً", "close": "قريب", "within reach": "في المتناول"}.get(m.group(1), m.group(1).replace(" km away", " كم")),
        _tr_text(m.group(2)), _tr_text(m.group(3)))),
    (r"has (\d+) available spaces", r"فيه \1 مكاناً شاغراً"), (r"has (\d+) spaces left", r"بقي فيه \1 مكاناً"),
    (r"is usually (available|fairly busy|full|unknown) at this time", lambda m: "عادةً " + {"available": "متاح", "fairly busy": "مزدحم نوعاً ما", "full": "ممتلئ", "unknown": "غير معروف"}[m.group(1)] + " في هذا الوقت"),
    (r"^is free$", "مجاني"), (r"has a price that is not listed", "سعره غير مذكور"), (r"costs (.+)", r"سعره \1"),
]]
_AR_LONG = re.compile("|".join(re.escape(k) for k in sorted(AR_SENTENCES, key=len, reverse=True)))


def _tr_text(p):
    if "&#x27;" in p:
        p = p.replace("&#x27;", "'")
    if p in AR:
        return AR[p]
    core = p.strip()
    if not core:
        return p
    lead, tail = p[:len(p) - len(p.lstrip())], p[len(p.rstrip()):]
    if core in AR:
        return lead + AR[core] + tail
    if core in AR_SENTENCES:
        return lead + AR_SENTENCES[core] + tail
    for pattern, rep in AR_RULES:
        if pattern.search(core):
            core = pattern.sub(rep, core)
    return lead + _AR_LONG.sub(lambda m: AR_SENTENCES[m.group(0)], core) + tail


def tr(s):
    """English text -> Arabic when the language switch is on. Other values pass through unchanged."""
    if not isinstance(s, str) or ss.get("lang") != "ar" or "<style" in s:
        return s
    if "<" in s and ">" in s:
        return "".join(x if (x.startswith("<") and x.endswith(">")) else _tr_text(x) for x in re.split(r"(<[^>]*>)", s))
    return _tr_text(s)


def pname(p):
    """Parking / charger name for display: the real Arabic name from OpenStreetMap when the language is Arabic."""
    return (p.get("name_ar") if ss.get("lang") == "ar" and p.get("name_ar") else p["name"])


def cb_lang():
    ss.lang = "en" if ss.get("lang") == "ar" else "ar"


# every st.* call that shows text goes through tr() so the whole app switches language in one place
def _wrap_widget(fn, with_options=False):
    def w(*a, **k):
        a = list(a)
        if a and isinstance(a[0], str):
            a[0] = tr(a[0])
        for key in ("label", "placeholder", "help", "body", "value"):
            if isinstance(k.get(key), str) and key != "value":
                k[key] = tr(k[key])
        if with_options and "format_func" not in k and ss.get("lang") == "ar":
            k["format_func"] = lambda o: tr(o) if isinstance(o, str) else o
        return fn(*a, **k)
    return w
for _n in ("markdown", "write", "caption", "title", "header", "subheader", "info", "warning", "error", "success", "toast",
           "button", "link_button", "text_input", "number_input", "checkbox", "toggle", "popover", "expander", "chat_input",
           "text_area", "spinner"):
    if hasattr(st, _n):
        setattr(st, _n, _wrap_widget(getattr(st, _n)))
for _n in ("selectbox", "radio", "multiselect", "segmented_control", "pills"):
    if hasattr(st, _n):
        setattr(st, _n, _wrap_widget(getattr(st, _n), True))

AR_KEYWORDS = {"اقرب": " nearest ", "أقرب": " nearest ", "مجاني": " free ", "مجانا": " free ", "مرآب": " garage ", "مرأب": " garage ",
               "شارع": " street ", "شحن": " charging ", "كهربائي": " electric ", "سالك": " salik ", "مؤقت": " timer ",
               "اين ركنت": " where did i park ", "أين ركنت": " where did i park ", "تكلفة": " cost ", "سعر": " rate aed ",
               "درهم": " aed ", "ساعات": " hours ", "ساعة": " hours ", "دقيقة": " minutes ", "مرحبا": " hello ", "اهلا": " hello ",
               "مساعدة": " help ", "دقة": " accurate ", "اتجاهات": " directions "}
def ar_to_en_keywords(text):
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    extra = "".join(v for k, v in AR_KEYWORDS.items() if k in text)
    return text + extra if extra else text

# ============================================================== 1. DEMO DATA ====
KEYS = ["id", "name", "city", "area", "type", "price", "total", "occupied", "hours", "lat", "lon"]
RAW = [  # price: 0 = free, None = not listed.  total/occupied: None = unknown.  ALL numbers are DEMO values.
    ("D1", "Dubai Mall Parking", "Dubai", "Downtown Dubai", "Garage", 20, 5000, 5000, "24/7", 25.1972, 55.2797),
    ("D2", "Al Wasl Road Street Parking", "Dubai", "Jumeirah 1", "Street", 4, 40, 23, "8:00 AM – 10:00 PM", 25.2085, 55.2600),
    ("D3", "Business Bay Parking", "Dubai", "Business Bay", "Garage", 8, 400, 174, "24/7", 25.1860, 55.2620),
    ("D4", "Sheikh Zayed Road Street Bays", "Dubai", "Trade Centre", "Street", 6, 25, 12, "7:00 AM – 11:00 PM", 25.2230, 55.2830),
    ("D5", "DIFC Gate Parking", "Dubai", "DIFC", "Garage", 25, 900, 487, "24/7", 25.2132, 55.2796),
    ("D6", "City Walk Parking", "Dubai", "Al Wasl", "Garage", 0, 1300, 1300, "10:00 AM – 10:00 PM", 25.2074, 55.2630),
    ("D7", "Jumeirah Beach Road Bays", "Dubai", "Jumeirah", "Street", 0, 30, 25, "24/7", 25.2300, 55.2450),
    ("D8", "Marina Walk Parking", "Dubai", "Dubai Marina", "Garage", 15, 600, 599, "6:00 AM – 12:00 AM", 25.0805, 55.1403),
    ("D9", "JBR Beach Parking", "Dubai", "Jumeirah Beach Residence", "Garage", 0, 180, 180, "24/7", 25.0780, 55.1337),
    ("D10", "Mall of the Emirates", "Dubai", "Al Barsha", "Garage", 10, 7000, 7000, "24/7", 25.1181, 55.2007),
    ("D11", "Karama Public Parking", "Dubai", "Al Karama", "Garage", 0, 150, 150, "6:00 AM – 10:00 PM", 25.2430, 55.3040),
    ("D12", "Al Fahidi Street Parking", "Dubai", "Bur Dubai", "Street", 0, 35, 22, "24/7", 25.2637, 55.2974),
    ("D13", "Deira Corniche Street Bays", "Dubai", "Deira", "Street", 3, 60, 60, "7:00 AM – 11:00 PM", 25.2700, 55.3170),
    ("S1", "Al Majaz Waterfront Parking", "Sharjah", "Al Majaz", "Open lot", 3, 400, 150, "24/7", 25.3263, 55.3836),
    ("S2", "Sahara Centre Parking", "Sharjah", "Al Nahda", "Garage", 0, 1800, 1500, "10:00 AM – 12:00 AM", 25.2989, 55.3744),
    ("S3", "Sharjah Corniche Street Parking", "Sharjah", "Corniche", "Street", 2, 150, 120, "24/7", 25.3573, 55.3827),
    ("S4", "Heart of Sharjah Garage", "Sharjah", "Old Souq", "Garage", 4, 200, 200, "8:00 AM – 10:00 PM", 25.3569, 55.3860),
    ("S5", "University City Parking", "Sharjah", "University City", "Open lot", 2, 600, 210, "24/7", 25.2894, 55.4627),
    ("S6", "Al Qasba Parking", "Sharjah", "Al Qasba", "Open lot", 3, 300, 280, "4:00 PM – 12:00 AM", 25.3230, 55.3850),
    ("S7", "City Centre Sharjah Parking", "Sharjah", "Al Khan", "Garage", 0, 2000, 900, "24/7", 25.3319, 55.3856),
    ("A1", "Ajman University Parking", "Ajman", "Al Jurf", "Open lot", 0, 450, 72, "24/7", 25.3990, 55.4680),
    ("A2", "City Centre Ajman Parking", "Ajman", "Al Zahra", "Garage", 0, 1200, 1100, "24/7", 25.3978, 55.4553),
    ("A3", "Ajman Corniche Bays", "Ajman", "Corniche", "Street", 2, 160, 60, "24/7", 25.4146, 55.4350),
    ("A4", "Ajman Marina Garage", "Ajman", "Ajman Marina", "Garage", 4, 350, 120, "24/7", 25.4066, 55.4410),
    ("A5", "Ajman Old Souq Bays", "Ajman", "Old Souq", "Street", 2, 80, 80, "7:00 AM – 11:00 PM", 25.4052, 55.4440),
    ("A6", "Ajman Museum Parking", "Ajman", "Al Bustan", "Open lot", None, None, None, "Not listed", 25.4041, 55.4457),
]
PARKINGS = [dict(zip(KEYS, row)) for row in RAW]
for _p in PARKINGS:
    _p.update(src="demo", fee=("yes" if (_p["price"] or 0) > 0 else "no" if _p["price"] == 0 else None), capacity=_p["total"])
DEMO_PARKINGS = PARKINGS
BY_ID = {p["id"]: p for p in PARKINGS}
CITIES = ["Dubai", "Sharjah", "Ajman"]
CITY_VIEW = {"Whole UAE": (25.20, 55.35, 8.2), "Dubai": (25.17, 55.24, 10.0),
             "Sharjah": (25.32, 55.40, 11.0), "Ajman": (25.40, 55.45, 12.0)}
REFS = {"Downtown Dubai": (25.1972, 55.2744)}          # default point distances are measured from


# ======================================================= 2. CALCULATIONS (logic) ====
def haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line distance between two coordinates in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def has_cap(p):
    """True only when real total + occupied numbers exist (we never invent them)."""
    t, o = p["total"], p["occupied"]
    return isinstance(t, int) and isinstance(o, int) and t > 0 and 0 <= o <= t


def free_spaces(p):
    """free = total - occupied (calculated by Python, never typed in)."""
    return p["total"] - p["occupied"] if has_cap(p) else None


def base_status(p):
    """No spaces -> Full. Fewer than 20 free OR 70%+ occupied -> Almost Full ("Limited"). Else Available."""
    if not has_cap(p):
        return "Unknown"
    free = free_spaces(p)
    if free == 0:
        return "Full"
    return "Almost Full" if (free < 20 or p["occupied"] / p["total"] >= 0.70) else "Available"


EST = "Typical estimate (not live)"
# Typical % of spaces taken at hour 0,3,6,...21. These are ASSUMED daily patterns, not measurements.
PATTERN = {  # (type, kind of day) -> occupancy at 0h,3h,6h,9h,12h,15h,18h,21h
    ("Garage", "work"): [15, 8, 25, 60, 78, 80, 85, 70], ("Garage", "off"): [20, 10, 18, 45, 80, 90, 95, 85],
    ("Street", "work"): [25, 15, 35, 85, 92, 90, 70, 45], ("Street", "off"): [30, 20, 25, 45, 60, 70, 75, 60],
    ("Open lot", "work"): [15, 10, 30, 80, 85, 75, 50, 25], ("Open lot", "off"): [20, 12, 20, 40, 55, 60, 55, 35],
}


def now_uae():
    return datetime.datetime.now(UAE_TZ)


def day_kind(dt):
    return "off" if dt.weekday() in (5, 6) else "work"          # UAE weekend: Saturday and Sunday


def typical_occupancy(p, dt):
    """Assumed typical % full for this kind of place at this weekday + time (simple pattern, NOT measured)."""
    row = PATTERN.get((p["type"], day_kind(dt))) or PATTERN[("Open lot", day_kind(dt))]
    h = dt.hour + dt.minute / 60
    i = int(h // 3)
    a, b = row[i], row[(i + 1) % 8]
    value = a + (b - a) * ((h - i * 3) / 3)
    if p["price"] == 0:
        value += 8                                             # free places fill up faster
    return max(5.0, min(100.0, value))


def report_average(p, dt):
    """Average of USER reports for this parking on the same weekday within +-1 hour. Needs 3+ reports."""
    vals = []
    for r in REPORTS:
        if r["parking_id"] != p["id"]:
            continue
        t = datetime.datetime.fromtimestamp(r["timestamp"], UAE_TZ)
        if t.weekday() == dt.weekday() and abs(t.hour - dt.hour) <= 1:
            vals.append({"available": 40, "almost_full": 85, "full": 100}[r["feedback_type"]])
    return (sum(vals) / len(vals), len(vals)) if len(vals) >= 3 else None


def occupancy_estimate(p, dt):
    """(percent full, source text). Real user average if there are enough reports, else the typical pattern."""
    avg = report_average(p, dt)
    if avg:
        return avg[0], "Average of %d user reports for this weekday and hour" % avg[1]
    return typical_occupancy(p, dt), EST


def status_from_percent(pct):
    return "Full" if pct >= 95 else "Almost Full" if pct >= 75 else "Available"


def effective_status(p):
    """(status, source). A community report from the last 2 hours beats the stored demo status."""
    for r in reversed(REPORTS):
        if r["parking_id"] == p["id"] and time.time() - r["timestamp"] <= REPORT_LIFETIME:
            return {"available": "Available", "almost_full": "Almost Full", "full": "Full"}[r["feedback_type"]], "Community report"
    status = base_status(p)
    if status != "Unknown":
        return status, "Demo data"
    pct, source = occupancy_estimate(p, now_uae())
    return status_from_percent(pct), source


def dist_km(p):
    lat, lon = ss.ref["pt"]
    return haversine_km(lat, lon, p["lat"], p["lon"])


def walk_text(km):
    m = max(1, round(km / 5 * 60))                       # walking at 5 km/h
    return "%d min" % m if m < 60 else "%dh %dm" % (m // 60, m % 60)


def price_text(p):
    if p["price"] is None:
        return "Paid (rate not listed)" if p.get("fee") == "yes" else "Not listed"
    return "Free" if p["price"] == 0 else "AED %s/hr" % num(p["price"])


def num(x):
    return ("%.2f" % x).rstrip("0").rstrip(".")


def score(p, status, source, km):
    """Visible rule-based score (NOT AI): availability, distance, price, data reliability."""
    pts = {"Available": 35, "Almost Full": 15, "Unknown": 8, "Full": -50}[status]
    pts += {"Community report": 6, "Demo data": 3, EST: 2}.get(source, 0)
    pts += 30 * max(0.0, 1 - km / 15)
    if p["price"] == 0:
        pts += 20
    elif p["price"] is not None:
        pts += 20 * (1 - min(p["price"], 25) / 25)
    else:
        pts += 6
    return pts


def reason(p, status, km):
    d = ("very close" if km < 1 else "close" if km < 3 else "within reach" if km < 10 else "%.1f km away" % km)
    free = free_spaces(p)
    if free is not None and status == "Available":
        s = "has %d available spaces" % free
    elif free is not None and status == "Almost Full":
        s = "has %d spaces left" % free
    else:
        s = "is usually %s at this time" % {"Available": "available", "Almost Full": "fairly busy", "Full": "full"}.get(status, "unknown")
    pr = ("is free" if p["price"] == 0 else "has a price that is not listed" if p["price"] is None
          else "costs AED %s/hr" % num(p["price"]))
    return "It is %s, %s, and %s." % (d, s, pr)


def recommend(items):
    """Best first. Full places are skipped."""
    ranked = []
    for p in items:
        status, source = effective_status(p)
        if status != "Full":
            km = dist_km(p)
            ranked.append((p, score(p, status, source, km), reason(p, status, km)))
    return sorted(ranked, key=lambda r: -r[1])


def estimate_cost(rate, minutes, free_min=0.0, daily_cap=None):
    """cost = rate x (duration - free period)/60, limited by an optional daily maximum."""
    billable = max(0.0, minutes - free_min)
    raw = rate * billable / 60
    if daily_cap is None:
        return billable, round(raw, 2), round(raw, 2)
    days, rest = divmod(billable, 1440)
    capped = days * min(rate * 24, daily_cap) + min(rate * rest / 60, daily_cap)
    return billable, round(raw, 2), round(capped, 2)


def fmt_duration(sec):
    m = int(sec // 60)
    h, m = divmod(m, 60)
    if h == 0 and m == 0:
        return "less than a minute"
    out = []
    if h:
        out.append("%d hour%s" % (h, "" if h == 1 else "s"))
    if m or not h:
        out.append("%d minute%s" % (m, "" if m == 1 else "s"))
    return " ".join(out)


def fmt_clock(sec):
    s = int(sec)
    return "%02d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)


def directions_url(p):
    return "https://www.google.com/maps/dir/?api=1&destination=%s,%s" % (p["lat"], p["lon"])


# ============================================================ 3. STORAGE + ACCOUNTS ====
def load_json(name, default):
    try:
        with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(name, data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def hash_pw(password, salt_hex):
    """Salted PBKDF2 hash. We never store the real password."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 200_000).hex()


def make_account(name, email, password):
    users = load_json("users.json", {})
    email = email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return None, "Please enter a valid email address."
    if len(password) < 8:
        return None, "Your password needs at least 8 characters."
    if email in users:
        return None, "An account with this email already exists. Try logging in."
    salt = secrets.token_hex(16)
    users[email] = {"name": name.strip() or email.split("@")[0].title(), "salt": salt, "hash": hash_pw(password, salt)}
    save_json("users.json", users)
    return {"name": users[email]["name"], "email": email, "guest": False}, ""


def check_login(email, password):
    rec = load_json("users.json", {}).get(email.strip().lower())
    if rec and hmac.compare_digest(rec["hash"], hash_pw(password, rec["salt"])):
        return {"name": rec["name"], "email": email.strip().lower(), "guest": False}
    return None


def user_key():
    return (ss.user or {}).get("email") or "guest"


def has_account():
    """Only signed-in users (email) get data saved to the shared file. Guests keep data in their own session only,
    so one visitor can never see another visitor's saved places or parked car."""
    return bool((ss.user or {}).get("email"))


def get_saved():
    if not has_account():
        return [i for i in ss.get("guest_saved", []) if i in BY_ID]
    return [i for i in load_json("saved.json", {}).get(user_key(), []) if i in BY_ID]


def google_user():
    """Returns a user dict when Streamlit's Google/OIDC sign-in is configured and completed."""
    try:
        logged = bool(st.user.is_logged_in)
        ss.google_dbg = "Google status: signed in = %s" % logged
        if logged:
            try:
                name, email = st.user.get("name"), st.user.get("email")
            except Exception:
                name, email = getattr(st.user, "name", None), getattr(st.user, "email", None)
            return {"name": name or email or "Google user", "email": email or "", "guest": False}
    except Exception as error:
        ss.google_dbg = "Google status: error %s: %s" % (type(error).__name__, str(error)[:120])
    return None


# ============================================ 3b. PARKING LOCATIONS FROM OPENSTREETMAP ====
REFRESH_SECONDS = 30 * 60                               # locations are refreshed every 30 minutes
OVERPASS_URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
                 "https://overpass.kumi.systems/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
EMIRATES = {"Dubai": ("AE-DU", "Dubai"), "Sharjah": ("AE-SH", "Sharjah"), "Ajman": ("AE-AJ", "Ajman")}
UAE_TZ = datetime.timezone(datetime.timedelta(hours=4))
TYPE_OF = {"multi-storey": "Garage", "underground": "Garage", "rooftop": "Garage",
           "street_side": "Street", "lane": "Street", "on_kerb": "Street"}


def overpass(query):
    """Asks the free OpenStreetMap servers. They are often busy (error 500/429/504), so try every mirror, twice."""
    last = None
    for attempt in range(2):
        for url in OVERPASS_URLS:
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": query}).encode(), headers=HEADERS)
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.load(r)
            except Exception as error:
                last = error
        if attempt == 0:
            time.sleep(3)
    raise last


def osm_to_parking(el, city):
    tags = el.get("tags", {})
    if tags.get("access") in ("private", "no"):
        return None
    lat = el.get("lat", (el.get("center") or {}).get("lat"))
    lon = el.get("lon", (el.get("center") or {}).get("lon"))
    if lat is None or lon is None:
        return None
    kind = TYPE_OF.get(tags.get("parking"), "Open lot")
    name = tags.get("name:en") or tags.get("name") or tags.get("official_name") or tags.get("alt_name")
    if not name and (tags.get("operator") or tags.get("brand")):
        name = (tags.get("operator") or tags.get("brand")) + " parking"
    street = tags.get("addr:street") or ""
    area = tags.get("addr:suburb") or tags.get("addr:neighbourhood") or ""
    cap = re.match(r"\d+", str(tags.get("capacity", "")))
    return {"id": "O%s%s" % (el["type"][0], el["id"]), "name": name, "name_ar": tags.get("name:ar") or "", "city": city, "area": area, "street": street, "type": kind,
            "price": 0 if tags.get("fee") == "no" else None, "fee": tags.get("fee"),
            "total": None, "occupied": None, "capacity": int(cap.group()) if cap else None,
            "hours": tags.get("opening_hours", "Not listed"), "lat": float(lat), "lon": float(lon), "src": "osm"}


LANDMARK_QUERY = ('[out:json][timeout:90];area%s->.a;(nwr["name"]["shop"="mall"](area.a);'
                  'nwr["name"]["tourism"~"^(hotel|attraction|museum|theme_park|zoo)$"](area.a);'
                  'nwr["name"]["amenity"~"^(hospital|university|college|marketplace|place_of_worship|townhall|library|theatre|cinema)$"](area.a);'
                  'nwr["name"]["railway"="station"](area.a);'
                  'nwr["name"]["leisure"~"^(park|stadium|sports_centre|marina)$"](area.a););out center tags;')
SUBURB_QUERY = '[out:json][timeout:60];area%s->.a;nwr["name"]["place"~"^(suburb|neighbourhood|quarter|village|town)$"](area.a);out center tags;'


def named_points(query_template, area_filter):
    """Named places (landmarks or suburbs) as (name, lat, lon). Never raises: missing extras just mean plainer names."""
    try:
        elements = overpass(query_template % area_filter).get("elements", [])
    except Exception:
        return []
    out = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        if name and lat is not None and lon is not None:
            out.append((name, float(lat), float(lon)))
    return out


def km_between(lat1, lon1, lat2, lon2):
    """Quick flat-earth distance in km (fine for short distances in the UAE)."""
    return math.hypot((lat2 - lat1) * 110.6, (lon2 - lon1) * 111.3 * math.cos(math.radians(lat1)))


def nearest_named(points, lat, lon, max_km):
    best, best_d = None, max_km
    for name, plat, plon in points:
        if abs(plat - lat) * 110.6 > best_d or abs(plon - lon) * 100 > best_d:
            continue
        d = km_between(lat, lon, plat, plon)
        if d < best_d:
            best, best_d = name, d
    return best


KIND_WORD = {"Garage": "Garage parking", "Street": "Street parking", "Open lot": "Parking lot"}


def give_names(items, landmarks, suburbs):
    """Real names where OpenStreetMap has them; otherwise 'Garage parking near Dubai Mall', 'Street parking on X', 'Parking lot in Al Barsha'."""
    grid = {}
    for pt in landmarks:
        grid.setdefault((int(pt[1] * 100), int(pt[2] * 100)), []).append(pt)
    for p in items:
        if not p["area"]:
            p["area"] = nearest_named(suburbs, p["lat"], p["lon"], 6.0) or p["city"]
        if p["name"]:
            continue
        cx, cy = int(p["lat"] * 100), int(p["lon"] * 100)
        near = [pt for dx in (-1, 0, 1) for dy in (-1, 0, 1) for pt in grid.get((cx + dx, cy + dy), [])]
        landmark = nearest_named(near, p["lat"], p["lon"], 0.35)
        word = KIND_WORD[p["type"]]
        if landmark:
            p["name"] = "%s near %s" % (word, landmark)
        elif p["street"]:
            p["name"] = "%s on %s" % (word, p["street"])
        elif p["area"] != p["city"]:
            p["name"] = "%s in %s" % (word, p["area"])
        else:
            p["name"] = "%s in %s" % (word, p["city"])


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner="Updating parking locations from OpenStreetMap (the first load can take a minute)...")
def osm_parkings():
    """Downloads every amenity=parking in Dubai, Sharjah and Ajman. Streamlit keeps the result for 30 minutes."""
    items, seen, landmarks, suburbs, failures = [], set(), [], [], []
    for city, (code, name) in EMIRATES.items():
        found = 0
        for area_filter in ('["ISO3166-2"="%s"]' % code, '["name:en"="%s"]["boundary"="administrative"]' % name):
            query = '[out:json][timeout:90];area%s->.a;nwr["amenity"="parking"](area.a);out center tags;' % area_filter
            try:
                elements = overpass(query).get("elements", [])
            except Exception as error:
                failures.append("%s: %s" % (city, error))
                continue
            for el in elements:
                item = osm_to_parking(el, city)
                if item and item["id"] not in seen:
                    seen.add(item["id"])
                    items.append(item)
                    found += 1
            if found:
                landmarks += named_points(LANDMARK_QUERY, area_filter)
                suburbs += named_points(SUBURB_QUERY, area_filter)
                break
    give_names(items, landmarks, suburbs)
    if len(items) < 50 or (failures and len(items) < 500):
        raise ValueError("OpenStreetMap returned only %d parking places%s" % (len(items), (" (" + failures[-1] + ")") if failures else ""))
    return {"items": items, "fetched": time.time()}


@st.cache_resource
def failure_note():
    """Shared by all visitors: when OpenStreetMap last failed, so we don't hammer its busy server on every click."""
    return {"t": 0.0, "error": ""}


def load_parkings():
    """Sets the global PARKINGS / BY_ID. Order: fresh OSM data -> last saved copy -> 26 demo entries."""
    global PARKINGS, BY_ID, DATA_INFO
    info = {"source": "osm", "fetched": None, "error": ""}
    note = failure_note()
    try:
        if time.time() - note["t"] < 90:           # failed a moment ago: use the fallback, retry after 90 seconds
            raise RuntimeError(note["error"])
        data = osm_parkings()
        save_json("osm_cache.json", data)
    except Exception as error:
        info["error"] = "%s: %s" % (type(error).__name__, error) if not isinstance(error, RuntimeError) else str(error)
        if not isinstance(error, RuntimeError):
            note.update(t=time.time(), error=info["error"])
        data = load_json("osm_cache.json", None)
        info["source"] = "saved copy" if data else "demo"
    if data and data.get("items"):
        PARKINGS, info["fetched"] = data["items"], data.get("fetched")
    else:
        PARKINGS = DEMO_PARKINGS
    BY_ID = {p["id"]: p for p in PARKINGS}
    DATA_INFO = info


DATA_INFO = {"source": "demo", "fetched": None, "error": ""}


def fmt_updated(ts):
    return datetime.datetime.fromtimestamp(ts, UAE_TZ).strftime("%I:%M %p").lstrip("0") if ts else "-"


def cb_refresh_data():
    st.cache_data.clear()
    failure_note().update(t=0.0)
    st.toast("Refreshing parking locations...")


def data_status(key):
    """Honest line about where the list comes from and when it was refreshed."""
    i = DATA_INFO
    if i["source"] == "osm":
        st.caption("📡 %d parking places from OpenStreetMap · updated %s (UAE time) · refreshes every 30 minutes · "
                   "availability is a typical-pattern estimate unless drivers report." % (len(PARKINGS), fmt_updated(i["fetched"])))
    elif i["source"] == "saved copy":
        st.warning("OpenStreetMap is busy right now, so this is the last saved copy from %s. Tap Refresh now in a minute." % fmt_updated(i["fetched"]))
        st.caption("Technical detail: %s" % i["error"])
    else:
        st.warning("OpenStreetMap's free server is busy right now, so only the 26 demo places are shown for the moment. "
                   "Wait a minute and tap Refresh now.")
        st.caption("Technical detail: %s" % i["error"])
    st.button("Refresh now", key="refresh_" + key, on_click=cb_refresh_data)


# ======================================================= 3c. EV CHARGING DATA ====
# Charging stations come from the same free OpenStreetMap database (amenity=charging_station). They are loaded only
# when someone opens the EV page. There is NO live "free/busy" information for chargers, so none is shown.
EV_PLUGS = [("Type 2", ("socket:type2",)), ("CCS (fast DC)", ("socket:type2_combo", "socket:ccs")),
            ("CHAdeMO", ("socket:chademo",)), ("Tesla", ("socket:tesla_supercharger", "socket:tesla_destination", "socket:nacs"))]


def osm_to_charger(el, city):
    tags = el.get("tags", {})
    if tags.get("access") in ("private", "no"):
        return None
    lat = el.get("lat", (el.get("center") or {}).get("lat"))
    lon = el.get("lon", (el.get("center") or {}).get("lon"))
    if lat is None or lon is None:
        return None
    plugs = [label for label, keys in EV_PLUGS if any(str(tags.get(k, "no")).lower() not in ("no", "0", "") for k in keys)]
    kws = []
    for k, v in tags.items():
        if k.endswith(":output") or k == "charging_station:output":
            kws += [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(v))[:1]]
    operator = tags.get("operator") or tags.get("brand") or ""
    area = tags.get("addr:suburb") or tags.get("addr:neighbourhood") or ""
    name = tags.get("name:en") or tags.get("name") or tags.get("official_name") or (operator + " charger" if operator else "")
    if not name:
        name = "EV charger in %s" % (area or city)
    cap = re.match(r"\d+", str(tags.get("capacity", "")))
    return {"id": "E%s%s" % (el["type"][0], el["id"]), "name": name, "name_ar": tags.get("name:ar") or "", "operator": operator, "city": city, "area": area,
            "plugs": plugs, "kw": max(kws) if kws else None, "points": int(cap.group()) if cap else None,
            "fee": tags.get("fee"), "hours": tags.get("opening_hours", ""), "lat": float(lat), "lon": float(lon)}


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner="Loading EV charging stations from OpenStreetMap...")
def osm_chargers():
    items, seen, failures = [], set(), []
    for city, (code, name) in EMIRATES.items():
        for area_filter in ('["ISO3166-2"="%s"]' % code, '["name:en"="%s"]["boundary"="administrative"]' % name):
            query = '[out:json][timeout:60];area%s->.a;nwr["amenity"="charging_station"](area.a);out center tags;' % area_filter
            try:
                elements = overpass(query).get("elements", [])
            except Exception as error:
                failures.append("%s: %s" % (city, error))
                continue
            found = 0
            for el in elements:
                item = osm_to_charger(el, city)
                if item and item["id"] not in seen:
                    seen.add(item["id"])
                    items.append(item)
                    found += 1
            if found:
                break
    if not items:           # last try: a plain map rectangle around Dubai, Sharjah and Ajman (no area lookup needed)
        try:
            query = '[out:json][timeout:60];nwr["amenity"="charging_station"](24.75,54.85,25.55,55.75);out center tags;'
            for el in overpass(query).get("elements", []):
                lat = el.get("lat", (el.get("center") or {}).get("lat"))
                city = "Sharjah" if (lat or 0) > 25.28 and (el.get("lon", (el.get("center") or {}).get("lon")) or 0) > 55.33 else "Dubai"
                item = osm_to_charger(el, city)
                if item and item["id"] not in seen:
                    seen.add(item["id"])
                    items.append(item)
        except Exception as error:
            failures.append("map rectangle: %s" % error)
    if not items:
        raise ValueError("no charging stations returned" + (" (%s)" % failures[-1] if failures else ""))
    return {"items": items, "fetched": time.time()}


@st.cache_resource
def ev_failure_note():
    return {"t": 0.0, "error": ""}


def load_chargers():
    """Returns (list, info). Order: fresh OpenStreetMap data -> last saved copy -> empty list (we never invent chargers)."""
    info = {"source": "osm", "fetched": None, "error": ""}
    note = ev_failure_note()
    try:
        if time.time() - note["t"] < 90:
            raise RuntimeError(note["error"])
        data = osm_chargers()
        save_json("ev_cache.json", data)
    except Exception as error:
        info["error"] = str(error) if isinstance(error, RuntimeError) else "%s: %s" % (type(error).__name__, error)
        if not isinstance(error, RuntimeError):
            note.update(t=time.time(), error=info["error"])
        data = load_json("ev_cache.json", None)
        info["source"] = "saved copy" if data else "none"
    items = (data or {}).get("items", [])
    info["fetched"] = (data or {}).get("fetched")
    return items, info


# ================================================================ 4. STATE ====
for _k, _v in {"search_limit": 25, "user": None, "page": "home", "detail": None, "theme": "light", "lang": "en", "loaded": False, "q": "",
               "auth_view": "login", "auth_msg": "", "nearby_msg": "",
               "ref": {"label": "Downtown Dubai", "pt": REFS["Downtown Dubai"]},
               "timer": {"state": "idle", "parking": None, "rate": None, "acc": 0.0, "seg": None},
               "timer_rate": "", "calc_rate": 5.0, "calc_hours": 1, "calc_mins": 0, "calc_free": 0.0,
               "calc_use_cap": False, "calc_cap": 30.0}.items():
    ss.setdefault(_k, _v)
REPORTS = load_json("reports.json", [])

# ================================================================ 5. LOOK (CSS) ====
LIGHT = dict(bg1="#EFE4D2", bg2="#FBF7EF", card="#FFFBF4", border="#EADFCB", text="#1B2A4A", muted="#4F493D",
             tile="#F6EDDF", blue="#2F6FDB", terra="#C0652B", navy="#1B2A4A", navtext="#FFF3DC", shadow="rgba(80,60,30,.12)", edge="#7A6D58", edge2="#0F1A33")
DARK = dict(bg1="#0F1426", bg2="#171E36", card="#1C2440", border="#2A3458", text="#EAF0FF", muted="#C5CFE8",
            tile="#252F50", blue="#6EA2FF", terra="#F0A168", navy="#2F6FDB", navtext="#FFFFFF", shadow="rgba(0,0,0,.35)", edge="#7F8FBF", edge2="#B7CCFF")

CSS = """
<style>
:root{--bg1:@bg1@;--bg2:@bg2@;--card:@card@;--border:@border@;--text:@text@;--muted:@muted@;--tile:@tile@;
--blue:@blue@;--terra:@terra@;--navy:@navy@;--navtext:@navtext@;--shadow:@shadow@;--edge:@edge@;--edge2:@edge2@}
.stApp{background:linear-gradient(180deg,var(--bg1),var(--bg2)) fixed;color:var(--text)}
header[data-testid="stHeader"],footer,#MainMenu,[data-testid="stSidebar"],[data-testid="stToolbar"],[data-testid="collapsedControl"]{display:none !important}
.block-container{max-width:1180px;padding:1.4rem 1.6rem 8rem}
.stApp,[data-testid="stMarkdownContainer"],[data-testid="stMarkdownContainer"] p,label,[data-testid="stWidgetLabel"] p{color:var(--text)}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{color:var(--muted)}
.pf-eyebrow{font-size:.72rem;letter-spacing:.14em;font-weight:800;color:var(--muted);text-transform:uppercase}
.pf-title{font-size:1.9rem;font-weight:800;line-height:1.1;margin:.15rem 0 .35rem;color:var(--text)}
.pf-lead{color:var(--muted);margin-bottom:.8rem;line-height:1.45}
.pf-hero{position:relative;border-radius:28px;padding:22px 20px 26px;color:#fff;overflow:hidden;min-height:250px;
background:linear-gradient(135deg,#27325A 0%,#4B5E91 50%,#C9906E 100%);background-size:cover;background-position:center;box-shadow:0 14px 34px var(--shadow)}
.pf-hero::before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(22,30,62,.72),rgba(22,30,62,.08))}
.pf-hero>*{position:relative}
.pf-hero .pf-brand{font-size:.78rem;letter-spacing:.18em;font-weight:800;color:#F4E6CF}
.pf-hero .pf-h1{font-size:2.35rem;line-height:1.04;font-weight:800;margin:.7rem 0 .5rem;color:#fff;max-width:11em}
.pf-hero .pf-hsub{color:#F1EEF8;font-size:1rem}
.pf-cardhead{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.pf-name{font-size:1.15rem;font-weight:800;color:var(--text)}
.pf-sub{color:var(--muted);font-size:.9rem;margin-top:2px}
.pf-tag{display:inline-block;background:var(--tile);color:var(--muted);border-radius:10px;padding:3px 10px;font-size:.78rem;font-weight:700;margin-top:10px}
.pf-tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0 8px}
.pf-tiles div{background:var(--tile);border-radius:14px;padding:10px 4px;text-align:center}
.pf-tiles small{display:block;color:var(--muted);font-size:.74rem}
.pf-tiles b{font-size:.98rem;color:var(--text)}
.pf-foot{display:flex;justify-content:space-between;color:var(--muted);font-size:.84rem;border-top:1px solid var(--border);padding-top:9px}
.pf-src{color:var(--muted);font-size:.74rem;margin-top:6px}
.pf-pill{display:inline-flex;align-items:center;gap:6px;border-radius:99px;padding:5px 12px;font-weight:700;font-size:.78rem;white-space:nowrap}
.pf-pill i{width:8px;height:8px;border-radius:50%;background:currentColor;display:inline-block}
.pf-ok{background:rgba(46,158,107,.15);color:#2E9E6B}.pf-warn{background:rgba(213,138,27,.17);color:#D58A1B}
.pf-bad{background:rgba(201,75,90,.15);color:#C94B5A}.pf-unk{background:rgba(120,125,140,.18);color:#7B8190}
.pf-banner{display:flex;gap:14px;align-items:center;border-radius:24px;padding:18px;color:#fff;background:linear-gradient(135deg,#1E3A8A,#2F5FD6);box-shadow:0 12px 28px rgba(30,58,138,.35)}
.pf-bicon{background:rgba(255,255,255,.18);border-radius:16px;width:46px;height:46px;display:grid;place-items:center;font-size:1.4rem;flex:none}
.pf-b1{font-size:.72rem;letter-spacing:.12em;font-weight:800;color:#BBD0FF}
.pf-b2{font-size:1.15rem;font-weight:800;color:#fff}
.pf-b3{font-size:.9rem;color:#E4ECFF;margin-top:2px}
.pf-icon{width:48px;height:48px;border-radius:16px;display:grid;place-items:center;font-size:1.4rem;background:var(--tile)}
.pf-row{display:flex;gap:14px;align-items:center}
.pf-rowt{font-weight:800;color:var(--text)}.pf-rowd{color:var(--muted);font-size:.88rem}
.pf-empty{text-align:center;padding:34px 10px;color:var(--muted)}
.pf-empty .pf-icon{margin:0 auto 10px;border-radius:50%;width:56px;height:56px}
.pf-empty b{display:block;color:var(--text);margin-bottom:4px}
.pf-info{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--border)}
.pf-info span{color:var(--muted)}.pf-info b{text-align:right;color:var(--text)}
[class*="st-key-card_"]{background:var(--card);border:1px solid var(--border);border-radius:24px;box-shadow:0 10px 26px var(--shadow);padding:16px 16px 12px}
.stButton>button,.stLinkButton>a,.stFormSubmitButton>button,[data-testid^="stBaseButton"]{border-radius:14px;min-height:44px;font-weight:700;border:1px solid var(--border);background:var(--card);color:var(--text);transition:.15s}
.stButton>button:hover,.stLinkButton>a:hover,.stFormSubmitButton>button:hover{transform:translateY(-1px);border-color:var(--terra);color:var(--terra)}
button[kind="primary"],button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{background:var(--navy);color:var(--navtext);border-color:var(--navy)}
button[kind="primary"] p,button[data-testid="stBaseButton-primary"] p,button[data-testid="stBaseButton-primaryFormSubmit"] p{color:var(--navtext)}
.stButton>button p,.stLinkButton>a p,.stFormSubmitButton>button p{color:inherit}
button[data-testid="stBaseButton-pills"],button[data-testid="stBaseButton-pillsActive"]{border-radius:99px;padding:6px 18px}
button[data-testid="stBaseButton-pillsActive"]{background:var(--blue);color:#fff;border-color:var(--blue)}
button[data-testid="stBaseButton-pillsActive"] p{color:#fff}
[data-baseweb="input"],[data-baseweb="input"]>div,[data-baseweb="select"]>div,[data-baseweb="base-input"]{background:var(--card) !important;border-color:var(--border) !important;border-radius:14px !important}
[data-baseweb="input"] input,[data-baseweb="select"] div{color:var(--text) !important}
[data-testid="stForm"]{border:0;padding:0;background:transparent}
[data-testid="stExpander"]{border:1px solid var(--border);border-radius:16px;background:var(--card)}
.st-key-bottomnav{position:fixed;left:0;right:0;bottom:0;z-index:999;background:var(--card);border-top:1px solid var(--border);padding:6px 8px calc(6px + env(safe-area-inset-bottom,0px));box-shadow:0 -6px 20px var(--shadow)}
.st-key-bottomnav [data-testid="stHorizontalBlock"]{max-width:600px;margin:0 auto;gap:0;flex-wrap:nowrap !important}
.st-key-bottomnav [data-testid="stColumn"],.st-key-bottomnav [data-testid="column"]{min-width:0 !important;flex:1 1 0 !important}
.st-key-bottomnav button{background:transparent !important;border:0 !important;box-shadow:none !important;color:var(--muted) !important;min-height:54px;font-size:.72rem;padding:0}
.st-key-bottomnav button p{color:inherit !important;font-size:.72rem}
.st-key-bottomnav button>div{flex-direction:column;gap:2px}
[class*="st-key-card_"] [data-testid="stHorizontalBlock"]{flex-wrap:nowrap !important;gap:8px}
[class*="st-key-card_"] [data-testid="stColumn"],[class*="st-key-card_"] [data-testid="column"]{min-width:0 !important;flex:1 1 0 !important}
#pf-load{position:fixed;inset:0;z-index:99999;background:radial-gradient(circle at 50% 35%,#1F2C52,#0E1428);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;color:#fff}
#pf-load .pf-lp{font-size:2rem;animation:pfbob 1.1s ease-in-out infinite;filter:drop-shadow(0 0 14px rgba(110,162,255,.7))}
#pf-load .pf-lb{width:104px;height:104px;border-radius:30px;background:linear-gradient(145deg,#243461,#1A2547);border:1px solid #3B4B7C;display:grid;place-items:center;font-size:3.4rem;font-weight:800;color:#F4D9A6;box-shadow:0 18px 40px rgba(0,0,0,.4)}
#pf-load .pf-lt{font-size:1.7rem;font-weight:800;margin-top:12px}#pf-load .pf-lt em{color:#6EA2FF;font-style:normal}
#pf-load .pf-ls{color:#A9B6D8}
#pf-load .pf-bar{width:210px;height:5px;border-radius:9px;background:#26325A;overflow:hidden}
#pf-load .pf-bar i{display:block;height:100%;background:linear-gradient(90deg,#3B82F6,#7FB0FF);animation:pffill 2.2s ease forwards}
@keyframes pfbob{50%{transform:translateY(-10px)}}@keyframes pffill{from{width:0}to{width:100%}}
.block-container>div{animation:pffade .3s ease}@keyframes pffade{from{opacity:.0;transform:translateY(6px)}to{opacity:1;transform:none}}
</style>
"""


BUTTON_BORDERS = """
/* clear, professional borders on every button so they never blend into the background */
.stButton>button,.stLinkButton>a,.stFormSubmitButton>button,.stDownloadButton>button,[data-testid^="stBaseButton"]{
  border:1.5px solid var(--edge) !important;box-shadow:0 2px 0 var(--shadow),0 1px 3px var(--shadow) !important;border-radius:14px}
button[kind="primary"],button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{
  border:1.5px solid var(--edge2) !important}
button[data-testid="stBaseButton-pills"]{border:1.5px solid var(--edge) !important;box-shadow:none !important}
button[data-testid="stBaseButton-pillsActive"]{border:1.5px solid var(--edge2) !important;box-shadow:none !important}
.stButton>button:hover,.stLinkButton>a:hover,.stFormSubmitButton>button:hover{border-color:var(--terra) !important}
.stButton>button:focus-visible,.stLinkButton>a:focus-visible,.stFormSubmitButton>button:focus-visible{outline:3px solid var(--blue) !important;outline-offset:2px}
.stButton>button:disabled{opacity:.55;border-style:dashed !important}
.st-key-bottomnav button{border:1.5px solid var(--edge) !important;border-radius:14px !important;background:var(--card) !important;margin:0 2px}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="base-input"]{border:1.5px solid var(--edge) !important}
"""


POLISH = """
/* visual polish only: same colours, smoother motion, softer depth, tidier detail */
html{scroll-behavior:smooth}
.stApp{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;text-rendering:optimizeLegibility}
.pf-title,.pf-name,.pf-h1{letter-spacing:-.015em}
.pf-tiles b,.pf-foot,.pf-b2{font-variant-numeric:tabular-nums}
[class*="st-key-card_"]{box-shadow:0 1px 2px var(--shadow),0 10px 26px -6px var(--shadow);
  transition:transform .22s cubic-bezier(.2,.7,.2,1),box-shadow .22s ease,border-color .22s ease;will-change:transform}
[class*="st-key-card_"]:hover{transform:translateY(-3px);box-shadow:0 2px 4px var(--shadow),0 18px 34px -8px var(--shadow);border-color:var(--edge)}
.pf-hero{box-shadow:0 2px 4px var(--shadow),0 22px 44px -10px var(--shadow)}
.pf-banner{transition:transform .22s ease,box-shadow .22s ease}.pf-banner:hover{transform:translateY(-2px)}
.pf-tiles div{transition:transform .18s ease}.pf-tiles div:hover{transform:translateY(-1px)}
.pf-pill{letter-spacing:.01em}
.stButton>button,.stLinkButton>a,.stFormSubmitButton>button{transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease,background-color .15s ease,color .15s ease !important}
.stButton>button:active,.stLinkButton>a:active,.stFormSubmitButton>button:active{transform:translateY(1px) scale(.985);box-shadow:none !important}
[data-baseweb="input"]:focus-within,[data-baseweb="select"]>div:focus-within,[data-baseweb="base-input"]:focus-within{
  border-color:var(--blue) !important;box-shadow:0 0 0 3px color-mix(in srgb,var(--blue) 25%,transparent) !important}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="base-input"]{transition:border-color .15s ease,box-shadow .15s ease}
[data-testid="stExpander"]{box-shadow:0 1px 2px var(--shadow);overflow:hidden}
.st-key-bottomnav{backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
.st-key-bottomnav button{transition:transform .15s ease,color .15s ease}
.st-key-bottomnav button:active{transform:scale(.94)}
.block-container>div{animation:pffade .35s cubic-bezier(.2,.7,.2,1) both}
.block-container>div:nth-child(2){animation-delay:.03s}.block-container>div:nth-child(3){animation-delay:.06s}
.block-container>div:nth-child(4){animation-delay:.09s}.block-container>div:nth-child(5){animation-delay:.12s}
::selection{background:color-mix(in srgb,var(--blue) 30%,transparent)}
*{scrollbar-width:thin;scrollbar-color:var(--edge) transparent}
img,[data-testid="stDeckGlJsonChart"],iframe{border-radius:18px}
@media (prefers-reduced-motion:reduce){*{animation:none !important;transition:none !important}}
@media (max-width:640px){.block-container{padding:1rem 1rem 8rem}.pf-hero{border-radius:24px}}
"""


READABILITY = """
html,body,.stApp{font-family:"Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif !important}
.stApp,[data-testid="stMarkdownContainer"] p,[data-testid="stMarkdownContainer"] li,label,[data-testid="stWidgetLabel"] p{font-size:1.08rem;font-weight:500;line-height:1.5}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{font-size:.95rem !important;font-weight:500}
.pf-eyebrow{font-size:.85rem;font-weight:800}
.pf-title{font-size:2.3rem;font-weight:800}
.pf-lead{font-size:1.1rem;color:var(--muted)}
.pf-name{font-size:1.3rem}
.pf-sub{font-size:1rem}
.pf-tag{font-size:.9rem}
.pf-pill{font-size:.9rem;padding:6px 13px}
.pf-tiles small{font-size:.85rem}
.pf-tiles b{font-size:1.12rem}
.pf-foot{font-size:.98rem}
.pf-src{font-size:.85rem}
.pf-rowt{font-size:1.1rem}
.pf-rowd{font-size:1rem}
.pf-b2{font-size:1.3rem}.pf-b3{font-size:1rem}
.pf-info{font-size:1.05rem}
.stButton>button p,.stLinkButton>a p,.stFormSubmitButton>button p{font-size:1.02rem;font-weight:700}
.pf-hero{min-height:320px;padding:34px 36px 38px}
.pf-hero .pf-h1{font-size:3.1rem;max-width:14em}
.pf-hero .pf-hsub{font-size:1.2rem}
[data-testid="stMetricValue"]{font-size:2rem;font-weight:800}
[data-testid="stToast"],[data-testid="stToastContainer"] > div{background:#10224A !important;border:2px solid #7FB2FF !important;border-radius:14px !important;
  box-shadow:0 10px 30px rgba(0,0,0,.35) !important;min-width:280px}
[data-testid="stToast"] *,[data-testid="stToastContainer"] *{color:#FFFFFF !important;font-size:1.05rem !important;font-weight:700 !important;opacity:1 !important}
[data-testid="stToast"] button svg{fill:#FFFFFF !important;color:#FFFFFF !important}
[data-testid="stSpinner"],[data-testid="stStatusWidget"]{background:#10224A !important;border:2px solid #7FB2FF !important;border-radius:14px !important;
  padding:12px 18px !important;box-shadow:0 8px 24px rgba(0,0,0,.3) !important;width:fit-content !important}
[data-testid="stSpinner"] *,[data-testid="stStatusWidget"] *{color:#FFFFFF !important;font-weight:700 !important;font-size:1.02rem !important;opacity:1 !important}
/* Parky chat window: force a light card with dark text, whatever the browser's own theme is */
[data-testid="stPopoverBody"]{background:var(--card) !important}
[data-testid="stPopoverBody"] *{color:var(--text) !important}
[data-testid="stPopoverBody"] [data-testid="stChatMessage"]{background:var(--bg2) !important;border:1.5px solid var(--edge) !important;border-radius:14px !important}
[data-testid="stPopoverBody"] input{background:#FFFFFF !important;color:#1B2A4A !important;border:1.5px solid var(--edge) !important;-webkit-text-fill-color:#1B2A4A !important}
[data-testid="stPopoverBody"] input::placeholder{color:#6B6F7A !important;-webkit-text-fill-color:#6B6F7A !important}
[data-testid="stPopoverBody"] [data-testid="stTextInput"] > div,[data-testid="stPopoverBody"] [data-baseweb="input"]{background:#FFFFFF !important}
[data-testid="stPopoverBody"] button{background:var(--card) !important;border:2px solid var(--edge) !important;border-radius:12px !important}
[data-testid="stPopoverBody"] button p{color:var(--text) !important;font-weight:700 !important}
[data-testid="stPopoverBody"] [data-testid="stFormSubmitButton"] button,[data-testid="stPopoverBody"] button[kind="primaryFormSubmit"]{background:#1F3A6E !important}
[data-testid="stPopoverBody"] [data-testid="stFormSubmitButton"] button *,[data-testid="stPopoverBody"] button[kind="primaryFormSubmit"] *{color:#FFFFFF !important}
.st-key-chatbot{position:fixed !important;right:16px;bottom:92px;z-index:1001;width:auto !important}
.st-key-chatbot button{border:2px solid var(--edge) !important;border-radius:999px !important;background:var(--blue) !important;color:#fff !important;
  font-weight:800 !important;box-shadow:0 8px 22px rgba(0,0,0,.28) !important;padding:.55rem 1.1rem !important}
.st-key-chatbot button p{color:#fff !important}
[data-testid="stPopoverBody"]{width:min(390px,92vw) !important;max-height:70vh;border:2px solid var(--edge) !important;border-radius:16px !important}
.st-key-bottomnav [data-testid="stHorizontalBlock"]{max-width:820px}
.st-key-bottomnav a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;min-height:54px;padding:0;
  border:1.5px solid var(--edge) !important;border-radius:14px !important;background:var(--card) !important;color:var(--blue) !important;
  font-size:.72rem;font-weight:700;text-decoration:none;margin:0 2px;box-shadow:none !important}
.st-key-bottomnav a p{font-size:.72rem !important;color:inherit !important}
@media (max-width:700px){.pf-title{font-size:1.8rem}.pf-hero{min-height:250px;padding:22px 20px 26px}.pf-hero .pf-h1{font-size:2.3rem}
  .block-container{padding:1rem 1rem 8rem}}
"""


def set_width(px):
    """Narrow pages (login, details, timer...) stay readable; list pages use the full website width."""
    st.markdown("<style>.block-container{max-width:%dpx !important}</style>" % px, unsafe_allow_html=True)


RTL_CSS = """.stApp .block-container,.stApp [data-testid="stMarkdownContainer"],.stApp label,.stApp input,.stApp textarea,
.st-key-chatbot{direction:rtl;text-align:right}
.stApp [data-testid="stDeck"],.stApp iframe,.stApp [data-testid="stDeckGlJsonChart"]{direction:ltr}
.stApp, .stApp *{font-family:"Segoe UI","Tahoma","Noto Naskh Arabic",system-ui,sans-serif}"""
LANG_CSS = ".st-key-langbtn{position:fixed;left:16px;bottom:92px;z-index:999}.st-key-langbtn button{border-radius:999px;font-weight:700}"


def inject_css():
    css = CSS
    for k, v in (DARK if ss.theme == "dark" else LIGHT).items():
        css = css.replace("@%s@" % k, v)
    nav_on = ".st-key-nav_%s button{color:var(--blue) !important}" % {"detail": "search"}.get(ss.page, ss.page)
    rtl = RTL_CSS if ss.get("lang") == "ar" else ""
    st.markdown(css + "<style>" + BUTTON_BORDERS + READABILITY + POLISH + nav_on + rtl + LANG_CSS + "</style>", unsafe_allow_html=True)


inject_css()

# ---------------------------------------------------------- loading screen ----
if not ss.loaded:
    holder = st.empty()
    holder.markdown('<div id="pf-load"><div class="pf-lp">📍</div><div class="pf-lb">P</div>'
                    '<div class="pf-lt">ParkFinder <em>UAE</em></div>'
                    '<div class="pf-ls">Finding the best parking near you...</div>'
                    '<div class="pf-bar"><i></i></div></div>', unsafe_allow_html=True)
    time.sleep(2.4)
    holder.empty()
    ss.loaded = True



def salik_link():
    """Phone -> the official 'Smart Salik' app page in its store (tap Open if installed); computer -> salik.ae."""
    try:
        agent = str(st.context.headers.get("User-Agent", "")).lower()
    except Exception:
        agent = ""
    if "iphone" in agent or "ipad" in agent:
        return "https://apps.apple.com/app/id912158362"                      # Smart Salik by RTA-SALIK
    if "android" in agent:
        return "https://play.google.com/store/search?q=Smart%20Salik&c=apps"  # Android store search
    return "https://www.salik.ae"


# ============================================================== 6. CALLBACKS ====
def cb_go(page):
    ss.page, ss.detail = page, None


def cb_open(pid):
    ss.detail = pid


def cb_close():
    ss.detail = None


def cb_theme():
    ss.theme = "dark" if ss.theme == "light" else "light"


def cb_toggle_save(pid):
    data = load_json("saved.json", {}) if has_account() else {}
    mine = get_saved()
    if pid in mine:
        mine.remove(pid)
        st.toast("Removed from saved parking")
    else:
        mine.append(pid)
        st.toast("Saved: " + pname(BY_ID[pid]))
    if has_account():
        data[user_key()] = mine
        save_json("saved.json", data)
    else:
        ss.guest_saved = mine


def cb_more_results():
    ss.search_limit += 25


def cb_search(src):
    ss.search_limit = 25
    ss.q = ss.get(src, "").strip()
    ss.page, ss.detail = "search", None


def cb_start_parking(pid):
    p, t = BY_ID[pid], ss.timer
    if t["state"] in ("running", "paused"):
        st.toast("A timer is already running. Stop or reset it first.")
    else:
        ss.timer = {"state": "idle", "parking": pid, "rate": None, "acc": 0.0, "seg": None}
        ss.timer_rate = num(p["price"]) if p["price"] is not None else ""
    ss.page, ss.detail = "timer", None


def cb_calc_cost(pid):
    price = BY_ID[pid]["price"]
    ss.calc_rate = float(price) if price is not None else 0.0
    ss.page, ss.detail = "calc", None


def t_elapsed(t):
    """Elapsed seconds from real timestamps (not from counting screen refreshes)."""
    return t["acc"] + (time.time() - t["seg"]) if t["state"] == "running" else t["acc"]


def cb_timer_start():
    text = str(ss.get("timer_rate", "")).strip().replace(",", ".")
    rate = None
    if text:
        try:
            rate = float(text)
            if rate < 0:
                raise ValueError
        except ValueError:
            st.toast("The rate was not a valid number, so no rate will be used.")
            rate = None
    ss.timer.update(state="running", rate=rate, acc=0.0, seg=time.time())


def cb_timer_pause():
    t = ss.timer
    if t["state"] == "running":
        t["acc"] += time.time() - t["seg"]
        t.update(state="paused", seg=None)
    elif t["state"] == "paused":
        t.update(state="running", seg=time.time())


def cb_timer_stop():
    t = ss.timer
    if t["state"] in ("running", "paused"):
        t.update(acc=t_elapsed(t), state="stopped", seg=None)


def cb_timer_reset():
    ss.timer = {"state": "idle", "parking": None, "rate": None, "acc": 0.0, "seg": None}


def cb_car_save(lat, lon):
    """Remember where the car is. Kept in this session and in a small file, per user."""
    spot = {"lat": lat, "lon": lon, "ts": time.time()}
    ss.car = spot
    if has_account():
        data = load_json("car.json", {})
        data[user_key()] = spot
        save_json("car.json", data)
    st.toast("Parking spot saved")


def cb_car_clear():
    ss.car = None
    ss.car_cleared = True
    if has_account():
        data = load_json("car.json", {})
        data.pop(user_key(), None)
        save_json("car.json", data)


def cb_set_area():
    """Set the point distances are measured from: a demo place name, or any UAE place (needs internet)."""
    text = ss.get("nearby_q", "").strip().lower()
    if not text:
        ss.nearby_msg = "Please type an area, landmark or city."
        return
    inside = [p for p in PARKINGS if p["area"].lower() == text or p["city"].lower() == text]
    if inside:       # a whole area or city: use the centre of its parking places
        label = inside[0]["area"] if inside[0]["area"].lower() == text else inside[0]["city"]
        ss.ref = {"label": label, "pt": (sum(p["lat"] for p in inside) / len(inside), sum(p["lon"] for p in inside) / len(inside))}
        ss.nearby_msg = "Distances are now measured from %s." % ss.ref["label"]
        return
    hit = next((p for p in PARKINGS if text in " ".join([p["name"], p["area"], p["city"]]).lower()), None)
    try:
        query = urllib.parse.urlencode({"q": text, "format": "json", "limit": 1, "countrycodes": "ae"})
        req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + query, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
        if data:
            ss.ref = {"label": data[0].get("display_name", text).split(",")[0], "pt": (float(data[0]["lat"]), float(data[0]["lon"]))}
            ss.nearby_msg = "Distances are now measured from %s." % ss.ref["label"]
            return
    except Exception:
        pass
    if hit:          # offline or not found online: fall back to a parking place with that name
        ss.ref = {"label": hit["area"] if text in hit["area"].lower() else hit["name"], "pt": (hit["lat"], hit["lon"])}
        ss.nearby_msg = "Distances are now measured from %s." % ss.ref["label"]
    else:
        ss.nearby_msg = "We couldn't find that place in the UAE. Try another area or landmark."


def cb_reset_area():
    ss.ref = {"label": "Downtown Dubai", "pt": REFS["Downtown Dubai"]}
    ss.nearby_msg = ""


def cb_logout():
    try:
        if st.user.is_logged_in:
            st.logout()
    except Exception:
        pass
    ss.user, ss.page, ss.detail, ss.auth_view = None, "home", None, "login"


def cb_guest():
    ss.user = {"name": "Guest", "email": "", "guest": True}


def cb_auth_view(view):
    ss.auth_view, ss.auth_msg = view, ""


SHOW_GOOGLE_LOGIN = False     # Google sign-in is built (OAuth), but Streamlit's free hosting loses the login cookie. Set True to show it.


def google_configured():
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def cb_google():
    if not google_configured():
        ss.auth_msg = ("Google sign-in isn't switched on for this copy of the app yet (the owner must add Google "
                       "keys in Streamlit's secrets). Use email or continue as a guest.")
        return
    try:
        st.login()
    except Exception:
        ss.auth_msg = "Google sign-in could not start. Please use email or continue as a guest."


def cb_delete_account():
    users = load_json("users.json", {})
    users.pop((ss.user or {}).get("email", ""), None)
    save_json("users.json", users)
    data = load_json("saved.json", {})
    data.pop(user_key(), None)
    save_json("saved.json", data)
    ss.user, ss.page, ss.detail, ss.auth_view = None, "home", None, "login"
    ss.auth_msg = "Your account was deleted."


# =========================================================== 7. UI HELPERS ====
def esc(x):
    return html.escape(str(x))


def md(x):
    st.markdown(x, unsafe_allow_html=True)


PILL = {"Available": ("pf-ok", "Available"), "Almost Full": ("pf-warn", "Limited"),
        "Full": ("pf-bad", "Full"), "Unknown": ("pf-unk", "Unknown")}


def pill(status, src=""):
    cls, label = PILL[status]
    if src.startswith(("Typical", "Average")):
        label = "Usually " + label.lower()
    return '<span class="pf-pill %s"><i></i>%s</span>' % (cls, label)


def title(eyebrow, text, lead=""):
    md((('<div class="pf-eyebrow">%s</div>' % esc(eyebrow)) if eyebrow else "")
       + '<div class="pf-title">%s</div>' % esc(text)
       + (('<div class="pf-lead">%s</div>' % esc(lead)) if lead else ""))


def empty_state(icon, head, text):
    md('<div class="pf-empty"><div class="pf-icon">%s</div><b>%s</b>%s</div>' % (icon, esc(head), esc(text)))


def where(p):
    """'Jumeirah 1 · Dubai' (or just 'Dubai' when we only know the city)."""
    return p["city"] if (not p["area"] or p["area"] == p["city"]) else "%s · %s" % (p["area"], p["city"])


def hours_text(p):
    return "Opening hours not listed" if p["hours"] == "Not listed" else p["hours"]


def src_text(src):
    if src.startswith("Typical"):
        return "Estimate from typical busyness at this day and time, not a live count"
    if src == "Community report":
        return "Reported by a driver in the last 2 hours"
    return "Source: " + src


def card_html(p, status, src, tag=None):
    km = dist_km(p)
    free = free_spaces(p)
    if free is not None:
        spaces = "%d / %d spaces" % (free, p["total"])
    else:
        spaces = "Usually about %d%% full now" % round(occupancy_estimate(p, now_uae())[0])
    return ('<div class="pf-cardhead"><div>'
            + ('<div class="pf-eyebrow" style="color:var(--blue)">★ %s</div>' % esc(tag) if tag else "")
            + '<div class="pf-name">%s</div><div class="pf-sub">%s%s</div></div>%s</div>'
            % (esc(pname(p)), esc(where(p)), "", pill(status, src))
            + '<span class="pf-tag">%s</span>' % esc(p["type"])
            + '<div class="pf-tiles"><div><small>Distance</small><b>%s</b></div><div><small>Walk</small><b>%s</b></div>'
              '<div><small>Price</small><b>%s</b></div></div>' % ("%.1f km" % km, walk_text(km), esc(price_text(p)))
            + '<div class="pf-foot"><span>%s</span><span>%s</span></div>' % (spaces, esc(hours_text(p)))
            + '<div class="pf-src">%s</div>' % esc(src_text(src)))


def parking_card(p, ctx, tag=None, show_start=False):
    status, src = effective_status(p)
    saved = p["id"] in SAVED
    with st.container(key="card_%s_%s" % (ctx, p["id"])):
        md(card_html(p, status, src, tag))
        c1, c2, c3 = st.columns(3)
        c1.button("Details", key="%s_d_%s" % (ctx, p["id"]), on_click=cb_open, args=(p["id"],), use_container_width=True)
        c2.link_button("Directions", directions_url(p), use_container_width=True)
        c3.button("♥ Saved" if saved else "♡ Save", key="%s_s_%s" % (ctx, p["id"]), on_click=cb_toggle_save,
                  args=(p["id"],), use_container_width=True)
        if show_start:
            st.button("Start Parking", key="%s_t_%s" % (ctx, p["id"]), on_click=cb_start_parking, args=(p["id"],),
                      type="primary", use_container_width=True)


def banner(p, text, label="Recommended for you", key="rec"):
    md('<div class="pf-banner"><div class="pf-bicon">✨</div><div><div class="pf-b1">%s</div>'
       '<div class="pf-b2">%s</div><div class="pf-b3">%s</div></div></div>' % (esc(label.upper()), esc(pname(p)), esc(text)))
    st.button("View details", key="%s_v_%s" % (key, p["id"]), on_click=cb_open, args=(p["id"],))


def info_card(icon, head, text, key, button=None, target=None):
    with st.container(key="card_%s" % key):
        left, right = st.columns([4, 1.4])
        left.markdown('<div class="pf-row"><div class="pf-icon">%s</div><div><div class="pf-rowt">%s</div>'
                      '<div class="pf-rowd">%s</div></div></div>' % (icon, esc(head), esc(text)), unsafe_allow_html=True)
        if button:
            right.button(button, key="btn_" + key, on_click=cb_go, args=(target,), use_container_width=True)


def chips(options, key, default):
    try:
        value = st.pills("Filter", options, default=default, key=key, label_visibility="collapsed")
    except Exception:           # older Streamlit versions have no pills
        value = st.radio("Filter", options, index=options.index(default), key=key, horizontal=True,
                         label_visibility="collapsed")
    return value or default


def ref_caption():
    st.caption("Distances are measured from %s (straight-line estimates). Change it on the Nearby page." % ss.ref["label"])


def footer():
    st.caption("Prototype · locations © OpenStreetMap contributors · no live availability sensors · built with help from AI tools"
               if DATA_INFO["source"] != "demo" else "Prototype · demo data, not live availability · built with help from AI tools")


def cards_grid(items, ctx, cols=2, **kw):
    """Parking cards side by side on a wide screen (they stack on a phone)."""
    for i in range(0, len(items), cols):
        for col, p in zip(st.columns(cols), items[i:i + cols]):
            with col:
                parking_card(p, ctx, **kw)


def info_grid(specs, cols=2):
    """specs = list of argument tuples for info_card."""
    for i in range(0, len(specs), cols):
        for col, spec in zip(st.columns(cols), specs[i:i + cols]):
            with col:
                info_card(*spec)


def hero_style():
    for name in ("hero.jpg", "hero.jpeg", "hero.png", "dubai.jpg", "dubai.png"):
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                return "background-image:url(data:image/%s;base64,%s)" % ("png" if name.endswith("png") else "jpeg", b64)
            except OSError:
                pass
    return ""


# ================================================================= 8. PAGES ====
def page_home():
    _, right = st.columns([6, 1])
    right.button("🌙" if ss.theme == "light" else "☀️", key="home_theme", on_click=cb_theme, help="Light / dark mode")
    md('<div class="pf-hero" style="%s"><div class="pf-brand">📍 PARKFINDER UAE</div>'
       '<div class="pf-h1">Find parking near your destination</div>'
       '<div class="pf-hsub">Street bays and garages across Dubai, Sharjah and Ajman.</div></div>' % hero_style())
    with st.form("home_form"):
        c1, c2 = st.columns([3, 1.4])
        c1.text_input("Search", key="home_q", placeholder="Where do you want to park?", label_visibility="collapsed")
        c2.form_submit_button("Find Parking", type="primary", on_click=cb_search, args=("home_q",), use_container_width=True)
    info_grid([("🎯", "Enable location", "Show every parking spot near you, including street parking", "h_loc", "Open →", "nearby"),
               ("✨", "Smart Recommendation", "Let us pick the best parking for you.", "h_rec", "Try →", "nearby"),
               ("🧭", "Nearby Parking", "Parking around you, with a free-parking filter and our best pick.", "h_near", "Open →", "nearby"),
               ("⏱️", "Parking Timer", "Keep track of how long you've been parked.", "h_timer", "Open →", "timer"),
               ("⚡", "EV Charging", "Find electric-car charging stations near you.", "h_ev", "Open →", "ev"),
               ("🚗", "Where did I park?", "Save your parking spot and get walking directions back to your car.", "h_car", "Open →", "car"),
               ("🧮", "Cost Calculator", "Estimate your parking cost before you park.", "h_calc", "Open →", "calc")], cols=2)
    c1, c2 = st.columns([4, 1])
    c1.markdown('<div class="pf-eyebrow" style="margin-top:14px">Nearby</div><div class="pf-title">Nearby parking</div>', unsafe_allow_html=True)
    c2.button("See all", key="home_all", on_click=cb_go, args=("search",))
    ref_caption()
    data_status("home")
    cards_grid(sorted(PARKINGS, key=dist_km)[:3], "home", cols=3)
    md('<div class="pf-eyebrow" style="margin-top:14px">Explore</div><div class="pf-title">Map view</div>')
    info_card("🗺️", ("All {:,} parking places mapped in OpenStreetMap" if DATA_INFO["source"] != "demo" else "{:,} demo parking places").format(len(PARKINGS)), "Pick a city, then tap a pin for details.", "h_map", "Open →", "map")
    info_card("📍", "ParkFinder UAE", "Street and garage parking across Dubai, Sharjah and Ajman.", "h_about", "About", "about")
    footer()


FILTER_CHIPS = ["All", "Free", "Paid", "Street", "Garage"]
STATUS_FILTER = {"Any": None, "Available": "Available", "Limited": "Almost Full", "Full": "Full", "Unknown": "Unknown"}


def passes_chip(p, chip):
    return (chip == "All" or (chip == "Free" and p["price"] == 0) or (chip == "Paid" and ((p["price"] or 0) > 0 or p.get("fee") == "yes"))
            or (chip in ("Street", "Garage") and p["type"] == chip))


def page_search():
    title(None, "Search results")
    with st.form("search_form"):
        c1, c2 = st.columns([4, 1])
        c1.text_input("Search", value=ss.q, key="search_q", placeholder="Where do you want to park?",
                      label_visibility="collapsed")
        c2.form_submit_button("Go", type="primary", on_click=cb_search, args=("search_q",), use_container_width=True)
    chip = chips(FILTER_CHIPS, "chip", "All")
    with st.expander("More filters"):
        f1, f2, f3 = st.columns(3)
        city = f1.selectbox("City", ["All"] + CITIES)
        avail = f2.selectbox("Availability", list(STATUS_FILTER))
        within = f3.selectbox("Within", ["Any", "1 km", "3 km", "5 km", "10 km", "25 km"])
    words = ss.q.lower().split()
    items = []
    for p in PARKINGS:
        hay = " ".join([p["name"], p["area"], p["city"], p["type"]]).lower()
        if not all(w in hay for w in words) or not passes_chip(p, chip):
            continue
        if city != "All" and p["city"] != city:
            continue
        if STATUS_FILTER[avail] and effective_status(p)[0] != STATUS_FILTER[avail]:
            continue
        if within != "Any" and dist_km(p) > float(within.split()[0]):
            continue
        items.append(p)
    items.sort(key=dist_km)
    ref_caption()
    ranked = recommend(items)
    if ranked:
        banner(ranked[0][0], ranked[0][2])
        st.caption("Rule-based pick from distance, availability and price. It is not AI.")
    st.markdown("**%d parking location%s found**" % (len(items), "" if len(items) == 1 else "s"))
    if not items:
        empty_state("🔍", "No parking locations found.", "Try searching another area or city, or loosen the filters.")
    shown = items[:ss.search_limit]
    cards_grid(shown, "search", cols=2)
    if len(items) > len(shown):
        st.caption("Showing the closest %d of %d." % (len(shown), len(items)))
        st.button("Show 25 more", key="search_more", on_click=cb_more_results, use_container_width=True)
    footer()


def draw_map(city):
    """Pins coloured by status. Returns the id of a tapped pin (or None). Falls back to a plain map / message."""
    color = {"Available": [46, 158, 107], "Almost Full": [233, 162, 59], "Full": [229, 88, 107], "Unknown": [138, 146, 144]}
    rows = []
    for p in PARKINGS:
        if city != "Whole UAE" and p["city"] != city:
            continue
        status = effective_status(p)[0]
        rows.append({"pid": p["id"], "name": pname(p), "label": PILL[status][1], "lat": p["lat"], "lon": p["lon"],
                     "color": color[status]})
    lat, lon, zoom = CITY_VIEW[city]
    try:
        import pydeck as pdk
        layer = pdk.Layer("ScatterplotLayer", data=rows, id="spots", get_position="[lon, lat]", get_fill_color="color",
                          get_line_color=[255, 255, 255], stroked=True, line_width_min_pixels=2, get_radius=180,
                          radius_min_pixels=9 if len(rows) < 300 else 4, radius_max_pixels=18, pickable=True)
        deck = pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom),
                        map_style="dark" if ss.theme == "dark" else "light", tooltip={"text": "{name}\n{label}"})
        try:
            event = st.pydeck_chart(deck, height=520, on_select="rerun", selection_mode="single-object", key="map_" + city)
            objects = event.selection.get("objects", {}).get("spots", [])
            return objects[0]["pid"] if objects else None
        except TypeError:                       # older Streamlit: no tap-to-select
            st.pydeck_chart(deck)
            return None
    except Exception:
        try:
            import pandas as pd
            st.map(pd.DataFrame(rows), latitude="lat", longitude="lon")
        except Exception:
            st.warning("The map isn't available right now, so please use the list below.")
        return None


def page_map():
    title(None, "Parking map", ("All {:,} mapped parking places across the UAE. Pick a city to zoom in, then tap a pin for details." if DATA_INFO["source"] != "demo" else "{:,} demo parking places. Pick a city to zoom in, then tap a pin for details.").format(len(PARKINGS)))
    city = chips(list(CITY_VIEW), "map_city", "Whole UAE")
    pid = draw_map(city)
    md('<div style="display:flex;gap:18px;justify-content:center;color:var(--muted);font-size:.85rem;margin:6px 0 12px">'
       '<span><span style="color:#2E9E6B">●</span> Available</span><span><span style="color:#E9A23B">●</span> Limited</span>'
       '<span><span style="color:#E5586B">●</span> Full</span></div>')
    near = sorted(PARKINGS if city == "Whole UAE" else [p for p in PARKINGS if p["city"] == city], key=dist_km)[:40]
    labels = {p["id"]: "%s · %s · %.1f km" % (pname(p), p["area"], dist_km(p)) for p in near}
    pick = st.selectbox("Or choose one of the 40 closest spots", ["—"] + list(labels), format_func=lambda i: labels.get(i, "—"))
    chosen = pid or (pick if pick != "—" else None)
    if chosen:
        parking_card(BY_ID[chosen], "map", tag="Selected")
    else:
        st.caption("Tap a pin on the map, or choose a spot above.")
    st.markdown("**Where we cover**")
    cols = st.columns(3)
    for col, c in zip(cols, CITIES):
        col.metric(c, "{:,}".format(sum(1 for p in PARKINGS if p["city"] == c)))
    st.caption("Total: {:,} parking places · {:,} with a mapped capacity · {:,} marked free".format(
        len(PARKINGS), sum(1 for p in PARKINGS if p.get("capacity")), sum(1 for p in PARKINGS if p["price"] == 0)))
    data_status("map")
    footer()


def use_my_location():
    """'Enable location' - the browser itself asks the person for permission. Nothing is stored."""
    with st.container(key="card_geo"):
        md('<div style="font-weight:700">🎯 Enable location</div>'
           '<div style="color:var(--muted);font-size:.9rem;margin-bottom:6px">Tap the button. Your browser will ask for '
           'permission, then we measure distances from where you are. Your position stays in this session only.</div>')
        if streamlit_geolocation is None:
            st.caption("Location button not installed (pip install streamlit-geolocation). Type an area below instead.")
            return
        loc = streamlit_geolocation()
        lat, lon = (loc or {}).get("latitude"), (loc or {}).get("longitude")
        if lat is None or lon is None:
            st.caption("Waiting for permission... If nothing happens, allow location for this site in your browser, "
                       "or type an area below.")
            return
        key = (round(lat, 5), round(lon, 5))
        if ss.get("geo_applied") != key:
            ss.geo_applied = key
            nearest = min(haversine_km(lat, lon, p["lat"], p["lon"]) for p in PARKINGS)
            if nearest > 150:
                ss.nearby_msg = ("Your location is %.0f km from the nearest demo parking, so these distances are not "
                                 "useful. Type a UAE area below instead." % nearest)
            else:
                ss.ref = {"label": "your location", "pt": (lat, lon)}
                ss.nearby_msg = "Using your device location (accuracy about %s m)." % int(loc.get("accuracy") or 0)


def page_nearby():
    title("Nearby", "Nearby Parking", "Use your location, filter for free parking, and see our best pick for you.")
    use_my_location()
    with st.form("nearby_form"):
        c1, c2 = st.columns([3, 1.4])
        c1.text_input("Area", key="nearby_q", placeholder="e.g. Dubai Marina, Deira, Mall of the Emirates",
                      label_visibility="collapsed")
        c2.form_submit_button("Set location", type="primary", on_click=cb_set_area, use_container_width=True)
    if ss.nearby_msg:
        st.caption(ss.nearby_msg)
    ref_caption()
    st.button("Reset to Downtown Dubai", key="n_reset", on_click=cb_reset_area)
    free_only = st.toggle("Free parking only")
    items = [p for p in sorted(PARKINGS, key=dist_km) if not free_only or p["price"] == 0]
    ranked = recommend(items)
    if ranked:
        banner(ranked[0][0], "Recommended: %s" % ranked[0][2], label="Best parking", key="best")
    if not items:
        empty_state("🔍", "No parking locations found.", "Turn off the free filter or set another area.")
    cards_grid(items[:12], "near", cols=2)
    if len(items) > 12:
        st.caption("Showing the 12 closest. Use Search to see all %d." % len(items))
    footer()


def page_saved():
    title(None, "Saved Parking", "Your saved parking locations.")
    items = [BY_ID[i] for i in SAVED]
    if not items:
        empty_state("♡", "Nothing saved yet", "Save parking locations so you can quickly find them again.")
    cards_grid(items, "saved", cols=2, show_start=True)
    footer()


def page_profile():
    title("Your account", "Profile", "Review the details linked to your ParkFinder account.")
    u = ss.user
    info_card("✉️", u["name"], u["email"] or "Guest mode: nothing is linked to an email.", "p_user")
    with st.container(key="card_p_theme"):
        st.toggle("Dark mode", value=ss.theme == "dark", on_change=cb_theme, key="dark_toggle")
        st.caption("Your theme is remembered while the app is open.")
    if u.get("guest"):
        info_card("👤", "Guest mode", "Saved spots stay on this computer. Log out to create an account.", "p_guest")
    elif u["email"] and u["email"] in load_json("users.json", {}):
        with st.container(key="card_p_delete"):
            md('<div class="pf-row"><div class="pf-icon">🗑️</div><div><div class="pf-rowt">Delete account</div>'
               '<div class="pf-rowd">Permanently removes your ParkFinder account and your saved spots. This cannot be undone.</div></div></div>')
            sure = st.checkbox("I understand this cannot be undone", key="del_sure")
            st.button("Delete my account", key="del_btn", on_click=cb_delete_account, disabled=not sure)
    st.button("Log out", key="logout", on_click=cb_logout, use_container_width=True)
    footer()


def page_about():
    title("About", "Parking in the UAE, without the circling",
          "ParkFinder UAE brings street bays and paid garages across Dubai, Sharjah and Ajman into one simple view, so you "
          "can see what is available, what it costs and how far you will walk before you set off.")
    info_card("🔍", "Search or tap a pin", "Look up an area, a landmark or a city and see what is free right now.", "a1")
    info_card("✨", "Compare at a glance", "Distance, walking time and hourly price sit side by side on every card.", "a2")
    info_card("🧭", "Drive straight there", "Open directions in one tap, or save the spot to your favourites for later.", "a3")
    md('<div class="pf-eyebrow" style="margin-top:14px">Coverage</div><div class="pf-title">Where we cover</div>')
    for c in CITIES:
        info_card("📍", c, ("{:,} parking places mapped" if DATA_INFO["source"] != "demo" else "{:,} demo parking places").format(sum(1 for p in PARKINGS if p["city"] == c)), "cov_" + c)
    with st.container(key="card_a_how"):
        md('<div class="pf-eyebrow">How we choose</div><div class="pf-title" style="font-size:1.5rem">Free street bays and paid garages, side by side</div>'
           '<div class="pf-lead">Every listing shows whether it is free or paid, a street bay or a garage, its opening hours and how '
           'many spaces are free. Locations come from OpenStreetMap and refresh every 30 minutes. Live free-space counts are not published for them, '
           'so availability shows a typical estimate for the day and time (marked "Usually..."), replaced by driver reports when '
           'they exist, and the top suggestion is a simple visible score of distance, availability and price.</div>')
        st.button("Browse parking", key="a_browse", on_click=cb_go, args=("search",), type="primary")
    footer()


def page_car():
    st.button("← Home", key="car_back", on_click=cb_go, args=("home",))
    title(None, "Where did I park?", "Save your spot when you leave the car, then get walking directions back to it later.")
    if ss.get("car") is None and has_account():
        ss.car = load_json("car.json", {}).get(user_key())
    car = ss.car
    with st.container(key="card_car_save"):
        md('<div style="font-weight:700">1. Save my parking spot</div>'
           '<div style="color:var(--muted);font-size:.95rem;margin-bottom:6px">Stand next to your car and tap the location '
           'button. Your browser will ask for permission. Then tap Save.</div>')
        lat = lon = None
        if streamlit_geolocation is None:
            st.caption("Location button not installed (pip install streamlit-geolocation).")
        else:
            loc = streamlit_geolocation()
            lat, lon = (loc or {}).get("latitude"), (loc or {}).get("longitude")
            if lat is None or lon is None:
                st.caption("Waiting for permission... allow location for this site in your browser.")
            else:
                st.caption("Location found (accuracy about %s m)." % int(loc.get("accuracy") or 0))
        st.button("Save my parking spot here", key="car_save", type="primary", disabled=lat is None,
                  on_click=cb_car_save, args=(lat, lon), use_container_width=True)
    if car:
        ago = max(0, time.time() - car["ts"])
        saved_at = datetime.datetime.fromtimestamp(car["ts"], UAE_TZ).strftime("%a %d %b, %H:%M")
        with st.container(key="card_car_find"):
            md('<div style="font-weight:700">2. Find my car</div>')
            st.write("**Saved:** %s (%s ago)" % (saved_at, fmt_duration(ago)))
            if lat is not None:
                d = haversine_km(lat, lon, car["lat"], car["lon"])
                st.write("**Distance from you now:** %s (%s)" % (("%d m" % round(d * 1000)) if d < 1 else ("%.1f km" % d), walk_text(d)))
            st.link_button("Walking directions to my car", "https://www.google.com/maps/dir/?api=1&destination=%s,%s&travelmode=walking"
                           % (car["lat"], car["lon"]), icon=":material/directions_walk:", type="primary", use_container_width=True)
            st.button("Clear saved spot", key="car_clear", on_click=cb_car_clear, use_container_width=True)
        st.caption("Your spot is stored for you only (guests: for this visit only; sign in to keep it). Directions open in Google Maps, which uses your phone's location.")
    else:
        st.info("No parking spot saved yet.")
    footer()


def ev_km(c):
    lat, lon = ss.ref["pt"]
    return haversine_km(lat, lon, c["lat"], c["lon"])


def cb_ev_more():
    ss.ev_limit = ss.get("ev_limit", 10) + 10


def cb_ev_refresh():
    clear = getattr(osm_chargers, "clear", None)
    if clear:
        clear()
    ev_failure_note().update(t=0.0)
    st.toast("Refreshing charging stations...")


def ev_card_html(c):
    km = ev_km(c)
    fee = {"no": "Free to use", "yes": "Paid"}.get(c["fee"], "Fee not listed")
    plugs = "".join('<span class="pf-tag" style="margin-right:6px">%s</span>' % esc(x) for x in c["plugs"]) or \
        '<span class="pf-tag">Plug types not listed</span>'
    return ('<div class="pf-cardhead"><div><div class="pf-name">⚡ %s</div><div class="pf-sub">%s%s</div></div></div>'
            % (esc(pname(c)), esc(c["city"] if not c["area"] else "%s · %s" % (c["area"], c["city"])),
               (" · " + esc(c["operator"])) if c["operator"] and c["operator"].lower() not in c["name"].lower() else "")
            + plugs
            + '<div class="pf-tiles"><div><small>Distance</small><b>%s</b></div><div><small>Power</small><b>%s</b></div>'
              '<div><small>Points</small><b>%s</b></div></div>'
            % ("%.1f km" % km, ("%s kW" % num(c["kw"])) if c["kw"] else "Not listed", c["points"] or "Not listed")
            + '<div class="pf-foot"><span>%s</span><span>%s</span></div>' % (esc(fee), esc(c["hours"] or "Opening hours not listed"))
            + '<div class="pf-src">Source: OpenStreetMap volunteers. Live free/busy status is not available.</div>')


def page_ev():
    title("EV", "EV Charging", "Find electric-car charging stations across Dubai, Sharjah and Ajman.")
    use_my_location()
    if ss.nearby_msg:
        st.caption(ss.nearby_msg)
    ref_caption()
    chargers, info = load_chargers()
    if info["source"] == "osm":
        st.caption("📡 %d charging stations from OpenStreetMap · updated %s (UAE time) · refreshes every 30 minutes."
                   % (len(chargers), fmt_updated(info["fetched"])))
    elif info["source"] == "saved copy":
        st.warning("OpenStreetMap is busy right now, so this is the last saved list from %s." % fmt_updated(info["fetched"]))
    else:
        st.warning("OpenStreetMap's free server is busy right now, so no charging stations can be shown yet. "
                   "Wait a minute and tap Refresh now.")
        st.caption("Technical detail: %s" % info["error"])
    st.button("Refresh now", key="ev_refresh", on_click=cb_ev_refresh)
    plug = st.radio("Plug type", ["Any"] + [p[0] for p in EV_PLUGS], horizontal=True, key="ev_plug")
    items = sorted([c for c in chargers if plug == "Any" or plug in c["plugs"]], key=ev_km)
    if chargers and not items:
        st.info("No charging station with %s plugs is listed. Many stations don't list their plug type, so try 'Any'." % plug)
    if items:
        try:
            import pydeck as pdk
            rows = [{"name": pname(c), "lat": c["lat"], "lon": c["lon"]} for c in items[:300]]
            lat, lon = ss.ref["pt"]
            st.pydeck_chart(pdk.Deck(layers=[pdk.Layer("ScatterplotLayer", data=rows, get_position="[lon, lat]", get_fill_color=[30, 120, 220],
                                                       get_line_color=[255, 255, 255], stroked=True, line_width_min_pixels=2,
                                                       get_radius=150, radius_min_pixels=6, radius_max_pixels=14, pickable=True)],
                                     initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=10.5),
                                     map_style="dark" if ss.theme == "dark" else "light", tooltip={"text": "{name}"}), height=380)
        except Exception:
            pass
    limit = ss.get("ev_limit", 10)
    for i in range(0, len(items[:limit]), 2):
        for col, c in zip(st.columns(2), items[i:min(i + 2, limit)]):
            with col:
                with st.container(key="card_ev_%s" % c["id"]):
                    md(ev_card_html(c))
                    st.link_button("Directions", directions_url(c), icon=":material/directions:", use_container_width=True)
    if len(items) > limit:
        st.button("Show more (%d left)" % (len(items) - limit), key="ev_more", on_click=cb_ev_more)
    st.caption("Tip: charging station details are added by volunteers, so plug type and power may be missing. "
               "Check the operator's app before you go.")
    footer()


def page_timer():
    t = ss.timer
    st.button("← Home", key="timer_back", on_click=cb_go, args=("home",))
    title(None, "Parking Timer", "Start the timer yourself when you park. It uses real timestamps, so it stays accurate.")
    p = BY_ID.get(t["parking"])
    st.markdown("**Parking:** " + (pname(p) if p else "none selected (manual timer)"))
    if t["state"] == "idle":
        st.text_input("Rate in AED per hour (optional)", key="timer_rate", placeholder="e.g. 5 or 2.50")
    timer_clock()
    b1, b2, b3, b4 = st.columns(4)
    b1.button("START", on_click=cb_timer_start, disabled=t["state"] != "idle", type="primary", use_container_width=True)
    b2.button("RESUME" if t["state"] == "paused" else "PAUSE", on_click=cb_timer_pause,
              disabled=t["state"] not in ("running", "paused"), use_container_width=True)
    b3.button("STOP", on_click=cb_timer_stop, disabled=t["state"] not in ("running", "paused"), type="primary", use_container_width=True)
    b4.button("RESET", on_click=cb_timer_reset, disabled=t["state"] == "idle", use_container_width=True)
    if t["state"] == "stopped":
        with st.container(key="card_t_done"):
            st.subheader("Parking Session Complete")
            st.write("**Parking:** " + (pname(p) if p else "Manual timer"))
            st.write("**Duration:** " + fmt_duration(t["acc"]))
            if t["rate"] is not None:
                st.success("Estimated cost: AED %.2f" % estimate_cost(t["rate"], t["acc"] / 60)[2])
                st.caption("An estimate based on AED %s/hour. The official fee may be different." % num(t["rate"]))
            else:
                st.caption("Add a rate next time to see an estimated cost.")
    footer()


def _live(fn):
    """Re-draw the clock every second when this Streamlit version supports fragments."""
    fragment = getattr(st, "fragment", None)
    if fragment:
        try:
            return fragment(run_every=1)(fn)
        except TypeError:
            pass
    return fn


@_live
def timer_clock():
    t = ss.timer
    e = t_elapsed(t)
    md("<div style='text-align:center;font-size:4rem;font-weight:800;color:var(--blue)'>%s</div>"
       "<div style='text-align:center;color:var(--muted)'>%s</div>"
       % (fmt_clock(e), "Parked for " + fmt_duration(e) if t["state"] != "idle" else "Press START when you park."))
    if t["rate"] is not None and t["state"] != "idle":
        md("<div style='text-align:center;font-weight:800'>Estimated cost: AED %.2f <span style='font-weight:400'>(estimate)</span></div>"
           % estimate_cost(t["rate"], e / 60)[2])


def page_calc():
    st.button("← Home", key="calc_back", on_click=cb_go, args=("home",))
    title(None, "Cost Calculator", "An estimate only. It does not know the official parking fee.")
    rate = st.number_input("Parking rate (AED per hour)", min_value=0.0, step=0.5, key="calc_rate")
    c1, c2 = st.columns(2)
    hours = c1.number_input("Duration: hours", min_value=0, step=1, key="calc_hours")
    mins = c2.number_input("Duration: minutes", min_value=0, step=5, key="calc_mins")
    free = st.number_input("Free period in minutes (optional)", min_value=0.0, step=5.0, key="calc_free")
    use_cap = st.checkbox("Use a maximum daily charge", key="calc_use_cap")
    cap = st.number_input("Maximum daily charge (AED)", min_value=0.0, step=1.0, key="calc_cap", disabled=not use_cap)
    total = hours * 60 + mins
    if total <= 0:
        st.info("Enter a parking duration to see the estimate.")
        return
    billable, raw, cost = estimate_cost(rate, total, free, cap if use_cap else None)
    with st.container(key="card_c_result"):
        st.markdown("**Parking rate:** AED %s/hour  \n**Duration:** %s" % (num(rate), fmt_duration(total * 60)))
        if free:
            st.markdown("**Free period:** %s minutes" % num(free))
        st.markdown("**Calculation:** %s × %s hours = AED %.2f" % (num(rate), num(billable / 60), raw))
        if use_cap and cost < raw:
            st.markdown("Daily maximum of AED %s applied." % num(cap))
        st.success("Estimated cost: AED %.2f" % cost)
        st.caption("This is an estimate. The official parking fee may be different.")
    footer()


def weekly_pattern(p):
    """Typical busyness for every weekday at four times, plus today's quietest hour. Clearly labelled as an estimate."""
    now = now_uae()
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    times = [(9, "9 AM"), (13, "1 PM"), (18, "6 PM"), (21, "9 PM")]
    base = now - datetime.timedelta(days=now.weekday())
    head = "".join("<th style='padding:4px 6px;%s'>%s</th>" % ("color:var(--blue)" if i == now.weekday() else "", d) for i, d in enumerate(days))
    body = ""
    for hour, label in times:
        cells = ""
        for i in range(7):
            dt = (base + datetime.timedelta(days=i)).replace(hour=hour, minute=0)
            pct = occupancy_estimate(p, dt)[0]
            colour = "#2E9E6B" if pct < 75 else "#E9A23B" if pct < 95 else "#E5586B"
            cells += "<td style='padding:4px 6px;text-align:center;color:%s;font-weight:700'>%d%%</td>" % (colour, round(pct))
        body += "<tr><td style='padding:4px 6px;color:var(--muted)'>%s</td>%s</tr>" % (label, cells)
    best = min((occupancy_estimate(p, now.replace(hour=h, minute=0))[0], h) for h in range(6, 23))[1]
    with st.container(key="card_det_week"):
        md('<div class="pf-rowt" style="font-size:1.1rem">Typical busyness this week</div>'
           '<div class="pf-rowd">How full this kind of place usually is (percent of spaces taken). It is an ESTIMATE from a simple '
           'daily pattern, not a live count. When 3+ drivers report for the same weekday and hour, their average is used instead.</div>'
           '<div style="overflow-x:auto"><table style="width:100%%;font-size:.85rem;border-collapse:collapse"><tr><th></th>%s</tr>%s</table></div>'
           '<div class="pf-rowd" style="margin-top:6px">Usually quietest today around <b>%s</b>.</div>'
           % (head, body, datetime.time(best).strftime("%I %p").lstrip("0")))


def details_page(p):
    status, src = effective_status(p)
    km = dist_km(p)
    saved = p["id"] in SAVED
    st.button("← Back", key="det_back", on_click=cb_close)
    md('<div class="pf-cardhead"><div><div class="pf-title">%s</div><div class="pf-sub">%s</div></div>%s</div>'
       % (esc(pname(p)), esc(where(p)), pill(status, src)))
    free = free_spaces(p)
    rows = [("Parking type", p["type"]), ("Price", price_text(p)), ("Distance", "%.1f km from %s" % (km, ss.ref["label"])),
            ("Walking time", walk_text(km)), ("Opening hours", hours_text(p)),
            ("Spaces", "%d free of %d (%.1f%% occupied)" % (free, p["total"], p["occupied"] / p["total"] * 100) if free is not None
             else "About %d%% full now%s" % (round(occupancy_estimate(p, now_uae())[0]),
                                        " · mapped capacity %d" % p["capacity"] if p.get("capacity") else "")),
            ("Availability", "%s (%s)" % (PILL[status][1], src)), ("Location data", "Demo data (approximate coordinates)" if p.get("src") == "demo"
             else "OpenStreetMap contributors (real mapped location)")]
    with st.container(key="card_det_info"):
        md("".join('<div class="pf-info"><span>%s</span><b>%s</b></div>' % (esc(k), esc(v)) for k, v in rows))
        c1, c2 = st.columns(2)
        c1.link_button("Get Directions", directions_url(p), use_container_width=True)
        c2.button("Remove Saved" if saved else "Save Parking", key="det_save", on_click=cb_toggle_save, args=(p["id"],), use_container_width=True)
        c3, c4 = st.columns(2)
        c3.button("Start Parking", key="det_start", on_click=cb_start_parking, args=(p["id"],), type="primary", use_container_width=True)
        c4.button("Calculate Cost", key="det_calc", on_click=cb_calc_cost, args=(p["id"],), use_container_width=True)
    weekly_pattern(p)
    with st.container(key="card_det_report"):
        md('<div class="pf-rowt" style="font-size:1.1rem">Report current availability</div>'
           '<div class="pf-rowd">Community reports come from users like you. They are labelled and expire after 2 hours.</div>')
        with st.form("report_" + p["id"], clear_on_submit=True):
            labels = {"available": "Available", "almost_full": "Limited (almost full)", "full": "Full"}
            fb = st.radio("What is it like right now?", list(labels), format_func=labels.get, horizontal=True)
            av = st.radio("Is there a free space right now?", ["yes", "no"], horizontal=True)
            if st.form_submit_button("Submit report", type="primary"):
                reports = load_json("reports.json", [])
                reports.append({"parking_id": p["id"], "parking_name": p["name"], "feedback_type": fb,
                                "available": av, "timestamp": time.time()})
                save_json("reports.json", reports)
                st.toast("Thanks! Saved as a community report.")
                st.rerun()
    footer()


# ================================================================ 9. LOGIN ====
def auth_screen():
    set_width(520)
    view = ss.auth_view
    heads = {"login": ("➜", "Welcome back", "Log in to your account"),
             "signup": ("👤", "Create your account", "Sign up to get started"),
             "reset": ("✉️", "Reset password", "We'll send you a link to reset it")}
    icon, head, sub = heads[view]
    md('<div style="text-align:center;margin-top:1.5rem"><div style="display:inline-grid;place-items:center;width:62px;height:62px;'
       'border-radius:18px;background:#17181C;color:#fff;font-size:1.7rem">%s</div>'
       '<div class="pf-title" style="margin-top:.8rem">%s</div><div class="pf-lead">%s</div></div>' % (icon, head, sub))
    if ss.auth_msg:
        st.info(ss.auth_msg)
    with st.container(key="card_auth"):
        if view in ("login", "signup") and SHOW_GOOGLE_LOGIN:
            st.button("Continue with Google", key="g_btn", on_click=cb_google, use_container_width=True)
            if google_configured():
                st.caption("If Google sends you back to this page, open the app in a normal (not private/Incognito) window "
                           "or allow cookies for this site, then try again.")
                if ss.get("google_dbg"):
                    st.caption(ss.google_dbg)
            md('<div style="text-align:center;color:var(--muted);margin:6px 0">— OR —</div>')
        if view == "login":
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                pw = st.text_input("Password", type="password", placeholder="••••••••")
                if st.form_submit_button("Log in", type="primary", use_container_width=True):
                    user = check_login(email, pw)
                    if user:
                        ss.user, ss.auth_msg = user, ""
                        st.rerun()
                    st.error("Email or password is incorrect.")
            st.button("Forgot password?", key="to_reset", on_click=cb_auth_view, args=("reset",))
        elif view == "signup":
            with st.form("signup_form"):
                name = st.text_input("Name", placeholder="Your name")
                email = st.text_input("Email", placeholder="you@example.com")
                pw = st.text_input("Password", type="password", placeholder="At least 8 characters")
                pw2 = st.text_input("Confirm Password", type="password", placeholder="Type it again")
                if st.form_submit_button("Create account", type="primary", use_container_width=True):
                    if pw != pw2:
                        st.error("The two passwords don't match.")
                    else:
                        user, error = make_account(name, email, pw)
                        if user:
                            ss.user = user
                            st.rerun()
                        st.error(error)
        else:
            with st.form("reset_form"):
                st.text_input("Email address", placeholder="you@example.com")
                if st.form_submit_button("Send reset link", type="primary", use_container_width=True):
                    st.info("This school prototype can't send emails, so no link was sent. You can create a new "
                            "account instead.")
    if view == "login":
        st.button("Don't have an account? Create one", key="to_signup", on_click=cb_auth_view, args=("signup",), use_container_width=True)
    else:
        st.button("← Back to log in", key="to_login", on_click=cb_auth_view, args=("login",), use_container_width=True)
    st.button("Continue as guest", key="guest_btn", on_click=cb_guest, use_container_width=True)
    st.caption("Accounts are stored only on this computer (prototype). Passwords are salted and hashed, never saved as typed.")


# ============================================================ 9b. HELP CHATBOT ====
# A simple RULE-BASED helper (keywords -> answers built from the app's own data). It is not AI and never invents facts.
QUICK_QUESTIONS = ["Nearest parking", "EV charging near me", "Free parking near me", "Cost for 3 hours at AED 5", "Where did I park?", "What is Salik?"]


def bot_places(items, n=3):
    lines = []
    for p in items[:n]:
        lines.append("- **%s** (%s): %.1f km, %s walk, %s" % (pname(p), where(p), dist_km(p), walk_text(dist_km(p)), price_text(p)))
    return "\n".join(lines)


def bot_reply(text):
    t = " " + re.sub(r"[^a-z0-9. ]", " ", ar_to_en_keywords(text).lower()) + " "
    has = lambda *words: any((" %s " % w in t) or (w in t and len(w) > 4) for w in words)
    ranked = sorted(PARKINGS, key=dist_km)
    if has("hi", "hello", "hey", "help", "salam"):
        return ("Hi! I'm Parky, your parking helper. I'm a simple keyword bot, not AI, and I only use this app's own data. "
                "Try: **nearest parking**, **free parking**, **garage**, **street parking**, **cost for 3 hours at AED 5**, "
                "**where did I park**, **timer**, **Salik**, or **how accurate is availability**.")
    if has("charger", "charging", "electric", "ev", "tesla"):
        chargers, info = load_chargers()
        near = sorted(chargers, key=ev_km)[:3]
        if not near:
            return "I couldn't load charging stations right now (OpenStreetMap may be busy). Open **EV Charging** on the home page and tap Refresh."
        lines = "\n".join("- **%s** (%s): %.1f km%s" % (pname(c), tr(c["city"]), ev_km(c), (", up to %s kW" % num(c["kw"])) if c["kw"] else "")
                          for c in near)
        return "The closest EV charging stations to %s:\n%s\n\nOpen **EV Charging** for plug types, a map and directions. I can't tell if a charger is free right now." % (
            ss.ref["label"], lines)
    if has("cost", "price", "pay", "fee", "much") and re.search(r"\d", t):
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
        hours = next((float(m) for m in re.findall(r"(\d+(?:\.\d+)?) ?(?:hours|hour|hrs|hr|h)\b", t)), None)
        mins = next((float(m) for m in re.findall(r"(\d+(?:\.\d+)?) ?(?:minutes|minute|mins|min)\b", t)), None)
        rate = next((float(m) for m in re.findall(r"(?:aed|dhs|dh|rate)\s*(\d+(?:\.\d+)?)", t)), None)
        if rate is None:
            rate = next((float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*(?:aed|dhs|dh)", t)), None)
        if (hours is not None or mins is not None) and rate is None:
            rest = [x for x in nums if x != hours and x != mins]
            rate = rest[0] if rest else None
        if rate is not None and (hours is not None or mins is not None):
            minutes = (hours or 0) * 60 + (mins or 0)
            total = estimate_cost(rate, minutes)[2]
            return "At AED %s per hour for %s, the estimated cost is **AED %.2f** (rate x time; the official fee may differ)." % (
                num(rate), fmt_duration(minutes * 60), total)
        return "Tell me the time and the rate, for example: **cost for 3 hours at AED 5**. You can also use the Cost Calculator on the home page."
    if has("free", "no fee", "without paying"):
        free = [p for p in ranked if p["price"] == 0]
        return ("The closest free parking places to %s:\n%s" % (ss.ref["label"], bot_places(free)) if free
                else "I couldn't find a parking place marked free in the current list.")
    for word, kind in (("garage", "Garage"), ("multi", "Garage"), ("street", "Street"), ("roadside", "Street"), ("lot", "Open lot")):
        if has(word):
            sel = [p for p in ranked if p["type"] == kind]
            return ("Closest %s parking to %s:\n%s" % (kind.lower(), ss.ref["label"], bot_places(sel)) if sel
                    else "No %s parking in the current list." % kind.lower())
    if has("nearest", "nearby", "near me", "closest", "close", "around"):
        return "The closest parking places to %s:\n%s\n\nOpen **Nearby** to change the starting point or use your location." % (
            ss.ref["label"], bot_places(ranked))
    if has("cheap", "cheapest", "lowest"):
        priced = sorted([p for p in PARKINGS if p["price"] is not None], key=lambda p: (p["price"], dist_km(p)))
        return ("The cheapest places with a known price:\n%s" % bot_places(priced)) if priced else "No prices are listed in the data."
    if has("where did i park", "my car", "find my car", "car spot", "saved spot", "save my spot", "parked"):
        car = ss.get("car")
        if car:
            return ("Your car spot is saved. [Walking directions to my car](https://www.google.com/maps/dir/?api=1&destination=%s,%s&travelmode=walking)"
                    % (car["lat"], car["lon"]))
        return "Open **Where did I park?** on the home page, allow location, then tap *Save my parking spot here*. Later you can get walking directions back."
    if has("timer", "stopwatch", "how long"):
        return "Open the **Parking Timer** from the home page. Press START when you park. It uses real timestamps and can estimate the cost if you enter a rate."
    if has("salik", "toll"):
        return "Salik is Dubai's road toll system. The **Salik** button at the bottom opens the official site, or the Smart Salik app page on your phone."
    if has("direction", "navigate", "route", "google maps"):
        return "Tap **Directions** on any parking card. It opens Google Maps with that parking place as the destination."
    if has("busy", "full", "available", "availability", "live", "accurate", "estimate"):
        return ("Availability here is a **typical-busyness estimate** for this weekday and time, not a live count. "
                "If at least 3 drivers report the same weekday and hour, the driver average is used instead. Always check on arrival.")
    if has("data", "source", "openstreetmap", "osm", "update", "refresh"):
        return "Parking places come from OpenStreetMap and refresh every 30 minutes. If its free server is busy you'll see a yellow note; tap **Refresh now**."
    if has("location", "permission", "gps"):
        return "On **Nearby** or **Where did I park?**, tap the location button. Your browser asks for permission; your position stays in your session only."
    if has("save", "favourite", "favorite", "heart"):
        return "Tap the heart (**Save**) on a parking card. Open the **Saved** tab to see them. Sign in to keep them between visits."
    if has("who made", "who built", "ai", "chatgpt"):
        return "ParkFinder UAE is a school project. I'm Parky, a rule-based helper that answers from the app's own data; I'm not an AI model."
    return "Sorry, Parky didn't understand that. Try: **nearest parking**, **free parking**, **cost for 3 hours at AED 5**, **where did I park**, or **Salik**."


def cb_bot_ask(question):
    ss.chat = (ss.get("chat") or []) + [("user", question), ("bot", bot_reply(question))]


def cb_bot_send():
    q = str(ss.get("bot_q", "")).strip()
    if q:
        cb_bot_ask(q[:200])


def chatbot():
    """Floating help button in the bottom-right corner."""
    with st.container(key="chatbot"):
        with st.popover("💬 Ask Parky", use_container_width=False):
            st.markdown("**Parky, your parking helper**  \n<span style='font-size:.85rem'>A simple keyword bot, not AI.</span>", unsafe_allow_html=True)
            for role, text in (ss.get("chat") or [])[-8:]:
                with st.chat_message("user" if role == "user" else "assistant"):
                    st.markdown(text)
            if not ss.get("chat"):
                st.caption("Ask me something, or tap a question:")
                for i, q in enumerate(QUICK_QUESTIONS):
                    st.button(q, key="botq_%d" % i, on_click=cb_bot_ask, args=(q,), use_container_width=True)
            with st.form("bot_form", clear_on_submit=True):
                st.text_input("Your question", key="bot_q", placeholder="e.g. nearest free parking", label_visibility="collapsed")
                st.form_submit_button("Send", type="primary", on_click=cb_bot_send, use_container_width=True)
            if ss.get("chat"):
                st.button("Clear chat", key="bot_clear", on_click=lambda: ss.update(chat=[]), use_container_width=True)


# =============================================================== 10. ROUTER ====
if ss.user is None:
    ss.user = google_user()
if ss.user is None:
    auth_screen()
    st.stop()

load_parkings()                     # refreshed from OpenStreetMap at most every 30 minutes
SAVED = get_saved()
PAGES = {"home": page_home, "search": page_search, "map": page_map, "saved": page_saved, "profile": page_profile,
         "nearby": page_nearby, "about": page_about, "timer": page_timer, "calc": page_calc, "car": page_car, "ev": page_ev}
NARROW = {"profile": 760, "about": 900, "timer": 720, "calc": 720, "car": 720}
if ss.detail in BY_ID:
    set_width(900)
    details_page(BY_ID[ss.detail])
else:
    if ss.page in NARROW:
        set_width(NARROW[ss.page])
    PAGES[ss.page]()

chatbot()

with st.container(key="langbtn"):
    st.button("English" if ss.get("lang") == "ar" else "العربية", key="lang_toggle", on_click=cb_lang)

with st.container(key="bottomnav"):
    nav_cols = st.columns(6)
    for col, (page, label, icon) in zip(nav_cols, [("home", "Home", "home"), ("search", "Search", "search"),
                                                    ("map", "Map", "map"), ("saved", "Saved", "favorite"),
                                                    ("profile", "Profile", "person")]):
        with col:
            st.button(label, key="nav_" + page, icon=":material/%s:" % icon, on_click=cb_go, args=(page,),
                      use_container_width=True)
    with nav_cols[5]:                   # opens the official Salik (Dubai road toll) website in a new tab
        st.link_button("Salik", salik_link(), icon=":material/toll:", use_container_width=True)

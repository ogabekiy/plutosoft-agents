# PlutoSoft AI Assistant

Loyiha PlutoSoft xizmatlari haqida savollarga javob beradigan AI yordamchi va mijozlar inboxini birlashtiradi. Agent savolga mos ma'lumotlarni lokal vektor bazasidan qidirib, Claude orqali o'zbek tilida javob yaratadi. Mijozlar Telegram yoki Instagram Direct'dan yozishi, operator esa dashboard'dan suhbatni ko'rib javob berishi mumkin.

## Ishlatilgan texnologiyalar

- **Python** — agent, botlar va webhook serverining asosiy tili.
- **Anthropic Claude API** — mijoz savollariga javob va lead suhbatining qisqa xulosasini yaratadi.
- **SentenceTransformers** — savol va hujjatlarni embeddingga aylantirib, matnni mazmuni bo'yicha qidirishga yordam beradi. Model: `paraphrase-multilingual-MiniLM-L12-v2`.
- **ChromaDB** — embedding va manba matnlarini lokal vektor bazasida saqlaydi va qidiradi.
- **Flask** — Instagram webhook hamda inbox dashboard backend'i.
- **Telegram Bot API** — long polling orqali mijoz xabarlarini qabul qilish va javob yuborish.
- **SQLite** — xabarlar, profil va leadlarni `conversation_history.sqlite3` faylida saqlaydi.
- **python-dotenv** — maxfiy kalitlar va sozlamalarni `.env` faylidan o'qiydi; dashboard'dan model tanlanganda `CLAUDE_MODEL` ni shu faylga yozadi.
- **HTML, CSS va JavaScript** — dashboard interfeysi, dark/light rejim va suhbatlarni boshqarish.

## Talablar

- Python 3
- Claude API ishlatish uchun Anthropic API kaliti
- Telegram ishlatish uchun BotFather'dan olingan bot tokeni
- Instagram ishlatish uchun Meta Developer app, professional Instagram akkaunti va public HTTPS tunnel (masalan, ngrok)

## O'rnatish

Loyiha ildizidan virtual muhit yarating va kerakli Python paketlarini o'rnating:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install anthropic chromadb sentence-transformers flask requests python-dotenv
cp .env.example .env
```

Windows PowerShell'da virtual muhitni faollashtirish:

```powershell
.\.venv\Scripts\Activate.ps1
```

Embedding notebook'ini ishga tushirish kerak bo'lsa, Jupyter'ni ham o'rnating:

```bash
python -m pip install jupyter
```

`.env` ichidagi placeholder qiymatlarni o'zingizning kalit va sozlamalaringiz bilan almashtiring. Haqiqiy `.env` Git'ga qo'shilmaydi.

### Environment o'zgaruvchilari

| O'zgaruvchi | Qachon kerak | Maqsadi |
|---|---|---|
| `ANTHROPIC_API_KEY` | AI ishlashi uchun | Claude API kaliti |
| `CLAUDE_MODEL` | AI ishlashi uchun | Dastur ishga tushgandagi Claude modeli |
| `IG_APP_ID`, `IG_APP_SECRET` | Instagram uchun | Meta app va OAuth |
| `IG_REDIRECT_URI` | Instagram OAuth uchun | Meta sozlamasidagi callback URL |
| `IG_WEBHOOK_VERIFY_TOKEN` | Instagram webhook uchun | Webhook tekshiruvining maxfiy tokeni |
| `IG_ACCESS_TOKEN`, `IG_USER_ID` | Instagram OAuth'dan keyin | Ulangan Instagram akkaunt ma'lumoti; OAuth oqimi `.env` ni yangilaydi |
| `TELEGRAM_BOT_TOKEN` | Telegram bot va `main.py` uchun | Mijozlar bilan yozishadigan bot tokeni |
| `TELEGRAM_BOT_TOKEN2`, `TELEGRAM_USER_ID` | Ixtiyoriy | Lead egasiga qo'shimcha Telegram xabarnomasi |
| `DASHBOARD_PASSWORD` | Dashboard uchun | Dashboard login paroli |
| `DASHBOARD_SECRET_KEY` | Tavsiya qilinadi | Flask sessiyalarini himoyalash uchun tasodifiy maxfiy kalit |

Dashboard'dagi model tanlagich `claude-haiku-5-5`, `claude-sonnet-5-5` va `claude-opus-5-5` variantlaridan birini tanlashga imkon beradi. Tanlov `.env` fayliga saqlanib, ishlayotgan jarayonda darhol qo'llanadi. Joriy model ID'larini [Anthropic model ro'yxatidan](https://platform.claude.com/docs/en/models/overview) tekshirish mumkin.

## Knowledge base tayyorlash

Agent `chroma_db/` ichidagi `plutosoft_uz` ChromaDB kolleksiyasidan foydalanadi. Agar kolleksiya hali yaratilmagan yoki bo'sh bo'lsa, `do_embedding.ipynb` notebook va `plutosoft-uz-chunks.jsonl` / `plutosoft-uz-embedded.jsonl` ma'lumotlari yordamida embeddinglarni tayyorlab, kolleksiyani avval to'ldiring. Embedding modelni birinchi marta olish uchun internet aloqasi kerak.

CLI rejimida agentni ishga tushirish:

```bash
python chat_with_claude.py
```

Suhbatdan chiqish uchun `exit` yoki `quit` yozing.

## Telegram bot

1. Telegram'da [@BotFather](https://t.me/BotFather) orqali bot yarating.
2. Bot tokenini `.env` dagi `TELEGRAM_BOT_TOKEN` qiymatiga kiriting.
3. Botga Telegram'dan `/start` yuboring.
4. Faqat Telegram xizmatini ishga tushiring:

```bash
python tg/connect_to_tg.py
```

Bot long polling ishlatadi, shu sababli Telegram uchun public webhook URL talab qilinmaydi. Xizmat yoki narxga qiziqqan mijozdan agent ism, telefon va ixtiyoriy izohni so'raydi. Tugallangan lead SQLite'ga saqlanadi. `TELEGRAM_BOT_TOKEN2` va `TELEGRAM_USER_ID` to'ldirilsa, egasiga qo'shimcha Telegram bildirishnomasi yuboriladi.

## Instagram Direct

Meta Developer Dashboard'da Instagram Login va `messages` webhook'ini sozlang. `.env` dagi `IG_REDIRECT_URI` Meta'da kiritilgan OAuth callback bilan aynan bir xil bo'lishi kerak. Instagram Login oqimidagi API typing indicator'ni qo'llamaydi.

1. Loyiha ildizidan Instagram serverini ishga tushirib, OAuth'ni ulang:

```bash
python ig/connect_to_ig.py
```

2. Boshqa terminalda public HTTPS tunnel yarating:

```bash
ngrok http 5000
```

3. Meta Webhooks'da callback URL'ni `https://<public-domain>/instagram/webhook` va verify token'ni `.env` dagi `IG_WEBHOOK_VERIFY_TOKEN` qilib sozlang; `messages` hodisasiga obuna bo'ling.
4. `https://<public-domain>/instagram/connect` manzilida Instagram OAuth ruxsatini yakunlang.

Instagram webhook va profil ma'lumotlari Meta ilovasining ruxsatlari, app holati va akkaunt sozlamalariga bog'liq.

## Barcha xizmatlar va dashboard

Instagram hamda Telegram sozlamalari `.env` da mavjud bo'lganda loyiha ildizidan ishga tushiring:

```bash
python main.py
```

Dashboard lokal manzili: `http://127.0.0.1:5000/dashboard`. Public tunnel ishlatilsa, tunnel domenidagi `/dashboard` yo'liga kiring. Dashboard `DASHBOARD_PASSWORD` orqali himoyalangan. Ommaviy tarmoqqa chiqarishdan oldin kuchli, alohida parol va `DASHBOARD_SECRET_KEY` o'rnating.

Dashboard imkoniyatlari:

- Instagram va Telegram suhbatlarini ko'rish, qidirish va kanal bo'yicha filtrlash;
- suhbat ichidan qo'lda matnli javob yuborish;
- dark/light ko'rinishni almashtirish (tanlov brauzerda eslab qolinadi);
- Claude modelini almashtirish;
- lead ismi, telefoni, izohi va AI xulosasini ko'rish.

Xabarlar va leadlar `conversation_history.sqlite3` lokal SQLite bazasida saqlanadi. Lead tugallanganda so'nggi 100 tagacha saqlangan suhbat xabari asosida Claude qisqa xulosa yaratadi. Xulosa generatsiyasi xato bersa ham lead bazaga saqlanadi, faqat xulosa bo'sh qoladi. Ixtiyoriy Telegram bildirishnomasiga xulosa ham qo'shiladi. Dashboard suhbat va lead ro'yxatlarini taxminan har 4 soniyada yangilaydi.

## Loyiha fayllari

- `main.py` — Instagram webhook va Telegram botini birga ishga tushiradi.
- `chat_with_claude.py` — RAG javobi va lead suhbati xulosasini yaratadi.
- `do_embedding.ipynb` — knowledge base uchun embedding tayyorlash notebook'i.
- `cl/chat_store.py` — SQLite xabar, profil va lead ma'lumotlari.
- `cl/send_leads.py` — lead yig'ish, saqlash va xabarnoma.
- `ig/connect_to_ig.py` — Instagram OAuth, webhook va Direct xabarlari.
- `ig/dashboard.py` — dashboard sahifasi va himoyalangan API.
- `ig/templates/`, `ig/static/` — dashboard HTML, CSS va JavaScript.
- `tg/connect_to_tg.py` — Telegram long-polling bot.
- `plutosoft-uz-chunks.jsonl`, `plutosoft-uz-embedded.jsonl` — knowledge base JSONL ma'lumotlari.
- `chroma_db/` — lokal vektor bazasi.
- `conversation_history.sqlite3` — lokal chat tarixi va lead bazasi.

## Hozirgi cheklovlar

Loyiha MVP holatida: dashboard faqat matnli xabar yuboradi, rasm yoki boshqa attachment yubormaydi. Instagram profil ma'lumotlari API orqali topilmasa, dashboard ism yoki ID bilan fallback qiladi. Lead yig'ish jarayonidagi tugallanmagan sessiyalar xotirada turadi va jarayon qayta ishga tushganda saqlanib qolmaydi. Tashqi servislarning ishlashi haqiqiy credential, Meta ruxsatlari va tarmoq ulanishiga bog'liq.

# PlutoSoft AI Assistant

Bu loyiha PlutoSoft kompaniyasi haqida ma'lumot beradigan AI chat assistant bo'lib, foydalanuvchining savollariga kontekstga asoslangan javob qaytaradi. Asosiy maqsad: kompaniya haqida mavjud ma'lumotlarni tez, aniq va doimiy tarzda taqdim etish.

## Loyihaning hozirgi holati

Loyiha hozirgi bosqichida Python asosidagi lokal RAG (Retrieval-Augmented Generation) ilova sifatida ishlamoqda. U quyidagi jarayonlarni bajaradi:

- Savolni qabul qiladi
- Matnlarni vektor embeddingga aylantiradi
- ChromaDB ichidagi ma'lumotlar bazasidan eng mos chunklarni topadi
- Topilgan kontekstni Claude modeli bilan birlashtirib javob yaratadi
- Foydalanuvchiga O'zbek tilida tabiiy va qisqa javob beradi

## Asosiy texnologiyalar

### 1. Python
Python loyiha asosiy tilidir. Bu yerda CLI interfeys, RAG pipeline, embedding va API ishlash logikasi yozilgan.

### 2. Anthropic SDK
`anthropic` paketidan foydalanilgan. Claude modeli API orqali chaqiriladi. U savolga javob berishda asosiy generativ qism vazifasini bajaradi.

### 3. SentenceTransformers
`sentence-transformers` modeli ishlatilgan. U savollar va ma'lumotlar chunklarini vektor ko'rinishga o'tkazadi. Bu orqali semantik qidiruv (semantic search) amalga oshiriladi.

### 4. ChromaDB
ChromaDB lokal vektor bazasi sifatida ishlatilgan. Bu yerda ma'lumotlar chunklari saqlanadi va savolga mos keladigan ma'lumotlar topiladi.

### 5. python-dotenv
`.env` fayldan konfiguratsiya qiymatlarini yuklash uchun `python-dotenv` ishlatilgan. Bu orqali API kaliti va model nomi xavfsiz tarzda saqlanadi.

### 6. Jupyter Notebook
`do_embedding.ipynb` fayli orqali embedding yaratish va ma'lumotlarni sinovdan o'tkazish ishlari amalga oshirilgan. Bu loyiha uchun prototyping va ma'lumot tayyorlash bosqichi bo'ldi.

### 7. JSONL ma'lumotlar fayllari
`plutosoft-uz-chunks.jsonl` va `plutosoft-uz-embedded.jsonl` fayllari ma'lumot bazasi uchun tayyorlangan chunklar va vektorlangan ma'lumotlarni saqlaydi.

## Nima uchun bunlar kerak?

- `SentenceTransformers` bo'lgani sababli savolning ma'nosi qidiriladi, oddiy string mosligidan ko'ra yaxshiroq natija keladi.
- `ChromaDB` tufayli katta ma'lumotlar bazasi ichida tez qidiruv ishlaydi.
- `Claude` yordamida topilgan kontekst asosida aniq, natural va foydali javob qaytariladi.
- `dotenv` orqali API kaliti va model konfiguratsiyasi koddan ajratilib saqlanadi, xavfsizlik yaxshilanadi.
- Local RAG arxitekturasi ma'lumotlar bazasini onlayn tashqariga chiqarmasdan ishlash imkonini beradi.

## Loyihaning ishlash prinsipi

1. `do_embedding.ipynb` orqali ma'lumotlar chunklarga bo'linadi va embeddingga aylantiriladi.
2. Embeddinglar `chroma_db/` katalogidagi ChromaDB bazasiga saqlanadi.
3. Foydalanuvchi savol berganda `generate_answer()` funksiyasi ishlaydi.
4. Savol embeddingga aylantiriladi va ChromaDBdan eng mos natijalar olinadi.
5. Ular `SYSTEM_PROMPT` bilan birga Claude modeliga yuboriladi.
6. Model kontekst asosida javobni qaytaradi.

## Foydalanish

1. `.env` faylini tayyorlang yoki `.env.example` dan nusxa oling.
2. Anthropic API kalitingizni kiriting.
3. Loyihani ishga tushiring:

```bash
python chat_with_claude.py
```

Agar virtual environment ishlatayotgan bo'lsangiz:

```bash
./.venv/bin/python chat_with_claude.py
```

## Instagram DM avtomatik javoblari

`ig/connect_to_ig.py` Instagram Login orqali webhook qabul qiladi va Direct xabarlarga AI javobini yuboradi. Instagram akkaunt professional (Business yoki Creator) bo'lishi kerak.

1. Meta Developer Dashboard'da Instagram Login va Instagram webhook'larini sozlang. Kerakli ruxsatlar kodda `SCOPES` orqali belgilanadi.
2. `.env` ichida `IG_APP_ID`, `IG_APP_SECRET`, `IG_REDIRECT_URI` va maxfiy `IG_WEBHOOK_VERIFY_TOKEN` ni sozlang. Instagram Login OAuth sozlamasidagi redirect URL `.env` dagi `IG_REDIRECT_URI` bilan aynan bir xil bo'lsin.
3. Flask serverni loyiha ildizidan ishga tushiring:

   ```bash
   ./.venv/bin/python ig/connect_to_ig.py
   ```

4. Serverga ommaviy HTTPS URL berish uchun ngrok kabi tunnel oching:

   ```bash
   ngrok http 5000
   ```

5. Meta Developer Dashboard > Webhooks'da Instagram obyekti uchun `https://<ngrok-domen>/instagram/webhook` callback URL va `.env` dagi `IG_WEBHOOK_VERIFY_TOKEN` ni kiriting hamda `messages` maydoniga obuna bo'ling.
6. Brauzerda `https://<ngrok-domen>/instagram/connect` ni ochib, Instagram orqali ruxsat bering. OAuth tugagach `IG_ACCESS_TOKEN` va `IG_USER_ID` `.env` ga yoziladi va Instagram akkaunt webhook'ga obuna qilinadi.
7. Meta ilovasi Published/Live bo'lishi yoki test rejimida xabar yuboruvchi akkaunt tester sifatida qo'shilib, taklifni qabul qilgan bo'lishi kerak. Instagram'da **Connected Tools > Allow Access to Messages** yoqilganini tekshirib, boshqa akkauntdan DM yuboring.

Instagram Login orqali ishlatilayotgan API oqimida typing indicator qo'llanmaydi. Ngrok URL o'zgarsa, Meta Dashboard'dagi webhook callback va `.env` dagi `IG_REDIRECT_URI` ni yangilang.

## Telegram bot

`tg/connect_to_tg.py` Telegram'dan kelgan matnli xabarlarni mavjud `generate_answer()` agentiga yuboradi va javobni foydalanuvchiga qaytaradi. Bot long polling ishlatadi, shuning uchun Telegram uchun public URL yoki webhook sozlash shart emas.

1. Telegram'da [@BotFather](https://t.me/BotFather) orqali bot yarating va bot tokenini oling.
2. Tokenni loyiha ildizidagi `.env` fayliga qo'shing:

   ```env
   TELEGRAM_BOT_TOKEN=BotFather_bergan_token
   ```

3. Loyiha ildizidan botni ishga tushiring:

   ```bash
   ./.venv/bin/python tg/connect_to_tg.py
   ```

4. Telegram'da botni ochib `/start` yuboring, so'ng savolingizni yozing.

Xizmat yoki narxga qiziqish bildirgan mijozdan agent ism, telefon va ixtiyoriy qo'shimcha xabarni so'raydi. To'liq ma'lumot `TELEGRAM_BOT_TOKEN2` orqali `TELEGRAM_USER_ID` ga yuboriladi. Bildirishnoma uchun alohida botni [@BotFather](https://t.me/BotFather) orqali yarating va o'zingiz ham o'sha botga kamida bir marta `/start` yuboring. `.env` da ikkala bot tokeni, `TELEGRAM_USER_ID` va `ANTHROPIC_API_KEY` sozlangan, RAG bazasi tayyor bo'lishi kerak. Javoblar 4096 belgidan uzun bo'lsa, bir nechta xabarga bo'linadi.

Lead yig'ish holati xotirada saqlanadi; dastur qayta ishga tushsa tugallanmagan suhbat holati yangidan boshlanadi. Bildirishnoma yuborilmasa, agent leadni yo'qotmaydi va mijozdan `/retry` yuborib qayta urinishni so'raydi.

Instagram va Telegram'ni birga ishga tushirish uchun loyiha ildizidan:

```bash
./.venv/bin/python main.py
```

Bu Telegram botini long polling bilan va Instagram webhook serverini `localhost:5000` da ishga tushiradi. Instagram uchun Meta webhook tunneli (masalan, ngrok) avvalgidek kerak.

## Fayllar haqida qisqacha

- `chat_with_claude.py` — asosiy chatbot logikasi
- `ig/connect_to_ig.py` — Instagram Login, DM webhook va avtomatik javob
- `tg/connect_to_tg.py` — Telegram bot va agent javoblari
- `do_embedding.ipynb` — embedding yaratish va ma'lumotlarni tayyorlash
- `plutosoft-uz-chunks.jsonl` — to'plangan ma'lumot chunklari
- `plutosoft-uz-embedded.jsonl` — embeddinglangan ma'lumotlar
- `chroma_db/` — lokal vektor ma'lumotlar bazasi
- `.env` — mahfiy konfiguratsiyalar

## Muhim eslatma

Bu loyiha hali MVP (minimum viable product) holatida. U CLI asosida ishlaydi va kelajakda web-frontend, admin panel, API server yoki ko'proq ma'lumotlar bazasi bilan kengaytirilishi mumkin.

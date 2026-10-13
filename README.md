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

## Fayllar haqida qisqacha

- `chat_with_claude.py` — asosiy chatbot logikasi
- `do_embedding.ipynb` — embedding yaratish va ma'lumotlarni tayyorlash
- `plutosoft-uz-chunks.jsonl` — to'plangan ma'lumot chunklari
- `plutosoft-uz-embedded.jsonl` — embeddinglangan ma'lumotlar
- `chroma_db/` — lokal vektor ma'lumotlar bazasi
- `.env` — mahfiy konfiguratsiyalar

## Muhim eslatma

Bu loyiha hali MVP (minimum viable product) holatida. U CLI asosida ishlaydi va kelajakda web-frontend, admin panel, API server yoki ko'proq ma'lumotlar bazasi bilan kengaytirilishi mumkin.

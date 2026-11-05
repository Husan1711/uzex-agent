# Yechim tavsifi

**Nima qiladi.** Veb-servis birja bitimlari haqidagi savollarga rus va oʻzbek tilida javob beradi. Har bir javob yonida bajarilgan SQL soʻrovlari va ularning natijasi koʻrinadi.

**Texnologiyalar.** Python, FastAPI, DuckDB, RapidFuzz, tool-calling qoʻllab-quvvatlaydigan LLM ([model nomini yozing]), oddiy HTML/JS interfeys, Docker.

**Usul.** RAG emas, text-to-SQL: raqamlarni LLM emas, baza hisoblaydi.
1. CSV fayllar bitta keng `deals` jadvaliga birlashtiriladi. Unda sumdagi summa (eksport bitim sanasidagi kurs boʻyicha), tonnadagi massa, vaznli narx uchun maydonlar, sotuvchi, xaridor va broker nomlari bor.
2. Sotuvchilar turlicha yozgan 230 ta tovar nomi 41 ta tovarga keltiriladi, sort, sinf, marka va oʻlcham alohida ajratiladi.
3. `resolve_entity` vositasi kompaniya, broker, tovar va viloyatni kirill yoki lotin yozuvida, INN yoki kod boʻyicha topadi. Oʻxshash, lekin aniq mos kelmagan nom boshqa obyekt sifatida belgilanadi.
4. LLM faqat SELECT soʻrovlarini bajara oladi. Baza faqat oʻqish rejimida, tashqi fayllarga kirish oʻchirilgan.

**Javoblar qanday tekshiriladi.**
- SQL lint: valyutalarni aralashtirish, turli birliklarni qoʻshish, oddiy oʻrtacha narx yoki bekor qilingan bitimlarni hisobga olish kabi xatolarda LLM ogohlantiriladi.
- Dalil tekshiruvi: yakuniy javobdagi har bir raqam, sana, kompaniya va tovar nomi shu savol boʻyicha olingan natijalar bilan avtomatik solishtiriladi. Mos kelmasa, javob qaytariladi va LLM uni tuzatadi.
- Ikki marta tuzatilmasa, matn koʻrsatilmaydi: faqat bazadan olingan jadval chiqadi.
- SQL natijasisiz “topildi” degan javob qabul qilinmaydi. Maʼlumot boʻlmasa, agent buni ochiq aytadi.
- Test toʻplami: mustaqil SQL bilan hisoblangan 30 ta RU/UZ savol va javobi yoʻq 12 ta “tuzoq” savol. Natija: [eval natijasini yozing, masalan 40/42].

**Hisoblash qoidalari.** Bekor qilingan bitimlar summa, hajm va narxga kirmaydi. Valyutalar aralashtirilmaydi. Narx vaznli oʻrtacha. Turli oʻlchov birliklari qoʻshilmaydi. Tanlangan filtrlar javobda aytiladi.

"""Add the FLUX workflow labels to all 25 existing catalogs."""
import json
from pathlib import Path

rows = {
"ru": "Сохранение рисунка|Строго|Сбалансированно|Свободно|Из референса|Манера|Палитра|Свет|Всё|Исправить кожу|Вернуть лицо|Исправить руки|Границы одежды|Сохранять белый фон|Цвета персонажей|Опора главы: {0}|Убрать опору|Исправления без кисти|Применить",
"en": "Drawing fidelity|Strict|Balanced|Free|From reference|Rendering style|Palette|Lighting|All|Fix skin|Restore face|Fix hands|Clothing boundaries|Keep white background|Character colors|Chapter guide: {0}|Remove guide|Brushless corrections|Apply",
"de": "Zeichnungstreue|Streng|Ausgewogen|Frei|Aus Referenz|Malstil|Palette|Licht|Alles|Haut korrigieren|Gesicht wiederherstellen|Hände korrigieren|Kleidungsgrenzen|Weißen Hintergrund behalten|Figurenfarben|Kapitelvorlage: {0}|Vorlage entfernen|Korrekturen ohne Pinsel|Anwenden",
"es": "Fidelidad al dibujo|Estricto|Equilibrado|Libre|De la referencia|Estilo pictórico|Paleta|Iluminación|Todo|Corregir piel|Restaurar rostro|Corregir manos|Bordes de ropa|Conservar fondo blanco|Colores de personajes|Guía del capítulo: {0}|Quitar guía|Correcciones sin pincel|Aplicar",
"fr": "Fidélité au dessin|Stricte|Équilibrée|Libre|Depuis la référence|Style pictural|Palette|Éclairage|Tout|Corriger la peau|Restaurer le visage|Corriger les mains|Contours des vêtements|Garder le fond blanc|Couleurs des personnages|Guide du chapitre : {0}|Retirer le guide|Corrections sans pinceau|Appliquer",
"it": "Fedeltà al disegno|Rigorosa|Bilanciata|Libera|Dal riferimento|Stile pittorico|Tavolozza|Luce|Tutto|Correggi pelle|Ripristina viso|Correggi mani|Contorni dei vestiti|Mantieni sfondo bianco|Colori dei personaggi|Guida del capitolo: {0}|Rimuovi guida|Correzioni senza pennello|Applica",
"pt-BR": "Fidelidade ao desenho|Rigorosa|Equilibrada|Livre|Da referência|Estilo de pintura|Paleta|Iluminação|Tudo|Corrigir pele|Restaurar rosto|Corrigir mãos|Limites das roupas|Manter fundo branco|Cores dos personagens|Guia do capítulo: {0}|Remover guia|Correções sem pincel|Aplicar",
"tr": "Çizime bağlılık|Sıkı|Dengeli|Serbest|Referanstan|Boyama tarzı|Palet|Işık|Tümü|Cildi düzelt|Yüzü geri getir|Elleri düzelt|Giysi sınırları|Beyaz arka planı koru|Karakter renkleri|Bölüm rehberi: {0}|Rehberi kaldır|Fırçasız düzeltmeler|Uygula",
"id": "Kesetiaan gambar|Ketat|Seimbang|Bebas|Dari referensi|Gaya pewarnaan|Palet|Pencahayaan|Semua|Perbaiki kulit|Pulihkan wajah|Perbaiki tangan|Batas pakaian|Pertahankan latar putih|Warna karakter|Panduan bab: {0}|Hapus panduan|Koreksi tanpa kuas|Terapkan",
"vi": "Giữ nguyên nét vẽ|Chặt chẽ|Cân bằng|Tự do|Từ ảnh tham chiếu|Phong cách tô|Bảng màu|Ánh sáng|Tất cả|Sửa màu da|Khôi phục khuôn mặt|Sửa bàn tay|Ranh giới trang phục|Giữ nền trắng|Màu nhân vật|Ảnh chuẩn chương: {0}|Bỏ ảnh chuẩn|Chỉnh sửa không cần cọ|Áp dụng",
"ja": "原画の保持|厳密|バランス|自由|参照画像から|塗り方|配色|照明|すべて|肌を修正|顔を復元|手を修正|服の境界|白い背景を保持|キャラクターの色|章の基準：{0}|基準を削除|ブラシ不要の修正|適用",
"ko": "원화 유지|엄격|균형|자유|참조 이미지에서|채색 스타일|팔레트|조명|전체|피부 수정|얼굴 복원|손 수정|의상 경계|흰 배경 유지|캐릭터 색상|챕터 기준: {0}|기준 제거|브러시 없이 수정|적용",
"zh-Hans": "保留原画|严格|平衡|自由|从参考图获取|绘画风格|配色|光照|全部|修正肤色|还原面部|修正双手|服装边界|保留白色背景|角色颜色|章节基准：{0}|移除基准|无需画笔的修正|应用",
"zh-Hant": "保留原畫|嚴格|平衡|自由|從參考圖取得|繪畫風格|配色|光照|全部|修正膚色|還原臉部|修正雙手|服裝邊界|保留白色背景|角色顏色|章節基準：{0}|移除基準|無需畫筆的修正|套用",
"ar": "الحفاظ على الرسم|صارم|متوازن|حر|من المرجع|أسلوب التلوين|لوحة الألوان|الإضاءة|الكل|تصحيح البشرة|استعادة الوجه|تصحيح اليدين|حدود الملابس|الحفاظ على الخلفية البيضاء|ألوان الشخصيات|مرجع الفصل: {0}|إزالة المرجع|تصحيحات دون فرشاة|تطبيق",
"fa": "حفظ طراحی|دقیق|متعادل|آزاد|از مرجع|شیوه رنگ‌آمیزی|پالت|نورپردازی|همه|اصلاح پوست|بازیابی چهره|اصلاح دست‌ها|مرز لباس|حفظ پس‌زمینه سفید|رنگ شخصیت‌ها|مرجع فصل: {0}|حذف مرجع|اصلاح بدون قلم‌مو|اعمال",
"ur": "اصل خاکے کا تحفظ|سخت|متوازن|آزاد|حوالے سے|رنگ آمیزی کا انداز|رنگوں کی ترتیب|روشنی|سب|جلد درست کریں|چہرہ بحال کریں|ہاتھ درست کریں|لباس کی حدود|سفید پس منظر رکھیں|کرداروں کے رنگ|باب کا حوالہ: {0}|حوالہ ہٹائیں|برش کے بغیر اصلاح|لاگو کریں",
"hi": "मूल चित्र का संरक्षण|सख्त|संतुलित|स्वतंत्र|संदर्भ से|रंगने की शैली|रंग-पट्टिका|प्रकाश|सभी|त्वचा सुधारें|चेहरा बहाल करें|हाथ सुधारें|कपड़ों की सीमाएँ|सफेद पृष्ठभूमि रखें|पात्रों के रंग|अध्याय संदर्भ: {0}|संदर्भ हटाएँ|ब्रश के बिना सुधार|लागू करें",
"bn": "মূল আঁকা সংরক্ষণ|কঠোর|ভারসাম্যপূর্ণ|স্বাধীন|রেফারেন্স থেকে|রঙের শৈলী|রঙের প্যালেট|আলো|সব|ত্বক ঠিক করুন|মুখ ফিরিয়ে আনুন|হাত ঠিক করুন|পোশাকের সীমানা|সাদা পটভূমি রাখুন|চরিত্রের রঙ|অধ্যায়ের রেফারেন্স: {0}|রেফারেন্স সরান|তুলি ছাড়া সংশোধন|প্রয়োগ করুন",
"mr": "मूळ रेखाटन जपणे|काटेकोर|संतुलित|मुक्त|संदर्भातून|रंगकामाची शैली|रंगसंगती|प्रकाश|सर्व|त्वचा सुधारा|चेहरा पूर्ववत करा|हात सुधारा|कपड्यांच्या सीमा|पांढरी पार्श्वभूमी ठेवा|पात्रांचे रंग|प्रकरणाचा संदर्भ: {0}|संदर्भ काढा|ब्रशशिवाय सुधारणा|लागू करा",
"pa": "ਮੂਲ ਚਿੱਤਰ ਦੀ ਸੰਭਾਲ|ਸਖ਼ਤ|ਸੰਤੁਲਿਤ|ਖੁੱਲ੍ਹਾ|ਹਵਾਲੇ ਤੋਂ|ਰੰਗਣ ਦੀ ਸ਼ੈਲੀ|ਰੰਗਾਂ ਦੀ ਪੱਟੀ|ਰੋਸ਼ਨੀ|ਸਭ|ਚਮੜੀ ਠੀਕ ਕਰੋ|ਚਿਹਰਾ ਬਹਾਲ ਕਰੋ|ਹੱਥ ਠੀਕ ਕਰੋ|ਕੱਪੜਿਆਂ ਦੀਆਂ ਹੱਦਾਂ|ਚਿੱਟਾ ਪਿਛੋਕੜ ਰੱਖੋ|ਪਾਤਰਾਂ ਦੇ ਰੰਗ|ਅਧਿਆਇ ਦਾ ਹਵਾਲਾ: {0}|ਹਵਾਲਾ ਹਟਾਓ|ਬੁਰਸ਼ ਤੋਂ ਬਿਨਾਂ ਸੁਧਾਰ|ਲਾਗੂ ਕਰੋ",
"ta": "மூல ஓவியத்தைப் பேணுதல்|கடுமை|சமநிலை|சுதந்திரம்|மேற்கோளிலிருந்து|வண்ணமிடும் பாணி|வண்ணத் தொகுப்பு|ஒளி|அனைத்தும்|தோலைச் சரிசெய்|முகத்தை மீட்டமை|கைகளைச் சரிசெய்|ஆடையின் எல்லைகள்|வெள்ளைப் பின்னணியைப் பேணு|கதாபாத்திர வண்ணங்கள்|அத்தியாய மேற்கோள்: {0}|மேற்கோளை நீக்கு|தூரிகையின்றித் திருத்தம்|பயன்படுத்து",
"te": "మూల చిత్రాన్ని కాపాడటం|కఠినం|సమతుల్యం|స్వేచ్ఛ|రిఫరెన్స్ నుండి|రంగుల శైలి|రంగుల సమూహం|వెలుతురు|అన్నీ|చర్మాన్ని సరిచేయి|ముఖాన్ని పునరుద్ధరించు|చేతులను సరిచేయి|దుస్తుల హద్దులు|తెలుపు నేపథ్యాన్ని ఉంచు|పాత్రల రంగులు|అధ్యాయం రిఫరెన్స్: {0}|రిఫరెన్స్ తొలగించు|బ్రష్ లేకుండా సవరణలు|వర్తింపజేయి",
"sw": "Kuhifadhi mchoro|Makini|Uwiano|Huru|Kutoka kielelezo|Mtindo wa kupaka rangi|Paleti|Mwangaza|Yote|Sahihisha ngozi|Rejesha uso|Sahihisha mikono|Mipaka ya mavazi|Hifadhi mandharinyuma meupe|Rangi za wahusika|Kielelezo cha sura: {0}|Ondoa kielelezo|Masahihisho bila brashi|Tumia",
"ha": "Kiyaye zane|Tsauri|Daidaito|Yanci|Daga misali|Salon fenti|Jerin launuka|Haske|Duka|Gyara fata|Maido da fuska|Gyara hannaye|Iyakokin tufafi|Kiyaye farin bango|Launukan jarumai|Misalin babi: {0}|Cire misali|Gyara ba tare da buroshi ba|Aiwatar",
}

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]/'studio/locales'
    keys = rows['ru'].split('|')
    assert len(rows) == 25
    for code, text in rows.items():
        values = text.split('|')
        assert len(values) == len(keys), code
        path = root/(code+'.json')
        catalog = json.loads(path.read_text('utf8'))
        catalog.update(zip(keys,values))
        path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n','utf8')

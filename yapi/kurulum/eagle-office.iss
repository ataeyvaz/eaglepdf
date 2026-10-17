; Eagle Office kurulum paketi: Sözcük + Tabcel + EaglePDF tek kurulumda (Inno Setup 6.5+). AKILLI KURULUM (kullanıcı kararı, bkz. surec.md §5):
;   - cihazda kurulu uygulamanın sürümü denetlenir; paketteki sürümden eski değilse DOKUNULMAZ,
;   - yalnızca kurulu OLMAYAN ya da paketten ESKİ uygulamalar varsayılan olarak seçilir ve kurulur,
;   - hepsi kurulu ve güncelse "yapılacak bir şey yok" der.
; Sürümler her uygulamanın kendi `__version__` değerinden gelir; derleme `derle.py` ile yapılır (sürümleri /D ile verir):
;   .venv\Scripts\python yapi\kurulum\derle.py            (tam derleme)      |  --hizli  (sıkıştırmasız deneme)
; ÖNCE üç PyInstaller çıktısı güncel olmalı: Sözcük (..\sozcuk\dist\Sozcuk), Tabcel (..\tabcel\dist\Tabcel), EaglePDF (dist\EaglePDF).
; Kurulu sürüm kaydı: HKA\Software\Eagle Office\Surumler\<Uygulama> = sürüm (bu kurulumdan önceki 1.1 kurulumlarında YOK:
;   dosya varsa "kurulu, sürümü bilinmiyor" sayılır ve varsayılan olarak dokunulmaz; kullanıcı isterse işaretleyip yeniden kurar).
; /DTEST=1 : ayrı AppId + ayrı kayıt anahtarı (gerçek kurulumu ezmeden deneme için).

#define SuiteName "Eagle Office"
#ifndef SuiteVersion
  #define SuiteVersion "1.2"
#endif
#ifndef SozcukVersion
  #define SozcukVersion "1.5"
#endif
#ifndef TabcelVersion
  #define TabcelVersion "0.1"
#endif
#ifndef EaglePdfVersion
  #define EaglePdfVersion "0.1"
#endif
#define AppPublisher "Eagle Office"
#define AppContact "mailto:ataeyvaz@gmail.com"
#define SozcukName "Sözcük"
#define SozcukExe "Sozcuk.exe"
#define TabcelName "Tabcel"
#define TabcelExe "Tabcel.exe"
#define EaglePdfName "EaglePDF"
#define EaglePdfExe "EaglePDF.exe"
#ifndef SozcukDist
  #define SozcukDist "..\..\..\sozcuk\dist\Sozcuk"
#endif
#ifndef TabcelDist
  #define TabcelDist "..\..\..\tabcel\dist\Tabcel"
#endif
#ifndef EaglePdfDist
  #define EaglePdfDist "..\..\dist\EaglePDF"
#endif
#ifndef CikisKlasoru
  #define CikisKlasoru "..\..\dist"
#endif
#define Gorsel "gorsel"
#ifdef TEST
  #define KayitKok "Software\Eagle Office TEST"
#else
  #define KayitKok "Software\Eagle Office"
#endif

[Setup]
#ifdef TEST
AppId={{7D4A2B16-3C8E-4E55-A1F0-9B6C5E2D8AFF}
OutputBaseFilename=EagleOffice-{#SuiteVersion}-TEST
#else
AppId={{7D4A2B16-3C8E-4E55-A1F0-9B6C5E2D8A71}
OutputBaseFilename=EagleOffice-{#SuiteVersion}-kurulum
#endif
AppName={#SuiteName}
AppVersion={#SuiteVersion}
AppVerName={#SuiteName} {#SuiteVersion}
AppPublisher={#AppPublisher}
AppSupportURL={#AppContact}
AppContact={#AppContact}
DefaultDirName={autopf}\{#SuiteName}
#ifdef TEST
DefaultGroupName={#SuiteName} TEST
#else
DefaultGroupName={#SuiteName}
#endif
DisableProgramGroupPage=yes
OutputDir={#CikisKlasoru}
SetupIconFile={#Gorsel}\eagle-office.ico
UninstallDisplayIcon={app}\eagle-office.ico
WizardImageFile={#Gorsel}\sihirbaz-buyuk.bmp
WizardSmallImageFile={#Gorsel}\sihirbaz-kucuk.bmp
#ifdef HIZLI
Compression=none
SolidCompression=no
#else
Compression=lzma2/max
SolidCompression=yes
#endif
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequiredOverridesAllowed=commandline dialog
ChangesAssociations=yes
; .argosmodel (zip) arşivlerini açmak için
ArchiveExtraction=full

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Types]
Name: "tam"; Description: "Eagle Office — tüm uygulamalar (Sözcük, Tabcel, EaglePDF)"
Name: "ozel"; Description: "Özel kurulum (uygulamaları ve ek çeviri dillerini seçin)"; Flags: iscustom

[Components]
Name: "sozcuk"; Description: "Sözcük — Türkçe kelime işlemci (Türkçe ↔ İngilizce çeviri dahil)"; Types: tam ozel
Name: "sozcuk\diller"; Description: "Ek çeviri dilleri — kurulum sırasında internetten indirilir"; Types: ozel
Name: "sozcuk\diller\de"; Description: "Türkçe ↔ Almanca"; Types: ozel
Name: "sozcuk\diller\it"; Description: "Türkçe ↔ İtalyanca"; Types: ozel
Name: "sozcuk\diller\es"; Description: "Türkçe ↔ İspanyolca"; Types: ozel
Name: "sozcuk\diller\fr"; Description: "Türkçe ↔ Fransızca"; Types: ozel
Name: "sozcuk\diller\ru"; Description: "Türkçe ↔ Rusça"; Types: ozel
Name: "sozcuk\diller\zh"; Description: "Türkçe ↔ Çince"; Types: ozel
Name: "sozcuk\diller\ja"; Description: "Türkçe ↔ Japonca"; Types: ozel
Name: "sozcuk\diller\hi"; Description: "Türkçe ↔ Hintçe"; Types: ozel
Name: "sozcuk\diller\ko"; Description: "Türkçe ↔ Korece"; Types: ozel
Name: "sozcuk\diller\ar"; Description: "Türkçe ↔ Arapça"; Types: ozel
Name: "sozcuk\diller\pt"; Description: "Türkçe ↔ Portekizce"; Types: ozel
Name: "tabcel"; Description: "Tabcel — Türkçe hesap tablosu"; Types: tam ozel
Name: "eaglepdf"; Description: "EaglePDF — Türkçe PDF görüntüleyici ve düzenleyici"; Types: tam ozel

[Tasks]
Name: "sozcukdesktop"; Description: "Masaüstünde Sözcük kısayolu oluştur"; GroupDescription: "Ek kısayollar:"; Components: sozcuk
Name: "tabceldesktop"; Description: "Masaüstünde Tabcel kısayolu oluştur"; GroupDescription: "Ek kısayollar:"; Components: tabcel
Name: "eaglepdfdesktop"; Description: "Masaüstünde EaglePDF kısayolu oluştur"; GroupDescription: "Ek kısayollar:"; Components: eaglepdf
Name: "docxassoc"; Description: "Word belgelerini (.docx) Sözcük ile açmak için ilişkilendir"; \
    GroupDescription: "Dosya türleri:"; Components: sozcuk; Flags: unchecked
Name: "xlsxassoc"; Description: "Excel çalışma kitaplarını (.xlsx) Tabcel ile açmak için ilişkilendir"; \
    GroupDescription: "Dosya türleri:"; Components: tabcel; Flags: unchecked
Name: "csvassoc"; Description: "CSV dosyalarını (.csv) Tabcel ile açmak için ilişkilendir"; \
    GroupDescription: "Dosya türleri:"; Components: tabcel; Flags: unchecked
Name: "pdfassoc"; Description: "PDF dosyalarını (.pdf) EaglePDF ile açmak için ilişkilendir"; \
    GroupDescription: "Dosya türleri:"; Components: eaglepdf; Flags: unchecked

[InstallDelete]
; yalnızca YENİDEN KURULAN uygulamanın eski dosyaları temizlenir; seçilmeyen (güncel) uygulamalara dokunulmaz
Type: filesandordirs; Name: "{app}\Sözcük\_internal"; Components: sozcuk
Type: filesandordirs; Name: "{app}\Tabcel\_internal"; Components: tabcel
Type: filesandordirs; Name: "{app}\EaglePDF\_internal"; Components: eaglepdf

[Files]
Source: "{#Gorsel}\eagle-office.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SozcukDist}\{#SozcukExe}"; DestDir: "{app}\Sözcük"; Components: sozcuk; Flags: ignoreversion
Source: "{#SozcukDist}\_internal\*"; DestDir: "{app}\Sözcük\_internal"; Components: sozcuk; \
    Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#TabcelDist}\{#TabcelExe}"; DestDir: "{app}\Tabcel"; Components: tabcel; Flags: ignoreversion
Source: "{#TabcelDist}\_internal\*"; DestDir: "{app}\Tabcel\_internal"; Components: tabcel; \
    Flags: ignoreversion recursesubdirs createallsubdirs
; EaglePDF: onedir (PySide6 LGPL yeniden bağlama hakkı için _internal klasörü korunur) + lisans dosyaları + AGPL kaynak zip
Source: "{#EaglePdfDist}\*"; DestDir: "{app}\EaglePDF"; Components: eaglepdf; \
    Flags: ignoreversion recursesubdirs createallsubdirs
; Ek çeviri dilleri (yalnızca seçilirse indirilir). DestName ".zip" olmalı: arşiv türü uzantıdan tanınıyor
Source: "https://argos-net.com/v1/translate-en_de-1_3.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_de-1_3.zip"; ExternalSize: 150508297; Components: sozcuk\diller\de; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-de_en-1_3.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-de_en-1_3.zip"; ExternalSize: 150512831; Components: sozcuk\diller\de; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-en_it-1_0.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_it-1_0.zip"; ExternalSize: 87660780; Components: sozcuk\diller\it; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-it_en-1_0.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-it_en-1_0.zip"; ExternalSize: 87190224; Components: sozcuk\diller\it; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-en_es-1_0.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_es-1_0.zip"; ExternalSize: 87503191; Components: sozcuk\diller\es; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-es_en-1_9.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-es_en-1_9.zip"; ExternalSize: 285208831; Components: sozcuk\diller\es; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-en_fr-1_9.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_fr-1_9.zip"; ExternalSize: 65472327; Components: sozcuk\diller\fr; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-fr_en-1_9.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-fr_en-1_9.zip"; ExternalSize: 66585033; Components: sozcuk\diller\fr; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-en_ru-1_9.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_ru-1_9.zip"; ExternalSize: 195746693; Components: sozcuk\diller\ru; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-ru_en-1_9.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-ru_en-1_9.zip"; ExternalSize: 156239112; Components: sozcuk\diller\ru; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-en_zh-1_9.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_zh-1_9.zip"; ExternalSize: 70743021; Components: sozcuk\diller\zh; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-zh_en-1_9.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-zh_en-1_9.zip"; ExternalSize: 74481402; Components: sozcuk\diller\zh; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-en_ja-1_1.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_ja-1_1.zip"; ExternalSize: 120470284; Components: sozcuk\diller\ja; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-ja_en-1_1.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-ja_en-1_1.zip"; ExternalSize: 117155716; Components: sozcuk\diller\ja; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-en_hi-1_1.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_hi-1_1.zip"; ExternalSize: 106752178; Components: sozcuk\diller\hi; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-hi_en-1_1.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-hi_en-1_1.zip"; ExternalSize: 102381771; Components: sozcuk\diller\hi; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-en_ko-1_1.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_ko-1_1.zip"; ExternalSize: 120789009; Components: sozcuk\diller\ko; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-ko_en-1_1.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-ko_en-1_1.zip"; ExternalSize: 118852077; Components: sozcuk\diller\ko; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-en_ar-1_0.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_ar-1_0.zip"; ExternalSize: 88502631; Components: sozcuk\diller\ar; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-ar_en-1_0.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-ar_en-1_0.zip"; ExternalSize: 81869670; Components: sozcuk\diller\ar; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-en_pt-1_9.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-en_pt-1_9.zip"; ExternalSize: 66179184; Components: sozcuk\diller\pt; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "https://argos-net.com/v1/translate-pt_en-1_9.argosmodel"; DestDir: "{app}\Sözcük\diller"; \
    DestName: "translate-pt_en-1_9.zip"; ExternalSize: 69447231; Components: sozcuk\diller\pt; \
    Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#SozcukName}"; Filename: "{app}\Sözcük\{#SozcukExe}"; Components: sozcuk
Name: "{group}\{#TabcelName}"; Filename: "{app}\Tabcel\{#TabcelExe}"; Components: tabcel
Name: "{group}\{#EaglePdfName}"; Filename: "{app}\EaglePDF\{#EaglePdfExe}"; Components: eaglepdf
Name: "{group}\{#SuiteName} Kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#SozcukName}"; Filename: "{app}\Sözcük\{#SozcukExe}"; Tasks: sozcukdesktop
Name: "{autodesktop}\{#TabcelName}"; Filename: "{app}\Tabcel\{#TabcelExe}"; Tasks: tabceldesktop
Name: "{autodesktop}\{#EaglePdfName}"; Filename: "{app}\EaglePDF\{#EaglePdfExe}"; Tasks: eaglepdfdesktop

[Registry]
; --- kurulu sürüm kayıtları (akıllı kurulum bunlara bakar)
Root: HKA; Subkey: "{#KayitKok}"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "{#KayitKok}\Surumler"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "{#KayitKok}\Surumler"; ValueType: string; ValueName: "Sozcuk"; ValueData: "{#SozcukVersion}"; \
    Components: sozcuk; Flags: uninsdeletevalue
Root: HKA; Subkey: "{#KayitKok}\Surumler"; ValueType: string; ValueName: "Tabcel"; ValueData: "{#TabcelVersion}"; \
    Components: tabcel; Flags: uninsdeletevalue
Root: HKA; Subkey: "{#KayitKok}\Surumler"; ValueType: string; ValueName: "EaglePDF"; ValueData: "{#EaglePdfVersion}"; \
    Components: eaglepdf; Flags: uninsdeletevalue
; --- Sözcük: "Birlikte aç" listesinde görünsün
Root: HKA; Subkey: "Software\Classes\Applications\{#SozcukExe}\shell\open\command"; \
    ValueType: string; ValueName: ""; ValueData: """{app}\Sözcük\{#SozcukExe}"" ""%1"""; \
    Components: sozcuk; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#SozcukExe}\SupportedTypes"; \
    ValueType: string; ValueName: ".docx"; ValueData: ""; Components: sozcuk; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#SozcukExe}\SupportedTypes"; \
    ValueType: string; ValueName: ".doc"; ValueData: ""; Components: sozcuk
Root: HKA; Subkey: "Software\Classes\Applications\{#SozcukExe}\SupportedTypes"; \
    ValueType: string; ValueName: ".rtf"; ValueData: ""; Components: sozcuk
Root: HKA; Subkey: "Software\Classes\Applications\{#SozcukExe}\SupportedTypes"; \
    ValueType: string; ValueName: ".odt"; ValueData: ""; Components: sozcuk
Root: HKA; Subkey: "Software\Classes\Applications\{#SozcukExe}\SupportedTypes"; \
    ValueType: string; ValueName: ".txt"; ValueData: ""; Components: sozcuk
Root: HKA; Subkey: "Software\Classes\.docx\OpenWithProgids"; ValueType: string; \
    ValueName: "Sozcuk.Belge"; ValueData: ""; Tasks: docxassoc; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Sozcuk.Belge"; ValueType: string; ValueName: ""; \
    ValueData: "Word Belgesi (Sözcük)"; Tasks: docxassoc; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Sozcuk.Belge\DefaultIcon"; ValueType: string; ValueName: ""; \
    ValueData: "{app}\Sözcük\{#SozcukExe},0"; Tasks: docxassoc
Root: HKA; Subkey: "Software\Classes\Sozcuk.Belge\shell\open\command"; ValueType: string; ValueName: ""; \
    ValueData: """{app}\Sözcük\{#SozcukExe}"" ""%1"""; Tasks: docxassoc
; --- Tabcel: "Birlikte aç" listesinde görünsün
Root: HKA; Subkey: "Software\Classes\Applications\{#TabcelExe}"; ValueType: string; \
    ValueName: "FriendlyAppName"; ValueData: "{#TabcelName}"; Components: tabcel; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#TabcelExe}\shell\open\command"; \
    ValueType: string; ValueName: ""; ValueData: """{app}\Tabcel\{#TabcelExe}"" ""%1"""; Components: tabcel
Root: HKA; Subkey: "Software\Classes\Applications\{#TabcelExe}\SupportedTypes"; \
    ValueType: string; ValueName: ".xlsx"; ValueData: ""; Components: tabcel
Root: HKA; Subkey: "Software\Classes\Applications\{#TabcelExe}\SupportedTypes"; \
    ValueType: string; ValueName: ".csv"; ValueData: ""; Components: tabcel
Root: HKA; Subkey: "Software\Classes\.xlsx\OpenWithProgids"; ValueType: string; \
    ValueName: "Tabcel.Kitap"; ValueData: ""; Tasks: xlsxassoc; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.csv\OpenWithProgids"; ValueType: string; \
    ValueName: "Tabcel.Kitap"; ValueData: ""; Tasks: csvassoc; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Tabcel.Kitap"; ValueType: string; ValueName: ""; \
    ValueData: "Çalışma Kitabı ({#TabcelName})"; Tasks: xlsxassoc csvassoc; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Tabcel.Kitap\DefaultIcon"; ValueType: string; ValueName: ""; \
    ValueData: "{app}\Tabcel\{#TabcelExe},0"; Tasks: xlsxassoc csvassoc
Root: HKA; Subkey: "Software\Classes\Tabcel.Kitap\shell\open\command"; ValueType: string; ValueName: ""; \
    ValueData: """{app}\Tabcel\{#TabcelExe}"" ""%1"""; Tasks: xlsxassoc csvassoc
; --- EaglePDF: "Birlikte aç" listesinde görünsün (varsayılan program seçimi Windows'ta kullanıcıdadır)
Root: HKA; Subkey: "Software\Classes\Applications\{#EaglePdfExe}"; ValueType: string; \
    ValueName: "FriendlyAppName"; ValueData: "{#EaglePdfName}"; Components: eaglepdf; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#EaglePdfExe}\shell\open\command"; \
    ValueType: string; ValueName: ""; ValueData: """{app}\EaglePDF\{#EaglePdfExe}"" ""%1"""; Components: eaglepdf
Root: HKA; Subkey: "Software\Classes\Applications\{#EaglePdfExe}\SupportedTypes"; \
    ValueType: string; ValueName: ".pdf"; ValueData: ""; Components: eaglepdf
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; \
    ValueName: "EaglePDF.PDF"; ValueData: ""; Tasks: pdfassoc; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\EaglePDF.PDF"; ValueType: string; ValueName: ""; \
    ValueData: "PDF Belgesi ({#EaglePdfName})"; Tasks: pdfassoc; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\EaglePDF.PDF\DefaultIcon"; ValueType: string; ValueName: ""; \
    ValueData: "{app}\EaglePDF\{#EaglePdfExe},0"; Tasks: pdfassoc
Root: HKA; Subkey: "Software\Classes\EaglePDF.PDF\shell\open\command"; ValueType: string; ValueName: ""; \
    ValueData: """{app}\EaglePDF\{#EaglePdfExe}"" ""%1"""; Tasks: pdfassoc

[Run]
Filename: "{app}\Sözcük\{#SozcukExe}"; Description: "Sözcük'ü şimdi çalıştır"; Components: sozcuk; \
    Flags: nowait postinstall skipifsilent unchecked
Filename: "{app}\Tabcel\{#TabcelExe}"; Description: "Tabcel'i şimdi çalıştır"; Components: tabcel; \
    Flags: nowait postinstall skipifsilent unchecked
Filename: "{app}\EaglePDF\{#EaglePdfExe}"; Description: "EaglePDF'i şimdi çalıştır"; Components: eaglepdf; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\Sözcük\_internal"
Type: filesandordirs; Name: "{app}\Sözcük\diller"
Type: filesandordirs; Name: "{app}\Tabcel\_internal"
Type: filesandordirs; Name: "{app}\EaglePDF\_internal"

[Code]
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\';
  OldSozcukId = '{6E1C0A9C-2E5B-4C9E-9C4B-5F2E0B9A7C11}_is1';
  OldTabcelId = '{B3F1C2D4-5A6E-4F70-8B19-2C7D9E0A4F33}_is1';
  SurumAnahtari = '{#KayitKok}\Surumler';
  // durum kodları
  DKurulDegil = 0;   // kurulu değil -> kurulur
  DEski = 1;         // kurulu sürüm paketten eski -> güncellenir
  DGuncel = 2;       // kurulu sürüm paketle aynı/daha yeni -> dokunulmaz
  DBilinmiyor = 3;   // dosya var ama sürüm kaydı yok (eski 1.1 kurulumu) -> dokunulmaz, kullanıcı isterse işaretler

var
  BilesenSayfasiGosterildi: Boolean;

function OldUninstaller(const Id: String): String;
var
  Value: String;
begin
  Result := '';
  if RegQueryStringValue(HKLM, UninstallKey + Id, 'UninstallString', Value) or
     RegQueryStringValue(HKCU, UninstallKey + Id, 'UninstallString', Value) then
    Result := RemoveQuotes(Value);
end;

procedure RemoveOldStandalone(const Id, DisplayName: String);
var
  Path: String;
  ResultCode: Integer;
begin
  Path := OldUninstaller(Id);
  if (Path = '') or (not FileExists(Path)) then
    Exit;
  if MsgBox('Bilgisayarda ayrı kurulmuş bir ' + DisplayName + ' bulundu.' + #13#10#13#10 +
            'Aynı uygulamanın iki kopyası olmaması için önce o kurulum kaldırılsın mı?' + #13#10 +
            'Belgeleriniz ve ayarlarınız silinmez.', mbConfirmation, MB_YESNO) = IDYES then
    Exec(Path, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
end;

function KayitliSurum(const Ad: String): String;
var
  V: String;
begin
  Result := '';
  if RegQueryStringValue(HKLM, SurumAnahtari, Ad, V) or RegQueryStringValue(HKCU, SurumAnahtari, Ad, V) then
    Result := V;
end;

function KuruluDizin(): String;
begin
  Result := AddBackslash(WizardDirValue);
end;

// Bir uygulamanın durumu: dosya (exe) yoksa kurulu değil; kayıt varsa sürümlere göre eski/güncel; kayıt yoksa bilinmiyor.
function UygulamaDurumu(const Ad, AltKlasor, Exe, PaketSurumu: String): Integer;
var
  Kurulu: String;
  KV, PV: Int64;
begin
  Result := DKurulDegil;
  if not FileExists(KuruluDizin() + AltKlasor + '\' + Exe) then
    Exit;
  Kurulu := KayitliSurum(Ad);
  if Kurulu = '' then
  begin
    Result := DBilinmiyor;
    Exit;
  end;
  if StrToVersion(Kurulu, KV) and StrToVersion(PaketSurumu, PV) then
  begin
    if ComparePackedVersion(KV, PV) < 0 then
      Result := DEski
    else
      Result := DGuncel;
  end
  else
    Result := DEski;   // sürüm metni çözülemiyorsa güvenli taraf: güncelle
end;

function Durum(const Bilesen: String): Integer;
begin
  if Bilesen = 'sozcuk' then
    Result := UygulamaDurumu('Sozcuk', 'Sözcük', '{#SozcukExe}', '{#SozcukVersion}')
  else if Bilesen = 'tabcel' then
    Result := UygulamaDurumu('Tabcel', 'Tabcel', '{#TabcelExe}', '{#TabcelVersion}')
  else
    Result := UygulamaDurumu('EaglePDF', 'EaglePDF', '{#EaglePdfExe}', '{#EaglePdfVersion}');
end;

function KomutSatirindaBilesenVar(): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if Pos('/COMPONENTS=', Uppercase(ParamStr(I))) = 1 then
      Result := True;
end;

function GerekliMi(const Bilesen: String): Boolean;
var
  D: Integer;
begin
  D := Durum(Bilesen);
  Result := (D = DKurulDegil) or (D = DEski);
end;

procedure VarsayilanSecimiUygula();
var
  Liste: String;
begin
  if KomutSatirindaBilesenVar() then
    Exit;   // kullanıcı /COMPONENTS ile kendisi belirlemiş
  Liste := '';
  if GerekliMi('sozcuk') then Liste := Liste + ',sozcuk' else Liste := Liste + ',!sozcuk';
  if GerekliMi('tabcel') then Liste := Liste + ',tabcel' else Liste := Liste + ',!tabcel';
  if GerekliMi('eaglepdf') then Liste := Liste + ',eaglepdf' else Liste := Liste + ',!eaglepdf';
  Delete(Liste, 1, 1);
  WizardSelectComponents(Liste);
  Log('Akilli kurulum varsayilan secim: ' + Liste +
      ' (durumlar sozcuk=' + IntToStr(Durum('sozcuk')) + ' tabcel=' + IntToStr(Durum('tabcel')) +
      ' eaglepdf=' + IntToStr(Durum('eaglepdf')) + ')');
end;

function DurumMetni(const Bilesen, PaketSurumu: String; Kayit: String): String;
begin
  case Durum(Bilesen) of
    DEski: Result := ' — kurulu sürüm ' + Kayit + ', yeni sürüm ' + PaketSurumu + ' (güncellenecek)';
    DGuncel: Result := ' — zaten kurulu (sürüm ' + Kayit + ', güncel)';
    DBilinmiyor: Result := ' — zaten kurulu (sürüm bilinmiyor); işaretlerseniz yeniden kurulur';
  else
    Result := '';
  end;
end;

procedure BilesenAciklamalariniGuncelle();
var
  I: Integer;
  Baslik: String;
begin
  for I := 0 to WizardForm.ComponentsList.Items.Count - 1 do
  begin
    Baslik := WizardForm.ComponentsList.ItemCaption[I];
    if Pos('Sözcük —', Baslik) = 1 then
      WizardForm.ComponentsList.ItemCaption[I] := Baslik + DurumMetni('sozcuk', '{#SozcukVersion}', KayitliSurum('Sozcuk'))
    else if Pos('Tabcel —', Baslik) = 1 then
      WizardForm.ComponentsList.ItemCaption[I] := Baslik + DurumMetni('tabcel', '{#TabcelVersion}', KayitliSurum('Tabcel'))
    else if Pos('EaglePDF —', Baslik) = 1 then
      WizardForm.ComponentsList.ItemCaption[I] := Baslik + DurumMetni('eaglepdf', '{#EaglePdfVersion}', KayitliSurum('EaglePDF'));
  end;
end;

procedure InitializeWizard();
begin
  VarsayilanSecimiUygula();
  // Her şey kurulu ve güncelse yapılacak bir şey yok
  if (not KomutSatirindaBilesenVar()) and (not GerekliMi('sozcuk')) and (not GerekliMi('tabcel')) and (not GerekliMi('eaglepdf')) then
  begin
    if WizardSilent then
    begin
      Log('Akilli kurulum: tum uygulamalar kurulu ve guncel; yapilacak bir sey yok.');
      Abort;
    end;
    if MsgBox('Eagle Office uygulamalarının hepsi bu bilgisayarda zaten kurulu ve güncel.' + #13#10#13#10 +
              'Yine de belirli uygulamaları yeniden kurmak ister misiniz?' + #13#10 +
              '(Hayır derseniz kurulum hiçbir şeye dokunmadan kapanır.)', mbConfirmation, MB_YESNO) = IDNO then
      Abort;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectComponents then
  begin
    if not BilesenSayfasiGosterildi then
    begin
      BilesenSayfasiGosterildi := True;
      VarsayilanSecimiUygula();   // dizin sayfasında konum değişmiş olabilir
      BilesenAciklamalariniGuncelle();
    end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectComponents then
    if (not WizardIsComponentSelected('sozcuk')) and (not WizardIsComponentSelected('tabcel')) and
       (not WizardIsComponentSelected('eaglepdf')) then
    begin
      MsgBox('Kurmak için en az bir uygulama seçmelisiniz (Sözcük, Tabcel ya da EaglePDF). ' +
             'Vazgeçtiyseniz İptal''e basabilirsiniz.', mbInformation, MB_OK);
      Result := False;
    end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if WizardIsComponentSelected('sozcuk') then
    RemoveOldStandalone(OldSozcukId, 'Sözcük');
  if WizardIsComponentSelected('tabcel') then
    RemoveOldStandalone(OldTabcelId, 'Tabcel');
end;

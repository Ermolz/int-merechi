# Практичне заняття № 3

**Формальні умови та обмеження OWL-онтології**
**Варіант 1 — Конфігуратор комплектуючих ПК (PC Builder)**
Дата: 22.09.2026

## Результат

Доповнено [PC_Builder.owl](PC_Builder.owl), створений на практичному занятті № 2. Усі 18 вихідних індивідів, їхні 20 об’єктних зв’язків і 18 числових значень збережено. Нова версія містить **20 класів, 10 Object Properties, 4 Data Properties, 3 власні типи даних, 18 індивідів, 20 явних об’єктних та 22 явні інформаційні твердження**. 14 нових класів є визначеними через `EquivalentClasses`; клас `Socket` також визначено переліком індивідів.

**HermiT реально запущено через OWLAPI поза графічним інтерфейсом Protégé.** Онтологія узгоджена; порушень OWL 2 DL і невиконуваних іменованих класів немає. Використано локальні бібліотеки Protégé: OWLAPI 4.5.29; файл HermiT `org.semanticweb.hermit-1.4.3.456.jar`; версія, яку повідомляє reasoner, — `1.4.1.432`.

Докази: [повний журнал](validation/reasoner-output.txt), [виведена ієрархія](validation/inferred-hierarchy.txt), [екземпляри класів](validation/inferred-instances.txt), [64 об’єктні зв’язки](validation/inferred-relations.txt), [SHA-256 перевіреного файла](validation/owl-sha256.txt). Файл OWL не змінювався під час перевірки.

## Основа й межі моделі

Предметна область — та сама навчальна модель PC Builder. Конфігурація складається з одного процесора, однієї материнської плати й одного блока живлення. Комплектуючі є записами каталогу: один запис БП дозволено використовувати у кількох конфігураціях. GPU, RAM, накопичувачі та інші частини ПК до цього варіанта не входять.

Надане завдання містить приклади `Equipment/hasState/EmergencyState`, але не задає окремого переліку Defined Classes для PC Builder. Тому конструкції адаптовано до власної предметної області: сокети, пороги TDP/Wattage, призначення та сокетна сумісність конфігурацій. Пороги `65 W` і `650 W`, а також три значення призначення — прийняті навчальні умови, не характеристики реальних серійних виробів.

IRI онтології: `https://example.org/pc-builder`. Version IRI: `https://example.org/pc-builder/2.0`. Зовнішніх імпортів немає.

## Відповідність завданню

| Вимога | Реалізація |
|---|---|
| Domain/Range для Object Properties | Усі 10 властивостей мають явно задані області |
| Domain/Range для Data Properties | Усі 4 властивості мають області та формальні діапазони значень |
| Власний тип даних / enumeration | `ConfigurationPurpose = {"office", "general", "performance"}`; додатково `PositiveWattage` та `NonNegativePrice` |
| Характеристики властивостей | Functional, InverseFunctional, Asymmetric, Irreflexive у відповідних місцях |
| Взаємно обернені властивості | 5 пар; зворотні факти отримує HermiT |
| Disjoint Classes | Дві групи базових класів; додаткову несумісність платформ виводить HermiT |
| someValuesFrom / allValuesFrom | Обов’язкові сокети та компоненти; дозволені типи компонентів |
| min / max / exact | Від 3 до 3 компонентів; рівно один CPU, Motherboard, PowerSupply та необхідні значення |
| Defined Classes | 14 нових класів через еквівалентність виразам |
| Закриття класу індивідами | `Socket ≡ {Socket_AM4, Socket_AM5, Socket_LGA1700}` |
| Перевірка Individuals | Логічна перевірка HermiT та окрема перевірка повноти явних даних |
| Запуск HermiT або Pellet | Виконано HermiT через OWLAPI |
| Аналіз inferred class hierarchy | Наведено нижче й збережено безпосередній результат запиту до reasoner |

## Object Properties

| Властивість | Domain | Range | Обернена |
|---|---|---|---|
| `hasSocket` | `CPU or Motherboard` | `Socket` | `isSocketOf` |
| `hasCPU` | `PCConfiguration` | `CPU` | `isCPUOf` |
| `hasMotherboard` | `PCConfiguration` | `Motherboard` | `isMotherboardOf` |
| `hasPowerSupply` | `PCConfiguration` | `PowerSupply` | `isPowerSupplyOf` |
| `hasComponent` | `PCConfiguration` | `Component` | `isComponentOf` |
| `isSocketOf` | `Socket` | `CPU or Motherboard` | `hasSocket` |
| `isCPUOf` | `CPU` | `PCConfiguration` | `hasCPU` |
| `isMotherboardOf` | `Motherboard` | `PCConfiguration` | `hasMotherboard` |
| `isPowerSupplyOf` | `PowerSupply` | `PCConfiguration` | `hasPowerSupply` |
| `isComponentOf` | `Component` | `PCConfiguration` | `hasComponent` |

`hasCPU`, `hasMotherboard`, `hasPowerSupply` — підвластивості `hasComponent`. Тому три компоненти кожної конфігурації виводяться з наявних спеціалізованих зв’язків.

Перші чотири прямі властивості — **Functional**; їхні обернені — **InverseFunctional**. Обернені не оголошено Functional: наприклад, `PSU_650W isPowerSupplyOf` має два значення. `hasComponent` і `isComponentOf` не функціональні й не обернено-функціональні.

Усі 10 Object Properties — **Asymmetric** та **Irreflexive**: об’єкт не пов’язується цією самою властивістю із собою, а пара `x R y` не може співіснувати з `y R x`. Їхні Domain і Range також несумісні. Симетричність, транзитивність і рефлексивність для цих відношень предметно не підходять.

У OWL записано лише 20 вихідних прямих зв’язків. HermiT отримав 20 обернених, 12 `hasComponent` і 12 `isComponentOf`: разом **64**. Наприклад:

```text
Явно:    PC_Office_AM4 hasCPU CPU_AM4_65W
Виведено: CPU_AM4_65W isCPUOf PC_Office_AM4
Виведено: PC_Office_AM4 hasComponent CPU_AM4_65W
Виведено: CPU_AM4_65W isComponentOf PC_Office_AM4
```

Один Domain `CPU or Motherboard` означає об’єднання. Два окремі Domain означали б перетин, що конфліктує з несумісністю цих класів. Domain/Range використовуються для логічних висновків про типи, а не як звичайна перевірка полів форми. [W3C: Domain and Range](https://www.w3.org/TR/owl2-primer/#Domain_and_Range_Restrictions).

## Data Properties та власні типи даних

| Властивість | Domain | Range | Умова |
|---|---|---|---|
| `hasTDP` | `CPU` | `PositiveWattage` | `xsd:integer[>= 1]`, Вт |
| `hasWattage` | `PowerSupply` | `PositiveWattage` | `xsd:integer[>= 1]`, Вт |
| `hasPrice` | `Component` | `NonNegativePrice` | `xsd:decimal[>= 0]`, умовні одиниці |
| `hasPurpose` | `PCConfiguration` | `ConfigurationPurpose` | `{"office", "general", "performance"}`, рядки |

Усі чотири властивості — **Functional**. Для Data Properties OWL 2 не надає аналога `inverseOf` або характеристики InverseFunctional. Використано `DatatypeDefinition`, `DatatypeRestriction` та `DataOneOf`. [W3C: Data Property Axioms](https://www.w3.org/TR/owl2-syntax/#Data_Property_Axioms), [W3C: Data Ranges](https://www.w3.org/TR/owl2-syntax/#Data_Ranges).

Додані факти: `PC_Office_AM4 → office`, `PC_Performance_AM4 → performance`, `PC_Modern_AM5 → general`, `PC_Intel_LGA1700 → performance`. Числові значення другої практичної залишилися без змін.

## Несумісність, кількість та існування

Попарно несумісні групи:

- `Component`, `Socket`, `PCConfiguration`.
- `CPU`, `Motherboard`, `PowerSupply`.

Усі 18 індивідів залишаються в `AllDifferent`. Це явно забороняє злиття різних імен у той самий об’єкт для задоволення обмежень кількості.

Обмеження в Manchester-подібному записі:

```text
Component SubClassOf:
  hasPrice exactly 1 xsd:decimal

CPU SubClassOf:
  Component,
  hasSocket exactly 1 Socket,
  hasSocket some Socket,
  hasSocket only Socket,
  hasTDP exactly 1 xsd:integer

Motherboard SubClassOf:
  Component,
  hasSocket exactly 1 Socket,
  hasSocket some Socket,
  hasSocket only Socket

PowerSupply SubClassOf:
  Component,
  hasWattage exactly 1 xsd:integer

PCConfiguration SubClassOf:
  hasCPU exactly 1 CPU,
  hasMotherboard exactly 1 Motherboard,
  hasPowerSupply exactly 1 PowerSupply,
  hasComponent some CPU,
  hasComponent some Motherboard,
  hasComponent some PowerSupply,
  hasComponent only (CPU or Motherboard or PowerSupply),
  hasComponent min 3 Component,
  hasComponent max 3 Component,
  hasPurpose exactly 1 ConfigurationPurpose
```

Старі числові `exactly 1` залишено; нові Range звужують допустимі значення до додатних потужностей і невід’ємних цін. `min 3` разом із `max 3` задає рівно три компоненти. Окремі `some` та `only` для сокетів частково повторюють наслідки `exactly 1` і Range, але явно демонструють обидва види обмежень із завдання.

Закрито лише навчальний довідник сокетів:

```text
Socket EquivalentTo: {Socket_AM4, Socket_AM5, Socket_LGA1700}
```

Новий індивід класу Socket мусив би збігтися з одним із цих трьох. Якщо явно вимагати його відмінності від усіх трьох, виникає суперечність. Решта класів не закривається наявними прикладами: каталог може поповнюватися новими CPU, платами, БП і конфігураціями.

## Defined Classes

Усі наведені умови записані через `EquivalentClasses`, тому задають необхідні й достатні умови. Вихідні індивіди не отримали жодного ручного твердження про належність до цих 14 класів.

| Defined Class | Еквівалентний вираз |
|---|---|
| `AM4CPU` | `CPU and (hasSocket value Socket_AM4)` |
| `AM5CPU` | `CPU and (hasSocket value Socket_AM5)` |
| `LGA1700CPU` | `CPU and (hasSocket value Socket_LGA1700)` |
| `AM4Motherboard` | `Motherboard and (hasSocket value Socket_AM4)` |
| `AM5Motherboard` | `Motherboard and (hasSocket value Socket_AM5)` |
| `LGA1700Motherboard` | `Motherboard and (hasSocket value Socket_LGA1700)` |
| `AM4Configuration` | `PCConfiguration and (hasCPU some AM4CPU) and (hasMotherboard some AM4Motherboard)` |
| `AM5Configuration` | `PCConfiguration and (hasCPU some AM5CPU) and (hasMotherboard some AM5Motherboard)` |
| `LGA1700Configuration` | `PCConfiguration and (hasCPU some LGA1700CPU) and (hasMotherboard some LGA1700Motherboard)` |
| `SocketCompatibleConfiguration` | `AM4Configuration or AM5Configuration or LGA1700Configuration` |
| `EfficientCPU` | `CPU and (hasTDP some xsd:integer[<= 65])` |
| `HighPowerSupply` | `PowerSupply and (hasWattage some xsd:integer[>= 650])` |
| `EfficientConfiguration` | `PCConfiguration and (hasCPU some EfficientCPU)` |
| `OfficeConfiguration` | `PCConfiguration and (hasPurpose value "office")` |

Наприклад, `hasSocket value Socket_AM4` — застосування зразка `hasState value EmergencyState` до PC Builder. Еквівалентна форма: `hasSocket some {Socket_AM4}`.

`SocketCompatibleConfiguration` означає лише збіг типу сокета CPU та плати в цьому закритому довіднику. Довільну конфігурацію не оголошено підкласом сумісних. При заміні AM4-плати на AM5-плату модель може залишатися узгодженою, але HermiT доводить, що така конфігурація не належить до сумісних. Це перевірено окремим контрольним прикладом.

## Отримана inferred class hierarchy

Нижче — ієрархія, отримана від HermiT; `owl:Nothing` не показано, оскільки невиконуваних іменованих класів немає.

```text
owl:Thing
├── Component
│   ├── CPU
│   │   ├── AM4CPU
│   │   ├── AM5CPU
│   │   ├── LGA1700CPU
│   │   └── EfficientCPU
│   ├── Motherboard
│   │   ├── AM4Motherboard
│   │   ├── AM5Motherboard
│   │   └── LGA1700Motherboard
│   └── PowerSupply
│       └── HighPowerSupply
├── PCConfiguration
│   ├── SocketCompatibleConfiguration
│   │   ├── AM4Configuration
│   │   ├── AM5Configuration
│   │   └── LGA1700Configuration
│   ├── EfficientConfiguration
│   └── OfficeConfiguration
└── Socket
```

Нові зв’язки підкласів не прописано окремими `SubClassOf` для визначених класів: reasoner вивів їх з еквівалентних виразів. Зокрема, три платформні конфігурації розташувалися під `SocketCompatibleConfiguration`, а той — під `PCConfiguration`.

`EfficientCPU` перетинається з класами сокетів: економічність і тип сокета — незалежні ознаки. `CPU_AM4_65W` належить одночасно до `AM4CPU` та `EfficientCPU`. Аналогічно `PC_Office_AM4` належить до `AM4Configuration`, `EfficientConfiguration` та `OfficeConfiguration`.

`OfficeConfiguration` не виведено підкласом `EfficientConfiguration`: одного економічного прикладу недостатньо для такого загального правила. HermiT також вивів несумісність `AM4CPU` з `AM5CPU` та відповідних класів конфігурацій: одна функціональна властивість сокета не може одночасно мати два різні значення.

## Виведені екземпляри

| Клас | Individuals, отримані від HermiT |
|---|---|
| `AM4CPU` | `CPU_AM4_65W`, `CPU_AM4_105W` |
| `AM5CPU` | `CPU_AM5_65W` |
| `LGA1700CPU` | `CPU_LGA1700_125W` |
| `AM4Motherboard` | `Motherboard_AM4_A`, `Motherboard_AM4_B` |
| `AM5Motherboard` | `Motherboard_AM5` |
| `LGA1700Motherboard` | `Motherboard_LGA1700` |
| `AM4Configuration` | `PC_Office_AM4`, `PC_Performance_AM4` |
| `AM5Configuration` | `PC_Modern_AM5` |
| `LGA1700Configuration` | `PC_Intel_LGA1700` |
| `SocketCompatibleConfiguration` | Усі 4 вихідні конфігурації |
| `EfficientCPU` | `CPU_AM4_65W`, `CPU_AM5_65W` |
| `HighPowerSupply` | `PSU_650W`, `PSU_750W` |
| `EfficientConfiguration` | `PC_Office_AM4`, `PC_Modern_AM5` |
| `OfficeConfiguration` | `PC_Office_AM4` |

## Перевірка обмежень

HermiT підтвердив узгодженість, виконуваність усіх 20 класів, очікувані екземпляри, обернені зв’язки й рівно три виведені компоненти кожної конфігурації. Додатковий код перевірив наявність усіх необхідних явних значень, а також навчальну умову `Wattage ≥ CPU TDP` і суми цін.

Виконано **16 негативних контролів** на окремих копіях лише в пам’яті. Кожен спричинив очікувану неузгодженість:

| № | Навмисна зміна |
|---|---|
| 1 | CPU одночасно оголошено Motherboard |
| 2 | CPU має два різні сокети |
| 3 | Union-domain hasSocket замінено двома окремими Domain |
| 4 | Текст замість числового TDP |
| 5 | Нульовий TDP |
| 6 | Від’ємна потужність БП |
| 7 | Від’ємна ціна |
| 8 | Призначення `gaming`, відсутнє в enumeration |
| 9 | Два різні значення функціонального hasPurpose |
| 10 | Четвертий відмінний компонент при max 3 |
| 11 | Компонент, який явно не є CPU, Motherboard або PowerSupply; для ізоляції only тимчасово вилучено max 3 |
| 12 | Четвертий сокет, явно відмінний від усіх трьох дозволених |
| 13 | Socket як значення hasComponent |
| 14 | Самопосилання через hasCPU |
| 15 | Другий відмінний CPU при exactly 1 |
| 16 | Явне max 0 для hasCPU за наявної вимоги існування; пряме твердження CPU тимчасово вилучено |

Два додаткові контрольні приклади залишаються узгодженими: вилучення явного зв’язку CPU та заміна плати на іншу платформу. У першому випадку HermiT усе одно доводить існування CPU; у другому — доводить неналежність до `SocketCompatibleConfiguration`.

OWL використовує припущення відкритого світу: невідоме значення не дорівнює забороненому або відсутньому. Тому `exactly 1` не гарантує наявності явного запису у файлі; повноту даних перевірено окремо. [W3C: What is OWL 2?](https://www.w3.org/TR/owl2-primer/#What_is_OWL_2.3F).

Порівняння чисел у різних індивідів (`Wattage ≥ TDP`) та сумування цін виконуються процедурно. Вони не подаються як висновки HermiT чи повна інженерна перевірка ПК.

## Повторення перевірки

У корені проєкту, PowerShell, JDK 11+:

```powershell
.\validation\run-validation.ps1
```

За потреби шлях до JDK можна передати явно:

```powershell
.\validation\run-validation.ps1 -JavaHome 'C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot'
```

Бібліотеки вже є в `validation/lib`; мережа й запущений Protégé не потрібні. Перевірка компілює актуальні вихідні файли, оновлює журнал, результати виведення й контрольну суму. Фінальний OWL не редагується.

Відтворення OWL, якщо встановлено Node.js:

```powershell
node .\build_ontology.mjs
```

Генератор читає збережену вихідну онтологію `validation/practice2/PC_Builder.owl`, додає аксіоми та записує кореневий `PC_Builder.owl`. Повторний запуск дає той самий файл.

Для перегляду у Protégé: відкрити кореневий `PC_Builder.owl`, вибрати `Reasoner → HermiT → Start reasoner`, перейти до `Classes` та виведеної ієрархії; перевірити `Equivalent To` для `AM4CPU` і `SocketCompatibleConfiguration`, а також виведені екземпляри та обернені зв’язки. Якщо завантажена стара версія, спочатку виконати `File → Reload`.

Нова версія в GUI автоматично не перевірялася. Зображення в `screenshots` належать практичній № 2; доказом поточного запуску HermiT є новий журнал, а не старі знімки.

## Збереження другої практичної

До початку змін створено локальний Git-репозиторій. Початковий коміт **`542a07a` — «Практика 2: початкова онтологія PC Builder»**, позначений тегом **`practice-2`**, містить усі 60 початкових файлів. Зовнішній Git remote не налаштовано.

[Звіт другої практичної](REPORT_PRACTICE2.md), [початковий OWL](validation/practice2/PC_Builder.owl) та [початковий журнал](validation/practice2/reasoner-output.txt) збережено окремо. Архів `PC_Builder_Practice2.zip` залишено без змін.

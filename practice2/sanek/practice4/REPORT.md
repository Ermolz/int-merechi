# Практичне заняття № 4

Варіант 5. Базові SWRL-правила MLOps.

[MLOps.owl](MLOps.owl) містить 5 активних правил: 2 для відношень і 3 для числової бізнес-логіки. Збережено 37 автоматично виведених фактів: 21 об’єктний зв’язок, 8 розрахованих значень і 8 належностей до класів. Файл також містить всі аксіоми попередніх практик.

## Правила

```text
R1_SharedGPU:
MLModel(?m) ^ MLModel(?n) ^ deployedOn(?m, ?g) ^ deployedOn(?n, ?g) ^ differentFrom(?m, ?n)
-> sharesGPUWith(?m, ?n)

R2_PeerAccelerator:
MLModel(?m) ^ sharesGPUWith(?m, ?n) ^ requiresAccelerator(?n, ?a)
-> hasPeerAccelerator(?m, ?a)

R3_FP16Memory:
MLModel(?m) ^ hasPrecision(?m, "FP16") ^ hasParameterCountNum(?m, ?p) ^ swrlb:multiply(?weights, ?p, 2) ^ swrlb:add(?required, ?weights, 2)
-> hasCalculatedVRAM(?m, ?required)

R4_SufficientMemory:
MLModel(?m) ^ deployedOn(?m, ?g) ^ hasCalculatedVRAM(?m, ?required) ^ hasAvailableVRAM(?g, ?available) ^ swrlb:greaterThanOrEqual(?available, ?required)
-> VRAMSufficientModel(?m)

R5_InsufficientMemory:
MLModel(?m) ^ deployedOn(?m, ?g) ^ hasCalculatedVRAM(?m, ?required) ^ hasAvailableVRAM(?g, ?available) ^ swrlb:lessThan(?available, ?required)
-> VRAMInsufficientModel(?m)
```

Навчальна формула FP16: 2 × P + 2 ГБ, де P задано у млрд параметрів. Другий доданок - фіксований резерв прикладу; довжина контексту, batch size і змінний кеш не моделюються. hasCalculatedVRAM зберігає розрахунок, hasRequiredVRAM - вихідні вимоги; для всіх восьми прикладів вони збігаються.

sharesGPUWith означає використання одного запису GPU у сценаріях; hasPeerAccelerator - прискорювач, потрібний іншій моделі з таким самим записом розміщення. Цей зв’язок не є рекомендацією або доказом достатності пам’яті. Порівняння VRAM стосується окремої моделі, без підсумовування одночасного споживання кількох моделей.

## Результати числових правил

| Модель | hasCalculatedVRAM, ГБ | GPU, ГБ | Клас |
|---|---:|---:|---|
| LLM_1B_Small | 4 | 8 | VRAMSufficientModel |
| LLM_3B_Edge | 8 | 8 | VRAMSufficientModel |
| LLM_7B_Chat | 16 | 24 | VRAMSufficientModel |
| LLM_7B_Limited | 16 | 8 | VRAMInsufficientModel |
| LLM_13B_Assistant | 28 | 24 | VRAMInsufficientModel |
| LLM_70B_Server | 142 | 80 | VRAMInsufficientModel |
| CV_1B_Detection | 4 | 8 | VRAMSufficientModel |
| CV_2B_Segmentation | 6 | 16 | VRAMSufficientModel |

Граничний випадок LLM_3B_Edge: 8 ≥ 8, тому пам’яті достатньо. VRAMSufficientModel та VRAMInsufficientModel є несумісними класами.

## Причини спрацьовування

1. R1: LLM_7B_Chat deployedOn GPU_24GB і LLM_13B_Assistant deployedOn GPU_24GB; індивіди різні → sharesGPUWith між ними в обох напрямах.
2. R2: LLM_7B_Chat sharesGPUWith LLM_13B_Assistant; LLM_13B_Assistant requiresAccelerator GPU_48GB → LLM_7B_Chat hasPeerAccelerator GPU_48GB.
3. R3 та R4: LLM_3B_Edge має FP16 і P=3; multiply дає 6, add дає 8; GPU_8GB має 8 ГБ; greaterThanOrEqual(8,8) → VRAMSufficientModel.
4. R3 та R5: LLM_13B_Assistant має P=13; розрахунок 28; GPU_24GB має 24 ГБ; lessThan(24,28) → VRAMInsufficientModel.

## П’ять питань DL Query

До виконання SWRL усі п’ять запитів мали порожній результат. Після Drools:

| Питання / вираз | Відповідь |
|---|---|
| Яка модель використовує запис GPU разом із LLM_7B_Chat? `MLModel and (sharesGPUWith value LLM_7B_Chat)` | LLM_13B_Assistant |
| Якій моделі через сусіда відомий GPU_48GB? `MLModel and (hasPeerAccelerator value GPU_48GB)` | LLM_7B_Chat |
| Яким моделям вистачає VRAM? `VRAMSufficientModel` | LLM_1B_Small, LLM_3B_Edge, LLM_7B_Chat, CV_1B_Detection, CV_2B_Segmentation |
| Яким моделям не вистачає VRAM? `VRAMInsufficientModel` | LLM_7B_Limited, LLM_13B_Assistant, LLM_70B_Server |
| Для яких моделей розраховано ≥ 24 ГБ? `MLModel and (hasCalculatedVRAM some xsd:integer[>= 24])` | LLM_13B_Assistant, LLM_70B_Server |

## Суперечливе правило та перевірка

У тимчасовій копії виконано `LargeLanguageModel(?m) -> ComputerVisionModel(?m)`. Воно порушило DisjointClasses(LargeLanguageModel, ComputerVisionModel). Після Drools HermiT підтвердив неузгодженість копії. Помилкове правило відсутнє у підсумковому файлі.

Синтаксис усіх п’яти правил перевірив SWRLAPI. Правила реально виконано Drools 7.57 через SWRLAPI 2.0.10. HermiT перевірив OWL-аксіоми та матеріалізовані результати без SWRL-правил; усі запити виконано через Manchester parser та HermiT. Підсумковий RDF/XML повторно прочитано, усі п’ять правил збережені. Виконання відбувалося поза GUI.

Для HermiT і DL Query підготовлено [MLOps_Inferred.owl](MLOps_Inferred.owl): той самий результат Drools без SWRL-правил, у профілі OWL 2 DL. Цей файл містить 5 VRAMSufficientModel та 3 VRAMInsufficientModel. У ньому можна виконати всі п’ять запитів через HermiT.

У Protégé: File → Open → MLOps.owl; Window → Tabs → SWRLTab для правил; Individuals для збережених нових фактів. У SWRLTab використати Import OWL Axioms → Run Drools → Export Inferred Axioms, якщо потрібен повторний запуск. Для запитів відкрити MLOps_Inferred.owl, запустити Reasoner → HermiT → Start reasoner та увімкнути Window → Tabs → DL Query; обрати Instances. HermiT не використовується для виконання числових SWRL built-ins.

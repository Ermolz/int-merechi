# Практичне заняття № 4. Базові SWRL-правила

Онтологія PC Builder містить шість правил SWRL.

| Правило | Умова й результат |
|---|---|
| R1 | Однаковий сокет CPU і плати → `compatibleWith` |
| R2 | Сокет CPU конфігурації → `usesSocket` |
| R3 | Обрана плата сумісна з CPU → `hasCompatibleMotherboard` |
| R4 | Потужність БЖ ≥ TDP процесора + 150 Вт → `PowerAdequateConfiguration` |
| R5 | Сума цін CPU, плати та БЖ → `hasTotalPrice` |
| R6 | Загальна ціна ≤ бюджет → `WithinBudgetConfiguration` |

## Запуск Drools

SWRLTab передав рушію 6 правил. Drools виконав їх успішно. [Скриншот запуску](evidence/01-drools.png)

У робочій копії з `PC_Office_AM4` прибрали три твердження. Після запуску Drools та перенесення результатів до OWL отримано:

| Правило | Умова спрацювання | Виведений факт | Скриншоти |
|---|---|---|---|
| R2 | `hasCPU` вказує на `CPU_AM4_65W`, його `hasSocket` — `Socket_AM4` | `usesSocket Socket_AM4` | [До](evidence/02-before-socket.png), [після](evidence/04-after-socket.png) |
| R3 | Обрана плата `Motherboard_AM4_A` і `compatibleWith(CPU_AM4_65W, Motherboard_AM4_A)` | `hasCompatibleMotherboard Motherboard_AM4_A` | [До](evidence/03-before-motherboard.png), [після](evidence/05-after-motherboard.png) |
| R5 | Ціни трьох комплектуючих 120, 90 і 50 підсумовує `swrlb:add` | `hasTotalPrice 260.00` | [Після](evidence/06-after-price.png) |

## Перевірка суперечності

Правило `CPU(?x) -> Motherboard(?x)` суперечить аксіомі несумісності цих класів. HermiT підтвердив, що модель узгоджена до додавання правила, неузгоджена з ним і знову узгоджена після його вилучення.

HermiT запускався через OWLAPI з уже збереженими фактами. Для цієї перевірки числові правила R4–R6 прибрано з моделі в пам’яті. [Журнал перевірки](evidence/hermit.txt)

## DL Query

| Питання | Запит | Результат HermiT |
|---|---|---|
| Які конфігурації вкладаються в бюджет? | `WithinBudgetConfiguration` | `PC_Intel_LGA1700`, `PC_Modern_AM5`, `PC_Office_AM4` |
| Які конфігурації використовують AM4? | `usesSocket value Socket_AM4` | `PC_Office_AM4`, `PC_Performance_AM4` |
| У якій конфігурації сумісна плата AM4 A? | `hasCompatibleMotherboard value Motherboard_AM4_A` | `PC_Office_AM4` |

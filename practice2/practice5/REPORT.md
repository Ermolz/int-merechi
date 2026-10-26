# Практичне заняття 5 Базові SPARQL запити

**Варіант 1. Конфігуратор комплектуючих ПК (PC Builder).**

Сформульовано п’ять аналітичних питань, підготовлено SELECT-запити та порівняно явні факти з результатами логічного виводу. Використано онтологію четвертої практики; її вихідний файл не змінено.

## Файли та режими виконання

- [PC_Builder_Asserted.owl](PC_Builder_Asserted.owl): OWL-аксіоми й уже збережені факти четвертої практики, без шести SWRL-правил. Правила не видалялися з оригіналу. Тут збережено й 25 фактів, отриманих SWRL раніше; вони вже належать до Asserted для цієї практики.
- [PC_Builder_Inferred.owl](PC_Builder_Inferred.owl): те саме знання з доданими належностями до іменованих класів і зв’язками, виведеними HermiT. Звичайні Data Properties перенесені з вихідного файла; їхні значення в цій практиці не перевизначаються.
- [queries/standard](queries/standard): п’ять запитів для стандартного SPARQL Query.
- [queries/snap](queries/snap): сумісні форми тих самих п’яти питань для Snap SPARQL.
- [results](results): десять CSV-таблиць, [results.json](results/results.json) та [78 нових трійок](results/new-triples.tsv).

Результати отримані справжніми движками `BasicSparqlReasoner` стандартного плагіна SPARQL Query 3.0.0 та Snap SPARQL API 4.0.0 із плагіна Snap 6.0.0. HermiT сформував замикання за іменованими класами й Object Properties. Snap працював зі Structural Reasoner над уже матеріалізованим файлом Inferred. Цей спосіб виконання відтворюється в Protégé й не вимагає запуску числових SWRL built-ins у HermiT.

Виконання через графічні вкладки не підтверджене: захоплення вікна Protégé двічі завершилося тайм-аутом. Перевірка виконана через API тих самих плагінів. Snap 6.0.0 додано в каталог плагінів; для появи його View потрібен перезапуск Protégé.

## Підсумок вибірок

| Питання | Asserted, рядків | Inferred, рядків |
|---|---:|---:|
| 1 | 4 | 4 |
| 2 | 0 | 1 |
| 3 | 4 | 4 |
| 4 | 0 | 3 |
| 5 | 0 | 4 |

## Запити та порівняльні таблиці

### Питання 1

Які процесори є в каталозі, який сокет і TDP має кожен?

Код: [стандартний](queries/standard/01_cpu_catalog.rq), [Snap](queries/snap/01_cpu_catalog.rq).

```sparql
PREFIX : <https://example.org/pc-builder#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?cpu ?socket ?tdp
WHERE {
  ?cpu a :CPU ;
       :hasSocket ?socket ;
       :hasTDP ?tdp .
}
ORDER BY ASC(?cpu)
```

**Asserted — стандартний SPARQL Query**

| cpu | socket | tdp |
|---|---|---|
| CPU_AM4_105W | Socket_AM4 | 105 |
| CPU_AM4_65W | Socket_AM4 | 65 |
| CPU_AM5_65W | Socket_AM5 | 65 |
| CPU_LGA1700_125W | Socket_LGA1700 | 125 |

**Inferred — Snap SPARQL**

| cpu | socket | tdp |
|---|---|---|
| CPU_AM4_105W | Socket_AM4 | 105 |
| CPU_AM4_65W | Socket_AM4 | 65 |
| CPU_AM5_65W | Socket_AM5 | 65 |
| CPU_LGA1700_125W | Socket_LGA1700 | 125 |

Явні CPU, hasSocket та hasTDP вже записані в онтології. Тому результати обох режимів збігаються.

### Питання 2

Які офісні конфігурації AM4 коштують не більше 300 умовних одиниць?

Код: [стандартний](queries/standard/02_office_am4_budget.rq), [Snap](queries/snap/02_office_am4_budget.rq).

```sparql
PREFIX : <https://example.org/pc-builder#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?pc ?cpu ?purpose ?totalPrice
WHERE {
  ?pc a :OfficeConfiguration, :AM4Configuration ;
      :hasCPU ?cpu ;
      :hasPurpose ?purpose ;
      :hasTotalPrice ?totalPrice .
  FILTER (?purpose = "office" && ?totalPrice <= 300)
}
ORDER BY ASC(?pc)
```

У Snap два типи записані окремо: `?pc a :OfficeConfiguration ; a :AM4Configuration ; ...`. Це еквівалентно стандартній формі з комою.

**Asserted — стандартний SPARQL Query**

| pc | cpu | purpose | totalPrice |
|---|---|---|---|

Порожня вибірка: 0 рядків.

**Inferred — Snap SPARQL**

| pc | cpu | purpose | totalPrice |
|---|---|---|---|
| PC_Office_AM4 | CPU_AM4_65W | office | 260.00 |

Для PC_Office_AM4 виведено належність до OfficeConfiguration за hasPurpose="office" та до AM4Configuration за процесором і платою AM4. Ціна 260.00 вже збережена після четвертої практики.

### Питання 3

Які ціни й TDP мають процесори та в яких конфігураціях вони використовуються, якщо ці зв’язки відомі?

Код: [стандартний](queries/standard/03_cpu_optional_usage.rq), [Snap](queries/snap/03_cpu_optional_usage.rq).

```sparql
PREFIX : <https://example.org/pc-builder#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?cpu ?price ?tdp ?pc ?purpose
WHERE {
  ?cpu a :CPU ;
       :hasPrice ?price ;
       :hasTDP ?tdp .
  OPTIONAL {
    ?cpu :isCPUOf ?pc .
    OPTIONAL { ?pc :hasPurpose ?purpose . }
  }
}
ORDER BY ASC(?cpu) ASC(?pc)
```

**Asserted — стандартний SPARQL Query**

| cpu | price | tdp | pc | purpose |
|---|---|---|---|---|
| CPU_AM4_105W | 220.00 | 105 | UNBOUND | UNBOUND |
| CPU_AM4_65W | 120.00 | 65 | UNBOUND | UNBOUND |
| CPU_AM5_65W | 250.00 | 65 | UNBOUND | UNBOUND |
| CPU_LGA1700_125W | 300.00 | 125 | UNBOUND | UNBOUND |

**Inferred — Snap SPARQL**

| cpu | price | tdp | pc | purpose |
|---|---|---|---|---|
| CPU_AM4_105W | 220.00 | 105 | PC_Performance_AM4 | performance |
| CPU_AM4_65W | 120.00 | 65 | PC_Office_AM4 | office |
| CPU_AM5_65W | 250.00 | 65 | PC_Modern_AM5 | general |
| CPU_LGA1700_125W | 300.00 | 125 | PC_Intel_LGA1700 | performance |

Чотири рядки CPU збережено в обох режимах. Після виводу isCPUOf як inverseOf(hasCPU) змінні pc і purpose стають зв’язаними. У режимі Asserted вони UNBOUND.

### Питання 4

Скільки процесорних комплектуючих припадає на кожен сокет, яка сума їхніх цін, середній TDP та один приклад CPU?

Код: [стандартний](queries/standard/04_socket_statistics.rq), [Snap](queries/snap/04_socket_statistics.rq).

```sparql
PREFIX : <https://example.org/pc-builder#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?socket
       (COUNT(DISTINCT ?cpu) AS ?cpuCount)
       (SUM(?price) AS ?priceSum)
       (AVG(?tdp) AS ?averageTDP)
       (SAMPLE(?cpu) AS ?sampleCPU)
WHERE {
  ?cpu a :Component ;
       :hasSocket ?socket ;
       :hasPrice ?price ;
       :hasTDP ?tdp .
}
GROUP BY ?socket
HAVING (COUNT(DISTINCT ?cpu) >= 1)
ORDER BY DESC(?cpuCount) ASC(?socket)
```

У формі для Snap прибрано HAVING через обмеження реалізації плагіна. Еквівалентність для цього набору даних перевірено окремо; пояснення наведено нижче.

**Asserted — стандартний SPARQL Query**

| socket | cpuCount | priceSum | averageTDP | sampleCPU |
|---|---|---|---|---|

Порожня вибірка: 0 рядків.

**Inferred — Snap SPARQL**

| socket | cpuCount | priceSum | averageTDP | sampleCPU |
|---|---|---|---|---|
| Socket_AM4 | 2 | 340.00 | 85.00 | CPU_AM4_105W |
| Socket_AM5 | 1 | 250.00 | 65.00 | CPU_AM5_65W |
| Socket_LGA1700 | 1 | 300.00 | 125.00 | CPU_LGA1700_125W |

Усі CPU є Component через ієрархію класів і Domain hasPrice. Явні rdf:type Component не записані, тому до виводу немає груп; після виводу з’являються три групи сокетів.

### Питання 5

Які конфігурації містять три комплектуючі та які сума і середня ціна їхніх компонентів?

Код: [стандартний](queries/standard/05_configuration_totals.rq), [Snap](queries/snap/05_configuration_totals.rq).

```sparql
PREFIX : <https://example.org/pc-builder#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?pc
       (COUNT(DISTINCT ?component) AS ?componentCount)
       (SUM(?price) AS ?totalPrice)
       (AVG(?price) AS ?averagePrice)
WHERE {
  ?pc a :PCConfiguration ;
      :hasComponent ?component .
  ?component :hasPrice ?price .
}
GROUP BY ?pc
HAVING (COUNT(DISTINCT ?component) = 3)
ORDER BY ASC(?totalPrice) ASC(?pc)
```

У формі для Snap прибрано HAVING через обмеження реалізації плагіна. Еквівалентність для цього набору даних перевірено окремо; пояснення наведено нижче.

**Asserted — стандартний SPARQL Query**

| pc | componentCount | totalPrice | averagePrice |
|---|---|---|---|

Порожня вибірка: 0 рядків.

**Inferred — Snap SPARQL**

| pc | componentCount | totalPrice | averagePrice |
|---|---|---|---|
| PC_Office_AM4 | 3 | 260.00 | 86.67 |
| PC_Performance_AM4 | 3 | 440.00 | 146.67 |
| PC_Modern_AM5 | 3 | 510.00 | 170.00 |
| PC_Intel_LGA1700 | 3 | 560.00 | 186.67 |

hasCPU, hasMotherboard та hasPowerSupply є підвластивостями hasComponent. Reasoner виводить по три hasComponent для кожної конфігурації; SUM дає 260, 440, 510 і 560.

## Синтаксис та обмеження движків

У стандартних запитах використано `;` для властивостей одного суб’єкта та `,` для двох типів у питанні 2. Snap 6.0.0 відхилив список об’єктів із комою; форма з повторним `a` має той самий BGP.

У тестованому Snap умови HAVING з агрегатами повернули порожні таблиці; форми без HAVING повернули потрібні групи. Тому стандартні запити містять GROUP BY / HAVING, а у Snap:

- Для питання 4 HAVING(COUNT(DISTINCT ?cpu) >= 1) можна вилучити: кожна група утворюється хоча б одним зв’язаним CPU.
- Для питання 5 вилучення HAVING(COUNT(DISTINCT ?component) = 3) допустиме для поточного Inferred: кожна PCConfiguration має три різні компоненти, що підтверджено OWL-обмеженнями min 3 / max 3 та перевіркою даних. Якщо модель або дані зміняться, цю еквівалентність потрібно перевірити знову.

LIMIT та OFFSET у запитах не використовуються. Сортування задано перевіреною формою ORDER BY ASC(...) / DESC(...). COUNT, SUM, AVG і SAMPLE виконані обома движками. SAMPLE може вибрати будь-який CPU групи; для AM4 допустимі CPU_AM4_65W або CPU_AM4_105W. Числові значення в таблицях округлено до двох знаків; CSV і JSON містять повні значення движків.

Кожен результат Snap додатково порівняно з результатом стандартного SPARQL над матеріалізованим Inferred. SAMPLE звіряється як довільний представник групи, а числові відмінності лише в округленні AVG враховано при перевірці.

## FILTER OPTIONAL та пропуски

У питанні 2 FILTER перевіряє текстове призначення та числову ціну. Значення hasPurpose є рядком, hasTotalPrice — числом. Контрольний вираз `FILTER(?purpose > 300)` на тих самих конфігураціях повернув 0 рядків в обох движках: несумісність типів дає Error, а FILTER залишає лише True; False та Error відкидаються.

У питанні 3 обов’язковий BGP спочатку зв’язує cpu, price і tdp. Зовнішній OPTIONAL шукає pc для вже відомого CPU, а вкладений OPTIONAL — purpose для цієї pc. Обов’язкові змінні оголошені до необов’язкових шаблонів. Відсутність isCPUOf у Asserted залишає pc і purpose незв’язаними та зберігає рядок CPU. UNBOUND означає відсутність прив’язки змінної, а не нуль, порожній літерал чи доказ відсутності об’єкта.

## Які трійки додав reasoner

Збережено **78 нових фактів**: 34 належності до іменованих класів і 44 Object Property assertions. Тавтологічні rdf:type owl:Thing не експортувалися.

| Тип фактів | Asserted | Inferred | Додано |
|---|---:|---:|---:|
| Class assertions | 25 | 59 | 34 |
| Object Property assertions | 34 | 78 | 44 |

| Новий зв’язок | Кількість |
|---|---:|
| hasComponent | 12 |
| isComponentOf | 12 |
| isCPUOf | 4 |
| isMotherboardOf | 4 |
| isPowerSupplyOf | 4 |
| isSocketOf | 8 |

Приклади нових трійок:

```turtle
@prefix : <https://example.org/pc-builder#> .
:PC_Office_AM4 a :OfficeConfiguration, :AM4Configuration .
:CPU_AM4_65W a :Component ; :isCPUOf :PC_Office_AM4 .
:PC_Office_AM4 :hasComponent :CPU_AM4_65W, :Motherboard_AM4_A, :PSU_450W .
```

Належність до батьківських і Defined Classes виникла з ієрархії, Domain та EquivalentClasses. Зворотні зв’язки виникли з inverseOf, а загальні hasComponent — з subPropertyOf. Саме ці трійки заповнили OPTIONAL і дали нові групи та рядки у питаннях 2–5. Сума і середнє у SELECT обчислюються SPARQL-агрегатами й самі не додають OWL-аксіом. Значення hasTotalPrice, отримані у практиці 4, вже входили до початкового Asserted.

## Як переглянути у Protégé

1. Перезапустити Protégé після додавання Snap 6.0.0.
2. Відкрити PC_Builder_Asserted.owl в окремому вікні. У Window → Tabs увімкнути SPARQL Query; вставляти коди з queries/standard і виконувати їх без reasoner.
3. В іншому вікні відкрити PC_Builder_Inferred.owl. У Reasoner обрати Structural Reasoner та Start reasoner.
4. Вибрати Window → Views → Query Views → Snap SPARQL Query і розмістити View на потрібній вкладці. Вставляти коди з queries/snap та натискати Execute.
5. Порівняти SELECT-стовпці з таблицями цього звіту та CSV. Використання окремих вікон зберігає два графи окремими для порівняння.

Для повторної локальної перевірки запустити `validation/run-validation.ps1`. Потрібні наявний JDK 17, бібліотеки попередніх практик і плагіни установленого Protégé. [Журнал](validation/run-output.txt) містить результати та перевірки; [SHA-256](validation/sha256.txt) фіксує перевірені OWL-файли.

Офіційні компоненти: [стандартний SPARQL Query](https://github.com/protegeproject/sparql-query-plugin), [Snap SPARQL API](https://github.com/protegeproject/snap-sparql-query), [офіційний запис Snap 6.0.0](https://raw.githubusercontent.com/protegeproject/autoupdate/master/snap-sparql-query/update-info/protege-5/update.properties). Посилання на релізи у вихідному завданні веде до стандартного SPARQL Query; Snap є окремим плагіном.

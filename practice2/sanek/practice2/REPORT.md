# Практичне заняття № 2

Варіант 5. Добір обладнання під ML-моделі (MLOps).

Реалізовано концептуальну модель у [MLOps.owl](MLOps.owl): 5 класів, 2 Object Properties, 3 Data Properties, 13 різних індивідів, 16 прямих об’єктних фактів і 21 числовий факт.

## Класи

LargeLanguageModel і ComputerVisionModel є підкласами MLModel; GPU є підкласом HardwareAccelerator. Створено 6 мовних моделей, 2 моделі комп’ютерного зору та 5 GPU. Загальні класи отримують екземпляри через успадкування.

## Властивості

| Властивість | Domain | Range |
|---|---|---|
| requiresAccelerator | MLModel | HardwareAccelerator |
| deployedOn | MLModel | GPU |
| hasParameterCountNum | MLModel | xsd:long, млрд параметрів |
| hasRequiredVRAM | MLModel | xsd:integer, ГБ |
| hasAvailableVRAM | GPU | xsd:integer, ГБ |

deployedOn є підвластивістю requiresAccelerator. Тому для LLM_13B_Assistant, яка потребує GPU_48GB та розміщена на GPU_24GB, reasoner виводить додатковий requiresAccelerator → GPU_24GB.

## Перевірка

HermiT через OWLAPI підтвердив узгодженість та відповідність OWL 2 DL. Усі п’ять класів мають екземпляри з урахуванням успадкування. Набір індивідів і значення відповідають UML першої практики.

У Protégé: File → Open → MLOps.owl; Entities → Classes, Object properties, Data properties, Individuals. Для графа: Window → Tabs → OntoGraf. Перевірку reasoner виконано поза GUI.

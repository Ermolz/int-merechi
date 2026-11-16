# Практичне заняття № 3

Варіант 5. Формальні умови та обмеження MLOps.

У [MLOps.owl](MLOps.owl) збережено всі факти другої практики. Доповнений файл містить 10 класів, 4 Object Properties, 4 Data Properties та 13 індивідів.

## Області та характеристики

requiresAccelerator: MLModel → HardwareAccelerator; isRequiredBy: HardwareAccelerator → MLModel. deployedOn: MLModel → GPU; hostsModel: GPU → MLModel. Перші два утворюють одну пару inverseOf, останні два - другу. Зворотні твердження явно не вводилися.

deployedOn є Functional; hostsModel - InverseFunctional. Усі чотири об’єктні властивості Asymmetric та Irreflexive. Data Properties є Functional; Domain числових параметрів і hasPrecision - MLModel, а hasAvailableVRAM - GPU.

PositiveParameterCount обмежує xsd:long значеннями ≥ 1; PositiveVRAM обмежує xsd:integer значеннями ≥ 1. ModelPrecision - enumeration {"FP16", "INT8"}; hasPrecision має цей Range. Усі приклади використовують FP16.

## Обмеження

MLModel має requiresAccelerator some HardwareAccelerator, only HardwareAccelerator, min 1 і max 2 HardwareAccelerator; deployedOn exactly 1 GPU та only GPU. Кожен числовий параметр і hasPrecision має exactly 1 значення відповідного типу. GPU має exactly 1 hasAvailableVRAM.

MLModel disjointWith HardwareAccelerator; LargeLanguageModel disjointWith ComputerVisionModel. Усі 13 індивідів попарно різні. Клас GPU закрито переліком GPU_8GB, GPU_16GB, GPU_24GB, GPU_48GB, GPU_80GB.

## Defined Classes та результати HermiT

| Клас | Equivalent To | Inferred Individuals |
|---|---|---|
| FP16Model | MLModel and (hasPrecision value "FP16") | усі 8 моделей |
| ModelOnGPU24 | MLModel and (deployedOn value GPU_24GB) | LLM_7B_Chat, LLM_13B_Assistant |
| LargeMemoryModel | MLModel and (hasRequiredVRAM some xsd:integer[>= 24]) | LLM_13B_Assistant, LLM_70B_Server |
| HighMemoryGPU | GPU and (hasAvailableVRAM some xsd:integer[>= 48]) | GPU_48GB, GPU_80GB |
| ModelOnHighMemoryGPU | MLModel and (deployedOn some HighMemoryGPU) | LLM_70B_Server |

Inferred hierarchy розміщує FP16Model, ModelOnGPU24, LargeMemoryModel та ModelOnHighMemoryGPU під MLModel; HighMemoryGPU - під GPU. Для GPU_8GB виведено чотири hostsModel; для LLM_13B_Assistant - два requiresAccelerator.

## Перевірка

HermiT поза GUI: онтологія узгоджена; профіль OWL 2 DL дотримано; невиконуваних іменованих класів немає. Вісім окремих копій з навмисними помилками стали неузгодженими: несумісні типи моделей, модель як GPU, два різні значення VRAM, нульова пам’ять, FP32 поза enumeration, два розміщення, перевищення max 2 та ототожнення різних індивідів. У підсумковому файлі цих помилок немає.

OWL перевіряє структуру та обмеження типів. Нестача VRAM сама по собі не створює OWL-суперечності; її класифікують SWRL-правила четвертої практики. Відсутність явного факту за відкритого світу не є автоматичним доказом порушення мінімальної кратності; повноту вихідних даних перевірено окремо.

У Protégé: Entities → Classes → Description для обмежень та Equivalent To; Object properties для Domain/Range/Inverse Of/Characteristics; Data properties і Datatypes для типів; Individuals для фактів. Reasoner → HermiT → Start reasoner, потім Classes → Inferred для ієрархії.

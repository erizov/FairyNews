# Этап № 2. Сбор и обработка базы | GPT Engineer

См. также: [перечни сайтов со сказками и новостями, технологии и архитектура RAG](istochniki_skazok_novostey_i_rag.md).

## 1. Имеющаяся база и необходимость доработки

**База данных (корпуса текстов) уже есть в наличии** — на этапе реализации проекта «Нейро-сказочник» предполагается опираться на неё как на отправную точку.

**Возможно потребуется дополнить и доработать** материалы: расширить объём, выровнять формат, устранить дубликаты, добавить метаданные (язык, регион, жанр, источник) или закрыть пробелы по отдельным доменам (русские / европейские / американские / восточные сказки, блок новостей).

Для **корректной работы системы** (генерация в русском стиле и антураже сказки, RAG по разным контурам) база должна быть **согласована с требованиями пайплайна**: единая схема хранения, лицензионно допустимое использование текстов, актуальность новостного слоя при необходимости.

---

## 2. Сбор и обработка базы

Параллельно с использованием уже имеющейся базы **требуется организовать сбор и обработку** данных по нижеперечисленным каналам — в зависимости от объёма задач этапа и приоритетов.

### 2.1. Открытые источники

- Использование **открытых** корпусов, архивов и датасетов, доступных в соответствии с лицензиями и условиями использования.
- Учёт **авторских прав** и **этики**: публичные сказки, фольклорные сборники, материалы с явным разрешением на обработку; для текстов **советских авторов** — проверять статус произведения и условия конкретного издания/файла.
- Собранные тексты группируются под **контуры RAG**: русский блок (народ + литература + **советская** детская и сказочная проза), европейский, американский, восточный (ориентальный); новости — отдельный контур с **актуализацией** по расписанию.

### 2.2. Парсинг сайтов

Парсинг и выгрузка — только при соблюдении **robots.txt**, **правил площадки** и **лицензий**. Технические шаги: стабильные селекторы или официальные API/RSS где доступны, расписание обновлений, **дедупликация**, нормализация кодировки и разметки, журнал версий корпуса.

**Что уже заложено в коде RAG:** загрузка текстов с Project Gutenberg — **httpx** (HTTPS); конфигурация семян — **YAML** (`pyyaml`); индекс — **ChromaDB**; эмбеддинги — **sentence-transformers** / **PyTorch**. Для будущего **парсинга страниц** сайтов (при расширении корпуса): **httpx** или **requests**, разбор HTML — **BeautifulSoup** / **lxml** (подключать по мере необходимости), плюс те же правила лицензий и **robots.txt**.

#### Топ-10 русскоязычных новостных сайтов (политика и общая повестка)

Ориентиры для сбора **текущих** новостей (не «официальный рейтинг»):

| № | Сайт |
|---|------|
| 1 | [kommersant.ru](https://www.kommersant.ru/) |
| 2 | [rbc.ru](https://www.rbc.ru/) |
| 3 | [vedomosti.ru](https://www.vedomosti.ru/) |
| 4 | [tass.ru](https://tass.ru/) |
| 5 | [ria.ru](https://ria.ru/) |
| 6 | [interfax.ru](https://www.interfax.ru/) |
| 7 | [lenta.ru](https://lenta.ru/) |
| 8 | [gazeta.ru](https://www.gazeta.ru/) |
| 9 | [iz.ru](https://iz.ru/) (Известия) |
| 10 | [rg.ru](https://rg.ru/) (Российская газета) |

*Дополнительно для сверки:* [themoscowtimes.com](https://www.themoscowtimes.com/) (англоязычно о России).

#### Топ-10 англоязычных новостных сайтов (международная политика)

| № | Сайт |
|---|------|
| 1 | [reuters.com](https://www.reuters.com/) |
| 2 | [apnews.com](https://apnews.com/) |
| 3 | [bbc.com/news](https://www.bbc.com/news) |
| 4 | [theguardian.com](https://www.theguardian.com/) |
| 5 | [ft.com](https://www.ft.com/) |
| 6 | [nytimes.com](https://www.nytimes.com/) |
| 7 | [washingtonpost.com](https://www.washingtonpost.com/) |
| 8 | [politico.com](https://www.politico.com/) |
| 9 | [economist.com](https://www.economist.com/) |
| 10 | [aljazeera.com](https://www.aljazeera.com/) |

#### Крупные ресурсы сказок для корпусов RAG

Ниже — **основные** входы для построения индексов: русский слой (включая **советских** авторов сказочной и детской прозы), европейский, американский, восточный. Перед массовой загрузкой — проверка **лицензии** каждого текста/издания.

**Россия: народная сказка, литературная сказка, советские авторы**

| Ресурс | Назначение для RAG |
|--------|-------------------|
| [feb-web.ru](https://feb-web.ru/) | ФЭБ: русский фольклор и литература, издание «Сказки», корпуса в духе записей **Афанасьева** и др.; научный фундамент и справка по мотивам — **В. Я. Пропп** («**Морфология сказки**» и связанные материалы в ФЭБ) |
| [lib.ru](http://lib.ru/) | Библиотека Мошкова: народные и литературные сказки; **советские авторы** (например **Чуковский, Маршак, Бианки** и др. в детско-сказочном жанре); **Евгений Шварц (E. Schwartz)** — **сказочная драматургия** и смежные тексты (по разделам, **проверка** статуса прав на каждое произведение) |
| [lib.rus.ec](https://lib.rus.ec/) | Либрусек: подборки сказок, fb2/pdf |
| [ru.wikisource.org](https://ru.wikisource.org/) | Викитека: тексты в общественном достоянии, разбор структуры страниц |
| [skazkii.ru](http://skazkii.ru/) | Детская библиотека онлайн; **проверить** условия копирования |
| [Project Gutenberg — русский фольклор (англ. переводы)](https://www.gutenberg.org/) | **PD-тексты для RAG-пайплайна:** Afanasyev tradition — [ebook 62509](https://www.gutenberg.org/ebooks/62509); Polevoi / skazki — [34705](https://www.gutenberg.org/ebooks/34705); Ransome — [16981](https://www.gutenberg.org/ebooks/16981); Blumenthal — [12851](https://www.gutenberg.org/ebooks/12851); см. также раздел «книги о сказках — Россия» на Gutenberg |
| [Wikipedia — Russian Fairy Tales](https://en.wikipedia.org/wiki/Russian_Fairy_Tales) | Обзорная статья (англ.): навигация, ссылки на первоисточники и смежные темы — не полнотекстовый корпус, но **ориентир** для справки и отбора |
| [НукаДети — русские народные](https://nukadeti.ru/skazki/russkie_narodnye) | Подборка русских народных сказок онлайн; перед загрузкой в корпус — **условия сайта** и **дедупликация** с уже имеющимися текстами |
| [Kaggle — Russian Child Tales](https://www.kaggle.com/datasets/bond005/russian-child-tales) | Датасет детских сказок (рус.); удобно для **массовой** выгрузки после проверки **лицензии** датасета и пересечения с lib.ru / другими источниками |
| [Russian Folk Tales](https://www.russianfolktales.com/tales) | Англоязычный сайт с пересказами и текстами; проверить **лицензию** и **дубликаты** с Gutenberg и локальными `.txt` |

**Советские** авторы (Маршак, Чуковский, Бианки, **Шварц** и др.) в Gutenberg **редко** в полном объёме; для корпуса — **ручная выгрузка** в `data/raw/local_tales/soviet/*.txt` (UTF‑8) или партнёрские лицензии, см. `rag/sources/fairy_tale_seeds.yaml`.

Метаданные чанков для русского контура желательно маркировать: `folk` | `literary` | `soviet_author` (и фамилия) | `propp_reference` (ссылка на сюжетные функции/мотивы по Проппу, при разметке) | `schwartz` (тексты **Шварца**), чтобы фильтровать выборку.

**Европейские сказки**

| Ресурс | Назначение для RAG |
|--------|-------------------|
| [gutenberg.org](https://www.gutenberg.org/) | **Европейские** циклы в PD: **братья Гримм** (*Grimm*), **Шарль Перро** (*Charles Perrault*), **Г. Х. Андерсен** (*Hans Christian Andersen*), **Эндрю Лэнг** (The Blue/Brown Fairy Book и др.); **Астрид Линдгрен** (*Astrid Lindgren*) — **целевой автор** для отбора, но большинство текстов **под охраной авторского права** → только лицензированные или фрагменты с разрешением, не полагаться на Gutenberg для Линдгрен «по умолчанию» |
| [standardebooks.org](https://standardebooks.org/) | Верстка PD: в т.ч. **Андерсен**, **Перро**, **Гримм** (уточнять наличие изданий в каталоге) |
| [Internet Archive](https://archive.org/) | Сканированные и текстовые издания; фильтрация по правам |
| [sites.pitt.edu/~dash/folktexts.html](https://sites.pitt.edu/~dash/folktexts.html) | Академический каталог **европейских** и др. мотивов (**Ashliman**) |

**Американские сказки и фольклор**

| Ресурс | Назначение для RAG |
|--------|-------------------|
| [gutenberg.org](https://www.gutenberg.org/) | Сборники, включающие **американский** материал (в т.ч. в сериях Лэнга — тексты индейских и др. традиций) |
| [sacred-texts.com](https://www.sacred-texts.com/) | Разделы фольклора **Северной Америки** и смежные |
| [archive.org](https://archive.org/) | Исторические издания американского фольклорного корпуса |

**Восточные (ориентальные) сказки**

| Ресурс | Назначение для RAG |
|--------|-------------------|
| [gutenberg.org](https://www.gutenberg.org/) | **«Тысяча и одной ночи»** (*One Thousand and One Nights* / **Arabian Nights**): полные и частичные переводы в PD; **индийские**, **персидские** циклы — при совпадении лицензии перевода/издания |
| [sacred-texts.com](https://www.sacred-texts.com/) | **1001 nights** и восточные тексты в открытых подборках (проверять статус) |
| [wikisource.org](https://wikisource.org/) | Многоязычная Викитека: **«Тысяча и одной ночи»** на разных языках, **арабские**, **персидские**, **индийские** эпосы и сказочные фрагменты при допустимой лицензии |

Подробности по технологиям индексации и гибридному поиску — в [istochniki_skazok_novostey_i_rag.md](istochniki_skazok_novostey_i_rag.md).

### 2.3. Сбор и обработка базы вручную

- **Ручной отбор и правка** фрагментов, которые нецелесообразно или нельзя автоматизировать на первом этапе (редкие жанры, спорные с точки зрения лицензии тексты, эталонная разметка).
- Ведение **журнала источников** и версий для воспроизводимости экспериментов и отчётности по диплому.

---

## Итог этапа

К результату этапа № 2 относятся: **уточнённый и по возможности расширенный корпус**, согласованный с архитектурой из этапа № 1, **документированные источники** и **правила обновления** новостного слоя и сказочных подкорпусов.

---

## RAG Report

=== Отчёт RAG (корпус сказок) (Fairy-tale RAG corpus report) ===

-- Краткая сводка (Brief summary) --
  Всего чанков (total chunks): 6702; Уникальных произведений (unique works): 12
  По языку текста чанков (by chunk text language): {'en': 6702}
  Чаще всего по странам (top countries): [('RU', 2722), ('GB-SCT', 1585), ('MENA', 764), ('DE', 666), ('GB-ENG', 570)]
  Чаще всего по авторам (top authors): [('Andrew Lang', 1585), ('Leo Tolstoy (Л. Н. Толстой)', 970), ('anonymous / compiled (tr. Lang)', 764), ('Alexander Afanasyev (corpus; tr. Post Wheeler et al.)', 701), ('Brothers Grimm', 666)]
  Чаще всего в подсказках героев (top hero tokens): [('fables', 970), ("children's stories", 970), ('moral tales', 970), ('natural science stories', 970), ('басни', 970)]


-- По домену (by domain) --
  russian: 2722
  european: 1995
  european_compilation: 1221
  oriental: 764

-- По стране / региону (by country / region) --
  RU: 2722
  GB-SCT: 1585
  MENA: 764
  DE: 666
  GB-ENG: 570
  DK: 383
  FR: 12

-- По автору (by author) --
  Andrew Lang: 1585
  Leo Tolstoy (Л. Н. Толстой): 970
  anonymous / compiled (tr. Lang): 764
  Alexander Afanasyev (corpus; tr. Post Wheeler et al.): 701
  Brothers Grimm: 666
  Anthony R. Montalba (compiler): 570
  Arthur Ransome (reteller): 456
  N. A. Polevoi (tr.) / Russian skazki tradition: 435
  Hans Christian Andersen: 383
  Verra Kalamatiano de Blumenthal: 160
  Charles Perrault: 12

-- По языку текста чанков (by chunk text language) --
  en: 6702

-- Произведения (снимок метаданных) (works (metadata snapshot)) --
  gutenberg:128 | oriental | MENA | anonymous / compiled (tr. Lang) | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Шахерезада; визири; джинны (разные варианты)
    Подсказки по образам героев (hero figure hints) (EN): Scheherazade; viziers; djinni (var.)
  gutenberg:12851 | russian | RU | Verra Kalamatiano de Blumenthal | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Антология — восточнославянские фольклорные мотивы
    Подсказки по образам героев (hero figure hints) (EN): Anthology — East Slavic folk motifs
  gutenberg:1597 | european | DK | Hans Christian Andersen | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Русалочка; Снежная королева; типичные персонажи Андерсена
    Подсказки по образам героев (hero figure hints) (EN): The Little Mermaid; The Snow Queen; usual Andersen figures
  gutenberg:16981 | russian | RU | Arthur Ransome (reteller) | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Баба-Яга; Иван; простак и летающее чудо; народные образы
    Подсказки по образам героев (hero figure hints) (EN): Baba Yaga; Ivan; fool who flies; folk figures
  gutenberg:25421 | european | FR | Charles Perrault | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Золушка; Синяя Борода; Спящая красавица; Кот в сапогах
    Подсказки по образам героев (hero figure hints) (EN): Cinderella; Bluebeard; Sleeping Beauty; Puss in Boots
  gutenberg:2591 | european | DE | Brothers Grimm | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Красная Шапочка; Белоснежка; волк; ведьма; множество народных образов
    Подсказки по образам героев (hero figure hints) (EN): Red Riding Hood; Snow White; wolf; witch; many folk figures
  gutenberg:3282 | european_compilation | GB-SCT | Andrew Lang | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Антология — смешанные регионы   
    Подсказки по образам героев (hero figure hints) (EN): Anthology — mixed regions       
  gutenberg:34705 | russian | RU | N. A. Polevoi (tr.) / Russian skazki tradition | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Салтан; цари; лиса; типичные русские сказочные образы
    Подсказки по образам героев (hero figure hints) (EN): Saltan; tsars; fox; typical Russian tale figures
  gutenberg:34956 | european_compilation | GB-ENG | Anthony R. Montalba (compiler) | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Антология — много народов       
    Подсказки по образам героев (hero figure hints) (EN): Anthology — many nations        
  gutenberg:38025 | russian | RU | Leo Tolstoy (Л. Н. Толстой) | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Басни; рассказы для детей; поучительные сказки; естествознание
    Подсказки по образам героев (hero figure hints) (EN): Fables; children's stories; moral tales; natural science stories
  gutenberg:503 | european | GB-SCT | Andrew Lang | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Антология — европейские и мировые сказочные образы
    Подсказки по образам героев (hero figure hints) (EN): Anthology — many European and world tale figures
  gutenberg:62509 | russian | RU | Alexander Afanasyev (corpus; tr. Post Wheeler et al.) | lang=en
    Подсказки по образам героев (hero figure hints) (RU): Жар-птица; Василиса; Мороз Иванович; Царевна-лягушка; типы сказок
    Подсказки по образам героев (hero figure hints) (EN): Fire-Bird; Vasilisa; Father Frost; Frog Princess; many tale types

-- Частота слов в подсказках героев (hero hint token frequency) --
  fables: 970
  children's stories: 970
  moral tales: 970
  natural science stories: 970
  басни: 970
  рассказы для детей: 970
  поучительные сказки: 970
  естествознание: 970
  anthology — many european and world tale figures: 934
  scheherazade: 764
  viziers: 764
  djinni (var.): 764
  шахерезада: 764
  визири: 764
  джинны (разные варианты): 764

Примечание (Note): «Произведение» = один уникальный source (книга Gutenberg по id или локальный .txt). Чанк не равен отдельной сказке без разметки по заголовкам. Язык текста чанка — поле content_lang (en/ru).

*Документ подготовлен для этапа согласования плана по сбору и обработке данных в рамках направления GPT Engineer.*

# EGRN / GeoJSON to DXF

Небольшое Windows-приложение для преобразования XML-выписок Росреестра и файлов GeoJSON в DXF.

![Выбор типов кадастровых записей](screenshots/Screenshot%202026-08-31%20194503.png)

## Возможности

- открытие кадастровой выписки XML через системный диалог Windows;
- автоматический поиск записей `*_record`, содержащих `contour`;
- поддержка GeoJSON-геометрий `Point`, `MultiPoint`, `LineString`, `MultiLineString`, `Polygon`, `MultiPolygon` и `GeometryCollection`;
- выбор нужных типов XML-записей или всех объектов GeoJSON одним чекбоксом **GeoJSON Features**;
- отдельный слой `kad_<name>` для каждого выбранного типа записи;
- отдельный слой `kad_<name>_part` для контуров внутри `object_part`;
- слой `kad_other` для контуров, не принадлежащих ни одной записи `*_record`;
- единый слой `geojson_features` с ACI-цветом 7 для всех объектов GeoJSON;
- последовательные ACI-цвета слоёв: 1, 2, 3 и далее;
- сохранение результата в DXF с единицами измерения в метрах.

![Результат экспорта в AutoCAD](screenshots/Screenshot%202026-08-31%20194519.png)

## Установка

Готовую Windows-сборку можно скачать на странице [Releases](https://github.com/max-bold/egrntodxf/releases/latest). Установка не требуется: запустите `egrntodxf.exe`.

При появлении предупреждения Microsoft Defender SmartScreen проверьте, что файл загружен из релиза этого репозитория, и разрешите запуск через **More info → Run anyway**.

## Использование

1. Нажмите **Open** и выберите XML-выписку Росреестра либо файл `.geojson`/`.json`.
2. Для XML отметьте нужные типы записей; для GeoJSON отметьте **GeoJSON Features**.
3. Нажмите **Save** и укажите имя DXF-файла.
4. Откройте полученный файл в AutoCAD или другом приложении с поддержкой DXF.

В выписках ЕГРН координата `X` соответствует северному направлению, а `Y` — восточному. При экспорте приложение намеренно записывает их в DXF в порядке `Y, X`.

## Запуск из исходников

Требуется Python 3.11 или новее.

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe egrntodxf_gui.py
```

## Сборка EXE

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m PyInstaller egrntodxf.spec
```

Готовый файл появится в `dist/egrntodxf.exe`.

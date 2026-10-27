# Samsung ports / Порты Samsung

## Что сделано

Проект предназначен **только для Samsung**. Производитель и бренд проверяются
перед установкой runtime и запуском; ColorOS root-wrapper также проверяет Samsung.
При этом «Samsung» не означает совместимость со всеми Samsung.

Из [OneOS](https://github.com/fahadalijaved23/OneOS/tree/73c3be36c35462742503380e1f025fead3cea48c)
перенесён исходный набор для портирования, закреплённый за commit
`73c3be36c35462742503380e1f025fead3cea48c`:

- native launcher и исходники ресурсных overlays;
- патчеры гостевого framework, изоляции хранилища, vold, ключей и installd;
- модель профилей, контракт подготовки/root, проверки безопасности;
- таблицы хешей ожидаемых наборов и инструменты сборки overlays/извлечения ABI installd.

Они находятся в [runtime/samsung-oneos/upstream](../runtime/samsung-oneos/upstream).
Session-скрипты `switcher/assets` изучены, но исключены из нового snapshot:
upstream NOTICE отдельно ограничивает повторное использование OneLineage-derived
скриптов вне OneOS. Для такого переноса нужно разрешение правообладателей либо
самостоятельная реализация; под общую Apache-лицензию их не переобозначаем.
LICENSE, NOTICE, CREDITS и SHA-256 каждого исходника сохранены. Исходники не
подменяют работающий S23 runtime и **не исполняются новым APK**: это база для
следующего backend. Обновление исходников не является готовым портом.

В APK добавлен **Compatibility / Совместимость**: локальный отчёт без root,
IMEI, номеров, SMS, аккаунтов и Wi-Fi. Передача отчёта происходит только через
открываемое пользователем меню «Поделиться». Таблица распознаёт 13 комбинаций
model + codename + SoC из OneOS; одно имя модели недостаточно.

## Статус моделей

| Samsung | Codename | SoC | Статус в gsionlocked |
| --- | --- | --- | --- |
| S23 | dm1q | SM8550 | Существующий локальный порт SM-S911B/FZG1 Android 16; новый установщик проверен только офлайн |
| S23+ | dm2q | SM8550 | Только справочный профиль, runtime не собран |
| S24 Ultra | e3q | SM8650 | HyperOS 4.0 / Android 17 образ определён; 34 APEX подготовлены, runtime не собран, запуск отключён |
| S25 / S25+ / S25 Ultra | pa1q / pa2q / pa3q | SM8750 | Только справочные профили, runtime не собран |
| S26 / S26 docomo / S26+ / S26 Ultra | m1q / m1q / m2q / m3q | SM8850 | Только справочные профили, runtime не собран |
| Z Fold7 / Z Fold8 / Z Fold8 Ultra | q7q / h8q / q8q | SM8750 / SM8850 / SM8850 | Только справочные профили, runtime не собран |

Статус «tested» в исходном OneOS относится к его образам, наборам и устройствам,
а не к этому приложению. Exynos и прочие Samsung не получают поддержку от этой таблицы.

## Чего не хватает для запуска на другом Samsung

Upstream использует Android 17 / One UI 9 и отдельные наборы patched framework.
Наш текущий backend и опубликованные архивы runtime остаются Android 16 / S23.
Нельзя снять проверку framework или заменить отдельные guest_start/return скрипты:
потребуются согласованные guards, namespace, display/input, ABI служб и восстановление хоста.

В OneOS **нет готовых `out/overlays*`**. Полная APK-сборка OneOS требует этих
внешних файлов; импорт исходников не создаёт их. Наш IN-образ совпадает с upstream
по raw SHA-256, но наш старый S23 runtime не равен upstream набору `x9u-in-sultra`.

Для полноценного нового порта нужно:

1. Получить локальный отчёт целевого Samsung и ABI его `services.jar`/installd,
   установить версию хоста, SoC, composer, панели и ввод.
2. На Linux собрать патчи из точного поддерживаемого `.img` инструментом
   `runtime/samsung-oneos/upstream/scripts/make-overlays.sh`. Нужны Android SDK,
   Java, Python 3, apktool, debugfs, zip/unzip и extract.erofs; внешние инструменты
   и проприетарные исходные образы в этот snapshot не входят.
3. Проверить результат относительно исходного набора:

   ```sh
   python tools/check_oneos_port.py --overlays /path/to/built/overlays --set x9u-in-sultra
   ```

   Изменённый для другого host ABI набор должен получить свои хеши и отдельный
   профиль после ревью; нельзя игнорировать несовпадения.
4. Интегрировать отдельный Android 17 backend с upstream контрактом staging,
   собрать подписанный runtime-пакет под соответствующий host framework.
5. Проверить старт, аварийный возврат, изоляцию данных и оборудование на целевой
   модели. До этого не публиковать профиль как поддерживаемый.

## Проверка исходников без телефона

```sh
python tools/check_oneos_port.py
python tools/test.py
```

Повторный импорт: клонировать OneOS, переключиться на закреплённый commit и выполнить
`python tools/import_oneos.py --repo /path/to/OneOS`. Импортируются committed blobs,
без локальных пользовательских файлов и готовых бинарников. Изменённые исходники
не перезаписываются. В APK сохраняются прежние хеши runtime; новые профили не
выдают разрешение на запуск.

## English

The S24 Ultra image identity is recorded separately in
[`profiles/e3q-hyperos4.json`](../profiles/e3q-hyperos4.json): model SM-S928B,
host SDK 37 / build S928BXXU6EZIF, and raw `hyperosS24Ultra.img` SHA-256
`ba016df72abf030c9e1d4d993a1aef23f6c4923538dd89e3de71c401b634518b`
(6,392,864,768 bytes). Read-only inspection identifies the guest build as
HyperOS 4.0 / Android 17, SDK 37 (`17OS4.0.260809.221254686.QCPECN.S`); 34
guest APEX payloads and an exact-host/guest ART adapter candidate have been
prepared locally. The profile remains disabled: the e3q framework/runtime has
not been built or boot-validated.

**Samsung phones only.** The app and ColorOS root wrapper reject other vendors.
The new Compatibility screen recognizes 13 upstream model/device/SoC tuples and
offers a local, manually shared identity report. Recognition is not launch support.

The pinned OneOS source snapshot contains framework and storage/key guards,
native/overlay sources, profile/staging contracts and
overlay build/hash tools. It is a porting kit, **not an installed Android 17 backend**.
OneLineage-derived session scripts are excluded under upstream NOTICE's reuse restriction.
Current downloadable runtimes remain specific to the existing Android 16 S23/FZG1 port.
No other Samsung has been validated in gsionlocked by this update.

Upstream's proprietary built `out/overlays*` are absent. Building the exact image's
patches, adapting the host ABI, integrating a separate backend and validating it on
target hardware are still required. Never remove the host-framework check to run
an S23 bundle on another phone. OneOS's test results do not transfer to this project.

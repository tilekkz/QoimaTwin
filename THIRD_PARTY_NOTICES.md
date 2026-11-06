# Источники и лицензии материалов

## Включённый донор

Xxcool/smart-warehouse, commit ea8c968515a4fc19be26aaf1a3f9419aec159438, copyright2026Xxcool, MIT. Полный текст сохранён в donors/smart-warehouse-LICENSE.txt и source ZIP. Источник: https://github.com/Xxcool/smart-warehouse . Архив содержит исходники выбранного commit; node_modules, скомпилированный dist и .git не входят.

Проверка сборки выполнялась Node24.22.1 через npm install с отключёнными lifecycle scripts и npm run build. Отдельно сохранён проверенный npm lockfile: donors/smart-warehouse-tested-package-lock.json. Для повторения npm-сборки скопировать его в распакованный проект под именем package-lock.json, затем npm ci и npm run build в подходящем Node-окружении. Source ZIP также содержит исходный pnpm lockfile автора; это другой способ разрешения зависимостей, отдельно здесь не проверенный.

## Данные

Daqing Chen (2012), Online Retail II, UCI Machine Learning Repository, DOI10.24432/C5CG6D, CC BY4.0. Источник: https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii . Лицензия: https://creativecommons.org/licenses/by/4.0/ .

Включены производные агрегаты и обезличенный ассортиментный срез. Изменения: нормализация столбцов, фильтрация, дедупликация, группировка invoice-SKU, выбор20SKU по прошлому, календарная агрегация, замена invoice на локальный order_id и прогнозы. Сырой XLSX не включён. Фильтры, хеш источника и ограничения находятся в data_manifest.json.

## Остальные упомянутые инструменты

SimPy, scikit-learn, Nixtla/mlforecast, OR-Tools, glTF-Transform и прочие исследованы как библиотеки/референсы; их полные исходники в этот пакет не включены. Лицензионные сведения и границы проверки — в02. При последующем переносе кода/ассетов в приложение нужно сохранить относящиеся copyright/license/NOTICE и зафиксировать точные версии. Упоминание репозитория не означает, что его код уже использован в Qoyma.

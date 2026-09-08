# 裕信汽車售服績效戰情中心（內部網頁版）

這個 repo 只放**編譯後的靜態網頁**（`docs/index.html`），給 GitHub Pages 用來架站。

- 網頁本身有共用密碼鎖（前端 SHA-256 驗證），只給知道密碼的裕信汽車員工使用。
- **不要直接編輯 `docs/index.html`**——它是由上一層資料夾的 `update_dashboard.py` 自動產生的。

## 如何更新網頁內容

1. 更新原始 Excel（`2026績效成效統計表(1).xlsx`）的四張資料表。
2. 在上一層資料夾執行：
   ```bash
   python update_dashboard.py
   ```
   這會自動重新產生 `docs/index.html`。
3. 回到這個資料夾，推送更新：
   ```bash
   git add docs/index.html
   git commit -m "更新績效資料"
   git push
   ```
4. 等 1-2 分鐘讓 GitHub Pages 重新部署，網頁就會更新。

## 更換共用密碼

⚠ **這個密碼目前是兩個檔案各存一份雜湊，不是真的共用**：`docs/index.html`（由 `update_dashboard.py` 產生）
與 `docs/parts-kpi-dashboard.html`（手動維護）各自寫死同一組 `PWD_HASH`。只改其中一邊，兩個頁面的密碼就會不一致。

1. 到上一層資料夾的 `update_dashboard.py`，找到 `WEB_PASSWORD = "..."` 那一行改掉，重新執行程式、
   `git add / commit / push`——這只會更新 `docs/index.html`。
2. 同時手動打開 `docs/parts-kpi-dashboard.html`，找到 `PWD_HASH = "..."`（在檔案接近結尾處），
   換成新密碼的 SHA-256 雜湊（瀏覽器 Console 執行
   `crypto.subtle.digest("SHA-256", new TextEncoder().encode("新密碼")).then(b=>console.log([...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,"0")).join("")))`
   即可算出雜湊），一起 commit / push。

---

# NISSAN 零件營運分析與查詢工具（`docs/parts-kpi-dashboard.html`）

同一個 repo 底下的第二個獨立網頁，來源是「零件DMS資料庫報表.xlsx」（裕信汽車服務部零件營運報表），
與上面的售服績效戰情中心完全獨立，互不影響。

- 網頁本身**不是靜態示意**：瀏覽器會讀取同目錄的 `docs/parts-kpi-data.json`，所有 KPI 卡片、六大商品矩陣、
  排除漏斗都在使用者裝置端即時運算，可用篩選器（門市／S 餐車型／車輛類別）即時重算。
- 密碼鎖與上面的售服績效戰情中心共用同一組密碼雜湊（`PWD_HASH`），輸入同一組密碼即可進入。
- `docs/parts-kpi-data.json` 已做隱私處理：真實車牌以流水代號取代，客戶姓名/電話/Email/地址/生日一律不匯出。

## 如何更新資料（目前只有 2026-08 一期）

1. 取得新一期的「零件DMS資料庫報表.xlsx」，更新 `extract_dataset.py` 開頭的 `PATH` 指向新檔案位置。
2. 在 repo 根目錄執行：
   ```bash
   python extract_dataset.py
   ```
   這會重新產生 `docs/parts-kpi-data.json`（覆蓋舊檔）。
3. 推送更新：
   ```bash
   git add docs/parts-kpi-data.json
   git commit -m "更新零件營運資料"
   git push
   ```
4. 等 1-2 分鐘讓 GitHub Pages 重新部署即可。

`extract_dataset.py` 需要 `pandas` 與 `openpyxl`（`pip install pandas openpyxl`）。目前腳本只處理單一期間，
若要支援跨月比較，需要修改腳本替每筆資料加上 `period` 欄位、並讓網頁的篩選邏輯依 `period` 分組。

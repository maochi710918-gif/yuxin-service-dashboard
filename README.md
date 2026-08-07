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

到上一層資料夾的 `update_dashboard.py`，找到 `WEB_PASSWORD = "..."` 那一行改掉，
重新執行程式、`git add / commit / push` 即可（不需要改任何其他程式碼）。

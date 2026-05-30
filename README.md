# GHMC Weather Backend (Windy Point Forecast)

Flask backend jo lat/lon leta hai aur 3h/6h/12h + 7-day forecast JSON return karta hai.

## Local run (VS Code)

1. Is folder ko VS Code mein kholo.
2. Terminal kholo (Ctrl + `) aur virtual env banao:

   ```
   python -m venv venv
   venv\Scripts\activate
   ```

3. Dependencies install karo:

   ```
   pip install -r requirements.txt
   ```

4. `.env` file mein apni asli Windy key daalo (placeholder hata ke).

5. Server chalao:

   ```
   python app.py
   ```

6. Browser mein test karo (Hyderabad ka example):

   ```
   http://localhost:5000/forecast?lat=17.385&lon=78.486
   ```

   JSON aana chahiye -> hourly (3) + daily (7).

## Deploy (Render)
- GitHub pe push karo (`.env` git mein NAHI jayegi — .gitignore handle karta hai).
- Render -> New Web Service -> repo connect.
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Environment -> add `WINDY_KEY` = your real key.

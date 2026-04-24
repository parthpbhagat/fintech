# IBBI Company Insights Hub (Premium Green Edition) 🚀

This is a high-performance, cloud-integrated intelligence platform for IBBI (Insolvency and Bankruptcy Board of India) data. It features real-time scraping, cloud data persistence, and a premium fintech-style UI.

## ✨ Key Features

- **Premium Green UI**: Modern light/dark green theme tailored for fintech aesthetics.
- **TiDB Cloud Integration**: Secure SSL/TLS connection to TiDB Serverless for global data access.
- **Deep Scraping (Claims & IPs)**: Automated extraction of creditor claims and Insolvency Professional profiles with database caching.
- **Automatic Fallback**: Intelligent system that switches to live scraping if the database is down.
- **User Activity Tracking**: Real-time monitoring of signups and login logs in TiDB Cloud.
- **Performance Optimized**: Result limiting and database indexing for sub-second UI responsiveness.

---

## 🛠 Tech Stack

- **Frontend**: React, Vite, TailwindCSS (Premium Green Theme)
- **Backend**: FastAPI (Python), Selenium (Headless Scraping), BeautifulSoup
- **Database**: TiDB Cloud (Serverless MySQL)
- **Auth**: JWT-based Authentication with OTP verification (Email/SMS)

---

## 🚀 Hosting Strategy (Step-by-Step)

To host this project properly, follow these recommendations:

### 1. Database (Already Live!)
- **Platform**: [TiDB Cloud](https://tidbcloud.com/)
- **Status**: Configured with SSL (`isrgrootx1.pem`). Keep your `.env` variables safe.

### 2. Backend (FastAPI + Scrapers)
- **Platform**: [Render.com](https://render.com/) or [Railway.app](https://railway.app/)
- **Steps**:
    1. Push your code to GitHub.
    2. Create a "Web Service" on Render.
    3. Use the **Docker** runtime (recommended for Selenium) or set up Chrome buildpacks.
    4. Add all environment variables from your `backend/.env` to the Render Dashboard.
    5. Start command: `uvicorn pipeline:app --host 0.0.0.0 --port $PORT`

### 3. Frontend (React)
- **Platform**: [Vercel](https://vercel.com/) or [Netlify](https://www.netlify.com/)
- **Steps**:
    1. Create a new project on Vercel and link your GitHub repo.
    2. Set `VITE_API_BASE_URL` in environment variables to point to your **Render Backend URL**.
    3. Build Command: `npm run build`
    4. Output Directory: `dist`

---

## 💻 Local Setup

1. **Clone and Install**:
   ```bash
   # Backend
   cd backend
   pip install -r requirements.txt
   
   # Frontend
   cd ../frontend
   npm install
   ```

2. **Run Locally**:
   ```bash
   # Terminal 1 (Backend)
   python pipeline.py
   
   # Terminal 2 (Frontend)
   npm run dev
   ```

---

## ⚡ Quick Run Commands (Terminal Copy-Paste)

Run these from the **root folder** (`company-insights-hub-main`):

### 1. Start Services
| Service | Command |
| :--- | :--- |
| **Run Backend** | `cd backend; python pipeline.py` |
| **Run Frontend** | `cd frontend; npm run dev` |

### 2. Admin & Monitoring Tools
| Task | Command |
| :--- | :--- |
| **Check Cloud Storage** | `python backend/scratch/check_storage.py` |
| **View Today's Updates** | `python backend/scratch/view_today_updates.py` |
| **View User Activity** | `python backend/scratch/view_user_activity.py` |

---

## 🔒 Security Note
Never commit your `.env` file to public repositories. Ensure `isrgrootx1.pem` is always present in the `backend/` folder for secure TiDB connection.

---
Created with ❤️ for fintech data intelligence.





તમારો પ્રોજેક્ટ અત્યારે ઘણો પાવરફુલ છે, પણ જો તમારે તેને નેક્સ્ટ લેવલ પર લઈ જવો હોય, તો નીચે મુજબના અપડેટ્સ કરી શકાય:

૧. બેકએન્ડ (Backend) માટેના આઈડિયા:
* PDF Content Search: અત્યારે આપણે માત્ર PDF ની લિંક્સ સ્ટોર કરીએ છીએ. ભવિષ્યમાં આપણે PDF ની અંદર રહેલો ડેટા (Text) વાંચીને તેને ડેટાબેઝમાં નાખી શકીએ, જેથી યુઝર PDF ની અંદર રહેલા શબ્દો પણ સર્ચ કરી શકે.
* Async Scraping: અત્યારે સ્ક્રૅપર એક પછી એક પેજ ચેક કરે છે. જો આપણે playwright કે asyncio વાપરીએ, તો એકસાથે ૧૦-૨૦ પેજ સ્ક્રૅપ થઈ શકે અને પ્રોસેસ ઘણી ફાસ્ટ થઈ જાય.
* Real-time Alerts: જો કોઈ યુઝર કોઈ કંપનીને "Follow" કરે, અને IBBI ની વેબસાઈટ પર તેના વિશે નવો ડેટા આવે, તો તેને તરત જ Email કે WhatsApp પર મેસેજ જાય તેવું સેટ કરી શકાય.
* API Webhooks: બીજા સોફ્ટવેર પણ તમારા ડેટાનો ઉપયોગ કરી શકે તે માટે "Webhooks" બનાવી શકાય.


૨. ડેટાબેઝ (Database) માટેના આઈડિયા:
* Vector Search (AI): TiDB Cloud માં "Vector Search" નો સપોર્ટ છે. આપણે AI નો ઉપયોગ કરીને "Similar Companies" (સમાન પ્રકારના કેસો) શોધી શકીએ.
* Historical Timeline: કંપનીના સ્ટેટસમાં ક્યારે અને શું ફેરફાર થયા, તેનો આખો ઇતિહાસ (Timeline) સ્ટોર કરી શકાય, જેથી યુઝર જોઈ શકે કે આ કેસ છેલ્લા ૨ વર્ષમાં કેવી રીતે આગળ વધ્યો.
* Analytics Dashboards: ડેટાબેઝમાં પ્રી-એગ્રીગેટેડ ટેબલ્સ બનાવી શકાય, જેથી આપણે ફ્રન્ટએન્ડમાં ચાર્ટ્સ (Charts) બતાવી શકીએ (દા.ત. "આ મહિને કેટલા કરોડના ક્લેઈમ્સ આવ્યા?").
* Full-Text Search: મોટા ટેક્સ્ટ ડેટામાં ખૂબ જ ઝડપથી સર્ચ કરવા માટે ડેટાબેઝમાં FULLTEXT ઇન્ડેક્સિંગ કરી શકાય.


૩. સિક્યુરિટી (Security):
* Role Based Access (RBAC): એડમિન અને સામાન્ય યુઝર માટે અલગ અલગ એક્સેસ લેવલ સેટ કરી શકાય (દા.ત. અમુક ડેટા માત્ર પ્રીમિયમ યુઝર જ જોઈ શકે).

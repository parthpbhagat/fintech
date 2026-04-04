# Company Insights Hub (IBBI Edition)

A specialized platform for tracking company insolvency and bankruptcy cases in India, exclusively utilizing data from the **IBBI (Insolvency and Bankruptcy Board of India)**.

## Features

- **Real-time IBBI Tracking**: Live fetching and parsing of IBBI Public Announcements and Claims data.
- **Advanced Search**: Search companies by name or CIN directly from the IBBI announcement database.
- **Claims Insights**: Automatic lookup of claims data and insolvency professional details.
- **Data Export**: Download company summaries and profile snapshots for offline use.
- **Authenticated Access**: Secure signup and login with OTP verification to protect access.

## Tech Stack

- **Frontend**: React, TypeScript, Tailwind CSS, TanStack Query.
- **Backend**: Python, FastAPI, BeautifulSoup (for live scraping), Requests.
- **Database**: SQLite (for user management), Local JSON Store (for profile caching).

## Getting Started

### Prerequisites

- Python 3.9+ installed on your system.
- Node.js and npm (for the frontend).

### Installation

1. Clone the repository and navigate to the project directory.
2. Install Python dependencies (ensure `requests`, `fastapi`, `uvicorn`, `beautifulsoup4`, and `pandas` are available).
3. Install frontend dependencies:
   ```bash
   npm install
   ```

### Configuration

Create a `backend/.env` file with the following variables (optional for full features):
```env
JWT_SECRET=your_secret_here
EMAIL_USER=your_gmail_user
EMAIL_PASS=your_gmail_app_password
# To enable SMS OTP, provide Twilio credentials:
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=...
```

### Running the Application

1. **Start the Backend**:
   Navigate to the `backend` folder and run:
   ```bash
   python pipeline.py
   ```
   The API will run on `http://localhost:8005`.

2. **Start the Frontend**:
   In the project root, run:
   ```bash
   npm run dev
   ```
   The application will be accessible at `http://localhost:8080`.

## Project Structure

```
company-insights-hub/
├── backend/
│   ├── pipeline.py      # Main IBBI scraper and API server
│   ├── auth.py          # Authentication and User Management
│   ├── data/            # Local data storage (SQLite, JSON cache)
├── src/
│   ├── components/      # React components (Navbar, UI elements)
│   ├── contexts/        # Auth Context
│   ├── pages/           # Page components (Index, Details, News)
│   ├── services/        # API services (Connects to backend)
└── README.md            # You are here
```

## Disclaimer

This application is for educational and research purposes. Data is gathered from publicly available sources on the IBBI website.

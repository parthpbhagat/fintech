# Company Insights Hub

A comprehensive platform for tracking company insolvency and bankruptcy cases in India, providing real-time updates, detailed case information, and advanced analytics.

## Features

- **Real-time Case Tracking**: Monitor insolvency and bankruptcy cases with live status updates.
- **Advanced Search & Filtering**: Find companies using advanced search criteria including CIN, name, status, and more.
- **Company Analytics**: Deep dive into company financials, legal status, and case history.
- **News Aggregation**: Stay updated with the latest news and announcements from IBBI and other sources.
- **User Authentication**: Secure login and user management system.
- **Comparison Tool**: Compare multiple companies side-by-side to analyze trends and metrics.

## Tech Stack

- **Frontend**: React, TypeScript, Tailwind CSS
- **Backend**: Node.js, Express
- **Database**: MongoDB
- **Authentication**: JWT (JSON Web Tokens)
- **Deployment**: Vercel

## Getting Started

### Prerequisites

- Node.js (v14 or higher)
- MongoDB
- npm or yarn

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd company-insights-hub
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

### Configuration

Create a `.env` file in the root directory with the following variables:

```env
PORT=5000
MONGODB_URI=your_mongodb_connection_string
JWT_SECRET=your_jwt_secret
```

### Running the Application

Start the development server:

```bash
npm run dev
```

The application will be accessible at `http://localhost:5173`.

## Project Structure

```
company-insights-hub/
├── src/
│   ├── components/      # React components
│   ├── contexts/        # React contexts (AuthContext, etc.)
│   ├── pages/           # Page components
│   ├── services/        # API services
│   ├── utils/           # Utility functions
│   └── App.tsx          # Main application component
├── server/              # Backend server
│   ├── config/          # Configuration
│   ├── controllers/     # Request handlers
│   ├── models/          # Database models
│   ├── routes/          # API routes
│   └── server.ts        # Server entry point
├── .env                 # Environment variables
├── package.json         # Project dependencies
└── README.md            # Project documentation
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

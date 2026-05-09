# Rallypoint

A comprehensive sports management and rating system for managing academies, players, matches, and competitive rankings with real-time event processing.

## Overview

Rallypoint is a full-stack application designed to manage competitive sports organizations, track player performance, calculate dynamic ratings, and maintain detailed match histories. Built with a modern tech stack, it provides REST APIs and a responsive web interface for comprehensive sports management.

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.x)
- **Database**: SQL Server
- **Authentication**: JWT-based OTP system
- **Job Scheduling**: Background jobs for daily/weekly tasks
- **Rate Limiting**: Request throttling and DDoS protection
- **Deployment**: Docker, Railway

### Frontend
- **Framework**: React with TypeScript
- **Build Tool**: Vite
- **Styling**: CSS
- **State Management**: React Context

## Project Structure

```
rallypoint/
├── app/                          # Backend FastAPI application
│   ├── routers/                  # API route handlers
│   │   ├── academies.py
│   │   ├── players.py
│   │   ├── matches.py
│   │   ├── events.py
│   │   ├── leaderboard.py
│   │   ├── seasons.py
│   │   └── ...
│   ├── services/                 # Business logic
│   │   ├── match_service.py
│   │   ├── player_service.py
│   │   ├── rating_engine.py      # ELO rating calculation
│   │   ├── leaderboard_service.py
│   │   ├── fixture_engine.py     # Match scheduling
│   │   └── ...
│   ├── schemas/                  # Pydantic models for validation
│   ├── dependencies/             # Shared dependencies (auth, pagination)
│   ├── jobs/                     # Background job tasks
│   ├── utils/                    # Utility functions
│   ├── main.py                   # FastAPI app initialization
│   ├── config.py                 # Configuration management
│   └── database.py               # Database connection
├── web/                          # React frontend application
│   ├── src/
│   │   ├── pages/               # Page components
│   │   ├── components/          # Reusable components
│   │   ├── api/                 # API client
│   │   └── auth/                # Authentication context
│   └── public/                  # Static assets
├── schemas/                      # Database schema definitions
├── sql/                          # SQL scripts and migrations
│   ├── migrations/              # Database migrations
│   └── seed*.sql               # Seed data scripts
├── tests/                        # Test suite
│   ├── unit/                    # Unit tests
│   └── integration/             # Integration tests
├── docs/                        # Project documentation
└── requirements.txt             # Python dependencies
```

## Features

- **Academy Management**: Register and manage sports academies
- **Player Profiles**: Comprehensive player information and history tracking
- **Match Management**: Create, schedule, and track match results
- **Dynamic Rating System**: ELO-based rating calculations with historical tracking
- **Event Management**: Organize tournaments and competitions
- **Leaderboards**: Real-time ranking and statistics
- **Dispute Handling**: Manage and resolve match disputes
- **Authentication**: Secure JWT-based authentication with OTP
- **Rate Limiting**: Built-in protection against abuse
- **Webhook Support**: Event notifications and integrations
- **Batch Operations**: Background jobs for daily/weekly tasks

## Getting Started

### Prerequisites
- Python 3.8+
- Node.js 16+
- SQL Server (or compatible database)
- Docker (optional, for containerized deployment)

### Backend Setup

1. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1  # On Windows
   # or
   source venv/bin/activate     # On macOS/Linux
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure database**:
   - Update database connection in `app/config.py`
   - Run SQL schema setup: `apply_schema.bat` or manually run SQL scripts in `sql/`
   - Apply migrations: `sql/migrations/`

4. **Set environment variables**:
   Create a `.env` file (reference: `.env.example`):
   ```env
   DATABASE_URL=your_database_connection_string
   JWT_SECRET_KEY=your_secret_key
   OTP_EXPIRY_MINUTES=5
   ```

5. **Run the backend**:
   ```bash
   python -m uvicorn app.main:app --reload
   ```
   API will be available at `http://localhost:8000`

### Frontend Setup

1. **Navigate to web directory**:
   ```bash
   cd web
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Configure API endpoint**:
   Update API client in `src/api/client.ts` with your backend URL

4. **Run development server**:
   ```bash
   npm run dev
   ```
   Frontend will be available at `http://localhost:5173`

## Running Tests

### Backend Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_match_service.py

# Run with coverage
pytest --cov=app tests/
```

### Frontend Tests
```bash
cd web
npm test
```

## API Documentation

Once the backend is running, access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Deployment

### Docker Deployment
```bash
docker build -t rallypoint .
docker run -p 8000:8000 rallypoint
```

### Railway Deployment
Configuration is set up in `railway.toml`. Connect your GitHub repository to Railway for automatic deployments.

## Database Schema

Key entities:
- **Users**: System users and authentication
- **Players**: Player profiles and history
- **Academies**: Academy information and status
- **Seasons**: Competition seasons
- **Matches**: Match records and results
- **Events**: Tournaments and competitions
- **Ratings**: Player rating history
- **Leaderboards**: Computed rankings

See `sql/` directory for complete schema definitions and `docs/` for detailed data model documentation.

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -am 'Add feature'`
3. Push to branch: `git push origin feature/your-feature`
4. Submit a pull request

## Documentation

- [API Contract](docs/jlrs_api_contract.md)
- [Data Model](docs/jlrs_data_model.md)
- [System Guide](docs/jlrs_system_guide.md)
- [Implementation Plan](docs/jlrs_impl_plan.md)
- [Edge Case Catalog](docs/jlrs_edge_case_catalog.md)

## License

[Add your license information here]

## Support

For issues or questions, please open an issue on the GitHub repository.

---

**Repository**: https://github.com/chintankanal/rallypoint

# RetroAgg

A global news aggregator prioritizing information pluralism and breaking content bubbles through diverse international sources.

![License](https://img.shields.io/badge/license-AGPL-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)

**License**: GNU Affero General Public License v3.0

## Philosophy

RetroAgg represents a rebellion against the algorithmic curation and Western-centric bias of modern news platforms. By prioritizing **non-Western perspectives**, it offers:

- **No algorithms** - Chronological feeds only, no personalization
- **No tracking** - Your reading habits stay private
- **High information density** - Maximum content, minimum bloat
- **Global pluralism** - Sources from Asia, Africa, MENA, Latin America, and the Global South

## Features

### Core Functionality
- **RSS Aggregation** - Async fetching from 30+ diverse global sources
- **Auto-deduplication** - Content hashing + headline similarity
- **Background Updates** - Automatic feed refresh every 15 minutes
- **Regional Filtering** - Filter by geographic region
- **Source Transparency** - Bias indicators

## Installation

### Prerequisites
- Python 3.11+
- pip

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/donrami/retroagg.git
cd retroagg
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Initialize the database**
```bash
cd app
python init_db.py
```

5. **Run the application**
```bash
python main.py
```

Or with uvicorn directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. **Open your browser**
```
http://localhost:8000
```

## Usage

### Web Interface
- **Home** (`/`) - Article feed with region/source filters
- **Sources** (`/sources`) - Source registry

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/articles` | GET | Get articles (with region/source filters) |
| `/api/sources` | GET | List all configured sources |
| `/api/refresh` | POST | Manually trigger RSS refresh |
| `/api/stats` | GET | Get basic statistics |
| `/health` | GET | Health check |

## Source Registry

### MENA (Middle East & North Africa)
- Al Jazeera (Qatar) - Arab perspective on global affairs
- Haaretz (Israel) - Israeli liberal viewpoint
- Middle East Eye - Independent Middle East coverage

### Asia
- South China Morning Post (Hong Kong)
- Kyodo News (Japan)
- The Wire (India) - Independent investigative journalism
- The Diplomat - Asia-Pacific politics

### Africa
- Mail & Guardian (South Africa)
- The Africa Report
- African Arguments

### Latin America
- Americas Quarterly
- Buenos Aires Times

### Global South
- Inter Press Service - Developing nation perspective
- Global Voices - Citizen media worldwide

### Baseline
- Reuters - Neutral wire service for comparison
- Deutsche Welle - German public broadcaster

## Configuration

Edit `app/config.py` to customize:

```python
FETCH_INTERVAL_MINUTES = 15  # Background fetch interval
REQUEST_TIMEOUT = 30         # HTTP timeout
MAX_RETRIES = 3             # Retry attempts for failed fetches
DUPLICATE_THRESHOLD = 0.70   # Headline similarity threshold
```

## Project Structure

```
retroagg/
├── app/
│   ├── models/          # SQLAlchemy models
│   ├── services/        # RSS fetcher, deduplicator
│   ├── routers/         # API and page routes
│   ├── schemas/         # Pydantic schemas
│   ├── templates/       # Jinja2 templates
│   ├── static/          # Static assets
│   ├── config.py        # Application settings
│   ├── database.py      # Database setup
│   ├── scheduler.py     # Background tasks
│   ├── init_db.py       # Database initialization
│   └── main.py          # FastAPI application
├── data/                # SQLite database
├── requirements.txt
└── README.md
```

## Legal/Ethical Considerations

- Only headlines and summaries are stored (Fair Use)
- All articles link to original sources
- No user tracking or profiling
- Transparent source attribution
- Respect for robots.txt and rate limits

## License

GNU Affero General Public License v3.0 - See LICENSE file for details

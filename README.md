# VAPI - JSON Data Processing API

A lightweight FastAPI-based REST API for receiving and storing JSON data from internal applications with simple API key authentication and MongoDB storage.

## Features

- ✅ Receive JSON data from internal applications
- ✅ Secure endpoints with API key authentication
- ✅ Store data in MongoDB
- ✅ CRUD operations for stored data
- ✅ Auto-generated API documentation
- ✅ Simple integration for internal apps

## Project Structure

```
vapi_dev/
├── app/
│   ├── core/
│   │   ├── config.py         # Configuration settings
│   │   ├── database.py       # MongoDB connection
│   │   └── security.py       # API key validation
│   ├── models/
│   │   └── schemas.py        # Pydantic models
│   ├── routes/
│   │   ├── health.py         # Health check endpoints
│   │   └── data.py           # Data management endpoints
│   └── __init__.py
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

## Installation

### Prerequisites
- Python 3.9+
- MongoDB (local or remote)

### Setup

1. Clone the repository and navigate to the project:
```bash
cd vapi_dev
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file from the template:
```bash
cp .env.example .env
```

5. Update `.env` with your configuration:
```
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=vapi_db
API_KEY=your-secure-api-key-here
```

## Running the Application

Start the development server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

### API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Health Check
- `GET /` - Root endpoint
- `GET /health` - Health check

### Data Management (Requires API Key)

All data endpoints require the `X-API-Key` header with your configured API key.

**Store JSON Data**
```bash
POST /api/data
Header: X-API-Key: your-api-key
```

Request body:
```json
{
  "data": {"key": "value", "nested": {"field": "data"}},
  "metadata": {"source": "external-app", "timestamp": "2024-03-26"}
}
```

Response:
```json
{
  "success": true,
  "message": "Data stored successfully",
  "id": "507f1f77bcf86cd799439011"
}
```

**Retrieve All Data**
```bash
GET /api/data?limit=10&skip=0
Header: X-API-Key: your-api-key
```

Query parameters:
- `limit`: Number of records to return (default: 10)
- `skip`: Number of records to skip (default: 0)

**Retrieve Specific Data**
```bash
GET /api/data/{data_id}
Header: X-API-Key: your-api-key
```

**Delete Data**
```bash
DELETE /api/data/{data_id}
Header: X-API-Key: your-api-key
```

## Usage Examples

### 1. Store Data
```bash
curl -X POST "http://localhost:8000/api/data" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "data": {"user": "john", "action": "login", "timestamp": "2024-03-26T10:30:00"},
    "metadata": {"source": "web-app", "version": "1.0"}
  }'
```

### 2. Retrieve All Data
```bash
curl -X GET "http://localhost:8000/api/data?limit=10&skip=0" \
  -H "X-API-Key: your-api-key"
```

### 3. Retrieve Specific Data
```bash
curl -X GET "http://localhost:8000/api/data/507f1f77bcf86cd799439011" \
  -H "X-API-Key: your-api-key"
```

### 4. Delete Data
```bash
curl -X DELETE "http://localhost:8000/api/data/507f1f77bcf86cd799439011" \
  -H "X-API-Key: your-api-key"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| MONGODB_URL | mongodb://localhost:27017 | MongoDB connection string |
| DATABASE_NAME | vapi_db | Database name |
| API_KEY | your-api-key-here-change-in-production | API key for authentication |

## Security Notes

⚠️ **Important for Production:**
- Change `API_KEY` to a strong random string
- Update `CORS` allowed origins to specific domains
- Use environment variables for sensitive data
- Enable HTTPS
- Implement rate limiting
- Use connection pooling for MongoDB
- Store API keys securely (use secrets management system)

## Development

### Run Health Check
```bash
curl http://localhost:8000/health
```

### View Interactive Docs
Visit `http://localhost:8000/docs` for Swagger UI

## Troubleshooting

### MongoDB Connection Error
- Ensure MongoDB is running: `mongod`
- Check `MONGODB_URL` in `.env`

### API Key Authentication Fails
- Verify `API_KEY` in `.env` matches the header value
- Header must be exactly `X-API-Key`

### Import Errors
- Make sure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

## License

Specify your license here

## Support

For issues or questions, contact your team development lead.

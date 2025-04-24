# FastAPI Boilerplate

A modern FastAPI boilerplate for building microservices with Kafka integration using FastStream and async task
processing using SAQ.

## 🎯 Use as Template

You can use this boilerplate as a template for your project using [Copier](https://copier.readthedocs.io/), a library for rendering project templates.

1. Install Copier:
```bash
pipx install copier
```
2. Clone this repository
```
git clone https://predictintel@dev.azure.com/predictintel/Cybersmart-Next/_git/fastapi-boilerplate
```
2. Generate a new project from this template:
```bash
copier copy fastapi-boilerplate  path/to/your/new/project
```

3. Follow the interactive prompts to configure your project.

## 🚀 Features

- **Modern FastAPI Framework**: High-performance, easy-to-use web framework
- **Event-Driven Architecture**: Kafka integration using FastStream for real-time event processing
- **Async Task Processing**: SAQ integration with Redis for background task processing
- **API Versioning**: Built-in support for API versioning (v1, v2)
- **Correlation ID**: Request tracking across services
- **Structured Logging**: Configurable logging with correlation ID support
- **Production-Ready**: Docker support, configuration management, and more
- **Background Tasks**: Celery worker integration for asynchronous task processing
- **Testing Suite**: Comprehensive test scripts for both Windows and Linux environments

## 🛠 Tech Stack

- **[FastAPI](https://fastapi.tiangolo.com/)**: Modern web framework for building APIs with Python
- **[FastStream](https://faststream.airt.ai/)**: Framework for building event-driven applications
- **[SAQ](https://github.com/tobymao/saq)**: Simple Async Queue for background task processing
- **[Kafka](https://kafka.apache.org/)**: Distributed event streaming platform
- **[Pydantic](https://docs.pydantic.dev/)**: Data validation using Python type annotations
- **[Celery](https://docs.celeryq.dev/)**: Distributed task queue for background processing

## 📁 Project Structure

```
fastapi-boilerplate/
├── app/                    # Application source code
│   ├── api/               # API endpoints
│   │   ├── v1/           # API version 1
│   │   └── v2/           # API version 2
│   └── worker/           # Workers
│       ├── celery/       # Celery task definitions
│       └── faststream/   # Kafka message handlers
│       └── saq/          # SAQ task handlers
│
├── core/                  # Core application bootstrap
│   ├── config.py         # Configuration management
│   ├── faststream.py     # FastStream setup
│   ├── celery.py        # Celery configuration
│   ├── saq.py           # SAQ setup
│   ├── middleware.py     # Application middleware
│   ├── log_config.py     # Logging configuration
│   ├── server.py         # ASGI server setup
│   └── filestorage.py    # Filestorage class
│
├── docs/                  # Documentation
├── tests/                # Test suite
├── .env                  # Environment variables
├── docker-compose.yaml   # Docker compose configuration
├── Dockerfile           # Docker build instructions
├── requirements.txt     # Python dependencies
└── main.py             # Application entry point
```

## 🚦 Getting Started

1. Clone the repository:

```bash
git clone https://github.com/yourusername/fastapi-boilerplate.git
cd fastapi-boilerplate
```

2. Create and activate virtual environment:

```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set up environment variables. Copy [.env.example](.env.example) as [.env](.env) and fill the variables

5. Start required services:

```bash
# Start Kafka and Redis
docker-compose up -d kafka redis
```

6. Run the application components:

```bash
# Start the FastAPI application
uvicorn main:app --reload --port 8000

# Start the Celery worker (in a separate terminal)
celery -A worker worker --loglevel=info
```

# Start the SAQ worker (in a separate terminal)

python -m saq app.worker.saq.settings --web

```

## 🧪 Running Tests

For detailed instructions on running tests in both Windows and Linux environments, please refer to the [Test Documentation](docs/running_tests.md).

## 🔄 Event Processing with FastStream

This boilerplate implements event processing using FastStream and Kafka:

- **Message Publishing**: Send messages to Kafka topics through API endpoints
- **Message Subscription**: Process messages from Kafka topics using FastStream workers
- **Correlation ID**: Track requests across services
- **Structured Logging**: Log messages with correlation IDs for traceability

Example ping endpoint that publishes a message:
```python
@router.get("/ping")
async def ping(request: Request):
    correlation_id = correlation_id_ctx_var.get()
    message = SampleReqMsg(
        correlation_id=correlation_id,
        data=MessageContent(message="Send for in-topic")
    )
    await publish_message(request, message, "in-topic")
    return {"version": settings.APP_VERSION, "message": "pong"}
```

## 🔄 Background Tasks with Celery

The boilerplate includes Celery integration for handling background tasks:

- **Asynchronous Processing**: Execute time-consuming tasks in the background
- **Task Scheduling**: Schedule tasks to run at specific times
- **Task Monitoring**: Track task status and results
- **Redis Backend**: Store task results and enable task result retrieval

Example Celery task:

```python
@celery_app.task
def process_data(data: dict):
    # Process data asynchronously
    result = perform_heavy_computation(data)
    return result
```

## 🐳 Docker Support

Run the entire application stack using Docker Compose:

```bash
# Development
docker-compose up -d

# Access the API at http://localhost:8000
```

## 📖 Documentation

- API documentation available at `/docs` or `/redoc`
- Additional documentation in `/docs` directory:
    - FastStream integration details
    - API versioning guide
    - Deployment instructions
    - Test execution guide

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

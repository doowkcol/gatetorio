"""Main FastAPI application"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, close_db
from app.services.mqtt_client import mqtt_service
from app.api import devices, users, sharing, commands
from app.api.schemas import HealthResponse
from app import __version__

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Gatetorio Central Server...")

    # Initialize database
    logger.info("Initializing database...")
    await init_db()

    # Initialize and connect MQTT client
    logger.info("Connecting to MQTT broker...")
    try:
        mqtt_service.initialize()
        mqtt_service.connect()
        logger.info("MQTT client connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")

    logger.info("Server startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Gatetorio Central Server...")

    # Disconnect MQTT
    mqtt_service.disconnect()

    # Close database connections
    await close_db()

    logger.info("Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=__version__,
    description="Central hub for Gatetorio gate controllers",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(devices.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(sharing.router, prefix=settings.API_PREFIX)
app.include_router(commands.router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.PROJECT_NAME,
        "version": __version__,
        "status": "running",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    # TODO: Add database connectivity check
    return HealthResponse(
        status="healthy",
        mqtt_connected=mqtt_service.connected,
        database_connected=True,  # Assume healthy for now
        version=__version__,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
    )

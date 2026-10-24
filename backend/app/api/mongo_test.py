# app/api/mongo_test.py
"""Temporary endpoint to test MongoDB connectivity."""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db

router = APIRouter(prefix="/api/mongo-test", tags=["MongoDB Test"])


@router.post("/insert")
async def insert_sample(db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await db.test_collection.insert_one({
        "message": "Hello from Motor!",
        "source": "Phase 3",
    })
    return {"inserted_id": str(result.inserted_id)}


@router.get("/find")
async def find_samples(db: AsyncIOMotorDatabase = Depends(get_db)):
    cursor = db.test_collection.find({})
    documents = await cursor.to_list(length=100)
    for doc in documents:
        doc["_id"] = str(doc["_id"])
    return {"count": len(documents), "documents": documents}


@router.delete("/cleanup")
async def cleanup(db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await db.test_collection.delete_many({})
    return {"deleted_count": result.deleted_count}
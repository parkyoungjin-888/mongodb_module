from typing import List, Type
from beanie import Document, init_beanie
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient


class BaseDocument(Document):
    @classmethod
    async def find_with_paginate(cls, query: dict, sort: list[str] = None, project_model: Type[BaseModel] = None,
                                 page_size: int = None, page_num: int = None) -> dict:
        default_sort = ['-_id']
        if sort is None or ('+_id' not in sort and '-_id' not in sort):
            sort = (sort or []) + default_sort

        cursor = cls.find(query, projection_model=project_model).sort(*sort)

        total_count = await cursor.count()

        if page_size is not None:
            skip = page_size * (page_num - 1)
            cursor = cursor.skip(skip).limit(page_size)

        doc_list = await cursor.to_list()
        doc_list = [doc.model_dump(by_alias=True) for doc in doc_list]
        return {'doc_list': doc_list, 'total_count': total_count}

    @classmethod
    async def delete_many(cls, query: dict) -> int:
        result = await cls.find(query).delete()
        return result.deleted_count

    @classmethod
    async def get_aggregate_result(cls, pipeline: list[dict]):
        return await cls.aggregate(pipeline).to_list()


def create_data_model_class(base_model: BaseModel, collection_name: str) -> Type[BaseDocument]:
    class DataModel(BaseDocument, base_model):
        class Settings:
            name = collection_name
    return DataModel


class BeanieControl:
    def __init__(self, host: str, port: int, db: str, collection: str, user: str, pwd: str):
        self.db = db
        self.collection = collection
        self.db_url = f'mongodb://{user}:{pwd}@{host}:{port}'

    async def init(self, base_model: BaseModel):
        data_model_list = [create_data_model_class(base_model, self.collection)]
        client = AsyncIOMotorClient(self.db_url)
        await init_beanie(database=client[self.db], document_models=data_model_list)
        return data_model_list[0]

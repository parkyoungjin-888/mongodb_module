import asyncio
from functools import wraps
import grpc
from google.protobuf import struct_pb2
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel

from mongodb_module.proto import collection_pb2 as pb2
from mongodb_module.proto import collection_pb2_grpc
from utils_module.type_convert import convert_map


def grpc_client_error_handler(response):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                func_response = await func(*args, **kwargs)
                return func_response
            except grpc.aio.AioRpcError as e:
                print(f'{func.__name__} gRPC Error: {e.code()} - {e.details()}')
                response.code = 400
                response.message = f'{func.__name__} gRPC Error: {e.code()} - {e.details()}'
                return MessageToDict(response, preserving_proto_field_name=True)
            except Exception as e:
                print(f'{func.__name__} Error: {str(e)}')
                response.code = 500
                response.message = f'{func.__name__} Error: {str(e)}'
                return MessageToDict(response, preserving_proto_field_name=True)

        return wrapper

    return decorator


class CollectionClient:
    def __init__(self, host: str, port: int, collection_model: BaseModel):
        self.channel = grpc.aio.insecure_channel(f'{host}:{port}')
        self.stub = collection_pb2_grpc.CollectionServerStub(self.channel)
        self.collection_model = collection_model

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.channel.close()

    @grpc_client_error_handler(pb2.IdResponse())
    async def insert_one(self, doc: dict) -> dict:
        doc_req = pb2.DocRequest(doc=doc)
        res = await self.stub.InsertOne(doc_req)
        res = MessageToDict(res, preserving_proto_field_name=True)
        return res

    @grpc_client_error_handler(pb2.IdListResponse())
    async def insert_many(self, doc_list: list[dict]) -> dict:
        doc_list_req = pb2.DocListRequest()
        for doc in doc_list:
            struct_doc = struct_pb2.Struct()
            struct_doc.update(doc)
            doc_list_req.doc_list.append(struct_doc)
        res = await self.stub.InsertMany(doc_list_req)
        res = MessageToDict(res, preserving_proto_field_name=True)
        return res

    @grpc_client_error_handler(pb2.DocResponse())
    async def get_tag(self, field_list: list[str], query: dict) -> dict:
        tag_req = pb2.TagRequest()
        tag_req.field_list.extend(field_list)
        tag_req.query = query
        res = await self.stub.GetTag(tag_req)
        res = MessageToDict(res, preserving_proto_field_name=True)
        if res['code'] // 100 != 2:
            return res
        doc = {}
        for key, value in res['doc'].items():
            doc[key] = list(map(lambda x: convert_map[x['type']](x['value']), value))
        res['doc'] = doc
        return res

    @grpc_client_error_handler(pb2.DocResponse())
    async def get_one(self, doc_id: str, model_validation: bool = True) -> dict:
        id_req = pb2.IdRequest()
        id_req.doc_id = doc_id
        res = await self.stub.GetOne(id_req)
        res = MessageToDict(res, preserving_proto_field_name=True)
        if res['code'] // 100 != 2:
            return res

        if model_validation:
            res['doc'] = self.collection_model(**res['doc']).model_dump(by_alias=True)
        return res

    @grpc_client_error_handler(pb2.DocListResponse())
    async def get_many(self, query: dict, project_model: BaseModel = None, sort: list[str] = None,
                       page_size: int = None, page_num: int = None, model_validation: bool = True) -> dict:
        query_req = pb2.QueryRequest()
        query_req.query = query
        if project_model is not None:
            query_req.project_model = project_model.__name__
        if sort is not None:
            query_req.sort.extend(sort)
        if page_size is not None:
            query_req.page_size = page_size
            query_req.page_num = page_num

        res = await self.stub.GetMany(query_req)
        res = MessageToDict(res, always_print_fields_with_no_presence=True, preserving_proto_field_name=True)
        if res['code'] // 100 != 2:
            return res

        if not model_validation:
            return res

        if project_model is not None:
            res['doc_list'] = [project_model(**doc).model_dump(by_alias=True) for doc in res['doc_list']]
        else:
            res['doc_list'] = [self.collection_model(**doc).model_dump(by_alias=True) for doc in res['doc_list']]
        return res

    @grpc_client_error_handler(pb2.DocResponse())
    async def update_one(self, query: dict, set: dict = None, unset: dict = None, push: dict = None,
                         array_filter: dict = None, upsert: bool = None) -> dict:
        update_req = pb2.UpdateRequest()
        update_req.query = query
        if set is None and unset is None and push is None:
            raise ValueError('set or unset or push be required')
        if set is not None:
            update_req.set = set
        if unset is not None:
            update_req.unset = unset
        if push is not None:
            update_req.push = push
        if array_filter is not None:
            update_req.array_filter = array_filter
        if upsert is not None:
            update_req.upsert = upsert
        res = await self.stub.UpdateOne(update_req)
        res = MessageToDict(res, always_print_fields_with_no_presence=True, preserving_proto_field_name=True)
        return res

    @grpc_client_error_handler(pb2.CountResponse())
    async def update_many(self, update_request_list: list[dict], ordered: bool = True) -> dict:
        update_many_req = pb2.UpdateManyRequest()
        for update_reqest in update_request_list:
            update_req = pb2.UpdateRequest()
            update_req.query = update_reqest['query']
            if update_reqest.get('set') and update_reqest.get('unset') and update_reqest.get('push'):
                raise ValueError('set or unset or push be required')
            if 'set' in update_reqest and update_reqest['set'] is not None:
                update_req.set = update_reqest['set']
            if 'unset' in update_reqest and update_reqest['unset'] is not None:
                update_req.unset = update_reqest['unset']
            if 'push' in update_reqest and update_reqest['push'] is not None:
                update_req.push = update_reqest['push']
            if 'array_filter' in update_reqest and update_reqest['array_filter'] is not None:
                update_req.array_filter = update_reqest['array_filter']
            if 'upsert' in update_reqest and update_reqest['upsert'] is not None:
                update_req.upsert = update_reqest['upsert']
            update_many_req.update_request_list.append(update_req)
        update_many_req.ordered = ordered
        res = await self.stub.UpdateMany(update_many_req)
        res = MessageToDict(res, always_print_fields_with_no_presence=True, preserving_proto_field_name=True)
        return res

    @grpc_client_error_handler(pb2.CountResponse())
    async def delete_one(self, query: dict) -> dict:
        query_req = pb2.QueryRequest()
        query_req.query = query
        res = await self.stub.DeleteOne(query_req)
        res = MessageToDict(res, always_print_fields_with_no_presence=True, preserving_proto_field_name=True)
        return res

    @grpc_client_error_handler(pb2.CountResponse())
    async def delete_many(self, query: dict) -> dict:
        query_req = pb2.QueryRequest()
        query_req.query = query
        res = await self.stub.DeleteMany(query_req)
        res = MessageToDict(res, always_print_fields_with_no_presence=True, preserving_proto_field_name=True)
        return res

    @grpc_client_error_handler(pb2.DocListResponse())
    async def aggregate(self, pipeline: list[dict]) -> dict:
        aggregate_req = pb2.AggregateRequest()
        for content in pipeline:
            pipeline_unit = struct_pb2.Struct()
            pipeline_unit.update(content)
            aggregate_req.pipeline.append(pipeline_unit)
        res = await self.stub.Aggregate(aggregate_req)
        res = MessageToDict(res, preserving_proto_field_name=True)
        return res

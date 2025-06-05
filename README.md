## Command
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ./mongodb_module/proto/collection.proto
```

## Version
+ 0.1.0 : init
+ 0.1.1 : 함수 인자 변경
+ 0.1.2 : beanie control 인자 수정
  + mongos를 사용하여 레플리카 세트 인자 제거
+ 0.1.3 : get_tag 반환값 수정
+ 0.1.4 : UpdateOne, DeleteOne 추가, UpdateMany ordered 옵션 추가
+ 0.1.5 : beanie client 에 모델 검증 옵션 추가, UpdateMany 여러 조건 입력 가능 하도록 수정

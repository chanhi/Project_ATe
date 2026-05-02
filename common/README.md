# common/

팀에서 공유하는 코드를 두는 디렉토리.
docker-compose.yml의 backend/worker 서비스에서 `/app/common`으로 마운트된다.

현재는 빈 상태. 프론트/AI/백엔드 팀이 공통으로 쓰는 상수, 에러 코드,
DTO 정의 등이 생기면 여기에 둔다.

예:
- `common/error_codes.py` — 표준 에러 코드
- `common/constants.py` — 팀 공유 상수

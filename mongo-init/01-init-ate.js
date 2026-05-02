// ══════════════════════════════════════════════
//  MongoDB 초기화 스크립트
//  mongo_data 볼륨이 처음 생성될 때 자동 실행됨
// ══════════════════════════════════════════════
//
// ⚠️ 주의: 이 스크립트는 볼륨이 비어있을 때만 실행된다.
// 기존 볼륨이 있으면 envfile을 바꿔도 반영되지 않으므로
// 필요 시 `docker compose down -v` 로 볼륨을 초기화해야 한다.

// admin DB에 루트 유저는 이미 MONGO_INITDB_ROOT_USERNAME/PASSWORD로 생성됨.
// 여기서는 애플리케이션용 DB와 기본 컬렉션을 확실히 만들어둔다.

db = db.getSiblingDB(process.env.MONGO_INITDB_DATABASE || "ate_db");

// 빈 컬렉션 생성 (Motor가 자동 생성하지만, 권한 문제 방지용)
db.createCollection("projects");
db.createCollection("uploaded_documents");
db.createCollection("test_cases");
db.createCollection("test_runs");
db.createCollection("scenarios");
db.createCollection("webhook_configs");
db.createCollection("webhook_events");

print("✅ ATe 데이터베이스 초기화 완료: " + db.getName());

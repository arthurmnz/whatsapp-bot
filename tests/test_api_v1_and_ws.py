import base64
import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

from docx import Document
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import _rate_buckets, issue_otp_for_user
from app.db.repositories.user_repo import create_registered_user
from app.db.seed import seed_initial_data
from app.db.session import Base, get_db
from app.main import app
from app.modules.jobs_career.sources.base import NormalizedJob


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "test-enc-key-32-bytes-seed-value")
    monkeypatch.setenv("HMAC_SECRET", "test-hmac-secret-seed-value")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-seed-value-2026")
    monkeypatch.setenv("ADMIN_REMOTE_JIDS", "5511999999999@s.whatsapp.net:Arthur Admin")
    monkeypatch.setenv("GENERATED_CVS_DIR", str(tmp_path / "generated_cvs"))
    monkeypatch.setenv("UPLOADED_CVS_DIR", str(tmp_path / "uploaded_cvs"))
    monkeypatch.setenv("CACHE_REDIS_URI", "")
    monkeypatch.setenv("EVOLUTION_API_URL", "http://evolution:8080")
    monkeypatch.setenv("EVOLUTION_INSTANCE", "bot")
    _rate_buckets.clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        seed_initial_data(db)
        create_registered_user(
            db,
            remote_jid="5511988887777@s.whatsapp.net",
            nome="Maria User",
            role_name="user",
        )

    def _override_get_db():
        with TestingSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    try:
        yield client, TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)


def _login_via_otp(client: TestClient, session_factory, phone: str) -> str:
    with patch("app.api.v1.auth.send_text", new_callable=AsyncMock) as mock_send:
        resp_req = client.post("/api/v1/auth/request-otp", json={"phone_or_jid": phone})
        assert resp_req.status_code == 200
        assert "otp" not in str(resp_req.json()).lower() or "enviado" in resp_req.json()["message"].lower()

    # Extrai OTP enviado no mock OU emite um determinístico em teste
    if mock_send.await_args:
        sent_text = mock_send.await_args.kwargs["text"]
        import re
        code = re.search(r"\*(\d{6})\*", sent_text).group(1)
    else:
        with session_factory() as db:
            from app.core.auth import find_user_by_phone_or_jid
            u = find_user_by_phone_or_jid(db, phone)
            code = issue_otp_for_user(u)

    resp_verify = client.post("/api/v1/auth/verify-otp", json={"phone_or_jid": phone, "code": code})
    assert resp_verify.status_code == 200
    data = resp_verify.json()
    assert "access_token" in data
    return data["access_token"]


def test_auth_otp_password_and_rbac_flow(api_client, monkeypatch: pytest.MonkeyPatch):
    client, session_factory = api_client
    monkeypatch.setenv("EVOLUTION_API_URL", "http://evolution:8080")
    monkeypatch.setenv("EVOLUTION_INSTANCE", "bot")

    # 1. Login via OTP para usuário comum (Maria User)
    user_token = _login_via_otp(client, session_factory, "5511988887777")
    user_headers = {"Authorization": f"Bearer {user_token}"}

    me_resp = client.get("/api/v1/auth/me", headers=user_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["role"] == "user"
    assert me_resp.json()["user"]["has_web_password"] is False

    # 2. Configura senha web e faz login por senha
    pwd_resp = client.post(
        "/api/v1/auth/set-password",
        json={"password": "MinhaSenhaForte123"},
        headers=user_headers,
    )
    assert pwd_resp.status_code == 200
    assert pwd_resp.json()["user"]["has_web_password"] is True

    login_pwd = client.post(
        "/api/v1/auth/login-password",
        json={"identifier": "5511988887777", "password": "MinhaSenhaForte123"},
    )
    assert login_pwd.status_code == 200
    assert login_pwd.json()["user"]["nome"] == "Maria User"

    # 3. RBAC no controle de dispositivos: usuário comum não pode desligar PC (403)
    denied = client.post("/api/v1/system/devices/shutdown", headers=user_headers)
    assert denied.status_code == 403

    # Admin pode controlar dispositivos
    admin_token = _login_via_otp(client, session_factory, "5511999999999")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    with patch(
        "app.api.v1.system.get_windows_status",
        new_callable=AsyncMock,
        return_value={"online": True, "hostname": "PC-WIN", "reason": "ok", "message": "Online"},
    ):
        ok_status = client.post("/api/v1/system/devices/status", headers=admin_headers)
        assert ok_status.status_code == 200
        assert ok_status.json()["result"]["online"] is True


def test_full_career_pipeline_profile_resume_jobs_applications_and_ws(api_client):
    client, session_factory = api_client
    token = _login_via_otp(client, session_factory, "5511999999999")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Atualiza perfil e preferências de mercado
    put_prof = client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "headline": "Engenheiro Backend Python",
            "years_experience": 5,
            "location": "São Paulo, Brasil",
            "skills": [
                {"name": "Python", "is_core": True},
                {"name": "FastAPI", "is_core": True},
                {"name": "PostgreSQL"},
                {"name": "Docker"},
            ],
            "preferences": {
                "target_roles": ["Backend Engineer", "Python Developer"],
                "work_models": ["remote"],
                "contract_types": ["clt", "pj"],
                "min_salary": 12000,
                "desired_stack": ["FastAPI", "Redis"],
                "dealbreakers": ["presencial"],
                "preferred_language": "auto",
            },
        },
    )
    assert put_prof.status_code == 200
    assert len(put_prof.json()["skills"]) == 4

    # 2. Upload de currículo DOCX
    doc = Document()
    doc.add_paragraph("Arthur Muniz")
    doc.add_paragraph("arthur@example.com | linkedin.com/in/arthurmnz")
    doc.add_paragraph("Resumo Profissional")
    doc.add_paragraph("Engenheiro Backend com 5 anos em Python, FastAPI e PostgreSQL.")
    doc.add_paragraph("Experiência Profissional")
    doc.add_paragraph("Backend Engineer — Acme Tech | 2021 - Atual")
    doc.add_paragraph("- Desenvolvi microsserviços em Python e FastAPI com Docker.")
    buf = io.BytesIO()
    doc.save(buf)

    upload_resp = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("arthur_cv.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"title": "CV Principal", "sync_profile": "true"},
    )
    assert upload_resp.status_code == 201
    resume_id = upload_resp.json()["id"]
    assert upload_resp.json()["is_default"] is True
    assert upload_resp.json()["has_file"] is True
    assert "file_path" not in upload_resp.json()

    # 3. Busca de vagas gratuita (mockando adapters externos) e ingestão manual
    mocked_job = NormalizedJob(
        source="remotive",
        external_id="rem-99",
        source_url="https://remotive.com/remote-jobs/python-backend-99",
        title="Senior Python Backend Engineer",
        company_name="RemoteScale",
        location="Remote",
        work_model="remote",
        language="en",
        description_raw="Looking for a Python Backend Engineer with FastAPI, PostgreSQL, Docker and Redis.",
    )
    with patch("app.modules.jobs_career.sources.remotive.RemotiveAdapter.fetch_jobs", new_callable=AsyncMock, return_value=[mocked_job]):
        with patch("app.modules.jobs_career.sources.github_br.GitHubBRAdapter.fetch_jobs", new_callable=AsyncMock, return_value=[]):
            with patch("app.modules.jobs_career.sources.arbeitnow.ArbeitnowAdapter.fetch_jobs", new_callable=AsyncMock, return_value=[]):
                with patch("app.modules.jobs_career.sources.himalayas.HimalayasAdapter.fetch_jobs", new_callable=AsyncMock, return_value=[]):
                    search_resp = client.post(
                        "/api/v1/jobs/search",
                        headers=headers,
                        json={"query": "python", "sources": ["remotive", "github_br"]},
                    )
    assert search_resp.status_code == 200
    assert len(search_resp.json()["items"]) == 1
    job_match = search_resp.json()["items"][0]
    job_id = job_match["job_id"]
    match_id = job_match["match_id"]
    assert job_match["match_score"] >= 60

    # Marca match como salvo
    patch_match = client.patch(f"/api/v1/jobs/matches/{match_id}", headers=headers, json={"status": "saved"})
    assert patch_match.status_code == 200
    assert patch_match.json()["status"] == "saved"

    # Ingestão manual com bloqueio SSRF
    ssrf_resp = client.post(
        "/api/v1/jobs/ingest",
        headers=headers,
        json={"url": "http://127.0.0.1:8080/internal"},
    )
    assert ssrf_resp.status_code == 400

    # 4. Otimização do currículo (ATS before/after + PDF/DOCX/MD)
    tailor_resp = client.post(
        "/api/v1/resumes/tailor",
        headers=headers,
        json={"base_resume_id": resume_id, "job_id": job_id, "target_language": "en"},
    )
    assert tailor_resp.status_code == 201
    tailored = tailor_resp.json()
    tailored_id = tailored["id"]
    assert tailored["target_language"] == "en"
    assert tailored["has_pdf"] is True
    assert tailored["has_docx"] is True
    assert tailored["ats_score_after"] >= tailored["ats_score_before"]

    # Edição manual de markdown e download em PDF/DOCX/MD
    patch_tailored = client.patch(
        f"/api/v1/resumes/tailored/{tailored_id}",
        headers=headers,
        json={"tailored_markdown": tailored["tailored_markdown"] + "\n- Extra highlight"},
    )
    assert patch_tailored.status_code == 200

    for fmt, expected_prefix in [("pdf", b"%PDF-"), ("docx", b"PK\x03\x04"), ("md", b"# ")]:
        dl = client.get(f"/api/v1/resumes/tailored/{tailored_id}/download?format={fmt}", headers=headers)
        assert dl.status_code == 200
        assert dl.content.startswith(expected_prefix)

    # 5. Kanban de candidaturas + interview prep
    app_resp = client.post(
        "/api/v1/applications",
        headers=headers,
        json={
            "company_name": "RemoteScale",
            "role_title": "Senior Python Backend Engineer",
            "job_id": job_id,
            "tailored_resume_id": tailored_id,
            "stage": "cv_ready",
        },
    )
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    prep_resp = client.post(f"/api/v1/applications/{app_id}/interview-prep", headers=headers)
    assert prep_resp.status_code == 200
    assert len(prep_resp.json()["interview_prep"]["likely_questions"]) >= 1

    # 6. Chat REST + WebSocket em tempo real
    thread_resp = client.post("/api/v1/chat/threads", headers=headers, json={"title": "Treino Carreira"})
    assert thread_resp.status_code == 201
    thread_id = thread_resp.json()["id"]

    msg_resp = client.post(
        f"/api/v1/chat/threads/{thread_id}/messages",
        headers=headers,
        json={"content": "/perfil"},
    )
    assert msg_resp.status_code == 201
    assert "Engenheiro Backend Python" in msg_resp.json()["reply_text"]

    # Query string token deve ser rejeitado por padrão
    with client.websocket_connect(f"/ws/chat?token={token}") as ws_rejected:
        ws_rejected.send_json({"type": "ping"})
        err_evt = ws_rejected.receive_json()
        assert err_evt["type"] == "error"

    # Autenticação segura via frame inicial JSON
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "auth", "token": token})
        conn_evt = ws.receive_json()
        assert conn_evt["type"] == "connected"
        ws.send_json({"type": "message", "thread_id": thread_id, "content": "/skills Redis"})
        status_evt = ws.receive_json()
        assert status_evt["type"] == "status"
        reply_evt = ws.receive_json()
        assert reply_evt["type"] == "assistant_message"
        assert "Redis" in reply_evt["content"]

    # 7. System overview
    ov = client.get("/api/v1/system/overview", headers=headers)
    assert ov.status_code == 200
    counts = ov.json()["counts"]
    assert counts["base_resumes"] == 1
    assert counts["tailored_resumes"] == 1
    assert counts["active_applications"] == 1


def test_whatsapp_document_upload_and_cv_pdf_dispatch(api_client):
    client, _ = api_client
    doc = Document()
    doc.add_paragraph("Arthur Muniz")
    doc.add_paragraph("Habilidades: Python, FastAPI, Docker, PostgreSQL")
    buf = io.BytesIO()
    doc.save(buf)
    b64_docx = base64.b64encode(buf.getvalue()).decode("ascii")

    # 1. Envia documento DOCX via webhook do WhatsApp
    doc_payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False},
            "pushName": "Arthur",
            "message": {
                "documentMessage": {
                    "fileName": "meu_cv.docx",
                    "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "base64": b64_docx,
                }
            },
        },
    }
    with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send:
        r1 = client.post("/webhook", json=doc_payload)
        assert r1.status_code == 200
        assert "processado e salvo" in r1.json()["reply"]
        mock_send.assert_awaited_once()

    # 2. Envia /avaliar com descrição da vaga -> gera e envia PDF via send_document
    eval_payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False},
            "pushName": "Arthur",
            "message": {
                "conversation": "/avaliar Vaga Backend Python com FastAPI, PostgreSQL e Docker remoto"
            },
        },
    }
    with patch("app.api.webhook.send_text", new_callable=AsyncMock) as mock_send_txt:
        with patch("app.api.webhook.send_document", new_callable=AsyncMock) as mock_send_doc:
            r2 = client.post("/webhook", json=eval_payload)
            assert r2.status_code == 200
            assert "Score ATS" in r2.json()["reply"]
            mock_send_txt.assert_awaited_once()
            mock_send_doc.assert_awaited_once()
            assert mock_send_doc.await_args.kwargs["filename"].endswith(".pdf")


def test_init_db_auto_migration_on_legacy_users_table(tmp_path: Path):
    from sqlalchemy import inspect, text
    from app.db.seed import init_db

    db_path = tmp_path / "legacy.db"
    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE roles (id INTEGER PRIMARY KEY, name VARCHAR(50) UNIQUE NOT NULL, description VARCHAR(255))"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, nome VARCHAR(150) NOT NULL, senha TEXT NOT NULL, remote_jid_hash VARCHAR(64) UNIQUE NOT NULL, role_id INTEGER NOT NULL, is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL)"
            )
        )

    init_db(bind_engine=eng)
    insp = inspect(eng)
    user_cols = {c["name"] for c in insp.get_columns("users")}
    assert "web_password_hash" in user_cols
    assert "updated_at" in user_cols
    assert insp.has_table("candidate_profiles")
    assert insp.has_table("tailored_resumes")
    assert insp.has_table("chat_threads")


def test_alembic_upgrade_head_clean_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    db_file = tmp_path / "alembic_test.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    eng = create_engine(db_url, connect_args={"check_same_thread": False})
    insp = inspect(eng)
    for table in [
        "users",
        "roles",
        "permissions",
        "candidate_profiles",
        "candidate_skills",
        "job_preferences",
        "resumes",
        "job_postings",
        "job_matches",
        "tailored_resumes",
        "job_applications",
        "chat_threads",
        "chat_messages",
    ]:
        assert insp.has_table(table), f"Tabela ausente após alembic upgrade head: {table}"


def test_auth_hardening_otp_logs_503_lockout_wildcard_and_password_change(
    api_client,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    client, session_factory = api_client
    caplog.set_level("DEBUG")

    # 1. Evolution não configurada não gera nem loga OTP
    monkeypatch.setenv("EVOLUTION_API_URL", "")
    resp_unconf = client.post("/api/v1/auth/request-otp", json={"phone_or_jid": "5511988887777"})
    assert resp_unconf.status_code == 200
    assert resp_unconf.json()["status"] == "unavailable"

    # 2. Falha de envio Evolution -> 503 e OTP invalidado
    monkeypatch.setenv("EVOLUTION_API_URL", "http://evolution:8080")
    monkeypatch.setenv("EVOLUTION_INSTANCE", "bot")
    with patch("app.api.v1.auth.send_text", new_callable=AsyncMock, side_effect=RuntimeError("evo down")):
        resp_503 = client.post("/api/v1/auth/request-otp", json={"phone_or_jid": "5511988887777"})
    assert resp_503.status_code == 503

    # 3. Envio com sucesso não vaza código no log e lockout após 5 tentativas preserva expires_at
    with patch("app.api.v1.auth.send_text", new_callable=AsyncMock) as mock_send:
        resp_ok = client.post("/api/v1/auth/request-otp", json={"phone_or_jid": "5511988887777"})
        assert resp_ok.status_code == 200
        import re
        sent_code = re.search(r"\*(\d{6})\*", mock_send.await_args.kwargs["text"]).group(1)

    assert sent_code not in caplog.text

    for _ in range(5):
        bad = client.post("/api/v1/auth/verify-otp", json={"phone_or_jid": "5511988887777", "code": "000000"})
        assert bad.status_code == 401

    # Mesmo com código certo após 5 erros, deve ter sido invalidado
    after_lock = client.post("/api/v1/auth/verify-otp", json={"phone_or_jid": "5511988887777", "code": sent_code})
    assert after_lock.status_code == 401

    # 4. Login válido, wildcard SQL bloqueado e troca de senha exige current_password
    _rate_buckets.clear()
    tok = _login_via_otp(client, session_factory, "5511988887777")
    hdrs = {"Authorization": f"Bearer {tok}"}

    assert client.post("/api/v1/auth/set-password", json={"password": "SenhaInicial123"}, headers=hdrs).status_code == 200

    # Wildcards SQL ('%', '_') não podem casar com "Maria User"
    for wild in ["%", "%User%", "Maria_User"]:
        wild_resp = client.post("/api/v1/auth/login-password", json={"identifier": wild, "password": "SenhaInicial123"})
        assert wild_resp.status_code == 401

    # Alterar senha sem current_password -> 401
    assert client.post("/api/v1/auth/set-password", json={"password": "NovaSenha123"}, headers=hdrs).status_code == 401
    assert client.post(
        "/api/v1/auth/set-password",
        json={"current_password": "errada", "password": "NovaSenha123"},
        headers=hdrs,
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/set-password",
        json={"current_password": "SenhaInicial123", "password": "NovaSenha123"},
        headers=hdrs,
    ).status_code == 200


def test_rate_limit_enforced_on_login(api_client):
    client, _ = api_client
    for _ in range(10):
        resp = client.post("/api/v1/auth/login-password", json={"identifier": "5511988887777", "password": "wrong"})
        assert resp.status_code == 401
    rl_resp = client.post("/api/v1/auth/login-password", json={"identifier": "5511988887777", "password": "wrong"})
    assert rl_resp.status_code == 429


def test_contract_fixes_languages_unlink_idor_and_file_delete(api_client, tmp_path: Path):
    client, session_factory = api_client
    admin_tok = _login_via_otp(client, session_factory, "5511999999999")
    admin_hdrs = {"Authorization": f"Bearer {admin_tok}"}

    user_tok = _login_via_otp(client, session_factory, "5511988887777")
    user_hdrs = {"Authorization": f"Bearer {user_tok}"}

    # 1. Profile languages aceita chave "language" ou "name"
    p_resp = client.put(
        "/api/v1/profile",
        headers=admin_hdrs,
        json={"languages": [{"language": "Inglês", "level": "Fluente"}, {"name": "Português", "level": "Nativo"}]},
    )
    assert p_resp.status_code == 200
    langs = p_resp.json()["languages"]
    assert langs[0]["name"] == "Inglês"
    assert langs[0]["language"] == "Inglês"

    # 2. Admin cria vaga manual privada; Maria User NÃO pode acessá-la via IDOR
    ingest = client.post(
        "/api/v1/jobs/ingest",
        headers=admin_hdrs,
        json={"title": "Vaga Privada Admin", "description_raw": "Vaga confidencial Python FastAPI Docker PostgreSQL."},
    )
    assert ingest.status_code == 201
    private_job_id = ingest.json()["job_id"]

    idor_tailor = client.post(
        "/api/v1/resumes/tailor",
        headers=user_hdrs,
        json={"job_id": private_job_id, "resume_text": "Maria User Python FastAPI"},
    )
    assert idor_tailor.status_code == 400

    idor_app = client.post(
        "/api/v1/applications",
        headers=user_hdrs,
        json={"company_name": "Secreta", "role_title": "Dev", "job_id": private_job_id},
    )
    assert idor_app.status_code == 404

    # 3. Upload & Delete de currículo apaga o arquivo físico
    up = client.post(
        "/api/v1/resumes/upload",
        headers=admin_hdrs,
        files={"file": ("cv.txt", b"Arthur Muniz\nPython FastAPI", "text/plain")},
    )
    assert up.status_code == 201
    res_id = up.json()["id"]
    uploaded_files = list((tmp_path / "uploaded_cvs").rglob("*.txt"))
    assert len(uploaded_files) == 1
    assert client.delete(f"/api/v1/resumes/{res_id}", headers=admin_hdrs).status_code == 200
    assert len(list((tmp_path / "uploaded_cvs").rglob("*.txt"))) == 0

    # 4. PATCH /applications/{id} com tailored_resume_id: null desvincula o currículo
    tr_resp = client.post(
        "/api/v1/resumes/tailor",
        headers=admin_hdrs,
        json={"job_id": private_job_id, "resume_text": "Arthur Muniz Python FastAPI Docker"},
    )
    assert tr_resp.status_code == 201
    tr_id = tr_resp.json()["id"]

    app_create = client.post(
        "/api/v1/applications",
        headers=admin_hdrs,
        json={"company_name": "Acme", "role_title": "Dev", "tailored_resume_id": tr_id},
    )
    assert app_create.status_code == 201
    app_id = app_create.json()["id"]
    assert app_create.json()["tailored_resume_id"] == tr_id

    unlink = client.patch(
        f"/api/v1/applications/{app_id}",
        headers=admin_hdrs,
        json={"tailored_resume_id": None},
    )
    assert unlink.status_code == 200
    assert unlink.json()["tailored_resume_id"] is None


def test_webhook_secret_token_and_orchestrator_rbac(api_client, monkeypatch: pytest.MonkeyPatch):
    client, _ = api_client
    monkeypatch.setenv("WEBHOOK_SECRET_TOKEN", "segredo-webhook-evo")

    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False},
            "pushName": "Arthur",
            "message": {"conversation": "/perfil"},
        },
    }
    # Sem header -> 401 (envolvido no handler de erro do webhook) ou HTTP 401
    bad_resp = client.post("/webhook", json=payload)
    assert bad_resp.status_code == 401

    with patch("app.api.webhook.send_text", new_callable=AsyncMock):
        ok_resp = client.post("/webhook", json=payload, headers={"x-webhook-token": "segredo-webhook-evo"})
        assert ok_resp.status_code == 200


@pytest.mark.asyncio
async def test_orchestrator_enforces_career_permissions():
    from unittest.mock import MagicMock
    from app.agent.orchestrator import AgentOrchestrator

    orch = AgentOrchestrator()
    restricted_user = MagicMock(
        id=99,
        nome="Restrito",
        is_active=True,
        role=MagicMock(name="limited", permissions=[MagicMock(code="agent:chat")]),
    )
    for cmd in ["/perfil", "/skills Python", "/vontades remoto", "/vagas", "/vaga texto", "/avaliar vaga", "/entrevista"]:
        resp = await orch.process_message(db=None, user=restricted_user, message=cmd, channel="web")
        assert "Acesso negado" in resp.reply_text


def test_normalize_database_url_driver_fallback():
    from app.db.session import normalize_database_url

    with patch("importlib.util.find_spec", side_effect=lambda name: object() if name == "psycopg2" else None):
        assert (
            normalize_database_url("postgresql+psycopg://u:p@host:5432/db")
            == "postgresql+psycopg2://u:p@host:5432/db"
        )
    with patch("importlib.util.find_spec", side_effect=lambda name: object() if name == "psycopg" else None):
        assert (
            normalize_database_url("postgresql+psycopg2://u:p@host:5432/db")
            == "postgresql+psycopg://u:p@host:5432/db"
        )

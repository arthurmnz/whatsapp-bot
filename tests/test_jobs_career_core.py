import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from docx import Document
from pypdf import PdfReader
import pytest

from app.agent.llm_factory import get_llm_config, invoke_llm_text
from app.modules.jobs_career.cv_parser import (
    extract_text_from_bytes,
    parse_cv_heuristic,
    validate_cv_upload,
)
from app.modules.jobs_career.cv_renderer import (
    render_cv_docx,
    render_cv_markdown,
    render_cv_pdf,
    render_markdown_to_pdf,
    resolve_safe_cv_path,
)
from app.modules.jobs_career.cv_tailor import evaluate_and_tailor_cv
from app.modules.jobs_career.matching import calculate_job_match
from app.modules.jobs_career.skills_taxonomy import (
    detect_language,
    extract_job_requirements,
    extract_known_skills_from_text,
    normalize_skill_name,
)
from app.modules.jobs_career.sources.greenhouse_lever import sanitize_company_slug
from app.modules.jobs_career.sources.manual import (
    JobUrlBlockedError,
    ingest_job_from_url,
    validate_public_url,
)


def test_skills_normalization_and_exact_boundaries():
    assert normalize_skill_name("Postgres") == "postgresql"
    assert normalize_skill_name("node") == "node.js"
    assert normalize_skill_name("TS") == "typescript"
    assert normalize_skill_name("React.js") == "react"

    # "go" não deve casar dentro de "Django", "MongoDB" ou "Google"
    skills = extract_known_skills_from_text("Experiência com Django, MongoDB, Google Cloud e Python")
    assert "python" in skills
    assert "django" in skills
    assert "mongodb" in skills
    assert "go" not in skills

    # "java" não deve casar dentro de "JavaScript"
    js_only = extract_known_skills_from_text("React, TypeScript e JavaScript moderno")
    assert "javascript" in js_only
    assert "java" not in js_only


def test_bilingual_language_detection():
    pt_text = "Vaga para Desenvolvedor Backend Sênior com Python, FastAPI e PostgreSQL. Contratação CLT ou PJ remota."
    en_text = "Senior Backend Engineer role requiring Python, FastAPI, PostgreSQL, and AWS experience. Remote position."
    assert detect_language(pt_text) == "pt-BR"
    assert detect_language(en_text) == "en"


def test_cv_upload_magic_bytes_and_docx_pdf_extraction(tmp_path: Path):
    # Rejeita falso PDF e falso DOCX
    with pytest.raises(ValueError):
        validate_cv_upload("fake.pdf", b"not a real pdf")
    with pytest.raises(ValueError):
        validate_cv_upload("fake.docx", b"not a zip docx")
    with pytest.raises(ValueError):
        validate_cv_upload("huge.txt", b"a" * (5 * 1024 * 1024 + 10))
    with pytest.raises(ValueError):
        validate_cv_upload("script.exe", b"MZ\x90\x00")

    # Cria DOCX real em memória e valida extração
    doc = Document()
    doc.add_paragraph("Maria Clara")
    doc.add_paragraph("Resumo Profissional")
    doc.add_paragraph("Engenheira de Software com Python, FastAPI e Docker.")
    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    assert validate_cv_upload("cv.docx", docx_bytes) == "docx"
    extracted_docx = extract_text_from_bytes(docx_bytes, "docx")
    assert "Maria Clara" in extracted_docx
    assert "FastAPI" in extracted_docx

    # Renderiza PDF real e extrai de volta com pypdf
    pdf_path = tmp_path / "test_cv.pdf"
    sample_data = {
        "contact": {"name": "João Conceição", "email": "joao@example.com", "location": "São Paulo, BR"},
        "headline": "Engenheiro Backend Sênior",
        "summary": "Atuação com arquitetura escalável, integração contínua e automação.",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "experiences": [
            {
                "company": "Empresa Alpha",
                "role": "Desenvolvedor Backend",
                "period": "2022 - Atual",
                "location": "Remoto",
                "bullets": ["Reduzi latência de APIs em 45% com cache em Redis."],
            }
        ],
        "education": [{"degree": "Ciência da Computação", "institution": "USP", "period": "2018 - 2021"}],
    }
    render_cv_pdf(sample_data, pdf_path, target_language="pt-BR")
    pdf_bytes = pdf_path.read_bytes()
    assert validate_cv_upload("test_cv.pdf", pdf_bytes) == "pdf"
    extracted_pdf = extract_text_from_bytes(pdf_bytes, "pdf")
    assert "Empresa Alpha" in extracted_pdf
    assert "FastAPI" in extracted_pdf

    # DOCX gerado também válido
    docx_path = tmp_path / "test_cv.docx"
    render_cv_docx(sample_data, docx_path, target_language="pt-BR")
    assert docx_path.exists()
    assert validate_cv_upload("test_cv.docx", docx_path.read_bytes()) == "docx"

    # Markdown editado regera PDF válido
    md_pdf_path = tmp_path / "edited.pdf"
    render_markdown_to_pdf("# Teste\n## Resumo\n- Item com acentuação: ação e coração.", md_pdf_path)
    reader = PdfReader(str(md_pdf_path))
    assert len(reader.pages) >= 1


def test_path_traversal_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GENERATED_CVS_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        resolve_safe_cv_path(1, str(tmp_path / "user_2" / "other.pdf"))
    with pytest.raises(ValueError):
        resolve_safe_cv_path(1, str(tmp_path / ".." / "etc" / "passwd"))


@pytest.mark.asyncio
async def test_evaluate_and_tailor_cv_bilingual_and_anti_hallucination():
    cv_text = """
    Arthur Muniz
    arthur@example.com | github.com/arthurmnz

    Resumo Profissional
    Desenvolvedor Backend com foco em Python e APIs REST.

    Habilidades
    Python, FastAPI, PostgreSQL, Docker

    Experiência Profissional
    Backend Developer — TechCorp | 2022 - Atual
    - Responsável por desenvolver APIs em FastAPI e integrações WhatsApp.
    """
    job_en = """
    Senior Python Engineer (Remote)
    Requirements:
    - Strong experience with Python, FastAPI, PostgreSQL, Redis, Docker and Kubernetes.
    - Automated testing with Pytest and CI/CD pipelines.
    """

    # Simula LLM tentando alucinar uma empresa falsa ("FakeGoogle") — guarda anti-alucinação deve barrar!
    fake_llm_resp = {
        "tailored_data": {
            "headline": "Senior Python Engineer",
            "summary": "Backend engineer specializing in Python, FastAPI, PostgreSQL, and Docker.",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "Redis"],
            "experiences": [
                {
                    "company": "FakeGoogle",
                    "role": "Staff Engineer",
                    "bullets": ["Built fake things at FakeGoogle"],
                }
            ],
        },
        "changes_summary": [{"section": "summary", "action": "aligned", "reason": "Aligned to English role"}],
    }

    with patch("app.modules.jobs_career.cv_tailor.invoke_llm_json", new_callable=AsyncMock, return_value=fake_llm_resp):
        res = await evaluate_and_tailor_cv(
            resume_text=cv_text,
            structured_resume=None,
            job_description=job_en,
            job_title="Senior Python Engineer",
            company_name="GlobalTech",
            target_language="auto",
            candidate_skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
        )

    assert res["target_language"] == "en"
    assert res["ats_score_after"] >= res["ats_score_before"]
    # Empresa original preservada e alucinação bloqueada
    companies = [e["company"] for e in res["tailored_data"]["experiences"]]
    assert "TechCorp" in companies
    assert "FakeGoogle" not in companies
    # Kubernetes não estava no CV nem nas candidate_skills -> não pode ser adicionada como skill inventada!
    assert "Kubernetes" not in res["tailored_data"]["skills"]
    # Redis estava em candidate_skills -> pode entrar e Kubernetes fica em real_gaps
    assert "Kubernetes" in res["evaluation_report"]["real_gaps"]
    assert "Professional Summary" in res["tailored_markdown"]
    assert len(res["cover_letter"]) > 20
    assert len(res["interview_prep"]["likely_questions"]) >= 1


def test_job_matching_with_preferences_and_dealbreakers():
    profile = MagicMock(years_experience=4.0)
    skills = [
        MagicMock(name="Python", normalized_name="python", is_core=True),
        MagicMock(name="FastAPI", normalized_name="fastapi", is_core=True),
        MagicMock(name="PostgreSQL", normalized_name="postgresql", is_core=False),
    ]
    prefs = MagicMock(
        target_roles=["Backend Developer", "Python Engineer"],
        seniority_levels=["mid", "senior"],
        work_models=["remote"],
        contract_types=["pj", "clt"],
        min_salary=10000.0,
        salary_currency="BRL",
        desired_stack=["fastapi", "docker"],
        dealbreakers=["presencial", "php"],
    )

    good_job = MagicMock(
        title="Backend Developer Python",
        company_name="Nubank",
        location="Remoto",
        work_model="remote",
        contract_type="clt",
        seniority="mid",
        salary_min=12000.0,
        salary_max=15000.0,
        salary_currency="BRL",
        description_raw="Buscamos dev Python, FastAPI, PostgreSQL e Docker. Trabalho 100% remoto.",
        extracted_requirements=extract_job_requirements(
            "Buscamos dev Python, FastAPI, PostgreSQL e Docker. Trabalho 100% remoto.",
            "Backend Developer Python",
        ),
    )

    bad_job = MagicMock(
        title="Desenvolvedor PHP Presencial",
        company_name="LegacyCorp",
        location="São Paulo",
        work_model="onsite",
        contract_type="clt",
        seniority="mid",
        salary_min=5000.0,
        salary_max=6000.0,
        salary_currency="BRL",
        description_raw="Vaga presencial em PHP e Laravel.",
        extracted_requirements=extract_job_requirements("Vaga presencial em PHP e Laravel.", "Desenvolvedor PHP Presencial"),
    )

    good_eval = calculate_job_match(profile, skills, prefs, good_job)
    bad_eval = calculate_job_match(profile, skills, prefs, bad_job)

    assert good_eval.match_score >= 75
    assert "Python" in good_eval.matched_skills
    assert bad_eval.match_score < 35
    assert bad_eval.score_breakdown["dealbreaker_penalty"] <= -25


def test_ssrf_and_slug_security_guards():
    assert sanitize_company_slug("Stripe-Inc") == "stripe-inc"
    assert sanitize_company_slug("../../etc") == "etc"

    for bad_url in [
        "http://127.0.0.1:8080/admin",
        "http://localhost:5000/webhook",
        "http://169.254.169.254/latest/meta-data",
        "http://100.64.0.1/internal",  # CGNAT não-global
        "file:///etc/passwd",
        "ftp://example.com/job",
    ]:
        with pytest.raises(ValueError):
            validate_public_url(bad_url)


@pytest.mark.asyncio
async def test_manual_url_blocks_antibot_content_type_and_size_limit():
    class _StreamCtx:
        def __init__(self, resp):
            self._resp = resp

        async def __aenter__(self):
            return self._resp

        async def __aexit__(self, exc_type, exc, tb):
            return False

    mock_resp_403 = MagicMock()
    mock_resp_403.status_code = 403
    mock_resp_403.is_error = True
    mock_resp_403.headers = {}

    with patch("app.modules.jobs_career.sources.manual.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]):
        with patch("httpx.AsyncClient.stream", return_value=_StreamCtx(mock_resp_403)):
            with pytest.raises(JobUrlBlockedError):
                await ingest_job_from_url("https://example.com/vaga/123")

    # Bloqueia Content-Type binário / inesperado
    mock_resp_bin = MagicMock()
    mock_resp_bin.status_code = 200
    mock_resp_bin.is_error = False
    mock_resp_bin.headers = {"content-type": "application/octet-stream"}
    with patch("app.modules.jobs_career.sources.manual.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]):
        with patch("httpx.AsyncClient.stream", return_value=_StreamCtx(mock_resp_bin)):
            with pytest.raises(ValueError, match="Conteúdo|conteúdo"):
                await ingest_job_from_url("https://example.com/file.bin")

    # Bloqueia resposta > 2 MB no streaming
    mock_resp_big = MagicMock()
    mock_resp_big.status_code = 200
    mock_resp_big.is_error = False
    mock_resp_big.headers = {"content-type": "text/html"}

    async def _big_chunks():
        yield b"x" * (2 * 1024 * 1024 + 10)

    mock_resp_big.aiter_bytes = _big_chunks
    with patch("app.modules.jobs_career.sources.manual.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]):
        with patch("httpx.AsyncClient.stream", return_value=_StreamCtx(mock_resp_big)):
            with pytest.raises(ValueError, match="2 MB"):
                await ingest_job_from_url("https://example.com/huge")


@pytest.mark.asyncio
async def test_llm_factory_providers_and_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_CHAT_MODEL", "llama3.1")
    monkeypatch.setenv("LLM_CV_MODEL", "qwen2.5")

    cfg = get_llm_config()
    assert cfg.provider == "ollama"
    assert cfg.is_local is True
    assert cfg.is_configured is True
    assert cfg.chat_model == "llama3.1"
    assert cfg.cv_model == "qwen2.5"
    assert "***REDACTED***" in repr(cfg)

    # Sem chave cloud e sem servidor respondendo -> invoke_llm_text retorna None sem quebrar
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_ROUTER_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert await invoke_llm_text("sys", "hi") is None


def test_docx_zip_bomb_rejected():
    import zipfile

    # 1. Mais de 200 entradas internas
    buf_many = io.BytesIO()
    with zipfile.ZipFile(buf_many, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "<w:document/>")
        for i in range(205):
            zf.writestr(f"word/extra_{i}.xml", "ok")
    with pytest.raises(ValueError, match="entradas"):
        validate_cv_upload("many.docx", buf_many.getvalue())

    # 2. Soma descomprimida > 25 MB
    buf_bomb = io.BytesIO()
    with zipfile.ZipFile(buf_bomb, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "<w:document/>")
        zf.writestr("word/payload.txt", b"A" * (26 * 1024 * 1024))
    with pytest.raises(ValueError, match="25 MB"):
        validate_cv_upload("bomb.docx", buf_bomb.getvalue())


def test_languages_key_normalization_across_renderers(tmp_path: Path):
    data = {
        "contact": {"name": "Ana Silva"},
        "languages": [
            {"language": "Inglês", "level": "Fluente"},
            {"name": "Espanhol", "level": "Intermediário"},
        ],
    }
    md = render_cv_markdown(data, target_language="pt-BR")
    assert "Inglês: Fluente" in md
    assert "Espanhol: Intermediário" in md

    docx_path = tmp_path / "langs.docx"
    render_cv_docx(data, docx_path, target_language="pt-BR")
    extracted = extract_text_from_bytes(docx_path.read_bytes(), "docx")
    assert "Inglês: Fluente" in extracted
    assert "Espanhol: Intermediário" in extracted

    pdf_path = tmp_path / "langs.pdf"
    render_cv_pdf(data, pdf_path, target_language="pt-BR")
    extracted_pdf = extract_text_from_bytes(pdf_path.read_bytes(), "pdf")
    assert "Inglês: Fluente" in extracted_pdf
    assert "Espanhol: Intermediário" in extracted_pdf


@pytest.mark.asyncio
async def test_evaluate_interview_answer_normalizes_llm_score():
    from app.modules.jobs_career.interview_service import evaluate_interview_answer

    with patch(
        "app.modules.jobs_career.interview_service.invoke_llm_json",
        new_callable=AsyncMock,
        return_value={"score": 999, "strengths": ["Bom"], "improvements": "Adicionar métricas", "upgraded_example": 123},
    ):
        res = await evaluate_interview_answer("Pergunta", "Minha resposta com 10% de melhoria")
    assert res["score"] == 10
    assert isinstance(res["strengths"], list)
    assert isinstance(res["improvements"], list)
    assert isinstance(res["upgraded_example"], str)


def test_production_secrets_enforcement(monkeypatch: pytest.MonkeyPatch):
    from app.core.auth import _get_jwt_secret
    from app.core.crypto import _get_fernet, hash_remote_jid

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("HMAC_SECRET", raising=False)
    monkeypatch.setenv("ENCRYPTION_KEY", "only-encryption-key-should-not-sign-jwt")

    with pytest.raises(RuntimeError):
        _get_jwt_secret()
    with pytest.raises(RuntimeError):
        hash_remote_jid("5511999999999")

    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError):
        _get_fernet()

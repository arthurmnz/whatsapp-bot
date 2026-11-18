import re
from typing import Any, Literal

SKILL_ALIASES: dict[str, str] = {
    "py": "python",
    "python3": "python",
    "python": "python",
    "ts": "typescript",
    "typescript": "typescript",
    "js": "javascript",
    "es6": "javascript",
    "javascript": "javascript",
    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    "next": "next.js",
    "nextjs": "next.js",
    "next.js": "next.js",
    "vue": "vue",
    "vuejs": "vue",
    "vue.js": "vue",
    "nuxt": "nuxt.js",
    "nuxtjs": "nuxt.js",
    "angular": "angular",
    "svelte": "svelte",
    "tailwind": "tailwind css",
    "tailwindcss": "tailwind css",
    "tailwind css": "tailwind css",
    "css3": "css",
    "css": "css",
    "html5": "html",
    "html": "html",
    "fastapi": "fastapi",
    "django": "django",
    "flask": "flask",
    "express": "express",
    "expressjs": "express",
    "nest": "nestjs",
    "nestjs": "nestjs",
    "spring": "spring boot",
    "springboot": "spring boot",
    "spring boot": "spring boot",
    "java": "java",
    "kotlin": "kotlin",
    "golang": "go",
    "go": "go",
    "rust": "rust",
    "csharp": "c#",
    "c#": "c#",
    "dotnet": ".net",
    ".net": ".net",
    "asp.net": ".net",
    "php": "php",
    "laravel": "laravel",
    "ruby": "ruby",
    "rails": "ruby on rails",
    "ruby on rails": "ruby on rails",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "pg": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "sqlite": "sqlite",
    "sql": "sql",
    "nosql": "nosql",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "redis": "redis",
    "elasticsearch": "elasticsearch",
    "kafka": "kafka",
    "rabbitmq": "rabbitmq",
    "docker": "docker",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "terraform": "terraform",
    "ansible": "ansible",
    "aws": "aws",
    "amazon web services": "aws",
    "gcp": "gcp",
    "google cloud": "gcp",
    "azure": "azure",
    "linux": "linux",
    "git": "git",
    "github": "github",
    "gitlab": "gitlab",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "github actions": "github actions",
    "graphql": "graphql",
    "rest": "rest api",
    "restful": "rest api",
    "rest api": "rest api",
    "grpc": "grpc",
    "microservices": "microservices",
    "microserviços": "microservices",
    "sqlalchemy": "sqlalchemy",
    "alembic": "alembic",
    "prisma": "prisma",
    "typeorm": "typeorm",
    "pydantic": "pydantic",
    "pytest": "pytest",
    "jest": "jest",
    "vitest": "vitest",
    "playwright": "playwright",
    "cypress": "cypress",
    "selenium": "selenium",
    "tdd": "tdd",
    "bdd": "bdd",
    "llm": "llm",
    "llms": "llm",
    "langchain": "langchain",
    "langgraph": "langgraph",
    "openai": "openai",
    "rag": "rag",
    "machine learning": "machine learning",
    "data science": "data science",
    "pandas": "pandas",
    "numpy": "numpy",
    "pyspark": "pyspark",
    "airflow": "airflow",
    "dbt": "dbt",
    "power bi": "power bi",
    "scrum": "scrum",
    "kanban": "kanban",
    "clean architecture": "clean architecture",
    "ddd": "ddd",
    "solid": "solid",
    "react native": "react native",
    "flutter": "flutter",
    "swift": "swift",
}

CANONICAL_DISPLAY: dict[str, str] = {
    "python": "Python",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "node.js": "Node.js",
    "react": "React",
    "next.js": "Next.js",
    "vue": "Vue.js",
    "nuxt.js": "Nuxt.js",
    "angular": "Angular",
    "svelte": "Svelte",
    "tailwind css": "Tailwind CSS",
    "css": "CSS",
    "html": "HTML",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "express": "Express",
    "nestjs": "NestJS",
    "spring boot": "Spring Boot",
    "java": "Java",
    "kotlin": "Kotlin",
    "go": "Go",
    "rust": "Rust",
    "c#": "C#",
    ".net": ".NET",
    "php": "PHP",
    "laravel": "Laravel",
    "ruby": "Ruby",
    "ruby on rails": "Ruby on Rails",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mariadb": "MariaDB",
    "sqlite": "SQLite",
    "sql": "SQL",
    "nosql": "NoSQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "kafka": "Kafka",
    "rabbitmq": "RabbitMQ",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "linux": "Linux",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "ci/cd": "CI/CD",
    "github actions": "GitHub Actions",
    "graphql": "GraphQL",
    "rest api": "REST API",
    "grpc": "gRPC",
    "microservices": "Microservices",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic",
    "prisma": "Prisma",
    "typeorm": "TypeORM",
    "pydantic": "Pydantic",
    "pytest": "Pytest",
    "jest": "Jest",
    "vitest": "Vitest",
    "playwright": "Playwright",
    "cypress": "Cypress",
    "selenium": "Selenium",
    "tdd": "TDD",
    "bdd": "BDD",
    "llm": "LLM",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "openai": "OpenAI API",
    "rag": "RAG",
    "machine learning": "Machine Learning",
    "data science": "Data Science",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "pyspark": "PySpark",
    "airflow": "Airflow",
    "dbt": "dbt",
    "power bi": "Power BI",
    "scrum": "Scrum",
    "kanban": "Kanban",
    "clean architecture": "Clean Architecture",
    "ddd": "DDD",
    "solid": "SOLID",
    "react native": "React Native",
    "flutter": "Flutter",
    "swift": "Swift",
}

SKILL_CATEGORIES: dict[str, str] = {
    "python": "language",
    "typescript": "language",
    "javascript": "language",
    "java": "language",
    "kotlin": "language",
    "go": "language",
    "rust": "language",
    "c#": "language",
    "php": "language",
    "ruby": "language",
    "swift": "language",
    "sql": "language",
    "react": "frontend",
    "next.js": "frontend",
    "vue": "frontend",
    "nuxt.js": "frontend",
    "angular": "frontend",
    "svelte": "frontend",
    "tailwind css": "frontend",
    "css": "frontend",
    "html": "frontend",
    "react native": "mobile",
    "flutter": "mobile",
    "fastapi": "backend",
    "django": "backend",
    "flask": "backend",
    "node.js": "backend",
    "express": "backend",
    "nestjs": "backend",
    "spring boot": "backend",
    ".net": "backend",
    "laravel": "backend",
    "ruby on rails": "backend",
    "graphql": "backend",
    "rest api": "backend",
    "grpc": "backend",
    "sqlalchemy": "backend",
    "alembic": "backend",
    "pydantic": "backend",
    "postgresql": "database",
    "mysql": "database",
    "mariadb": "database",
    "sqlite": "database",
    "nosql": "database",
    "mongodb": "database",
    "redis": "database",
    "elasticsearch": "database",
    "docker": "devops",
    "kubernetes": "devops",
    "terraform": "devops",
    "ansible": "devops",
    "aws": "cloud",
    "gcp": "cloud",
    "azure": "cloud",
    "linux": "devops",
    "ci/cd": "devops",
    "github actions": "devops",
    "git": "tool",
    "github": "tool",
    "gitlab": "tool",
    "kafka": "messaging",
    "rabbitmq": "messaging",
    "pytest": "testing",
    "jest": "testing",
    "vitest": "testing",
    "playwright": "testing",
    "cypress": "testing",
    "selenium": "testing",
    "tdd": "practice",
    "bdd": "practice",
    "clean architecture": "architecture",
    "microservices": "architecture",
    "ddd": "architecture",
    "solid": "architecture",
    "llm": "ai",
    "langchain": "ai",
    "langgraph": "ai",
    "openai": "ai",
    "rag": "ai",
    "machine learning": "ai",
    "data science": "data",
    "pandas": "data",
    "numpy": "data",
    "pyspark": "data",
    "airflow": "data",
    "dbt": "data",
    "power bi": "data",
    "scrum": "agile",
    "kanban": "agile",
}

_PT_HINTS = {
    "vaga",
    "requisitos",
    "experiência",
    "experiencia",
    "desenvolvimento",
    "desenvolvedor",
    "engenheiro",
    "conhecimento",
    "conhecimentos",
    "habilidades",
    "remoto",
    "híbrido",
    "hibrido",
    "presencial",
    "salário",
    "salario",
    "benefícios",
    "beneficios",
    "candidatura",
    "diferencial",
    "diferenciais",
    "responsabilidades",
    "atuar",
    "empresa",
    "trabalho",
    "contratação",
    "contratacao",
    "clt",
    "pj",
    "sênior",
    "pleno",
    "júnior",
    "formação",
    "resumo",
    "objetivo",
    "currículo",
    "curriculo",
    "para",
    "com",
    "não",
    "nao",
    "você",
    "voce",
}

_EN_HINTS = {
    "requirements",
    "responsibilities",
    "experience",
    "skills",
    "remote",
    "hybrid",
    "onsite",
    "salary",
    "benefits",
    "qualifications",
    "developer",
    "engineer",
    "software",
    "summary",
    "education",
    "work",
    "company",
    "looking",
    "candidate",
    "strong",
    "knowledge",
    "years",
    "team",
    "build",
    "with",
    "and",
    "the",
    "for",
    "you",
    "our",
    "will",
}


def normalize_skill_name(raw: str) -> str:
    """Normaliza nome de skill aplicando dicionário de sinônimos técnicos."""
    cleaned = re.sub(r"\s+", " ", (raw or "").strip().lower())
    cleaned = cleaned.strip(".,;:/()[]{}")
    if not cleaned:
        return ""
    return SKILL_ALIASES.get(cleaned, cleaned)


def display_skill_name(raw: str) -> str:
    """Retorna forma canônica legível de uma tecnologia mantendo nomes desconhecidos."""
    norm = normalize_skill_name(raw)
    if norm in CANONICAL_DISPLAY:
        return CANONICAL_DISPLAY[norm]
    return (raw or "").strip()


def infer_skill_category(normalized: str) -> str:
    """Infere categoria técnica para uma skill normalizada."""
    return SKILL_CATEGORIES.get(normalized, "other")


def detect_language(text: str) -> Literal["pt-BR", "en"]:
    """Detecta automaticamente se o texto está em Português (pt-BR) ou Inglês (en)."""
    if not text or not text.strip():
        return "pt-BR"

    lowered = text.lower()
    tokens = re.findall(r"[a-zà-ú]+", lowered)
    pt_score = sum(1 for t in tokens if t in _PT_HINTS)
    en_score = sum(1 for t in tokens if t in _EN_HINTS)

    # Acentos típicos de português reforçam sinal pt-BR
    pt_chars = len(re.findall(r"[ãõçáéíóúâêôà]", lowered))
    pt_score += pt_chars // 3

    return "pt-BR" if pt_score >= en_score else "en"


def extract_known_skills_from_text(text: str) -> list[str]:
    """Extrai skills normalizadas presentes em um texto usando limites exatos de token."""
    if not text:
        return []
    lowered = text.lower()
    found: list[str] = []
    seen: set[str] = set()

    # Ordena aliases mais longos primeiro para priorizar tokens compostos (ex.: "react native", "spring boot")
    sorted_aliases = sorted(SKILL_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_aliases:
        # Tokens curtos ou ambíguos exigem delimitador estrito
        escaped = re.escape(alias)
        pattern = rf"(?<![a-z0-9_+#]){escaped}(?![a-z0-9_+#])"
        if re.search(pattern, lowered):
            norm = SKILL_ALIASES[alias]
            if norm not in seen:
                seen.add(norm)
                found.append(norm)
    return found


def infer_work_model(text: str) -> str:
    lowered = (text or "").lower()
    if any(w in lowered for w in ("remoto", "remote", "home office", "anywhere", "teletrabalho")):
        if any(w in lowered for w in ("híbrido", "hibrido", "hybrid")):
            return "hybrid"
        return "remote"
    if any(w in lowered for w in ("híbrido", "hibrido", "hybrid")):
        return "hybrid"
    if any(w in lowered for w in ("presencial", "onsite", "on-site", "in-office")):
        return "onsite"
    return "unknown"


def infer_contract_type(text: str) -> str:
    lowered = (text or "").lower()
    has_clt = bool(re.search(r"\bclt\b", lowered))
    has_pj = bool(re.search(r"\bpj\b", lowered))
    if has_clt and has_pj:
        return "clt/pj"
    if has_clt:
        return "clt"
    if has_pj:
        return "pj"
    if any(w in lowered for w in ("contractor", "freelance", "b2b")):
        return "contractor"
    if any(w in lowered for w in ("full-time", "full time", "efetivo")):
        return "full_time"
    return "unknown"


def infer_seniority(text: str) -> str:
    lowered = (text or "").lower()
    if any(w in lowered for w in ("staff", "principal", "architect", "arquiteto")):
        return "staff"
    if any(w in lowered for w in ("sênior", "senior", "sr.", "sr ")):
        return "senior"
    if any(w in lowered for w in ("pleno", "mid-level", "mid level", "middle")):
        return "mid"
    if any(w in lowered for w in ("júnior", "junior", "jr.", "jr ", "entry level", "entry-level")):
        return "junior"
    if any(w in lowered for w in ("estágio", "estagiário", "intern", "trainee")):
        return "intern"
    return "unknown"


def extract_salary_range(text: str) -> tuple[float | None, float | None, str | None]:
    """Extrai faixa salarial aproximada (R$, USD, EUR) de descrições de vagas."""
    if not text:
        return None, None, None
    # Ex: R$ 10.000 - R$ 15.000 ou R$ 8000
    brl_match = re.search(
        r"r\$\s*(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?|\d{4,6})(?:\s*(?:-|a|até|to)\s*r?\$?\s*(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?|\d{4,6}))?",
        text,
        re.IGNORECASE,
    )
    if brl_match:
        def _parse_brl(val: str) -> float:
            cleaned = val.replace(".", "").replace(" ", "").replace(",", ".")
            return float(cleaned)
        smin = _parse_brl(brl_match.group(1))
        smax = _parse_brl(brl_match.group(2)) if brl_match.group(2) else None
        return smin, smax, "BRL"

    usd_match = re.search(
        r"(?:us\$|\$|usd)\s*(\d{2,3}(?:,\d{3})*|\d{4,6})(?:\s*(?:-|to)\s*(?:us\$|\$|usd)?\s*(\d{2,3}(?:,\d{3})*|\d{4,6}))?",
        text,
        re.IGNORECASE,
    )
    if usd_match:
        smin = float(usd_match.group(1).replace(",", ""))
        smax = float(usd_match.group(2).replace(",", "")) if usd_match.group(2) else None
        if smin >= 500:  # evita capturar valores irrelevantes como $10
            return smin, smax, "USD"
    return None, None, None


def extract_job_requirements(description: str, title: str = "") -> dict[str, Any]:
    """Extrai requisitos obrigatórios, desejáveis, keywords ATS e metadados da vaga."""
    combined = f"{title}\n{description}"
    all_skills = extract_known_skills_from_text(combined)

    must_have: list[str] = []
    nice_to_have: list[str] = []

    nice_section = ""
    must_section = description or ""
    split_match = re.search(
        r"(?:diferenciais|desejável|desejavel|nice to have|bonus|plus|preferred qualifications)[:\s]*([\s\S]*)",
        description or "",
        re.IGNORECASE,
    )
    if split_match:
        nice_section = split_match.group(1)
        must_section = (description or "")[: split_match.start()]

    must_skills = set(extract_known_skills_from_text(f"{title}\n{must_section}"))
    nice_skills = set(extract_known_skills_from_text(nice_section)) - must_skills

    for sk in all_skills:
        if sk in nice_skills:
            nice_to_have.append(sk)
        else:
            must_have.append(sk)

    smin, smax, currency = extract_salary_range(combined)
    return {
        "must_have": must_have,
        "nice_to_have": nice_to_have,
        "keywords_ats": all_skills,
        "work_model": infer_work_model(combined),
        "contract_type": infer_contract_type(combined),
        "seniority": infer_seniority(combined),
        "salary_min": smin,
        "salary_max": smax,
        "salary_currency": currency,
        "language": detect_language(combined),
    }


def normalize_languages_list(raw_languages: list[Any] | None) -> list[dict[str, str]]:
    """Padroniza lista de idiomas aceitando chaves `name`, `language` ou strings simples."""
    normalized: list[dict[str, str]] = []
    for item in raw_languages or []:
        if isinstance(item, dict):
            lang_name = str(item.get("name") or item.get("language") or "").strip()
            lang_level = str(item.get("level") or item.get("proficiency") or "").strip()
            if lang_name:
                normalized.append({"name": lang_name, "language": lang_name, "level": lang_level})
        elif isinstance(item, str) and item.strip():
            parts = re.split(r"[:\-–|]", item.strip(), maxsplit=1)
            lang_name = parts[0].strip()
            lang_level = parts[1].strip() if len(parts) > 1 else ""
            if lang_name:
                normalized.append({"name": lang_name, "language": lang_name, "level": lang_level})
    return normalized

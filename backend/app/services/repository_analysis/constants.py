"""Declarative patterns, constants, and configurable limits for repository analysis."""

from typing import Dict, List, Set

# Default directories and files ignored during traversal and analysis
DEFAULT_IGNORE_PATTERNS: Set[str] = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    "target",
    "coverage",
    "__pycache__",
    ".cache",
    ".next",
    "out",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    "bin",
    "obj",
    ".gradle",
    ".mvn",
    ".DS_Store",
}

# Extension map for language detection
LANGUAGE_EXTENSION_MAP: Dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".hpp": "C++",
    ".php": "PHP",
    ".rb": "Ruby",
    ".sh": "Shell",
    ".html": "HTML",
    ".css": "CSS",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".swift": "Swift",
}

# Entry point patterns per language/framework
ENTRY_POINT_PATTERNS: List[Dict[str, str]] = [
    # Python
    {"name": "main.py", "language": "Python", "description": "Python main entry point"},
    {"name": "app.py", "language": "Python", "description": "Python app entry point"},
    {"name": "server.py", "language": "Python", "description": "Python server entry point"},
    {"name": "manage.py", "language": "Python", "description": "Django management entry point"},
    {"name": "__main__.py", "language": "Python", "description": "Python package execution entry point"},
    {"name": "wsgi.py", "language": "Python", "description": "WSGI server entry point"},
    {"name": "asgi.py", "language": "Python", "description": "ASGI server entry point"},
    {"name": "app/main.py", "language": "Python", "description": "Application module main entry point"},
    {"name": "src/main.py", "language": "Python", "description": "Source module main entry point"},
    {"name": "src/app.py", "language": "Python", "description": "Source module app entry point"},
    # JS / TS / Node
    {"name": "index.js", "language": "JavaScript", "description": "JavaScript index entry point"},
    {"name": "index.ts", "language": "TypeScript", "description": "TypeScript index entry point"},
    {"name": "server.js", "language": "JavaScript", "description": "Node server entry point"},
    {"name": "server.ts", "language": "TypeScript", "description": "TypeScript server entry point"},
    {"name": "app.js", "language": "JavaScript", "description": "Express/Node app entry point"},
    {"name": "app.ts", "language": "TypeScript", "description": "Node/TypeScript app entry point"},
    {"name": "src/index.js", "language": "JavaScript", "description": "Source index entry point"},
    {"name": "src/index.ts", "language": "TypeScript", "description": "Source TypeScript index entry point"},
    {"name": "src/main.ts", "language": "TypeScript", "description": "Source main TypeScript entry point"},
    {"name": "src/main.tsx", "language": "TypeScript", "description": "React TypeScript main entry point"},
    {"name": "src/App.tsx", "language": "TypeScript", "description": "React App component entry point"},
    {"name": "src/App.jsx", "language": "JavaScript", "description": "React App component entry point"},
    {"name": "pages/index.js", "language": "JavaScript", "description": "Next.js page entry point"},
    {"name": "pages/index.tsx", "language": "TypeScript", "description": "Next.js TypeScript page entry point"},
    {"name": "app/page.tsx", "language": "TypeScript", "description": "Next.js App Router root page"},
    {"name": "app/page.js", "language": "JavaScript", "description": "Next.js App Router root page"},
    # Java
    {"name": "Main.java", "language": "Java", "description": "Java Main class"},
    {"name": "src/main/java", "language": "Java", "description": "Standard Java source root"},
    # Go
    {"name": "main.go", "language": "Go", "description": "Go main entry point"},
    {"name": "cmd/main.go", "language": "Go", "description": "Go CLI main entry point"},
    # Rust
    {"name": "src/main.rs", "language": "Rust", "description": "Rust main binary entry point"},
    {"name": "src/lib.rs", "language": "Rust", "description": "Rust library root entry point"},
]

# Declarative Framework Detection Patterns
FRAMEWORK_PATTERNS: List[Dict] = [
    {
        "name": "FastAPI",
        "category": "Framework",
        "languages": ["Python"],
        "keywords": ["fastapi"],
        "code_indicators": ["from fastapi import", "import fastapi", "FastAPI("],
        "confidence": 1.0,
    },
    {
        "name": "Flask",
        "category": "Framework",
        "languages": ["Python"],
        "keywords": ["flask"],
        "code_indicators": ["from flask import", "import flask", "Flask(__name__)"],
        "confidence": 1.0,
    },
    {
        "name": "Django",
        "category": "Framework",
        "languages": ["Python"],
        "keywords": ["django"],
        "code_indicators": ["import django", "django.shortcuts", "DJANGO_SETTINGS_MODULE"],
        "file_indicators": ["manage.py"],
        "confidence": 1.0,
    },
    {
        "name": "Next.js",
        "category": "Framework",
        "languages": ["JavaScript", "TypeScript"],
        "keywords": ["next"],
        "file_indicators": ["next.config.js", "next.config.mjs", "next.config.ts"],
        "code_indicators": ["from 'next/", "require('next"],
        "confidence": 1.0,
    },
    {
        "name": "React",
        "category": "Framework",
        "languages": ["JavaScript", "TypeScript"],
        "keywords": ["react"],
        "code_indicators": ["import React", "from 'react'", "import { useState"],
        "confidence": 1.0,
    },
    {
        "name": "Vue",
        "category": "Framework",
        "languages": ["JavaScript", "TypeScript"],
        "keywords": ["vue"],
        "code_indicators": ["import Vue", "from 'vue'", "createApp("],
        "confidence": 1.0,
    },
    {
        "name": "Express",
        "category": "Framework",
        "languages": ["JavaScript", "TypeScript"],
        "keywords": ["express"],
        "code_indicators": ["require('express')", "import express", "express()"],
        "confidence": 1.0,
    },
    {
        "name": "Angular",
        "category": "Framework",
        "languages": ["JavaScript", "TypeScript"],
        "keywords": ["@angular/core"],
        "code_indicators": ["@Component(", "@NgModule("],
        "confidence": 1.0,
    },
    {
        "name": "NestJS",
        "category": "Framework",
        "languages": ["JavaScript", "TypeScript"],
        "keywords": ["@nestjs/core"],
        "code_indicators": ["@Controller(", "@Injectable("],
        "confidence": 1.0,
    },
    {
        "name": "Vite",
        "category": "Framework",
        "languages": ["JavaScript", "TypeScript"],
        "keywords": ["vite"],
        "file_indicators": ["vite.config.js", "vite.config.ts"],
        "confidence": 1.0,
    },
    {
        "name": "Spring Boot",
        "category": "Framework",
        "languages": ["Java"],
        "keywords": ["spring-boot", "springframework"],
        "code_indicators": ["@SpringBootApplication", "import org.springframework"],
        "confidence": 1.0,
    },
    {
        "name": "Gin",
        "category": "Framework",
        "languages": ["Go"],
        "keywords": ["gin-gonic/gin"],
        "code_indicators": ["gin.Default()", "gin.New()"],
        "confidence": 1.0,
    },
]

# Declarative Package Manager Patterns
PACKAGE_MANAGER_PATTERNS: List[Dict] = [
    {"name": "pnpm", "files": ["pnpm-lock.yaml", "pnpm-workspace.yaml"]},
    {"name": "yarn", "files": ["yarn.lock"]},
    {"name": "npm", "files": ["package-lock.json", "package.json"]},
    {"name": "poetry", "files": ["poetry.lock"], "toml_section": "[tool.poetry]"},
    {"name": "pip", "files": ["requirements.txt", "Pipfile", "setup.py"]},
    {"name": "cargo", "files": ["Cargo.toml"]},
    {"name": "go modules", "files": ["go.mod"]},
    {"name": "maven", "files": ["pom.xml"]},
    {"name": "gradle", "files": ["build.gradle", "build.gradle.kts"]},
]

# Declarative Extensible Technology Patterns (Databases, ORMs, Auth, AI, Testing, Deployment)
TECHNOLOGY_PATTERNS: List[Dict] = [
    # Databases
    {"name": "PostgreSQL", "category": "Database", "keywords": ["postgresql", "psycopg2", "asyncpg", "postgres"], "confidence": 0.95},
    {"name": "MySQL", "category": "Database", "keywords": ["mysql", "pymysql", "mysql2"], "confidence": 0.95},
    {"name": "SQLite", "category": "Database", "keywords": ["sqlite3", "sqlite"], "confidence": 0.9},
    {"name": "MongoDB", "category": "Database", "keywords": ["mongodb", "pymongo", "mongoose"], "confidence": 0.95},
    {"name": "Redis", "category": "Database", "keywords": ["redis", "ioredis"], "confidence": 0.95},
    # ORMs
    {"name": "SQLModel", "category": "ORM", "keywords": ["sqlmodel"], "confidence": 0.95},
    {"name": "SQLAlchemy", "category": "ORM", "keywords": ["sqlalchemy"], "confidence": 0.95},
    {"name": "Prisma", "category": "ORM", "keywords": ["prisma", "@prisma/client"], "confidence": 0.95},
    {"name": "TypeORM", "category": "ORM", "keywords": ["typeorm"], "confidence": 0.95},
    {"name": "Sequelize", "category": "ORM", "keywords": ["sequelize"], "confidence": 0.95},
    # Authentication
    {"name": "JWT", "category": "Authentication", "keywords": ["pyjwt", "jwt", "python-jose", "jsonwebtoken"], "confidence": 0.9},
    {"name": "NextAuth.js", "category": "Authentication", "keywords": ["next-auth"], "confidence": 0.95},
    {"name": "Passport.js", "category": "Authentication", "keywords": ["passport"], "confidence": 0.9},
    {"name": "Auth0", "category": "Authentication", "keywords": ["auth0"], "confidence": 0.9},
    # AI Stack
    {"name": "Google GenAI SDK", "category": "AI", "keywords": ["google-genai"], "confidence": 1.0},
    {"name": "Google Generative AI", "category": "AI", "keywords": ["google.generativeai"], "confidence": 1.0},
    {"name": "OpenAI API", "category": "AI", "keywords": ["openai"], "confidence": 1.0},
    {"name": "LangChain", "category": "AI", "keywords": ["langchain"], "confidence": 1.0},
    {"name": "LangGraph", "category": "AI", "keywords": ["langgraph"], "confidence": 1.0},
    {"name": "LlamaIndex", "category": "AI", "keywords": ["llama_index", "llamaindex"], "confidence": 1.0},
    {"name": "Hugging Face Transformers", "category": "AI", "keywords": ["transformers"], "confidence": 1.0},
    {"name": "PyTorch", "category": "AI", "keywords": ["torch", "pytorch"], "confidence": 1.0},
    {"name": "TensorFlow", "category": "AI", "keywords": ["tensorflow"], "confidence": 1.0},
    {"name": "Anthropic SDK", "category": "AI", "keywords": ["anthropic"], "confidence": 1.0},
    {"name": "ChromaDB", "category": "AI", "keywords": ["chromadb"], "confidence": 1.0},
    {"name": "Pinecone", "category": "AI", "keywords": ["pinecone"], "confidence": 1.0},
    # Testing
    {"name": "Pytest", "category": "Testing", "keywords": ["pytest"], "confidence": 0.95},
    {"name": "Unittest", "category": "Testing", "keywords": ["unittest"], "confidence": 0.9},
    {"name": "Jest", "category": "Testing", "keywords": ["jest"], "confidence": 0.95},
    {"name": "Vitest", "category": "Testing", "keywords": ["vitest"], "confidence": 0.95},
    # Deployment - Docker & Docker Compose requires BOTH files; plain Docker only needs Dockerfile
    {"name": "Docker & Docker Compose", "category": "Deployment", "files": ["Dockerfile", "docker-compose.yml"], "match_all": True, "confidence": 0.95},
    {"name": "Docker", "category": "Deployment", "files": ["Dockerfile"], "match_all": True, "confidence": 0.9},
    {"name": "Heroku / Procfile", "category": "Deployment", "files": ["Procfile"], "match_all": True, "confidence": 0.95},
]

# Configurable Limits for LLM Context Preview
MAX_PREVIEW_FILES: int = 10
MAX_PREVIEW_LINES_PER_FILE: int = 150
MAX_PREVIEW_CHARS_PER_FILE: int = 1500

# Directory scoring weights
DIRECTORY_SCORE_WEIGHTS: Dict[str, int] = {
    "entry_point": 20,
    "api_route": 15,
    "controller": 15,
    "service": 15,
    "model": 15,
    "source_code": 10,
    "config": 5,
    "schema": 5,
    "migration": 5,
    "test": 3,
    "docs": 1,
    "asset": 1,
}

# Direct name scores for standard functional directories
KEY_FUNCTIONAL_DIR_BONUS: Dict[str, int] = {
    "src": 15,
    "app": 15,
    "api": 15,
    "routes": 15,
    "controllers": 15,
    "services": 15,
    "models": 15,
    "components": 12,
    "views": 10,
    "schemas": 10,
    "core": 10,
    "utils": 8,
    "config": 8,
    "handlers": 10,
    "middleware": 10,
    "db": 10,
    "database": 10,
    "repositories": 10,
    "pages": 12,
    "lib": 8,
}

# Binary file extensions to skip from text previews
BINARY_FILE_EXTENSIONS: Set[str] = {
    ".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".dylib", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf", ".zip",
    ".tar", ".gz", ".7z", ".class", ".jar", ".war", ".ear", ".db",
    ".sqlite", ".woff", ".woff2", ".ttf", ".eot"
}

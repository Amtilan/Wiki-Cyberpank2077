# 🤖 Wiki-Cyberpunk2077

<div align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python Version"/>
  <img src="https://img.shields.io/badge/FastAPI-0.105.0-009688.svg" alt="FastAPI Version"/>
  <img src="https://img.shields.io/badge/React-18.0.0-61DAFB.svg" alt="React Version"/>
  <img src="https://img.shields.io/badge/Tailwind-3.3.0-38B2AC.svg" alt="Tailwind Version"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"/>
</div>

<div align="center">
  <h3>nFactorial Incubator 2025</h3>
  <p>Интерактивная вики по вселенной Cyberpunk 2077 с AI-чатом</p>
</div>

## 📖 Описание проекта

Это веб-приложение представляет собой интерактивную энциклопедию по миру Cyberpunk 2077 - популярной RPG от CD Projekt Red. Пользователи могут изучить лор игры, информацию о персонажах и даже пообщаться с Джонни Сильверхендом через AI-интерфейс.

Игра Cyberpunk 2077 погружает игроков в мрачное будущее мегаполиса Найт-Сити, где технологические импланты, корпоративная власть и уличные банды определяют повседневную жизнь. Наш проект стремится передать атмосферу этого уникального сеттинга и дать фанатам удобный доступ к информации об игровой вселенной.

## 🏗️ Архитектура проекта

```mermaid
graph TD
    A[Frontend: React + TailwindCSS] -->|API Requests| B[Backend: FastAPI]
    B -->|Database Queries| C[(Database: SQLite/PostgreSQL)]
    B -->|AI Chat Requests| D[OpenAI API]
    E[User] --> A
    
    style A fill:#61DAFB,stroke:#333,stroke-width:2px,color:#fff
    style B fill:#009688,stroke:#333,stroke-width:2px,color:#fff
    style C fill:#F8C471,stroke:#333,stroke-width:2px,color:#fff
    style D fill:#74AA9C,stroke:#333,stroke-width:2px,color:#fff
    style E fill:#E74C3C,stroke:#333,stroke-width:2px,color:#fff
```

## 🛠️ Технический стек

```mermaid
flowchart LR
    subgraph Frontend
        A[React] --- B[Vite]
        B --- C[TailwindCSS]
    end
    
    subgraph Backend
        D[FastAPI] --- E[Python 3.11+]
        E --- F[SQLAlchemy]
        F --- G[Pydantic]
    end
    
    subgraph Database
        H[SQLite/PostgreSQL]
    end
    
    subgraph Deployment
        I[Vercel] --- J[Railway/Render]
    end
    
    subgraph Integrations
        K[OpenAI API] --- L[HTTPX]
    end
    
    Frontend --> Backend
    Backend --> Database
    Backend --> Integrations
    
    style Frontend fill:#61DAFB,stroke:#333,stroke-width:2px
    style Backend fill:#009688,stroke:#333,stroke-width:2px
    style Database fill:#F8C471,stroke:#333,stroke-width:2px
    style Deployment fill:#E74C3C,stroke:#333,stroke-width:2px
    style Integrations fill:#8E44AD,stroke:#333,stroke-width:2px
```

### Почему такой стек?

- **FastAPI**: Высокопроизводительный асинхронный фреймворк с автоматической документацией (OpenAPI)
- **React + Vite**: Современный стек для построения реактивных интерфейсов с быстрой сборкой
- **TailwindCSS**: Утилитарный CSS-фреймворк для быстрой вёрстки без лишнего CSS
- **SQLite/PostgreSQL**: Простая но надёжная БД (SQLite для разработки, PostgreSQL для продакшн)
- **OpenAI API**: Интеграция с передовыми языковыми моделями для создания диалогов с персонажами игры

## 📋 Структура приложения

### Страницы (Frontend)

- **/** — Главная страница с приветствием в стиле Cyberpunk
- **/lore** — Информация о мире игры и его истории
- **/characters** — Галерея персонажей с подробными описаниями
- **/chat** — Интерактивный чат с Джонни Сильверхендом

### API эндпоинты (Backend)

```mermaid
classDiagram
    class API {
        GET /api/characters
        GET /api/characters/name
        POST /api/chat
    }
    
    class Characters {
        +name: str
        +description: str
        +image_url: str
        +relationships: List[str]
    }
    
    class Chat {
        +message: str
        +character: str
        +response: str
    }
    
    API -- Characters: returns
    API -- Chat: processes
```

## 🚀 Установка и запуск

### Локальный запуск

```bash
# Клонировать репозиторий
git clone https://github.com/yourusername/Wiki-Cyberpank2077.git
cd Wiki-Cyberpank2077

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt

# Запустить бэкенд
cd backend
uvicorn app.main:app --reload

# В отдельном терминале запустить фронтенд
cd frontend
npm install
npm run dev
```

### Docker запуск

```bash
# Собрать и запустить всё приложение
docker-compose up -d
```

## 🔄 API Workflow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Database
    participant OpenAI
    
    User->>Frontend: Открывает страницу
    Frontend->>Backend: GET /api/characters
    Backend->>Database: Запрос персонажей
    Database-->>Backend: Данные персонажей
    Backend-->>Frontend: JSON с персонажами
    Frontend-->>User: Отображает персонажей
    
    User->>Frontend: Отправляет сообщение в чат
    Frontend->>Backend: POST /api/chat {message}
    Backend->>OpenAI: Запрос к API с промптом
    OpenAI-->>Backend: Ответ AI (Джонни)
    Backend-->>Frontend: Ответ персонажа
    Frontend-->>User: Показывает диалог
```

## 🤔 Особенности и компромиссы

### Преимущества

- **Автодокументация API**: FastAPI генерирует OpenAPI схему и интерактивную документацию (/docs, /redoc)
- **Асинхронный бэкенд**: Использование `async/await` с HTTPX для внешних API
- **Оптимизация производительности**: Минимальные зависимости и легковесная архитектура
- **Separation of Concerns**: Frontend общается с внешними API только через бэкенд

### Компромиссы

- **SQLite вместо PostgreSQL** для прототипа: Жертвуем масштабируемостью ради скорости разработки
- **Ограниченный функционал чата**: MVP с базовыми возможностями без истории сообщений
- **Отсутствие аутентификации**: Для первой версии проекта не требуется система пользователей

## 📊 Процесс проектирования

Проект разрабатывался с использованием итеративного подхода:

1. **Прототипирование**: Создание базовой структуры API и фронтенда
2. **Разработка бэкенда**: Имплементация основных эндпоинтов и интеграция с OpenAI API
3. **Разработка фронтенда**: Дизайн и вёрстка страниц в стиле Cyberpunk
4. **Интеграция**: Соединение фронтенда и бэкенда, тестирование работоспособности
5. **Деплой**: Размещение приложения на Vercel (фронтенд) и Railway (бэкенд)

## 🎥 Демонстрация

[![Демо проекта](https://img.shields.io/badge/YouTube-Demo-red?style=for-the-badge&logo=youtube)](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

## 📝 Лицензия

Этот проект лицензирован под [MIT License](LICENSE).

---

<div align="center">
  <p>Создано для nFactorial Incubator 2025 с ❤️ и высокой дозой киберпанка</p>
  <p>Wake up, Samurai. We have a code to write. 🔥</p>
</div>
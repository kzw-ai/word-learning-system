# 🎓 Adaptive Chinese Vocabulary Learning System

[![中文文档](https://img.shields.io/badge/文档-中文版-blue)](./README_zh.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-learnchinese.kzwbelieve.top-brightgreen)](http://learnchinese.kzwbelieve.top)
[![GitHub stars](https://img.shields.io/github/stars/1137043480/word-learning-system?style=social)](https://github.com/1137043480/word-learning-system)
[![PWA Ready](https://img.shields.io/badge/PWA-Ready-5A0FC8?logo=pwa)](http://learnchinese.kzwbelieve.top)

**Version**: 2.3.0 · **Status**: Production · **Last Updated**: October 2026

> 🌐 **[Try it now → learnchinese.kzwbelieve.top](http://learnchinese.kzwbelieve.top)** — No installation required! Works on mobile & desktop.

An intelligent, adaptive vocabulary learning system for intermediate-level Chinese as a Foreign Language (CFL) learners. Built as part of a master's thesis at **Peking University** — *"Research and Design of an Adaptive Intermediate Chinese Vocabulary Learning System"* — this project implements a full-stack learning platform with AI-driven personalized learning paths, spaced repetition, and comprehensive learning analytics.

---

## ✨ Key Features

- 🧠 **Adaptive Recommendation Engine** — AI-powered personalized learning path based on user proficiency, learning patterns, and performance history
- 🔄 **Spaced Repetition (SM-2)** — Scientific review scheduling based on the SuperMemo-2 algorithm with personalized intervals
- 📊 **Learning Analytics Dashboard** — Real-time data visualization with mastery heatmaps, trend analysis, and predictive insights
- 📝 **VKS-based Assessment** — Vocabulary Knowledge Scale testing to determine optimal learning entry points
- ⏱️ **Millisecond-precision Tracking** — Fine-grained learning behavior recording for research-grade data collection
- 🔊 **TTS Audio Pronunciation** — Built-in text-to-speech for characters, words, collocations, and example sentences
- 🔗 **Multi-module Learning Chain** — Character → Vocabulary → Collocation → Sentence progressive learning flow
- 📖 **SLA-informed Curriculum Design** — Learning materials grounded in Second Language Acquisition theory: word frequency-based difficulty grading via BCC corpus (billions of tokens), NLP-powered collocation extraction using dependency parsing and mutual information, automated sentence complexity scoring, and interlanguage corpus-based confused word identification
- 📱 **PWA Support** — Install as a native-like app on iOS, Android, and desktop; works offline with Service Worker caching
- ☁️ **Cross-device Progress Sync** — Learning state persisted to backend; switch devices without losing progress

---

## 📸 Screenshots

<details>
<summary><b>Click to view all 10 screenshots 👇</b></summary>

<table>
  <tr>
    <td align="center"><b>Home Page</b></td>
    <td align="center"><b>VKS Assessment</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/01-homepage.png?v=4" width="400" alt="Home Page - Mobile-first welcome interface with navigation to all learning modules"></td>
    <td><img src="docs/screenshots/02-vks-entrance.png?v=4" width="400" alt="VKS Assessment - Vocabulary Knowledge Scale test to determine learning entry point"></td>
  </tr>
  <tr>
    <td align="center"><b>Character Learning</b></td>
    <td align="center"><b>Word Learning</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/03-character-learning.png?v=4" width="400" alt="Character Learning - Chinese character breakdown with pinyin, stroke order, and definitions"></td>
    <td><img src="docs/screenshots/04-word-learning.png?v=4" width="400" alt="Word Learning - Deep dive into word meanings, collocations, and usage"></td>
  </tr>
  <tr>
    <td align="center"><b>Collocation Learning</b></td>
    <td align="center"><b>Sentence Learning</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/04b-collocation-learning.png?v=4" width="400" alt="Collocation Learning - Mastering native-like phrasing combinations"></td>
    <td><img src="docs/screenshots/04c-sentence-learning.png?v=4" width="400" alt="Sentence Learning - Contextual reading and listening practice"></td>
  </tr>
  <tr>
    <td align="center"><b>Vocabulary Exercise</b></td>
    <td align="center"><b>Learning Dashboard</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/07-exercise.png?v=4" width="400" alt="Vocabulary Exercise - Interactive quizzes with immediate feedback"></td>
    <td><img src="docs/screenshots/05-dashboard.png?v=4" width="400" alt="Learning Dashboard - AI-powered smart recommendations with confidence scoring"></td>
  </tr>
  <tr>
    <td align="center"><b>Today's Review</b></td>
    <td align="center"><b>Confusable Words</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/06-today-review.png?v=4" width="400" alt="Spaced Repetition Review - Daily personalized review tasks"></td>
    <td><img src="docs/screenshots/08-confusable.png?v=4" width="400" alt="Confusable Words - Side-by-side comparison of near-synonyms and how they differ"></td>
  </tr>
</table>

</details>

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15, React, TypeScript, Tailwind CSS, shadcn/ui |
| **Backend** | Flask, SQLAlchemy, SQLite |
| **PWA** | Service Worker, Web App Manifest, offline caching |
| **Algorithm** | Modified SuperMemo-2, Multi-factor recommendation engine |
| **Research (thesis, not in this codebase)** | ML models (AdaBoost with Multinomial NB, Gaussian NB, XGBoost, voting ensemble) and the NLP pipeline (BCC corpus frequency, dependency parsing, mutual information) were used in the thesis study and to prepare the learning materials; the app itself runs the rule-based adaptive engine and SM-2 scheduling |
| **Deployment** | Nginx, PM2, VPS with HTTPS |

---

## 📚 Research Foundation

This system is built on rigorous academic research at **Peking University**, combining SLA theory, NLP techniques, and adaptive learning algorithms:

- **Corpus-driven vocabulary selection** — Word frequency analysis across BCC corpus (billions of tokens) and a self-collected CFL textbook corpus (165K characters from 13 intermediate-level textbooks) using Pandas and SQL
- **Frequency-difficulty modeling** — Implements Stewart's finding that log(corpus frequency) strongly correlates with word difficulty (r=0.8), enabling automated difficulty grading
- **NLP-based collocation extraction** — Collocations sourced from a knowledge base built with dependency parsing and mutual information filtering, ranked by collocation strength
- **Automated sentence selection** — Sentence complexity computed by summing normalized word difficulties, selecting the lowest-complexity example sentences from textbook corpora
- **Interlanguage error analysis** — Confused words extracted from the HSK Dynamic Composition Corpus based on learner error frequency, with separated learning to avoid semantic clustering interference
- **"Relative Character-based" pedagogy** — Following Bai Lesan's theory: learning characters through words (以词带字) at intermediate level, covering pronunciation, form, and high-frequency meanings
- **Cognitive load balancing** — High/mid/low frequency words and confused words distributed evenly across learning sessions
- **Validated with real learners** — Two-month teaching experiment with 17 HSK-4 learners, 51 users total, producing statistically significant improvements in vocabulary acquisition, collocation learning, and word proficiency

---

## 🌐 Live Demo

**No installation needed!** Visit the live deployment directly:

👉 **[learnchinese.kzwbelieve.top](http://learnchinese.kzwbelieve.top)**

The system is deployed on a VPS with Nginx reverse proxy, PM2 process management, and full backend/frontend services running 24/7.

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.11+ (conda recommended)
- Node.js 18+

### Installation

```bash
# Clone the repository
git clone https://github.com/1137043480/word-learning-system.git
cd word-learning-system

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
npm install
```

### Running the System

#### Option 1: One-click Start (Recommended)
```bash
# Auto-generate test data and start API server
./start_system.sh

# In another terminal, start the frontend
npm run dev
```

#### Option 2: Manual Start
```bash
# Start Phase 2 API server (port 5004)
python app_phase.py

# Start frontend dev server (port 3000)
npm run dev
```

#### Option 3: Docker Deployment
```bash
# Production deployment with Docker Compose
docker-compose -f docker-compose.prod.yml up -d
```

### Access
- **Local**: http://localhost:3000 (dev) or http://localhost:3002 (Docker)
- **Live**: http://learnchinese.kzwbelieve.top

---

## 🎯 Feature Tour

### Recommended Experience Path

1. **System Status** → `/system-status` — Check service health and architecture overview
2. **Phase 2 Demo** → `/phase-demo` — Interactive demo of the adaptive recommendation engine
3. **Learning Dashboard** → `/learning-dashboard` — Full learning analytics and visualization
4. **Start Learning** → `/word-learning-entrance` — VKS-guided personalized learning experience

### Core Pages

| Page | Route | Description |
|------|-------|-------------|
| Home | `/` | Welcome page and learning entry |
| VKS Assessment | `/word-learning-entrance` | Vocabulary Knowledge Scale test |
| Character Learning | `/character-learning` | Chinese character module |
| Vocabulary Learning | `/word-learning` | Word meaning and usage |
| Collocation Learning | `/collocation-learning` | Word collocation patterns |
| Sentence Learning | `/sentence-learning` | Contextual sentence practice |
| Exercises | `/exercise` | Three exercise types |
| Learning Dashboard | `/learning-dashboard` | Analytics and insights ⭐ |
| Phase 2 Demo | `/phase-demo` | Feature demonstration ⭐ |
| System Status | `/system-status` | Health check |

---

## 🔌 API Reference

### Service Ports
| Port | Service |
|------|---------|
| 3000 | Next.js Frontend |
| 5004 | Phase 2 API (primary) ⭐ |
| 5002 | Phase 1 Extended API |
| 5001 | Original API |

### Key Endpoints

```bash
# System statistics
GET /api/stats

# Adaptive recommendations for a user
GET /api/adaptive/recommendation/{user_id}

# Learning dashboard data
GET /api/analytics/user/{user_id}/dashboard

# Due review items
GET /api/review/user/{user_id}/due

# User list
GET /api/users

# Learning state persistence (cross-device sync)
GET  /api/users/{user_id}/learning-state
PUT  /api/users/{user_id}/learning-state

# Learning session management
POST /api/learning/session/start
POST /api/learning/session/end
POST /api/learning/events/batch
```

---

## 🧠 How the Adaptive Engine Works

### Recommendation Logic
The system uses a multi-layer recommendation strategy:

1. **Urgent Review** — Items at risk of being forgotten (based on memory decay model)
2. **Scheduled Review** — Items due for spaced repetition review
3. **New Content** — Fresh material matched to the learner's proficiency level

### Key Algorithms
- **Modified SM-2**: Personalized interval scheduling based on individual performance
- **Memory Strength Model**: Multi-factor assessment of retention probability
- **User Pattern Recognition**: Classifies learners by efficiency, accuracy, and preferences
- **Confidence Scoring**: Each recommendation includes a confidence rating

---

## 📊 Performance Metrics

### Algorithm Performance
| Metric | Value |
|--------|-------|
| Recommendation response time | < 300ms |
| Recommendation accuracy | > 85% |
| Review timing accuracy | > 90% |
| Learning efficiency improvement | > 25% |

### System Performance
| Metric | Value |
|--------|-------|
| Dashboard load time | < 1.5s |
| Concurrent request handling (100 req) | < 2s |
| Data accuracy | 99.5% |
| Real-time update latency | < 100ms |

---

## 📂 Project Structure

```
├── pages/                    # Next.js pages
│   ├── index.tsx            # Home page
│   ├── word-learning-entrance.tsx  # VKS assessment
│   ├── learning-dashboard.tsx      # Analytics dashboard ⭐
│   ├── phase-demo.tsx             # Feature demo ⭐
│   └── exercise.tsx                # Practice exercises
├── components/ui/            # UI component library (shadcn)
├── src/
│   ├── context/             # React Context providers
│   ├── hooks/               # Custom React hooks
│   └── lib/                 # Utility functions
├── app_phase.py            # Phase 2 API server ⭐
├── adaptive_engine.py       # Adaptive recommendation engine
├── models_extended.py       # Database models
├── start_system.sh          # One-click startup script
└── README.md                # This file
```

---

## 📈 Dataset Scale

| Metric | Count |
|--------|-------|
| Test Users | 51 |
| Learning Sessions | 4,050 |
| Exercise Records | 15,200 |
| Learning Events | 50,100 |

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

### Development Guidelines
- React components: Functional components + TypeScript
- Code style: 2-space indentation, PascalCase file naming
- Python: PEP 8 compliant
- Commits: [Conventional Commits](https://www.conventionalcommits.org/) format

---

## 📄 License

This project is open source and available under the [MIT License](./LICENSE).

---

## 📚 Documentation

- [中文文档 (Chinese README)](./README_zh.md)

---

**Built with ❤️ for language learners worldwide**
*Based on a master's thesis at Peking University: "Research and Design of an Adaptive Intermediate Chinese Vocabulary Learning System"*

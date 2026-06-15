# Agentic AI Interogative Agendas

Research prototype for a controlled agentic hiring-support study on explanation, anthropomorphic delivery, trust, overreliance, and verification in agentic AI decision support. The project implements a Streamlit workflow in which the hiring case remains fixed while provenance cues, conversational style, and Human Intervention Checkpoints vary across conditions.

The repository name retains the original spelling, `interogative`.

## Overview

The application evaluates a fictional candidate against internal hiring materials: company context, role requirements, and screening policy. It is designed as an experimental research instrument, not as a real hiring or screening system.

The study uses a 2 x 2 x 2 condition structure:

- Explainability: low or high provenance visibility
- Anthropomorphic cues: low or high
- Human Intervention Checkpoints: absent or present

## Repository Structure

```text
apps/                  Streamlit entry points for the eight study conditions
scripts/               Dataset and knowledge-base preparation utilities
src/agentic_hiring/    Shared retrieval, recommendation, rendering, and logging code
study/                 Study materials, measures, protocol, and local data workspace
tests/                 Automated validation tests
outputs/               Generated analysis outputs and reports
```

## Setup

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

Add your OpenAI API key to `.env` or your deployment secrets:

```bash
OPENAI_API_KEY=your-api-key
AGENTIC_REQUIRE_LIVE_RAG=true
```

For study deployment, keep `AGENTIC_REQUIRE_LIVE_RAG=true` so sessions cannot continue without the live retrieval and generation backend.

## Prepare the Knowledge Base

```bash
PYTHONPATH=src python scripts/build_internal_knowledge_base.py
```

This indexes the internal company context, role description, and screening policy used by the study assistant. Candidate CVs are handled as session-specific inputs.

## Run an App

Launch one assigned condition, for example:

```bash
python -m streamlit run apps/app_01_lowE_lowA_noIA.py
```

The eight app entry points in `apps/` correspond to the full condition matrix.

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Research Use

This software is a research instrument using fictional hiring materials. It is designed to study recommendation following, overreliant advancement, and verification uptake; it should not be used to support real hiring, screening, promotion, or employment decisions.
